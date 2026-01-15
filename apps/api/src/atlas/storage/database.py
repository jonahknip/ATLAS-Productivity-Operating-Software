"""
Database Setup and Connection Management.

Supports both SQLite (local dev) and PostgreSQL (production).
Uses aiosqlite for SQLite and asyncpg for Postgres.
"""

import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncGenerator, Protocol, runtime_checkable

from atlas.config import get_settings


@runtime_checkable
class DatabaseConnection(Protocol):
    """Protocol for database connections."""
    async def execute(self, query: str, *args: Any) -> Any: ...
    async def fetchone(self) -> Any: ...
    async def fetchall(self) -> Any: ...
    async def close(self) -> None: ...


class SQLiteDatabase:
    """Async SQLite database manager for local development."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self._connection: Any = None

    async def connect(self) -> None:
        """Initialize database connection and run migrations."""
        import aiosqlite
        
        # Ensure parent directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._connection = await aiosqlite.connect(self.db_path)
        await self._connection.execute("PRAGMA foreign_keys = ON")
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

        await self._connection.execute("""
            CREATE TABLE IF NOT EXISTS _migrations (
                id INTEGER PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        migrations = [
            ("001_create_receipts", self._migration_001_create_receipts),
        ]

        for name, migration_fn in migrations:
            cursor = await self._connection.execute(
                "SELECT 1 FROM _migrations WHERE name = ?", (name,)
            )
            if await cursor.fetchone():
                continue

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
            CREATE TABLE IF NOT EXISTS receipts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                receipt_id TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT NOT NULL,
                user_input TEXT NOT NULL,
                receipt_json TEXT NOT NULL
            )
        """)
        
        await self._connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_receipts_receipt_id ON receipts(receipt_id)
        """)
        await self._connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_receipts_created_at ON receipts(created_at DESC)
        """)

    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[Any, None]:
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
    ) -> Any:
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
        import aiosqlite
        
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
        import aiosqlite
        
        if not self._connection:
            raise RuntimeError("Database not connected")
        
        self._connection.row_factory = aiosqlite.Row
        cursor = await self.execute(query, params)
        rows = await cursor.fetchall()
        
        return [dict(row) for row in rows]


class PostgresDatabase:
    """Async PostgreSQL database manager for production."""

    def __init__(self, database_url: str):
        self.database_url = database_url
        self._pool: Any = None

    async def connect(self) -> None:
        """Initialize database connection pool and run migrations."""
        import asyncpg
        
        self._pool = await asyncpg.create_pool(self.database_url, min_size=2, max_size=10)
        await self._run_migrations()

    async def disconnect(self) -> None:
        """Close database connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None

    async def _run_migrations(self) -> None:
        """Run database schema migrations."""
        if not self._pool:
            raise RuntimeError("Database not connected")

        async with self._pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS _migrations (
                    id SERIAL PRIMARY KEY,
                    name TEXT UNIQUE NOT NULL,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            migrations = [
                ("001_create_receipts", self._migration_001_create_receipts),
            ]

            for name, migration_fn in migrations:
                row = await conn.fetchrow(
                    "SELECT 1 FROM _migrations WHERE name = $1", name
                )
                if row:
                    continue

                await migration_fn(conn)
                await conn.execute(
                    "INSERT INTO _migrations (name) VALUES ($1)", name
                )

    async def _migration_001_create_receipts(self, conn: Any) -> None:
        """Create the receipts table."""
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS receipts (
                id SERIAL PRIMARY KEY,
                receipt_id TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT NOT NULL,
                user_input TEXT NOT NULL,
                receipt_json TEXT NOT NULL
            )
        """)
        
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_receipts_receipt_id ON receipts(receipt_id)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_receipts_created_at ON receipts(created_at DESC)
        """)

    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[Any, None]:
        """Context manager for database transactions."""
        if not self._pool:
            raise RuntimeError("Database not connected")
        
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                yield conn

    async def execute(
        self, query: str, params: tuple[Any, ...] | None = None
    ) -> Any:
        """Execute a query."""
        if not self._pool:
            raise RuntimeError("Database not connected")
        
        # Convert ? placeholders to $1, $2, etc. for Postgres
        pg_query = self._convert_placeholders(query)
        
        async with self._pool.acquire() as conn:
            if params:
                return await conn.execute(pg_query, *params)
            return await conn.execute(pg_query)

    async def fetch_one(
        self, query: str, params: tuple[Any, ...] | None = None
    ) -> dict[str, Any] | None:
        """Fetch a single row as dict."""
        if not self._pool:
            raise RuntimeError("Database not connected")
        
        pg_query = self._convert_placeholders(query)
        
        async with self._pool.acquire() as conn:
            if params:
                row = await conn.fetchrow(pg_query, *params)
            else:
                row = await conn.fetchrow(pg_query)
        
        if row:
            return dict(row)
        return None

    async def fetch_all(
        self, query: str, params: tuple[Any, ...] | None = None
    ) -> list[dict[str, Any]]:
        """Fetch all rows as list of dicts."""
        if not self._pool:
            raise RuntimeError("Database not connected")
        
        pg_query = self._convert_placeholders(query)
        
        async with self._pool.acquire() as conn:
            if params:
                rows = await conn.fetch(pg_query, *params)
            else:
                rows = await conn.fetch(pg_query)
        
        return [dict(row) for row in rows]

    @staticmethod
    def _convert_placeholders(query: str) -> str:
        """Convert ? placeholders to $1, $2, etc. for Postgres."""
        result = []
        param_num = 0
        i = 0
        while i < len(query):
            if query[i] == '?':
                param_num += 1
                result.append(f'${param_num}')
            else:
                result.append(query[i])
            i += 1
        return ''.join(result)


# Type alias for database
Database = SQLiteDatabase | PostgresDatabase

# Global database instance
_database: Database | None = None


async def get_database() -> Database:
    """Get the global database instance, initializing if needed."""
    global _database
    
    if _database is None:
        settings = get_settings()
        db_url = settings.database_url
        
        if settings.is_postgres:
            # Production: use PostgreSQL
            _database = PostgresDatabase(db_url)
        else:
            # Local dev: use SQLite
            if db_url.startswith("sqlite"):
                db_path = db_url.split("///")[-1]
            else:
                db_path = "./atlas.db"
            _database = SQLiteDatabase(db_path)
        
        await _database.connect()
    
    return _database


async def close_database() -> None:
    """Close the global database connection."""
    global _database
    
    if _database:
        await _database.disconnect()
        _database = None
