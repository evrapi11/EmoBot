import os
import asyncpg
from typing import List, Optional, Set
from dataclasses import dataclass

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
            user_row = await conn.fetchrow(
                "SELECT * FROM users WHERE discord_id = $1", 
                discord_id
            )
            if not user_row:
                return None
            
            user_id = user_row['id']
            
            games = await conn.fetch("""
                SELECT g.name FROM games g
                JOIN user_games ug ON g.id = ug.game_id
                WHERE ug.user_id = $1
            """, user_id)
            
            artists = await conn.fetch("""
                SELECT a.name FROM artists a
                JOIN user_artists ua ON a.id = ua.artist_id
                WHERE ua.user_id = $1
            """, user_id)
            
            interests = await conn.fetch("""
                SELECT i.name FROM interests i
                JOIN user_interests ui ON i.id = ui.interest_id
                WHERE ui.user_id = $1
            """, user_id)
            
            return cls(
                discord_id=user_row['discord_id'],
                username=user_row['username'],
                games=[row['name'] for row in games],
                artists=[row['name'] for row in artists],
                interests=[row['name'] for row in interests],
                scanning_enabled=user_row['scanning_enabled'],
                last_processed_message=user_row['last_processed_message'],
                id=user_row['id']
            )
    
    @classmethod
    async def find_all_except(cls, discord_id: str) -> List['UserProfile']:
        pool = get_pool()
        async with pool.acquire() as conn:
            user_rows = await conn.fetch(
                "SELECT * FROM users WHERE discord_id != $1", 
                discord_id
            )
            
            profiles = []
            for user_row in user_rows:
                user_id = user_row['id']
                
                games = await conn.fetch("""
                    SELECT g.name FROM games g
                    JOIN user_games ug ON g.id = ug.game_id
                    WHERE ug.user_id = $1
                """, user_id)
                
                artists = await conn.fetch("""
                    SELECT a.name FROM artists a
                    JOIN user_artists ua ON a.id = ua.artist_id
                    WHERE ua.user_id = $1
                """, user_id)
                
                interests = await conn.fetch("""
                    SELECT i.name FROM interests i
                    JOIN user_interests ui ON i.id = ui.interest_id
                    WHERE ui.user_id = $1
                """, user_id)
                
                profiles.append(cls(
                    discord_id=user_row['discord_id'],
                    username=user_row['username'],
                    games=[row['name'] for row in games],
                    artists=[row['name'] for row in artists],
                    interests=[row['name'] for row in interests],
                    scanning_enabled=user_row['scanning_enabled'],
                    last_processed_message=user_row['last_processed_message'],
                    id=user_row['id']
                ))
            
            return profiles
    
    async def save(self):
        pool = get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                if self.id:
                    await conn.execute(
                        """UPDATE users 
                           SET username = $1, scanning_enabled = $2, last_processed_message = $3
                           WHERE id = $4""",
                        self.username, self.scanning_enabled, self.last_processed_message, self.id
                    )
                    user_id = self.id
                else:
                    row = await conn.fetchrow(
                        """INSERT INTO users 
                           (discord_id, username, scanning_enabled, last_processed_message)
                           VALUES ($1, $2, $3, $4) RETURNING id""",
                        self.discord_id, self.username, self.scanning_enabled, self.last_processed_message
                    )
                    user_id = row['id']
                    self.id = user_id
                
                await _update_user_relationships(conn, user_id, 'games', 'user_games', 'game_id', self.games)
                await _update_user_relationships(conn, user_id, 'artists', 'user_artists', 'artist_id', self.artists)
                await _update_user_relationships(conn, user_id, 'interests', 'user_interests', 'interest_id', self.interests)

async def _update_user_relationships(conn, user_id: int, table_name: str, junction_table: str, foreign_key: str, items: List[str]):
    await conn.execute(f"DELETE FROM {junction_table} WHERE user_id = $1", user_id)
    
    for item in items:
        item_row = await conn.fetchrow(f"SELECT id FROM {table_name} WHERE name = $1", item)
        if not item_row:
            item_row = await conn.fetchrow(f"INSERT INTO {table_name} (name) VALUES ($1) RETURNING id", item)
        
        item_id = item_row['id']
        await conn.execute(f"INSERT INTO {junction_table} (user_id, {foreign_key}) VALUES ($1, $2)", user_id, item_id)

async def find_users_with_game(game_name: str) -> List[str]:
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT u.discord_id FROM users u
            JOIN user_games ug ON u.id = ug.user_id
            JOIN games g ON ug.game_id = g.id
            WHERE g.name = $1
        """, game_name)
        return [row['discord_id'] for row in rows]

async def find_users_with_artist(artist_name: str) -> List[str]:
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT u.discord_id FROM users u
            JOIN user_artists ua ON u.id = ua.user_id
            JOIN artists a ON ua.artist_id = a.id
            WHERE a.name = $1
        """, artist_name)
        return [row['discord_id'] for row in rows]

async def find_users_with_interest(interest_name: str) -> List[str]:
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT u.discord_id FROM users u
            JOIN user_interests ui ON u.id = ui.user_id
            JOIN interests i ON ui.interest_id = i.id
            WHERE i.name = $1
        """, interest_name)
        return [row['discord_id'] for row in rows]

async def get_popular_games(limit: int = 10) -> List[tuple]:
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT g.name, COUNT(*) as user_count
            FROM games g
            JOIN user_games ug ON g.id = ug.game_id
            GROUP BY g.id, g.name
            ORDER BY user_count DESC
            LIMIT $1
        """, limit)
        return [(row['name'], row['user_count']) for row in rows]

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
                    CREATE TABLE IF NOT EXISTS users (
                        id SERIAL PRIMARY KEY,
                        discord_id VARCHAR(255) UNIQUE NOT NULL,
                        username VARCHAR(255) NOT NULL,
                        scanning_enabled BOOLEAN DEFAULT TRUE,
                        last_processed_message TEXT
                    )
                ''')
                
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS games (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR(255) UNIQUE NOT NULL
                    )
                ''')
                
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS artists (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR(255) UNIQUE NOT NULL
                    )
                ''')
                
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS interests (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR(255) UNIQUE NOT NULL
                    )
                ''')
                
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS user_games (
                        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                        game_id INTEGER REFERENCES games(id) ON DELETE CASCADE,
                        PRIMARY KEY (user_id, game_id)
                    )
                ''')
                
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS user_artists (
                        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                        artist_id INTEGER REFERENCES artists(id) ON DELETE CASCADE,
                        PRIMARY KEY (user_id, artist_id)
                    )
                ''')
                
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS user_interests (
                        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                        interest_id INTEGER REFERENCES interests(id) ON DELETE CASCADE,
                        PRIMARY KEY (user_id, interest_id)
                    )
                ''')
                
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS oauth_accounts (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                        provider VARCHAR(50) NOT NULL,
                        provider_user_id VARCHAR(255) NOT NULL,
                        email VARCHAR(255),
                        username VARCHAR(255),
                        avatar_url TEXT,
                        access_token TEXT,
                        refresh_token TEXT,
                        expires_at TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(provider, provider_user_id)
                    )
                ''')
            
            print("Successfully connected to PostgreSQL!")
        except Exception as e:
            print(f"Failed to connect to PostgreSQL: {e}")
            raise