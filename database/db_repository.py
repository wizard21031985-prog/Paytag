# database/db_repository.py
import sys
from typing import Optional, List
from pymongo import MongoClient
from pymongo.errors import CollectionInvalid
from database.base_repository import BaseRepository


class MongoRepository(BaseRepository):
    def __init__(self, config: dict):
        self.config = config
        self.business_db_name = config['database']['business_db_name']
        self.technical_db_name = config['database']['technical_db_name']

        self.client = None
        self.business_db = None
        self.technical_db = None

        self._establish_connection()

    def _establish_connection(self):
        try:
            mongo_uri = self.config['database']['mongo_uri']
            self.client = MongoClient(mongo_uri, serverSelectionTimeoutMS=3000)
            self.client.admin.command('ping')

            self.business_db = self.client[self.business_db_name]
            self.technical_db = self.client[self.technical_db_name]

            print("[DATABASE] Data Access Layer active and connected.")
            self._initialize_infrastructure()
        except Exception as e:
            print(f"[DATABASE ERROR] Connection failed: {e}", file=sys.stderr)
            self.client = None

    def _initialize_infrastructure(self):
        """Builds indices and ensures capped tables exist with zero business dependencies."""
        if not self.client:
            return

        existing_tech_cols = self.technical_db.list_collection_names()
        capped_cfg = self.config['database']['capped_collections']

        if "system_logs" not in existing_tech_cols:
            try:
                self.technical_db.create_collection("system_logs", capped=True, size=capped_cfg['system_logs_bytes'])
            except CollectionInvalid:
                pass
        self.technical_db.system_logs.create_index([("transaction_number", 1), ("timestamp", 1)], name="idx_tx_time")

        if "health_checks" not in existing_tech_cols:
            try:
                self.technical_db.create_collection("health_checks", capped=True,
                                                    size=capped_cfg['health_checks_bytes'])
            except CollectionInvalid:
                pass
        self.technical_db.health_checks.create_index([("timestamp", -1)], name="idx_time_desc")

        self.business_db.sessions.create_index([("transaction_number", 1)], unique=True, name="idx_unique_tx")
        self.business_db.basket_items.create_index([("transaction_number", 1), ("rfid", 1)], unique=True,
                                                   name="idx_unique_basket_rfid")

    # --- SESSIONS TABLE PRIMITIVES ---

    def insert_session(self, session_doc: dict) -> bool:
        if not self.business_db: return False
        try:
            self.business_db.sessions.insert_one(session_doc)
            return True
        except Exception as e:
            print(f"[DB PRIMITIVE ERROR] insert_session failed: {e}", file=sys.stderr)
            return False

    def update_session(self, transaction_number: str, update_fields: dict) -> bool:
        if not self.business_db: return False
        try:
            self.business_db.sessions.update_one(
                {"transaction_number": transaction_number},
                {"$set": update_fields}
            )
            return True
        except Exception as e:
            print(f"[DB PRIMITIVE ERROR] update_session failed: {e}", file=sys.stderr)
            return False

    # --- BASKET ITEMS TABLE PRIMITIVES ---

    def upsert_item(self, query_fields: dict, insert_fields: dict) -> bool:
        if not self.business_db: return False
        try:
            self.business_db.basket_items.update_one(
                query_fields,
                {"$setOnInsert": insert_fields},
                upsert=True
            )
            return True
        except Exception as e:
            print(f"[DB PRIMITIVE ERROR] upsert_item failed: {e}", file=sys.stderr)
            return False

    def update_item(self, transaction_number: str, rfid: str, update_fields: dict) -> bool:
        if not self.business_db: return False
        try:
            self.business_db.basket_items.update_one(
                {"transaction_number": transaction_number, "rfid": rfid},
                {"$set": update_fields}
            )
            return True
        except Exception as e:
            print(f"[DB PRIMITIVE ERROR] update_item failed: {e}", file=sys.stderr)
            return False

    def find_item(self, transaction_number: str, rfid: str) -> Optional[dict]:
        if not self.business_db: return None
        try:
            return self.business_db.basket_items.find_one(
                {"transaction_number": transaction_number, "rfid": rfid},
                {"_id": 0}
            )
        except Exception as e:
            print(f"[DB PRIMITIVE ERROR] find_item failed: {e}", file=sys.stderr)
            return None

    def find_all_items(self, transaction_number: str) -> List[dict]:
        if not self.business_db: return []
        try:
            cursor = self.business_db.basket_items.find(
                {"transaction_number": transaction_number},
                {"_id": 0}
            )
            return list(cursor)
        except Exception as e:
            print(f"[DB PRIMITIVE ERROR] find_all_items failed: {e}", file=sys.stderr)
            return []

    def delete_item(self, transaction_number: str, rfid: str) -> bool:
        if not self.business_db: return False
        try:
            result = self.business_db.basket_items.delete_one(
                {"transaction_number": transaction_number, "rfid": rfid}
            )
            return result.deleted_count > 0
        except Exception as e:
            print(f"[DB PRIMITIVE ERROR] delete_item failed: {e}", file=sys.stderr)
            return False

    # --- TECHNICAL LOGGING TABLE PRIMITIVES ---

    def insert_log(self, log_doc: dict) -> bool:
        if not self.technical_db: return False
        try:
            self.technical_db.system_logs.insert_one(log_doc)
            return True
        except Exception as e:
            print(f"[DB PRIMITIVE ERROR] insert_log failed: {e}", file=sys.stderr)
            return False

    def insert_heartbeat(self, heartbeat_doc: dict) -> bool:
        if not self.technical_db: return False
        try:
            self.technical_db.health_checks.insert_one(heartbeat_doc)
            return True
        except Exception as e:
            print(f"[DB PRIMITIVE ERROR] insert_heartbeat failed: {e}", file=sys.stderr)
            return False
