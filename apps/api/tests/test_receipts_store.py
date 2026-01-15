"""Tests for the Receipts Store."""

import pytest
import tempfile
from pathlib import Path

from atlas.core.models import (
    Intent,
    IntentType,
    ModelAttempt,
    Receipt,
    ReceiptStatus,
)
from atlas.storage.database import Database
from atlas.storage.receipts import ReceiptsStore


@pytest.fixture
async def db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        database = Database(db_path)
        await database.connect()
        yield database
        await database.disconnect()


@pytest.fixture
async def store(db: Database) -> ReceiptsStore:
    """Create a receipts store with test database."""
    return ReceiptsStore(db)


def make_receipt(
    user_input: str = "test input",
    status: ReceiptStatus = ReceiptStatus.SUCCESS,
) -> Receipt:
    """Create a test receipt."""
    return Receipt(
        user_input=user_input,
        status=status,
        models_attempted=[
            ModelAttempt(
                provider="ollama",
                model="llama3.2",
                attempt_number=1,
                success=True,
                latency_ms=500,
            )
        ],
        intent_final=Intent(
            type=IntentType.CAPTURE_TASKS,
            confidence=0.95,
            raw_entities=["task1", "task2"],
        ),
    )


class TestReceiptsStore:
    """Test receipt CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_and_get(self, store: ReceiptsStore) -> None:
        """Can create and retrieve a receipt."""
        receipt = make_receipt()
        
        created = await store.create(receipt)
        assert created.receipt_id == receipt.receipt_id
        
        retrieved = await store.get(receipt.receipt_id)
        assert retrieved is not None
        assert retrieved.receipt_id == receipt.receipt_id
        assert retrieved.user_input == receipt.user_input
        assert retrieved.status == receipt.status

    @pytest.mark.asyncio
    async def test_get_nonexistent_returns_none(self, store: ReceiptsStore) -> None:
        """Getting a nonexistent receipt returns None."""
        result = await store.get("nonexistent-id")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_returns_receipts(self, store: ReceiptsStore) -> None:
        """List returns stored receipts."""
        # Create multiple receipts
        for i in range(5):
            await store.create(make_receipt(f"input {i}"))
        
        receipts = await store.list(limit=10)
        assert len(receipts) == 5

    @pytest.mark.asyncio
    async def test_list_respects_limit(self, store: ReceiptsStore) -> None:
        """List respects the limit parameter."""
        for i in range(10):
            await store.create(make_receipt(f"input {i}"))
        
        receipts = await store.list(limit=3)
        assert len(receipts) == 3

    @pytest.mark.asyncio
    async def test_list_returns_newest_first(self, store: ReceiptsStore) -> None:
        """List returns receipts in reverse chronological order."""
        for i in range(3):
            await store.create(make_receipt(f"input {i}"))
        
        receipts = await store.list()
        # The last created should be first
        assert receipts[0].user_input == "input 2"

    @pytest.mark.asyncio
    async def test_list_filters_by_status(self, store: ReceiptsStore) -> None:
        """List can filter by status."""
        await store.create(make_receipt("success", ReceiptStatus.SUCCESS))
        await store.create(make_receipt("failed", ReceiptStatus.FAILED))
        await store.create(make_receipt("success2", ReceiptStatus.SUCCESS))
        
        successes = await store.list(status=ReceiptStatus.SUCCESS)
        assert len(successes) == 2
        assert all(r.status == ReceiptStatus.SUCCESS for r in successes)
        
        failures = await store.list(status=ReceiptStatus.FAILED)
        assert len(failures) == 1

    @pytest.mark.asyncio
    async def test_count(self, store: ReceiptsStore) -> None:
        """Count returns total number of receipts."""
        assert await store.count() == 0
        
        for i in range(5):
            await store.create(make_receipt(f"input {i}"))
        
        assert await store.count() == 5

    @pytest.mark.asyncio
    async def test_count_with_status_filter(self, store: ReceiptsStore) -> None:
        """Count respects status filter."""
        await store.create(make_receipt("s1", ReceiptStatus.SUCCESS))
        await store.create(make_receipt("f1", ReceiptStatus.FAILED))
        await store.create(make_receipt("s2", ReceiptStatus.SUCCESS))
        
        assert await store.count(status=ReceiptStatus.SUCCESS) == 2
        assert await store.count(status=ReceiptStatus.FAILED) == 1

    @pytest.mark.asyncio
    async def test_update(self, store: ReceiptsStore) -> None:
        """Can update an existing receipt."""
        receipt = make_receipt(status=ReceiptStatus.PENDING_CONFIRM)
        await store.create(receipt)
        
        # Update status
        receipt.status = ReceiptStatus.SUCCESS
        await store.update(receipt)
        
        retrieved = await store.get(receipt.receipt_id)
        assert retrieved is not None
        assert retrieved.status == ReceiptStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_delete(self, store: ReceiptsStore) -> None:
        """Can delete a receipt."""
        receipt = make_receipt()
        await store.create(receipt)
        
        # Verify it exists
        assert await store.get(receipt.receipt_id) is not None
        
        # Delete it
        deleted = await store.delete(receipt.receipt_id)
        assert deleted is True
        
        # Verify it's gone
        assert await store.get(receipt.receipt_id) is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, store: ReceiptsStore) -> None:
        """Deleting nonexistent receipt returns False."""
        deleted = await store.delete("nonexistent-id")
        assert deleted is False

    @pytest.mark.asyncio
    async def test_stores_full_receipt_data(self, store: ReceiptsStore) -> None:
        """Receipt with all fields is stored and retrieved correctly."""
        receipt = Receipt(
            user_input="complex input",
            status=ReceiptStatus.SUCCESS,
            profile_id="user_123",
            models_attempted=[
                ModelAttempt(
                    provider="ollama",
                    model="llama3.2",
                    attempt_number=1,
                    success=False,
                    fallback_trigger=None,
                ),
                ModelAttempt(
                    provider="openai",
                    model="gpt-4o",
                    attempt_number=1,
                    success=True,
                    latency_ms=1200,
                ),
            ],
            intent_final=Intent(
                type=IntentType.PLAN_DAY,
                confidence=0.88,
                parameters={"date": "2024-01-15"},
                raw_entities=["meeting", "lunch"],
            ),
            warnings=["warning 1", "warning 2"],
            errors=[],
        )
        
        await store.create(receipt)
        retrieved = await store.get(receipt.receipt_id)
        
        assert retrieved is not None
        assert retrieved.profile_id == "user_123"
        assert len(retrieved.models_attempted) == 2
        assert retrieved.models_attempted[1].latency_ms == 1200
        assert retrieved.intent_final is not None
        assert retrieved.intent_final.parameters["date"] == "2024-01-15"
        assert len(retrieved.warnings) == 2
