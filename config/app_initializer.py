# config/app_initializer.py
import sys
from queue import Queue
from datetime import datetime
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
        timestamp = datetime.utcnow().isoformat()
        sys.stdout.write(f"[{timestamp}] [INFO] [BOOTSTRAP] Initializing core environment components...\n")
        sys.stdout.flush()

        db_queue = Queue()
        main_queue = Queue()

        try:
            config = load_config(self.config_path)
            sys.stdout.write(f"[{datetime.utcnow().isoformat()}] [INFO] [BOOTSTRAP] Configuration matrix successfully loaded.\n")
            sys.stdout.flush()
        except Exception as e:
            sys.stderr.write(f"[{datetime.utcnow().isoformat()}] [CRITICAL] [BOOTSTRAP ERROR] Critical failure parsing configurations: {e}\n")
            sys.stderr.flush()
            sys.exit(1)

        try:
            db_repo: BaseRepository = MongoRepository(config)
            sys.stdout.write(f"[{datetime.utcnow().isoformat()}] [INFO] [BOOTSTRAP] Primitive Data Access Layer initialized.\n")
            sys.stdout.flush()
        except Exception as e:
            sys.stderr.write(f"[{datetime.utcnow().isoformat()}] [ERROR] [BOOTSTRAP ERROR] Database infrastructure unreachable at startup: {e}\n")
            sys.stderr.flush()
            db_repo = MongoRepository.__new__(MongoRepository)
            db_repo.config = config
            db_repo.client = None
            db_repo.business_db = None
            db_repo.technical_db = None

        logger = PayTagLogger(config=config, db_queue=db_queue)
        logger.log_system_event(severity="INFO", message="Asynchronous Logger Service active and attached to queue pipeline.")

        db_worker = DatabaseIngestionWorker(
            db_repo=db_repo,
            db_queue=db_queue,
            main_queue=main_queue,
            logger=logger
        )
        db_worker.start()

        logger.log_system_event(severity="INFO", message="Initialization cascade completed. Application context secured.")
        return AppContext(
            config=config,
            db_repo=db_repo,
            db_queue=db_queue,
            main_queue=main_queue,
            logger=logger
        )
