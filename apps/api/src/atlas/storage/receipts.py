"""
Receipts Store - Persistence layer for execution receipts.

Every execution in ATLAS produces a receipt. This store ensures
receipts are persisted reliably and can be queried for debugging,
auditing, and undo operations.
"""

import json
from datetime import datetime
from typing import Any
from uuid import UUID

from atlas.core.models import Receipt, ReceiptStatus
from atlas.storage.database import Database


class ReceiptsStore:
    """
    Store for execution receipts.
    
    Provides CRUD operations for receipts with full JSON storage
    for complete audit trail.
    """

    def __init__(self, database: Database):
        self.db = database

    async def create(self, receipt: Receipt) -> Receipt:
        """
        Persist a new receipt.
        
        Args:
            receipt: The receipt to store
            
        Returns:
            The stored receipt (unchanged)
        """
        receipt_json = receipt.model_dump_json()
        
        await self.db.execute(
            """
            INSERT INTO receipts (receipt_id, status, user_input, receipt_json)
            VALUES (?, ?, ?, ?)
            """,
            (
                str(receipt.receipt_id),
                receipt.status.value,
                receipt.user_input,
                receipt_json,
            ),
        )
        
        # Commit the transaction
        if self.db._connection:
            await self.db._connection.commit()
        
        return receipt

    async def get(self, receipt_id: str | UUID) -> Receipt | None:
        """
        Get a receipt by ID.
        
        Args:
            receipt_id: The receipt UUID (string or UUID)
            
        Returns:
            The receipt or None if not found
        """
        row = await self.db.fetch_one(
            "SELECT receipt_json FROM receipts WHERE receipt_id = ?",
            (str(receipt_id),),
        )
        
        if row:
            return Receipt.model_validate_json(row["receipt_json"])
        return None

    async def list(
        self,
        limit: int = 50,
        offset: int = 0,
        status: ReceiptStatus | None = None,
    ) -> list[Receipt]:
        """
        List receipts with optional filtering.
        
        Args:
            limit: Maximum number of receipts to return
            offset: Number of receipts to skip
            status: Optional status filter
            
        Returns:
            List of receipts, newest first
        """
        if status:
            rows = await self.db.fetch_all(
                """
                SELECT receipt_json FROM receipts 
                WHERE status = ?
                ORDER BY created_at DESC 
                LIMIT ? OFFSET ?
                """,
                (status.value, limit, offset),
            )
        else:
            rows = await self.db.fetch_all(
                """
                SELECT receipt_json FROM receipts 
                ORDER BY created_at DESC 
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            )
        
        return [Receipt.model_validate_json(row["receipt_json"]) for row in rows]

    async def count(self, status: ReceiptStatus | None = None) -> int:
        """
        Count total receipts.
        
        Args:
            status: Optional status filter
            
        Returns:
            Total count
        """
        if status:
            row = await self.db.fetch_one(
                "SELECT COUNT(*) as count FROM receipts WHERE status = ?",
                (status.value,),
            )
        else:
            row = await self.db.fetch_one("SELECT COUNT(*) as count FROM receipts")
        
        return row["count"] if row else 0

    async def update(self, receipt: Receipt) -> Receipt:
        """
        Update an existing receipt.
        
        Used when confirming pending tool calls or updating status.
        
        Args:
            receipt: The updated receipt
            
        Returns:
            The updated receipt
        """
        receipt_json = receipt.model_dump_json()
        
        await self.db.execute(
            """
            UPDATE receipts 
            SET status = ?, receipt_json = ?
            WHERE receipt_id = ?
            """,
            (receipt.status.value, receipt_json, str(receipt.receipt_id)),
        )
        
        if self.db._connection:
            await self.db._connection.commit()
        
        return receipt

    async def delete(self, receipt_id: str | UUID) -> bool:
        """
        Delete a receipt by ID.
        
        Args:
            receipt_id: The receipt UUID
            
        Returns:
            True if deleted, False if not found
        """
        cursor = await self.db.execute(
            "DELETE FROM receipts WHERE receipt_id = ?",
            (str(receipt_id),),
        )
        
        if self.db._connection:
            await self.db._connection.commit()
        
        return cursor.rowcount > 0

    async def get_recent(self, hours: int = 24, limit: int = 100) -> list[Receipt]:
        """
        Get recent receipts within a time window.
        
        Args:
            hours: Number of hours to look back
            limit: Maximum receipts to return
            
        Returns:
            List of recent receipts
        """
        rows = await self.db.fetch_all(
            """
            SELECT receipt_json FROM receipts 
            WHERE created_at >= datetime('now', ?)
            ORDER BY created_at DESC 
            LIMIT ?
            """,
            (f"-{hours} hours", limit),
        )
        
        return [Receipt.model_validate_json(row["receipt_json"]) for row in rows]

    async def get_by_status(
        self, status: ReceiptStatus, limit: int = 50
    ) -> list[Receipt]:
        """
        Get receipts by status.
        
        Useful for finding pending confirmations or failed executions.
        
        Args:
            status: The status to filter by
            limit: Maximum receipts to return
            
        Returns:
            List of matching receipts
        """
        return await self.list(limit=limit, status=status)
