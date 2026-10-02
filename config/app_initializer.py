# config/app_initializer.py
import sys
from queue import Queue
from config.config_loader import load_config
from database.base_repository import BaseRepository
from database.db_repository import MongoRepository
from database.db_worker import DatabaseIngestionWorker

class AppContext:
    """A clean container holding clean interface contracts and thread queues for the system."""
    def __init__(self, config: dict, db_repo: BaseRepository, db_queue: Queue, main_queue: Queue, logger=None):
        self.config = config
        self.db_repo = db_repo
        self.db_queue = db_queue       # Thread-safe write queue (Many Providers push here)
        self.main_queue = main_queue   # Master event queue (Single Consumer processes here)
        self.logger = logger


class ApplicationInitializer:
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path

    def bootstrap(self) -> AppContext:
        print("[BOOTSTRAP] Initiating system initialization cascade...")

        # 1. Initialize Thread-Safe Core System Queues
        # db_queue isolates database network latency from your operational code lines
        db_queue = Queue()
        # main_queue maps out all critical asynchronous alerts for central management
        main_queue = Queue()

        # 2. Load configuration settings from the decoupled YAML matrix
        try:
            config = load_config(self.config_path)
            print("[BOOTSTRAP] Configuration matrix successfully loaded.")
        except Exception as e:
            print(f"[BOOTSTRAP ERROR] Critical failure parsing configurations: {e}", file=sys.stderr)
            sys.exit(1)

        # 3. Instantiate Primitive Data Repository (Establishes native client connectivity)
        try:
            db_repo: BaseRepository = MongoRepository(config)
            print("[BOOTSTRAP] Primitive Data Access Layer initialized.")
        except Exception as e:
            # If MongoDB is totally down during initial boot, this catches the ping failure
            print(f"[BOOTSTRAP ERROR] Database infrastructure unreachable at startup: {e}", file=sys.stderr)
            print("[BOOTSTRAP ALERT] Storage layer running in fallback offline mode. Ready for MALFUNCTION state mapping.", file=sys.stderr)
            db_repo = MongoRepository.__new__(MongoRepository) # Create uninitialized instance placeholder
            db_repo.config = config
            db_repo.client = None
            db_repo.business_db = None
            db_repo.technical_db = None

        # 4. Instantiate and Boot the Background Database Ingestion Worker Thread
        db_worker = DatabaseIngestionWorker(
            db_repo=db_repo,
            db_queue=db_queue,
            main_queue=main_queue
        )
        # Spin up the background thread worker loop immediately at boot time
        db_worker.start()

        # 5. Future Step Placeholder: Initialize Pluggable Logger Service
        logger = None

        print("[BOOTSTRAP] Initialization cascade completed. Application context secured.")
        return AppContext(
            config=config,
            db_repo=db_repo,
            db_queue=db_queue,
            main_queue=main_queue,
            logger=logger
        )
