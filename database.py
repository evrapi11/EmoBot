import os
import asyncpg
from typing import List, Optional
from dataclasses import dataclass
import json

@dataclass
class UserProfile:
    discord_id: str
    username: str
    games: List[str]
    artists: List[str]
    interests: List[str]
    scanning_enabled: bool = True
    last_processed_message: Optional[str] = None
    id: Optional[int] = None
    
    @classmethod
    async def find_by_discord_id(cls, discord_id: str) -> Optional['UserProfile']:
        pool = get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM user_profiles WHERE discord_id = $1", 
                discord_id
            )
            if row:
                return cls(
                    discord_id=row['discord_id'],
                    username=row['username'],
                    games=json.loads(row['games']),
                    artists=json.loads(row['artists']),
                    interests=json.loads(row['interests']),
                    scanning_enabled=row['scanning_enabled'],
                    last_processed_message=row['last_processed_message'],
                    id=row['id']
                )
        return None
    
    @classmethod
    async def find_all_except(cls, discord_id: str) -> List['UserProfile']:
        pool = get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM user_profiles WHERE discord_id != $1", 
                discord_id
            )
            profiles = []
            for row in rows:
                profiles.append(cls(
                    discord_id=row['discord_id'],
                    username=row['username'],
                    games=json.loads(row['games']),
                    artists=json.loads(row['artists']),
                    interests=json.loads(row['interests']),
                    scanning_enabled=row['scanning_enabled'],
                    last_processed_message=row['last_processed_message'],
                    id=row['id']
                ))
            return profiles
    
    async def save(self):
        pool = get_pool()
        async with pool.acquire() as conn:
            games_json = json.dumps(self.games)
            artists_json = json.dumps(self.artists)
            interests_json = json.dumps(self.interests)
            
            if self.id:
                await conn.execute(
                    """UPDATE user_profiles 
                       SET username = $1, games = $2, artists = $3, interests = $4, 
                           scanning_enabled = $5, last_processed_message = $6
                       WHERE id = $7""",
                    self.username, games_json, artists_json, interests_json,
                    self.scanning_enabled, self.last_processed_message, self.id
                )
            else:
                row = await conn.fetchrow(
                    """INSERT INTO user_profiles 
                       (discord_id, username, games, artists, interests, scanning_enabled, last_processed_message)
                       VALUES ($1, $2, $3, $4, $5, $6, $7) RETURNING id""",
                    self.discord_id, self.username, games_json, artists_json, 
                    interests_json, self.scanning_enabled, self.last_processed_message
                )
                self.id = row['id']

_pool = None

def get_pool():
    global _pool
    return _pool

async def init_db():
    global _pool
    if _pool is None:
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            raise ValueError("DATABASE_URL not found in environment variables")
        
        try:
            _pool = await asyncpg.create_pool(database_url)
            
            async with _pool.acquire() as conn:
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS user_profiles (
                        id SERIAL PRIMARY KEY,
                        discord_id VARCHAR(255) UNIQUE NOT NULL,
                        username VARCHAR(255) NOT NULL,
                        games TEXT NOT NULL DEFAULT '[]',
                        artists TEXT NOT NULL DEFAULT '[]',
                        interests TEXT NOT NULL DEFAULT '[]',
                        scanning_enabled BOOLEAN DEFAULT TRUE,
                        last_processed_message TEXT
                    )
                ''')
            
            print("Successfully connected to PostgreSQL!")
        except Exception as e:
            print(f"Failed to connect to PostgreSQL: {e}")
            raise