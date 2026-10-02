# database/db_repository.py
import sys
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
        mongo_uri = self.config['database']['mongo_uri']
        self.client = MongoClient(mongo_uri, serverSelectionTimeoutMS=3000)
        self.client.admin.command('ping')

        self.business_db = self.client[self.business_db_name]
        self.technical_db = self.client[self.technical_db_name]

        print("[DATABASE] Data Access Layer primitives active and connected.")
        self._initialize_infrastructure()

    def _initialize_infrastructure(self):
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
                self.technical_db.create_collection("health_checks", capped=True, size=capped_cfg['health_checks_bytes'])
            except CollectionInvalid:
                pass
        self.technical_db.health_checks.create_index([("timestamp", -1)], name="idx_time_desc")

        self.business_db.sessions.create_index([("transaction_number", 1)], unique=True, name="idx_unique_tx")
        self.business_db.basket_items.create_index([("transaction_number", 1), ("rfid", 1)], unique=True, name="idx_unique_basket_rfid")

    # --- PRIMITIVE EXECUTIONS (Exception Propagation Assured) ---

    def insert_session(self, session_doc: dict):
        self.business_db.sessions.insert_one(session_doc)

    def update_session(self, transaction_number: str, update_fields: dict):
        self.business_db.sessions.update_one({"transaction_number": transaction_number}, {"$set": update_fields})

    def upsert_item(self, query_fields: dict, insert_fields: dict):
        self.business_db.basket_items.update_one(query_fields, {"$setOnInsert": insert_fields}, upsert=True)

    def update_item(self, transaction_number: str, rfid: str, update_fields: dict):
        self.business_db.basket_items.update_one({"transaction_number": transaction_number, "rfid": rfid}, {"$set": update_fields})

    def delete_item(self, transaction_number: str, rfid: str) -> bool:
        result = self.business_db.basket_items.delete_one({"transaction_number": transaction_number, "rfid": rfid})
        return result.deleted_count > 0

    def insert_log(self, log_doc: dict):
        self.technical_db.system_logs.insert_one(log_doc)

    def insert_heartbeat(self, heartbeat_doc: dict):
        self.technical_db.health_checks.insert_one(heartbeat_doc)
