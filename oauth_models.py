import os
import asyncpg
from typing import List, Optional
from dataclasses import dataclass
from datetime import datetime
from database import get_pool

@dataclass
class OAuthAccount:
    provider: str
    provider_user_id: str
    email: Optional[str] = None
    username: Optional[str] = None
    avatar_url: Optional[str] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    expires_at: Optional[datetime] = None
    user_id: Optional[int] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    @classmethod
    async def find_by_provider_and_id(cls, provider: str, provider_user_id: str) -> Optional['OAuthAccount']:
        pool = get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM oauth_accounts WHERE provider = $1 AND provider_user_id = $2",
                provider, provider_user_id
            )
            if not row:
                return None
            
            return cls(
                id=row['id'],
                user_id=row['user_id'],
                provider=row['provider'],
                provider_user_id=row['provider_user_id'],
                email=row['email'],
                username=row['username'],
                avatar_url=row['avatar_url'],
                access_token=row['access_token'],
                refresh_token=row['refresh_token'],
                expires_at=row['expires_at'],
                created_at=row['created_at'],
                updated_at=row['updated_at']
            )
    
    @classmethod
    async def find_by_user_id(cls, user_id: int) -> List['OAuthAccount']:
        pool = get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM oauth_accounts WHERE user_id = $1",
                user_id
            )
            
            accounts = []
            for row in rows:
                accounts.append(cls(
                    id=row['id'],
                    user_id=row['user_id'],
                    provider=row['provider'],
                    provider_user_id=row['provider_user_id'],
                    email=row['email'],
                    username=row['username'],
                    avatar_url=row['avatar_url'],
                    access_token=row['access_token'],
                    refresh_token=row['refresh_token'],
                    expires_at=row['expires_at'],
                    created_at=row['created_at'],
                    updated_at=row['updated_at']
                ))
            
            return accounts
    
    async def save(self):
        pool = get_pool()
        async with pool.acquire() as conn:
            if self.id:
                await conn.execute(
                    """UPDATE oauth_accounts 
                       SET email = $1, username = $2, avatar_url = $3, 
                           access_token = $4, refresh_token = $5, expires_at = $6,
                           updated_at = CURRENT_TIMESTAMP
                       WHERE id = $7""",
                    self.email, self.username, self.avatar_url, 
                    self.access_token, self.refresh_token, self.expires_at,
                    self.id
                )
            else:
                row = await conn.fetchrow(
                    """INSERT INTO oauth_accounts 
                       (user_id, provider, provider_user_id, email, username, 
                        avatar_url, access_token, refresh_token, expires_at)
                       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) 
                       RETURNING id, created_at, updated_at""",
                    self.user_id, self.provider, self.provider_user_id, 
                    self.email, self.username, self.avatar_url,
                    self.access_token, self.refresh_token, self.expires_at
                )
                self.id = row['id']
                self.created_at = row['created_at']
                self.updated_at = row['updated_at']
    
    async def delete(self):
        if not self.id:
            return
        
        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM oauth_accounts WHERE id = $1", self.id)

async def link_oauth_account_to_user(oauth_account: OAuthAccount, user_id: int):
    oauth_account.user_id = user_id
    await oauth_account.save()

async def unlink_oauth_account(provider: str, provider_user_id: str):
    account = await OAuthAccount.find_by_provider_and_id(provider, provider_user_id)
    if account:
        await account.delete()