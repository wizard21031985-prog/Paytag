# config/app_initializer.py
import sys
from config.config_loader import load_config
from database.base_repository import BaseRepository
from database.db_repository import MongoRepository

class AppContext:
    """A clean container holding clean, primitive interface contracts for application layers."""
    def __init__(self, config: dict, db_repo: BaseRepository, logger=None):
        self.config = config
        self.db_repo = db_repo
        self.logger = logger


class ApplicationInitializer:
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path

    def bootstrap(self) -> AppContext:
        print("[BOOTSTRAP] Initiating system initialization cascade...")

        try:
            config = load_config(self.config_path)
            print("[BOOTSTRAP] Configuration matrix successfully loaded.")
        except Exception as e:
            print(f"[BOOTSTRAP ERROR] Critical failure parsing configurations: {e}", file=sys.stderr)
            sys.exit(1)

        # Instantiates the data layer which attempts internal socket connections
        db_repo: BaseRepository = MongoRepository(config)
        logger = None

        print("[BOOTSTRAP] Initialization cascade completed. Application context secured.")
        return AppContext(
            config=config,
            db_repo=db_repo,
            logger=logger
        )
