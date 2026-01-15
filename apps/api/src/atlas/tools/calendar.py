"""
Calendar Tools - Operations for calendar blocks.

Calendar write operations are MEDIUM risk and require confirmation.
"""

from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from atlas.core.models import Change, RiskLevel, UndoStep
from atlas.tools.base import Tool, ToolResult


# In-memory calendar storage
_calendar_blocks: dict[str, dict[str, Any]] = {}


class CalendarGetDayTool(Tool):
    """Get calendar events for a specific day."""

    @property
    def name(self) -> str:
        return "CALENDAR_GET_DAY"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.LOW

    @property
    def description(self) -> str:
        return "Get all calendar blocks and free slots for a given date"

    async def execute(self, date: str, **kwargs: Any) -> ToolResult:
        # Get blocks for this date
        blocks = [
            b for b in _calendar_blocks.values()
            if b["date"] == date
        ]
        
        # Sort by start time
        blocks.sort(key=lambda b: b["start"])
        
        # Calculate free slots (simple implementation)
        free_slots = []
        work_start = "09:00"
        work_end = "17:00"
        
        if not blocks:
            free_slots.append({"start": work_start, "end": work_end})
        else:
            # Before first block
            if blocks[0]["start"] > work_start:
                free_slots.append({"start": work_start, "end": blocks[0]["start"]})
            
            # Between blocks
            for i in range(len(blocks) - 1):
                if blocks[i]["end"] < blocks[i + 1]["start"]:
                    free_slots.append({
                        "start": blocks[i]["end"],
                        "end": blocks[i + 1]["start"],
                    })
            
            # After last block
            if blocks[-1]["end"] < work_end:
                free_slots.append({"start": blocks[-1]["end"], "end": work_end})
        
        return ToolResult(
            success=True,
            data={
                "date": date,
                "blocks": blocks,
                "free_slots": free_slots,
            },
        )


class CalendarCreateBlocksTool(Tool):
    """Create calendar blocks. Requires confirmation."""

    @property
    def name(self) -> str:
        return "CALENDAR_CREATE_BLOCKS"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.MEDIUM

    @property
    def description(self) -> str:
        return "Create one or more calendar blocks for a given date"

    async def execute(
        self,
        date: str,
        blocks: list[dict[str, Any]],
        **kwargs: Any,
    ) -> ToolResult:
        created_blocks = []
        block_ids = []
        
        for block_data in blocks:
            block_id = f"block_{uuid4().hex[:12]}"
            
            block = {
                "block_id": block_id,
                "date": date,
                "title": block_data.get("title", "Untitled"),
                "start": block_data.get("start", "09:00"),
                "end": block_data.get("end", "10:00"),
                "type": block_data.get("type", "task"),
                "created_at": datetime.utcnow().isoformat(),
            }
            
            _calendar_blocks[block_id] = block
            created_blocks.append(block)
            block_ids.append(block_id)
        
        return ToolResult(
            success=True,
            data={"created": created_blocks},
            changes=[
                Change(
                    entity_type="calendar_block",
                    entity_id=block["block_id"],
                    action="created",
                    after=block,
                )
                for block in created_blocks
            ],
            undo_step=UndoStep(
                tool_name="CALENDAR_DELETE_BLOCKS",
                args={"block_ids": block_ids},
                description=f"Delete {len(block_ids)} calendar block(s)",
            ),
        )


class CalendarDeleteBlocksTool(Tool):
    """Delete calendar blocks by ID."""

    @property
    def name(self) -> str:
        return "CALENDAR_DELETE_BLOCKS"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.MEDIUM

    @property
    def description(self) -> str:
        return "Delete one or more calendar blocks by their IDs"

    async def execute(
        self,
        block_ids: list[str],
        **kwargs: Any,
    ) -> ToolResult:
        deleted_blocks = []
        not_found = []
        
        for block_id in block_ids:
            block = _calendar_blocks.pop(block_id, None)
            if block:
                deleted_blocks.append(block)
            else:
                not_found.append(block_id)
        
        if not deleted_blocks:
            return ToolResult(
                success=False,
                error=f"No blocks found: {not_found}",
            )
        
        # Build undo data for recreating blocks
        undo_blocks = [
            {
                "title": b["title"],
                "start": b["start"],
                "end": b["end"],
                "type": b["type"],
            }
            for b in deleted_blocks
        ]
        
        # Get the date from first deleted block
        date = deleted_blocks[0]["date"] if deleted_blocks else ""
        
        return ToolResult(
            success=True,
            data={
                "deleted": [b["block_id"] for b in deleted_blocks],
                "deleted_data": deleted_blocks,
                "not_found": not_found,
            },
            changes=[
                Change(
                    entity_type="calendar_block",
                    entity_id=block["block_id"],
                    action="deleted",
                    before=block,
                )
                for block in deleted_blocks
            ],
            undo_step=UndoStep(
                tool_name="CALENDAR_CREATE_BLOCKS",
                args={"date": date, "blocks": undo_blocks},
                description=f"Restore {len(deleted_blocks)} deleted calendar block(s)",
            ),
        )


class CalendarUpdateBlockTool(Tool):
    """Update a calendar block."""

    @property
    def name(self) -> str:
        return "CALENDAR_UPDATE_BLOCK"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.MEDIUM

    @property
    def description(self) -> str:
        return "Update a calendar block's properties"

    async def execute(
        self,
        block_id: str,
        updates: dict[str, Any],
        **kwargs: Any,
    ) -> ToolResult:
        block = _calendar_blocks.get(block_id)
        
        if not block:
            return ToolResult(
                success=False,
                error=f"Block not found: {block_id}",
            )
        
        before = block.copy()
        
        allowed_fields = {"title", "start", "end", "type"}
        for key, value in updates.items():
            if key in allowed_fields:
                block[key] = value
        
        return ToolResult(
            success=True,
            data={
                "block_id": block_id,
                "before": {k: before.get(k) for k in updates.keys()},
                "after": {k: block.get(k) for k in updates.keys()},
            },
            changes=[
                Change(
                    entity_type="calendar_block",
                    entity_id=block_id,
                    action="updated",
                    before=before,
                    after=block.copy(),
                )
            ],
            undo_step=UndoStep(
                tool_name="CALENDAR_UPDATE_BLOCK",
                args={
                    "block_id": block_id,
                    "updates": {k: before.get(k) for k in updates.keys()},
                },
                description="Restore calendar block to previous state",
            ),
        )


def get_all_blocks() -> dict[str, dict[str, Any]]:
    """Get all calendar blocks (for testing/debugging)."""
    return _calendar_blocks.copy()


def clear_all_blocks() -> None:
    """Clear all calendar blocks (for testing)."""
    _calendar_blocks.clear()
