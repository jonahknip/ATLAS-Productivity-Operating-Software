"""
Task Tools - CRUD operations for tasks.

All task tools are LOW risk and provide undo capabilities.
Uses MCP Dashboard server when available, falls back to in-memory storage.
"""

from datetime import datetime
from typing import Any
from uuid import uuid4

from atlas.core.models import Change, RiskLevel, UndoStep
from atlas.tools.base import Tool, ToolResult
from atlas.mcp import get_mcp_client


# In-memory task storage (fallback when MCP not available)
_tasks: dict[str, dict[str, Any]] = {}


class TaskCreateTool(Tool):
    """Create a new task."""

    @property
    def name(self) -> str:
        return "TASK_CREATE"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.LOW

    @property
    def description(self) -> str:
        return "Create a new task with title, description, due date, and priority"

    async def execute(self, **kwargs: Any) -> ToolResult:
        title = kwargs.get("title", "Untitled Task")
        description = kwargs.get("description", "")
        due_date = kwargs.get("due_date")
        priority = kwargs.get("priority", "medium")
        tags = kwargs.get("tags", [])
        
        # Try MCP server first
        mcp = get_mcp_client()
        response = await mcp.call_dashboard("task.create", {
            "title": title,
            "description": description,
            "due_date": due_date,
            "priority": priority,
            "tags": tags,
        })
        
        if response.success and response.data:
            task_id = str(response.data.get("task_id") or response.data.get("id") or "unknown")
            return ToolResult(
                success=True,
                data={"task_id": task_id, "source": "mcp"},
                changes=[
                    Change(
                        entity_type="task",
                        entity_id=task_id,
                        action="created",
                        after=response.data,
                    )
                ],
                undo_step=UndoStep(
                    tool_name="TASK_DELETE",
                    args={"task_id": task_id},
                    description=f"Delete task: {title}",
                ),
            )
        
        # Fallback to in-memory storage
        task_id = f"task_{uuid4().hex[:12]}"
        now = datetime.utcnow().isoformat()
        
        task = {
            "task_id": task_id,
            "title": title,
            "description": description,
            "due_date": due_date,
            "priority": priority,
            "tags": tags or [],
            "status": "pending",
            "created_at": now,
            "updated_at": now,
        }
        
        _tasks[task_id] = task
        
        return ToolResult(
            success=True,
            data={"task_id": task_id, "created_at": now, "source": "local"},
            changes=[
                Change(
                    entity_type="task",
                    entity_id=task_id,
                    action="created",
                    after=task,
                )
            ],
            undo_step=UndoStep(
                tool_name="TASK_DELETE",
                args={"task_id": task_id},
                description=f"Delete task: {title}",
            ),
        )


class TaskListTool(Tool):
    """List tasks with optional filters."""

    @property
    def name(self) -> str:
        return "TASK_LIST"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.LOW

    @property
    def description(self) -> str:
        return "List tasks with optional status, date, and tag filters"

    async def execute(self, **kwargs: Any) -> ToolResult:
        status = kwargs.get("status")
        due_before = kwargs.get("due_before")
        tags = kwargs.get("tags")
        limit = kwargs.get("limit", 50)
        
        # Try MCP server first
        mcp = get_mcp_client()
        response = await mcp.call_dashboard("task.list", {
            "status": status,
            "due_before": due_before,
            "tags": tags,
            "limit": limit,
        })
        
        if response.success and response.data:
            return ToolResult(
                success=True,
                data={"tasks": response.data.get("tasks", []), "source": "mcp"},
            )
        
        # Fallback to in-memory storage
        tasks = list(_tasks.values())
        
        # Apply filters
        if status:
            tasks = [t for t in tasks if t["status"] == status]
        
        if due_before:
            tasks = [t for t in tasks if t.get("due_date") and t["due_date"] <= due_before]
        
        if tags:
            tasks = [t for t in tasks if any(tag in t.get("tags", []) for tag in tags)]
        
        # Sort by created_at descending
        tasks.sort(key=lambda t: t["created_at"], reverse=True)
        
        # Apply limit
        tasks = tasks[:limit]
        
        return ToolResult(
            success=True,
            data={"tasks": tasks, "total": len(tasks), "source": "local"},
        )


class TaskGetTool(Tool):
    """Get a task by ID."""

    @property
    def name(self) -> str:
        return "TASK_GET"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.LOW

    @property
    def description(self) -> str:
        return "Get a specific task by its ID"

    async def execute(self, **kwargs: Any) -> ToolResult:
        task_id = kwargs.get("task_id")
        
        if not task_id:
            return ToolResult(success=False, error="task_id is required")
        
        # Try MCP server first
        mcp = get_mcp_client()
        response = await mcp.call_dashboard("task.get", {"task_id": task_id})
        
        if response.success and response.data:
            return ToolResult(
                success=True,
                data={"task": response.data, "source": "mcp"},
            )
        
        # Fallback to in-memory storage
        task = _tasks.get(task_id)
        
        if not task:
            return ToolResult(
                success=False,
                error=f"Task not found: {task_id}",
            )
        
        return ToolResult(
            success=True,
            data={"task": task, "source": "local"},
        )


class TaskUpdateTool(Tool):
    """Update an existing task."""

    @property
    def name(self) -> str:
        return "TASK_UPDATE"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.LOW

    @property
    def description(self) -> str:
        return "Update a task's properties (status, title, etc.)"

    async def execute(self, **kwargs: Any) -> ToolResult:
        task_id = kwargs.get("task_id")
        updates = kwargs.get("updates", {})
        
        if not task_id:
            return ToolResult(success=False, error="task_id is required")
        
        # Try MCP server first
        mcp = get_mcp_client()
        response = await mcp.call_dashboard("task.update", {
            "task_id": task_id,
            "updates": updates,
        })
        
        if response.success and response.data:
            return ToolResult(
                success=True,
                data={"task_id": task_id, "updated": True, "source": "mcp"},
                changes=[
                    Change(
                        entity_type="task",
                        entity_id=task_id,
                        action="updated",
                        after=response.data,
                    )
                ],
            )
        
        # Fallback to in-memory storage
        task = _tasks.get(task_id)
        
        if not task:
            return ToolResult(
                success=False,
                error=f"Task not found: {task_id}",
            )
        
        # Store previous state for undo
        before = task.copy()
        
        # Apply updates
        allowed_fields = {"title", "description", "due_date", "priority", "tags", "status"}
        for key, value in updates.items():
            if key in allowed_fields:
                task[key] = value
        
        task["updated_at"] = datetime.utcnow().isoformat()
        
        return ToolResult(
            success=True,
            data={
                "task_id": task_id,
                "before": {k: before.get(k) for k in updates.keys()},
                "after": {k: task.get(k) for k in updates.keys()},
                "source": "local",
            },
            changes=[
                Change(
                    entity_type="task",
                    entity_id=task_id,
                    action="updated",
                    before=before,
                    after=task.copy(),
                )
            ],
            undo_step=UndoStep(
                tool_name="TASK_UPDATE",
                args={
                    "task_id": task_id,
                    "updates": {k: before.get(k) for k in updates.keys()},
                },
                description=f"Restore task to previous state",
            ),
        )


class TaskDeleteTool(Tool):
    """Delete a task."""

    @property
    def name(self) -> str:
        return "TASK_DELETE"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.LOW

    @property
    def description(self) -> str:
        return "Delete a task by its ID"

    async def execute(self, **kwargs: Any) -> ToolResult:
        task_id = kwargs.get("task_id")
        
        if not task_id:
            return ToolResult(success=False, error="task_id is required")
        
        # Try MCP server first
        mcp = get_mcp_client()
        
        # Get task first for undo info
        get_response = await mcp.call_dashboard("task.get", {"task_id": task_id})
        task_data = get_response.data if get_response.success else None
        
        response = await mcp.call_dashboard("task.delete", {"task_id": task_id})
        
        if response.success:
            undo_step = None
            if task_data:
                undo_step = UndoStep(
                    tool_name="TASK_CREATE",
                    args={
                        "title": task_data.get("title", ""),
                        "description": task_data.get("description", ""),
                        "due_date": task_data.get("due_date"),
                        "priority": task_data.get("priority", "medium"),
                        "tags": task_data.get("tags", []),
                    },
                    description=f"Restore deleted task",
                )
            
            return ToolResult(
                success=True,
                data={"task_id": task_id, "deleted": True, "source": "mcp"},
                changes=[
                    Change(
                        entity_type="task",
                        entity_id=task_id,
                        action="deleted",
                        before=task_data,
                    )
                ],
                undo_step=undo_step,
            )
        
        # Fallback to in-memory storage
        task = _tasks.pop(task_id, None)
        
        if not task:
            return ToolResult(
                success=False,
                error=f"Task not found: {task_id}",
            )
        
        return ToolResult(
            success=True,
            data={"task_id": task_id, "deleted": True, "source": "local"},
            changes=[
                Change(
                    entity_type="task",
                    entity_id=task_id,
                    action="deleted",
                    before=task,
                )
            ],
            undo_step=UndoStep(
                tool_name="TASK_CREATE",
                args={
                    "title": task["title"],
                    "description": task.get("description", ""),
                    "due_date": task.get("due_date"),
                    "priority": task.get("priority", "medium"),
                    "tags": task.get("tags", []),
                },
                description=f"Restore deleted task: {task['title']}",
            ),
        )


def get_all_tasks() -> dict[str, dict[str, Any]]:
    """Get all tasks (for testing/debugging)."""
    return _tasks.copy()


def clear_all_tasks() -> None:
    """Clear all tasks (for testing)."""
    _tasks.clear()
