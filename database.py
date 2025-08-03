import os
from pymongo import MongoClient
from typing import List, Optional
from dataclasses import dataclass, asdict
from bson import ObjectId

@dataclass
class UserProfile:
    discord_id: str
    username: str
    games: List[str]
    artists: List[str]
    interests: List[str]
    scanning_enabled: bool = True
    last_processed_message: Optional[str] = None
    _id: Optional[ObjectId] = None
    
    @classmethod
    async def find_by_discord_id(cls, discord_id: str) -> Optional['UserProfile']:
        collection = get_collection()
        doc = collection.find_one({"discord_id": discord_id})
        if doc:
            return cls(**{k: v for k, v in doc.items() if k != '_id'}, _id=doc.get('_id'))
        return None
    
    @classmethod
    async def find_all_except(cls, discord_id: str) -> List['UserProfile']:
        collection = get_collection()
        docs = collection.find({"discord_id": {"$ne": discord_id}})
        return [cls(**{k: v for k, v in doc.items() if k != '_id'}, _id=doc.get('_id')) for doc in docs]
    
    async def save(self):
        collection = get_collection()
        doc = asdict(self)
        doc.pop('_id', None)
        
        if self._id:
            collection.update_one({"_id": self._id}, {"$set": doc})
        else:
            result = collection.insert_one(doc)
            self._id = result.inserted_id

_client = None
_db = None

def get_collection():
    global _db
    return _db.user_profiles

async def init_db():
    global _client, _db
    if _client is None:
        mongodb_uri = os.getenv('MONGODB_URI')
        if not mongodb_uri:
            raise ValueError("MONGODB_URI not found in environment variables")
        
        _client = MongoClient(mongodb_uri)
        _db = _client.emobot
        
        try:
            _client.admin.command('ping')
            print("Successfully connected to MongoDB!")
        except Exception as e:
            print(f"Failed to connect to MongoDB: {e}")
            raise