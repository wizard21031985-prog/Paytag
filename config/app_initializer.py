# config/app_initializer.py
import sys
from queue import Queue
from config.config_loader import load_config
from database import BaseRepository, MongoRepository, DatabaseIngestionWorker
from logger import PayTagLogger

class AppContext:
    def __init__(self, config: dict, db_repo: BaseRepository, db_queue: Queue, main_queue: Queue, logger: PayTagLogger):
        self.config = config
        self.db_repo = db_repo
        self.db_queue = db_queue
        self.main_queue = main_queue
        self.logger = logger


class ApplicationInitializer:
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path

    def bootstrap(self) -> AppContext:
        print("[BOOTSTRAP] Initiating system initialization cascade...")

        db_queue = Queue()
        main_queue = Queue()

        try:
            config = load_config(self.config_path)
            print("[BOOTSTRAP] Configuration matrix successfully loaded.")
        except Exception as e:
            print(f"[BOOTSTRAP ERROR] Critical failure parsing configurations: {e}", file=sys.stderr)
            sys.exit(1)

        try:
            db_repo: BaseRepository = MongoRepository(config)
            print("[BOOTSTRAP] Primitive Data Access Layer initialized.")
        except Exception as e:
            print(f"[BOOTSTRAP ERROR] Database infrastructure unreachable at startup: {e}", file=sys.stderr)
            db_repo = MongoRepository.__new__(MongoRepository)
            db_repo.config = config
            db_repo.client = None
            db_repo.business_db = None
            db_repo.technical_db = None

        db_worker = DatabaseIngestionWorker(
            db_repo=db_repo,
            db_queue=db_queue,
            main_queue=main_queue
        )
        db_worker.start()

        # Instantiate pluggable Logger and inject our non-blocking queue channel
        logger = PayTagLogger(config=config, db_queue=db_queue)
        print("[BOOTSTRAP] Asynchronous Logger Service active and attached to ingestion stream.")

        # Log a clean system boot event to confirm the thread pipeline is functioning!
        logger.log_system_event(severity="INFO", message="PayTag Terminal Integration client successfully booted up.")

        print("[BOOTSTRAP] Initialization cascade completed. Application context secured.")
        return AppContext(
            config=config,
            db_repo=db_repo,
            db_queue=db_queue,
            main_queue=main_queue,
            logger=logger
        )
