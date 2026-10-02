# database/db_worker.py
import sys
import threading
from queue import Queue, Empty
from datetime import datetime
from database.base_repository import BaseRepository
from database.db_actions import DbAction
from pymongo.errors import PyMongoError


class DatabaseIngestionWorker:
    def __init__(self, db_repo: BaseRepository, db_queue: Queue, main_queue: Queue, logger):
        self.db_repo = db_repo
        self.db_queue = db_queue  # Message queue for incoming database writes (Consumer)
        self.main_queue = main_queue  # Master application event queue (Alert Destination)
        self.logger = logger  # Injected unified logger service instance

        self._running = False
        self._thread = None

    def start(self):
        """Spawns the ingestion consumer loop on an isolated background thread."""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._worker_loop, name="DB_Worker_Thread", daemon=True)
        self._thread.start()


        self.logger.log_system_event(
            severity="INFO",
            message="Background database ingestion stream thread successfully armed."
        )

    def stop(self):
        """Executes a controlled shutdown, draining any outstanding task backlog gracefully."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=3.0)

            self.logger.log_system_event(
                severity="INFO",
                message="Database ingestion stream thread safely stopped."
            )

    def _worker_loop(self):
        """Central loop monitoring the ingestion queue for incoming structural payloads."""
        while self._running:
            try:
                # 1-second timeout blocks gracefully while keeping the thread responsive to stop signals
                message = self.db_queue.get(timeout=1)

                action = message.get("action")
                payload = message.get("payload", {})

                # Forward execution into the exception-protected database gateway
                self._safe_execute_write(action, payload)

                # Signal to the queue that the item was completely resolved
                self.db_queue.task_done()

            except Empty:
                continue

    def _safe_execute_write(self, action: DbAction, payload: dict):
        """
        The central execution gateway. Invokes raw database repository primitives.
        If MongoDB fails over the wire, exceptions bubble up here to be caught!
        """
        try:
            self.logger.log_system_event(
                severity="INFO",
                message=f"Database Action: {DbAction.name}, payload : {payload}."
            )

            if action == DbAction.INSERT_SESSION:
                self.db_repo.insert_session(payload)

            elif action == DbAction.UPDATE_SESSION:
                self.db_repo.update_session(payload["transaction_number"], payload["update_fields"])

            elif action == DbAction.UPSERT_ITEM:
                self.db_repo.upsert_item(payload["query_fields"], payload["insert_fields"])

            elif action == DbAction.UPDATE_ITEM:
                self.db_repo.update_item(payload["transaction_number"], payload["rfid"], payload["update_fields"])

            elif action == DbAction.DELETE_ITEM:
                self.db_repo.delete_item(payload["transaction_number"], payload["rfid"])

            elif action == DbAction.INSERT_LOG:
                self.db_repo.insert_log(payload)

            elif action == DbAction.INSERT_HEARTBEAT:
                self.db_repo.insert_heartbeat(payload)

        except PyMongoError as mongo_error:
            # --- CENTRALIZED EXCEPTION PARSER ENGINE ---
            self._handle_database_crash(action, mongo_error)

    def _handle_database_crash(self, action: DbAction, error: PyMongoError):
        """Centralized protocol executed when a fatal database infrastructure loss occurs."""
        # 1. Instantly kill the ingestion worker to block task drainage and save RAM memory states
        self._running = False

        # 2. Package standardized critical system alert profile
        fatal_alert = {
            "source": "DATABASE_WORKER",
            "timestamp": datetime.utcnow(),
            "severity": "CRITICAL",
            "error_type": type(error).__name__,
            "message": f"Critical storage dropout during action '{action.value}': {str(error)}",
            "is_fatal": True
        }

        # 3. Handle crash-loop boundary logic
        # We write to console manually here to guarantee a visible message even if MongoDB is offline.
        sys.stderr.write(
            f"[{fatal_alert['timestamp'].isoformat()}] [{fatal_alert['severity']}] [DATABASE WORKER] {fatal_alert['message']}\n")
        sys.stderr.flush()

        # 4. Inject death-envelope into the main_queue to force main thread into MALFUNCTION lockout mode
        self.main_queue.put(fatal_alert)
