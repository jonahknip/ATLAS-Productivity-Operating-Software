"""
SQLite Database Setup and Connection Management.

Uses aiosqlite for async operations with SQLite.
The database is the persistence backbone for ATLAS.
"""

import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncGenerator

import aiosqlite

from atlas.config import get_settings


class Database:
    """
    Async SQLite database manager.
    
    Handles connection pooling, schema migrations, and
    provides a clean async context manager interface.
    """

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self._connection: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        """Initialize database connection and run migrations."""
        # Ensure parent directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._connection = await aiosqlite.connect(self.db_path)
        # Enable foreign keys
        await self._connection.execute("PRAGMA foreign_keys = ON")
        # Use WAL mode for better concurrency
        await self._connection.execute("PRAGMA journal_mode = WAL")
        
        await self._run_migrations()

    async def disconnect(self) -> None:
        """Close database connection."""
        if self._connection:
            await self._connection.close()
            self._connection = None

    async def _run_migrations(self) -> None:
        """Run database schema migrations."""
        if not self._connection:
            raise RuntimeError("Database not connected")

        # Create migrations table if not exists
        await self._connection.execute("""
            CREATE TABLE IF NOT EXISTS _migrations (
                id INTEGER PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Define migrations
        migrations = [
            ("001_create_receipts", self._migration_001_create_receipts),
        ]

        for name, migration_fn in migrations:
            # Check if migration already applied
            cursor = await self._connection.execute(
                "SELECT 1 FROM _migrations WHERE name = ?", (name,)
            )
            if await cursor.fetchone():
                continue

            # Run migration
            await migration_fn()
            await self._connection.execute(
                "INSERT INTO _migrations (name) VALUES (?)", (name,)
            )
            await self._connection.commit()

    async def _migration_001_create_receipts(self) -> None:
        """Create the receipts table."""
        if not self._connection:
            return

        await self._connection.execute("""
            CREATE TABLE receipts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                receipt_id TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT NOT NULL,
                user_input TEXT NOT NULL,
                receipt_json TEXT NOT NULL
            )
        """)
        
        # Index for fast lookups
        await self._connection.execute("""
            CREATE INDEX idx_receipts_receipt_id ON receipts(receipt_id)
        """)
        await self._connection.execute("""
            CREATE INDEX idx_receipts_created_at ON receipts(created_at DESC)
        """)

    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[aiosqlite.Connection, None]:
        """Context manager for database transactions."""
        if not self._connection:
            raise RuntimeError("Database not connected")
        
        try:
            yield self._connection
            await self._connection.commit()
        except Exception:
            await self._connection.rollback()
            raise

    async def execute(
        self, query: str, params: tuple[Any, ...] | None = None
    ) -> aiosqlite.Cursor:
        """Execute a query."""
        if not self._connection:
            raise RuntimeError("Database not connected")
        
        if params:
            return await self._connection.execute(query, params)
        return await self._connection.execute(query)

    async def fetch_one(
        self, query: str, params: tuple[Any, ...] | None = None
    ) -> dict[str, Any] | None:
        """Fetch a single row as dict."""
        if not self._connection:
            raise RuntimeError("Database not connected")
        
        self._connection.row_factory = aiosqlite.Row
        cursor = await self.execute(query, params)
        row = await cursor.fetchone()
        
        if row:
            return dict(row)
        return None

    async def fetch_all(
        self, query: str, params: tuple[Any, ...] | None = None
    ) -> list[dict[str, Any]]:
        """Fetch all rows as list of dicts."""
        if not self._connection:
            raise RuntimeError("Database not connected")
        
        self._connection.row_factory = aiosqlite.Row
        cursor = await self.execute(query, params)
        rows = await cursor.fetchall()
        
        return [dict(row) for row in rows]


# Global database instance
_database: Database | None = None


async def get_database() -> Database:
    """Get the global database instance, initializing if needed."""
    global _database
    
    if _database is None:
        settings = get_settings()
        # Extract path from SQLite URL
        db_url = settings.database_url
        if db_url.startswith("sqlite"):
            # Handle both sqlite:/// and sqlite+aiosqlite:///
            db_path = db_url.split("///")[-1]
        else:
            db_path = "./atlas.db"
        
        _database = Database(db_path)
        await _database.connect()
    
    return _database


async def close_database() -> None:
    """Close the global database connection."""
    global _database
    
    if _database:
        await _database.disconnect()
        _database = None
