# database/__init__.py
from database.base_repository import BaseRepository
from database.db_repository import MongoRepository

# Declares what is publicly available when importing from this folder package
__all__ = ["BaseRepository", "MongoRepository"]
