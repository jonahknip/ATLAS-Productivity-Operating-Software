"""
Note Tools - CRUD operations for notes.

All note tools are LOW risk and support search.
Uses MCP Dashboard server when available, falls back to in-memory storage.
"""

from datetime import datetime
from typing import Any
from uuid import uuid4

from atlas.core.models import Change, RiskLevel, UndoStep
from atlas.tools.base import Tool, ToolResult
from atlas.mcp import get_mcp_client


# In-memory note storage (fallback when MCP not available)
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

    async def execute(self, **kwargs: Any) -> ToolResult:
        title = kwargs.get("title", "Untitled Note")
        content = kwargs.get("content", "")
        tags = kwargs.get("tags", [])
        
        # Try MCP server first
        mcp = get_mcp_client()
        response = await mcp.call_dashboard("note.create", {
            "title": title,
            "content": content,
            "tags": tags,
        })
        
        if response.success and response.data:
            note_id = str(response.data.get("note_id") or response.data.get("id") or "unknown")
            return ToolResult(
                success=True,
                data={"note_id": note_id, "source": "mcp"},
                changes=[
                    Change(
                        entity_type="note",
                        entity_id=note_id,
                        action="created",
                        after=response.data,
                    )
                ],
                undo_step=UndoStep(
                    tool_name="NOTE_DELETE",
                    args={"note_id": note_id},
                    description=f"Delete note: {title}",
                ),
            )
        
        # Fallback to in-memory storage
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
            data={"note_id": note_id, "created_at": now, "source": "local"},
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

    async def execute(self, **kwargs: Any) -> ToolResult:
        query = kwargs.get("query", "")
        tags = kwargs.get("tags")
        limit = kwargs.get("limit", 20)
        
        # Try MCP server first
        mcp = get_mcp_client()
        response = await mcp.call_dashboard("note.search", {
            "query": query,
            "tags": tags,
            "limit": limit,
        })
        
        if response.success and response.data:
            return ToolResult(
                success=True,
                data={"notes": response.data.get("notes", []), "source": "mcp"},
            )
        
        # Fallback to in-memory storage
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
            data={"notes": results, "total": len(results), "source": "local"},
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

    async def execute(self, **kwargs: Any) -> ToolResult:
        note_id = kwargs.get("note_id")
        
        if not note_id:
            return ToolResult(success=False, error="note_id is required")
        
        # Try MCP server first
        mcp = get_mcp_client()
        response = await mcp.call_dashboard("note.get", {"note_id": note_id})
        
        if response.success and response.data:
            return ToolResult(
                success=True,
                data={"note": response.data, "source": "mcp"},
            )
        
        # Fallback to in-memory storage
        note = _notes.get(note_id)
        
        if not note:
            return ToolResult(
                success=False,
                error=f"Note not found: {note_id}",
            )
        
        return ToolResult(
            success=True,
            data={"note": note, "source": "local"},
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

    async def execute(self, **kwargs: Any) -> ToolResult:
        note_id = kwargs.get("note_id")
        updates = kwargs.get("updates", {})
        
        if not note_id:
            return ToolResult(success=False, error="note_id is required")
        
        # Try MCP server first
        mcp = get_mcp_client()
        response = await mcp.call_dashboard("note.update", {
            "note_id": note_id,
            "updates": updates,
        })
        
        if response.success and response.data:
            return ToolResult(
                success=True,
                data={"note_id": note_id, "updated": True, "source": "mcp"},
                changes=[
                    Change(
                        entity_type="note",
                        entity_id=note_id,
                        action="updated",
                        after=response.data,
                    )
                ],
            )
        
        # Fallback to in-memory storage
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
                "source": "local",
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

    async def execute(self, **kwargs: Any) -> ToolResult:
        note_id = kwargs.get("note_id")
        
        if not note_id:
            return ToolResult(success=False, error="note_id is required")
        
        # Try MCP server first
        mcp = get_mcp_client()
        
        # Get note first for undo info
        get_response = await mcp.call_dashboard("note.get", {"note_id": note_id})
        note_data = get_response.data if get_response.success else None
        
        response = await mcp.call_dashboard("note.delete", {"note_id": note_id})
        
        if response.success:
            undo_step = None
            if note_data:
                undo_step = UndoStep(
                    tool_name="NOTE_CREATE",
                    args={
                        "title": note_data.get("title", ""),
                        "content": note_data.get("content", ""),
                        "tags": note_data.get("tags", []),
                    },
                    description=f"Restore deleted note",
                )
            
            return ToolResult(
                success=True,
                data={"note_id": note_id, "deleted": True, "source": "mcp"},
                changes=[
                    Change(
                        entity_type="note",
                        entity_id=note_id,
                        action="deleted",
                        before=note_data,
                    )
                ],
                undo_step=undo_step,
            )
        
        # Fallback to in-memory storage
        note = _notes.pop(note_id, None)
        
        if not note:
            return ToolResult(
                success=False,
                error=f"Note not found: {note_id}",
            )
        
        return ToolResult(
            success=True,
            data={"note_id": note_id, "deleted": True, "source": "local"},
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
