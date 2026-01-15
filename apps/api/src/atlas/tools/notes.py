"""
Note Tools - CRUD operations for notes.

All note tools are LOW risk and support search.
"""

from datetime import datetime
from typing import Any
from uuid import uuid4

from atlas.core.models import Change, RiskLevel, UndoStep
from atlas.tools.base import Tool, ToolResult


# In-memory note storage
_notes: dict[str, dict[str, Any]] = {}


class NoteCreateTool(Tool):
    """Create a new note."""

    @property
    def name(self) -> str:
        return "NOTE_CREATE"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.LOW

    @property
    def description(self) -> str:
        return "Create a new note with title, content, and tags"

    async def execute(
        self,
        title: str,
        content: str = "",
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        note_id = f"note_{uuid4().hex[:12]}"
        now = datetime.utcnow().isoformat()
        
        note = {
            "note_id": note_id,
            "title": title,
            "content": content,
            "tags": tags or [],
            "created_at": now,
            "updated_at": now,
        }
        
        _notes[note_id] = note
        
        return ToolResult(
            success=True,
            data={"note_id": note_id, "created_at": now},
            changes=[
                Change(
                    entity_type="note",
                    entity_id=note_id,
                    action="created",
                    after=note,
                )
            ],
            undo_step=UndoStep(
                tool_name="NOTE_DELETE",
                args={"note_id": note_id},
                description=f"Delete note: {title}",
            ),
        )


class NoteSearchTool(Tool):
    """Search notes by content or tags."""

    @property
    def name(self) -> str:
        return "NOTE_SEARCH"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.LOW

    @property
    def description(self) -> str:
        return "Search notes by query string or tags"

    async def execute(
        self,
        query: str = "",
        tags: list[str] | None = None,
        limit: int = 20,
        **kwargs: Any,
    ) -> ToolResult:
        results = []
        query_lower = query.lower()
        
        for note in _notes.values():
            # Calculate relevance score
            relevance = 0.0
            
            # Check title match
            if query_lower and query_lower in note["title"].lower():
                relevance += 0.5
            
            # Check content match
            if query_lower and query_lower in note["content"].lower():
                relevance += 0.3
            
            # Check tag match
            if tags:
                matching_tags = set(tags) & set(note.get("tags", []))
                if matching_tags:
                    relevance += 0.2 * len(matching_tags)
            
            # If no query/tags, include all notes
            if not query and not tags:
                relevance = 0.5
            
            if relevance > 0:
                # Create snippet from content
                content = note["content"]
                snippet = content[:200] + "..." if len(content) > 200 else content
                
                results.append({
                    "note_id": note["note_id"],
                    "title": note["title"],
                    "snippet": snippet,
                    "tags": note.get("tags", []),
                    "relevance": round(relevance, 2),
                    "created_at": note["created_at"],
                })
        
        # Sort by relevance
        results.sort(key=lambda x: x["relevance"], reverse=True)
        results = results[:limit]
        
        return ToolResult(
            success=True,
            data={"notes": results, "total": len(results)},
        )


class NoteGetTool(Tool):
    """Get a note by ID."""

    @property
    def name(self) -> str:
        return "NOTE_GET"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.LOW

    @property
    def description(self) -> str:
        return "Get the full content of a note by its ID"

    async def execute(self, note_id: str, **kwargs: Any) -> ToolResult:
        note = _notes.get(note_id)
        
        if not note:
            return ToolResult(
                success=False,
                error=f"Note not found: {note_id}",
            )
        
        return ToolResult(
            success=True,
            data={"note": note},
        )


class NoteUpdateTool(Tool):
    """Update an existing note."""

    @property
    def name(self) -> str:
        return "NOTE_UPDATE"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.LOW

    @property
    def description(self) -> str:
        return "Update a note's title, content, or tags"

    async def execute(
        self,
        note_id: str,
        updates: dict[str, Any],
        **kwargs: Any,
    ) -> ToolResult:
        note = _notes.get(note_id)
        
        if not note:
            return ToolResult(
                success=False,
                error=f"Note not found: {note_id}",
            )
        
        before = note.copy()
        
        allowed_fields = {"title", "content", "tags"}
        for key, value in updates.items():
            if key in allowed_fields:
                note[key] = value
        
        note["updated_at"] = datetime.utcnow().isoformat()
        
        return ToolResult(
            success=True,
            data={
                "note_id": note_id,
                "before": {k: before.get(k) for k in updates.keys()},
                "after": {k: note.get(k) for k in updates.keys()},
            },
            changes=[
                Change(
                    entity_type="note",
                    entity_id=note_id,
                    action="updated",
                    before=before,
                    after=note.copy(),
                )
            ],
            undo_step=UndoStep(
                tool_name="NOTE_UPDATE",
                args={
                    "note_id": note_id,
                    "updates": {k: before.get(k) for k in updates.keys()},
                },
                description="Restore note to previous state",
            ),
        )


class NoteDeleteTool(Tool):
    """Delete a note."""

    @property
    def name(self) -> str:
        return "NOTE_DELETE"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.LOW

    @property
    def description(self) -> str:
        return "Delete a note by its ID"

    async def execute(self, note_id: str, **kwargs: Any) -> ToolResult:
        note = _notes.pop(note_id, None)
        
        if not note:
            return ToolResult(
                success=False,
                error=f"Note not found: {note_id}",
            )
        
        return ToolResult(
            success=True,
            data={"note_id": note_id, "deleted": True},
            changes=[
                Change(
                    entity_type="note",
                    entity_id=note_id,
                    action="deleted",
                    before=note,
                )
            ],
            undo_step=UndoStep(
                tool_name="NOTE_CREATE",
                args={
                    "title": note["title"],
                    "content": note.get("content", ""),
                    "tags": note.get("tags", []),
                },
                description=f"Restore deleted note: {note['title']}",
            ),
        )


def get_all_notes() -> dict[str, dict[str, Any]]:
    """Get all notes (for testing/debugging)."""
    return _notes.copy()


def clear_all_notes() -> None:
    """Clear all notes (for testing)."""
    _notes.clear()
