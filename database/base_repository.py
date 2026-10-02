# database/base_repository.py
from abc import ABC, abstractmethod

class BaseRepository(ABC):

    # --- SESSIONS TABLE PRIMITIVES ---
    @abstractmethod
    def insert_session(self, session_doc: dict):
        """Inserts a raw dictionary document into the sessions collection."""
        pass

    @abstractmethod
    def update_session(self, transaction_number: str, update_fields: dict):
        """Directly overrides specific fields inside a targeted session document."""
        pass

    # --- BASKET ITEMS TABLE PRIMITIVES ---
    @abstractmethod
    def upsert_item(self, query_fields: dict, insert_fields: dict):
        """Atomic upsert tool to insert or update an individual basket item row."""
        pass

    @abstractmethod
    def update_item(self, transaction_number: str, rfid: str, update_fields: dict):
        """Modifies field values for a specific item row."""
        pass

    @abstractmethod
    def delete_item(self, transaction_number: str, rfid: str) -> bool:
        """Physically removes a targeted item row from the active basket collection."""
        pass

    # --- TECHNICAL LOGGING TABLE PRIMITIVES ---
    @abstractmethod
    def insert_log(self, log_doc: dict):
        """Appends a raw record into the capped system_logs collection."""
        pass

    @abstractmethod
    def insert_heartbeat(self, heartbeat_doc: dict):
        """Appends a raw hardware snapshot into the capped health_checks collection."""
        pass
