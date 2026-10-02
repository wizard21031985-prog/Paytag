# database/db_worker.py
import sys
import threading
from queue import Queue, Empty
from datetime import datetime
from database.base_repository import BaseRepository
from database.db_actions import DbAction
from pymongo.errors import PyMongoError


class DatabaseIngestionWorker:
    def __init__(self, db_repo: BaseRepository, db_queue: Queue, main_queue: Queue):
        self.db_repo = db_repo
        self.db_queue = db_queue
        self.main_queue = main_queue

        self._running = False
        self._thread = None

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._worker_loop, name="DB_Worker_Thread", daemon=True)
        self._thread.start()
        print("[DATABASE WORKER] Background ingestion stream thread successfully armed.")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=3.0)
            print("[DATABASE WORKER] Ingestion stream thread safely stopped.")

    def _worker_loop(self):
        while self._running:
            try:
                message = self.db_queue.get(timeout=1)

                action = message.get("action")
                payload = message.get("payload", {})

                # Execute the write within our non-blocking exception trap
                self._safe_execute_write(action, payload)

                # ALWAYS call task_done so the queue doesn't lock up, even on errors
                self.db_queue.task_done()

            except Empty:
                continue

    def _safe_execute_write(self, action: DbAction, payload: dict):
        try:
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
            # --- CONTINUOUS PIPELINE EXCEPTION PARSER ---
            self._handle_database_error(action, mongo_error)

    def _handle_database_error(self, action: DbAction, error: PyMongoError):
        """
        Parses the database exception. Forwards the payload to the main queue
        while keeping the worker thread alive to receive subsequent messages.
        """
        # Determine severity dynamically (or let the main parser handle it)
        # If it's a complete server connection loss, the main thread will tell us to stop later.
        error_payload = {
            "source": "DATABASE_WORKER",
            "timestamp": datetime.utcnow(),
            "severity": "CRITICAL",
            "error_type": type(error).__name__,
            "message": f"Critical storage dropout during action '{action.value}': {str(error)}",
            "is_fatal": True
        }

        # Immediate alert warning to the local console stream
        sys.stderr.write(f"[DATABASE WORKER WARNING] Extraction glitch: {error_payload['message']}\n")
        sys.stderr.flush()

        # Stream the error event forward into the central queue
        self.main_queue.put(error_payload)
