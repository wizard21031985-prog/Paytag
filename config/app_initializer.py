# config/app_initializer.py
import sys
from pymongo import MongoClient
from config.config_loader import load_config
# from database.db_repository import MongoRepository
# from logger.logger_service import PayTagLogger

class AppContext:
    """A clean container holding initialized resource references for the app."""
    def __init__(self, config: dict, mongo_client: MongoClient, db_repo=None, logger=None):
        self.config = config
        self.mongo_client = mongo_client
        self.db_repo = db_repo
        self.logger = logger


class ApplicationInitializer:
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path

    def bootstrap(self) -> AppContext:
        """
        Executes the systematic boot sequence of the application.
        Loads configurations, sets up database handshakes, and wires infrastructure.
        """
        print("[BOOTSTRAP] Initiating system initialization cascade...")

        # 1. Load configuration settings
        try:
            config = load_config(self.config_path)
            print("[BOOTSTRAP] Configuration matrix successfully loaded.")
        except Exception as e:
            print(f"[BOOTSTRAP ERROR] Critical failure parsing configurations: {e}", file=sys.stderr)
            sys.exit(1)

        # 2. Establish raw MongoDB client handshake
        try:
            mongo_uri = config['database']['mongo_uri']
            # Using a short timeout so the bootloader fails fast if MongoDB is down
            mongo_client = MongoClient(mongo_uri, serverSelectionTimeoutMS=3000)
            # Force a connection heartbeat check
            mongo_client.admin.command('ping')
            print("[BOOTSTRAP] Database engine communication channel verified online.")
        except Exception as e:
            print(f"[BOOTSTRAP ERROR] Database infrastructure unreachable: {e}", file=sys.stderr)
            print("[BOOTSTRAP ALERT] Routing execution pathway to check for MALFUNCTION state initialization guidelines...", file=sys.stderr)
            # This raw client reference will still be passed so the recovery loops can use it later
            mongo_client = None

        # 3. Future Step placeholders: Initialize Repository & Logger Service
        db_repo = None  # self._init_database_repository(config, mongo_client)
        logger = None   # self._init_logger_service(config, mongo_client)

        print("[BOOTSTRAP] Initialization cascade completed. Application context secured.")
        return AppContext(
            config=config,
            mongo_client=mongo_client,
            db_repo=db_repo,
            logger=logger
        )
