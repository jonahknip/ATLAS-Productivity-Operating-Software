"""
ATLAS API - Main FastAPI application.

Entry point for the ATLAS backend server.
"""

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from atlas import __version__
from atlas.config import get_settings
from atlas.core.fallback import FallbackManager
from atlas.core.models import Receipt, ReceiptStatus, RoutingProfile
from atlas.engine import Executor
from atlas.middleware import APITokenMiddleware
from atlas.providers import ProviderRegistry
from atlas.providers.ollama import OllamaAdapter
from atlas.providers.openai import OpenAIAdapter
from atlas.providers.anthropic import AnthropicAdapter
from atlas.providers.groq import GroqAdapter
from atlas.storage import ReceiptsStore, get_database, close_database
from atlas.mcp import close_mcp_client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# Skills & Tools
from atlas.skills.registry import SkillRegistry
from atlas.skills.capture_tasks import CaptureTasksSkill
from atlas.skills.search_summarize import SearchSummarizeSkill
from atlas.skills.plan_day import PlanDaySkill
from atlas.skills.meeting_notes import ProcessMeetingNotesSkill
from atlas.skills.build_workflow import BuildWorkflowSkill

from atlas.tools.registry import ToolRegistry
from atlas.tools.tasks import (
    TaskCreateTool,
    TaskListTool,
    TaskGetTool,
    TaskUpdateTool,
    TaskDeleteTool,
)
from atlas.tools.notes import (
    NoteCreateTool,
    NoteSearchTool,
    NoteGetTool,
    NoteUpdateTool,
    NoteDeleteTool,
)
from atlas.tools.calendar import (
    CalendarGetDayTool,
    CalendarCreateBlocksTool,
    CalendarDeleteBlocksTool,
    CalendarUpdateBlockTool,
)
from atlas.skills.build_workflow import (
    WorkflowSaveTool,
    WorkflowEnableTool,
    WorkflowListTool,
    WorkflowDeleteTool,
)


# Global instances
provider_registry = ProviderRegistry()
fallback_manager = FallbackManager()
skill_registry = SkillRegistry()
tool_registry = ToolRegistry()
receipts_store: ReceiptsStore | None = None
executor: Executor | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - setup and teardown."""
    global receipts_store, executor
    
    settings = get_settings()

    # Initialize database
    database = await get_database()
    receipts_store = ReceiptsStore(database)

    # Register providers
    provider_registry.register(OllamaAdapter(base_url=settings.ollama_base_url))

    if settings.openai_api_key:
        provider_registry.register(OpenAIAdapter(api_key=settings.openai_api_key))
    
    if settings.anthropic_api_key:
        provider_registry.register(AnthropicAdapter(api_key=settings.anthropic_api_key))
    
    if settings.groq_api_key:
        provider_registry.register(GroqAdapter(api_key=settings.groq_api_key))

    # Register tools
    tool_registry.register(TaskCreateTool())
    tool_registry.register(TaskListTool())
    tool_registry.register(TaskGetTool())
    tool_registry.register(TaskUpdateTool())
    tool_registry.register(TaskDeleteTool())
    tool_registry.register(NoteCreateTool())
    tool_registry.register(NoteSearchTool())
    tool_registry.register(NoteGetTool())
    tool_registry.register(NoteUpdateTool())
    tool_registry.register(NoteDeleteTool())
    tool_registry.register(CalendarGetDayTool())
    tool_registry.register(CalendarCreateBlocksTool())
    tool_registry.register(CalendarDeleteBlocksTool())
    tool_registry.register(CalendarUpdateBlockTool())
    tool_registry.register(WorkflowSaveTool())
    tool_registry.register(WorkflowEnableTool())
    tool_registry.register(WorkflowListTool())
    tool_registry.register(WorkflowDeleteTool())

    # Register skills
    skill_registry.register(CaptureTasksSkill())
    skill_registry.register(SearchSummarizeSkill())
    skill_registry.register(PlanDaySkill())
    skill_registry.register(ProcessMeetingNotesSkill())
    skill_registry.register(BuildWorkflowSkill())

    # Create executor with skills and tools
    executor = Executor(
        provider_registry,
        fallback_manager,
        skill_registry,
        tool_registry,
    )

    # Initial health check
    await provider_registry.check_all_health()

    yield

    # Cleanup
    await provider_registry.close_all()
    await close_mcp_client()
    await close_database()


app = FastAPI(
    title="ATLAS API",
    description="Provider-Agnostic Productivity OS",
    version=__version__,
    lifespan=lifespan,
)

# Get settings for middleware configuration
_settings = get_settings()

# CORS middleware - configured from environment
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Token authentication middleware for /v1/* routes
app.add_middleware(APITokenMiddleware)


# =============================================================================
# Request/Response Models
# =============================================================================


class ExecuteRequest(BaseModel):
    """Request body for /v1/execute."""
    text: str
    routing_profile: str = "BALANCED"
    profile_id: str | None = None


class ReceiptResponse(BaseModel):
    """Response model for receipt endpoints."""
    receipt_id: str
    timestamp_utc: str
    profile_id: str | None
    status: str
    user_input: str
    models_attempted: list[dict[str, Any]]
    intent_final: dict[str, Any] | None
    tool_calls: list[dict[str, Any]]
    changes: list[dict[str, Any]]
    undo: list[dict[str, Any]]
    warnings: list[str]
    errors: list[str]

    @classmethod
    def from_receipt(cls, receipt: Receipt) -> "ReceiptResponse":
        """Convert a Receipt model to response format."""
        return cls(
            receipt_id=str(receipt.receipt_id),
            timestamp_utc=receipt.timestamp_utc.isoformat(),
            profile_id=receipt.profile_id,
            status=receipt.status.value,
            user_input=receipt.user_input,
            models_attempted=[
                {
                    "provider": m.provider,
                    "model": m.model,
                    "attempt_number": m.attempt_number,
                    "success": m.success,
                    "fallback_trigger": m.fallback_trigger.value if m.fallback_trigger else None,
                    "latency_ms": m.latency_ms,
                    "timestamp_utc": m.timestamp_utc.isoformat(),
                }
                for m in receipt.models_attempted
            ],
            intent_final=(
                {
                    "type": receipt.intent_final.type.value,
                    "confidence": receipt.intent_final.confidence,
                    "parameters": receipt.intent_final.parameters,
                    "raw_entities": receipt.intent_final.raw_entities,
                }
                if receipt.intent_final
                else None
            ),
            tool_calls=[
                {
                    "tool_name": tc.tool_name,
                    "args": tc.args,
                    "status": tc.status.value,
                    "result": tc.result,
                    "error": tc.error,
                    "timestamp_utc": tc.timestamp_utc.isoformat(),
                }
                for tc in receipt.tool_calls
            ],
            changes=[
                {
                    "entity_type": c.entity_type,
                    "entity_id": c.entity_id,
                    "action": c.action,
                    "before": c.before,
                    "after": c.after,
                }
                for c in receipt.changes
            ],
            undo=[
                {
                    "tool_name": u.tool_name,
                    "args": u.args,
                    "description": u.description,
                }
                for u in receipt.undo
            ],
            warnings=receipt.warnings,
            errors=receipt.errors,
        )


class ReceiptsListResponse(BaseModel):
    """Response for listing receipts."""
    receipts: list[ReceiptResponse]
    total: int
    limit: int
    offset: int


class UndoResponse(BaseModel):
    """Response for undo operation."""
    success: bool
    receipt_id: str
    message: str
    undo_steps_executed: int


# =============================================================================
# Health & Status Endpoints
# =============================================================================


@app.get("/health")
async def health() -> dict[str, str]:
    """Basic health check."""
    return {"status": "healthy", "version": __version__}


@app.get("/version")
async def version() -> dict[str, Any]:
    """Version and build information."""
    settings = get_settings()
    return {
        "version": __version__,
        "app_name": settings.app_name,
        "database": "postgres" if settings.is_postgres else "sqlite",
    }


@app.get("/api/status")
async def status() -> dict[str, Any]:
    """Detailed system status including providers."""
    settings = get_settings()
    
    # Get receipt count
    receipt_count = 0
    if receipts_store:
        receipt_count = await receipts_store.count()

    return {
        "version": __version__,
        "providers": provider_registry.get_status_summary(),
        "receipts_count": receipt_count,
        "config": {
            "routing_caps": {
                "max_attempts_per_model": settings.max_attempts_per_model,
                "max_models_per_request": settings.max_models_per_request,
            },
        },
    }


# =============================================================================
# Provider Endpoints
# =============================================================================


@app.post("/api/providers/{name}/health")
async def check_provider_health(name: str) -> dict[str, Any]:
    """Trigger health check for a specific provider."""
    health_result = await provider_registry.check_health(name)
    return {
        "provider": name,
        "status": health_result.status.value,
        "latency_ms": health_result.latency_ms,
        "models_available": health_result.models_available,
        "error": health_result.error,
    }


@app.get("/api/providers")
async def list_providers() -> dict[str, Any]:
    """List all registered providers and their status."""
    return {
        "providers": provider_registry.get_status_summary(),
    }


@app.get("/api/providers/{name}/models")
async def list_provider_models(name: str) -> dict[str, Any]:
    """List available models from a provider."""
    models = await provider_registry.list_models(name)
    return {
        "provider": name,
        "models": models,
    }


class ProviderConfigRequest(BaseModel):
    """Request body for provider configuration."""
    api_key: str | None = None
    base_url: str | None = None


@app.post("/api/providers/{name}/configure")
async def configure_provider(name: str, config: ProviderConfigRequest) -> dict[str, Any]:
    """
    Configure a provider with API key or URL.
    
    This allows dynamic provider configuration from the UI.
    """
    try:
        # Check if provider already registered
        existing = provider_registry.get(name)
        if existing:
            await existing.close()
            provider_registry.unregister(name)
        
        # Create new provider based on name
        if name == "ollama":
            base_url = config.base_url or "http://localhost:11434"
            adapter = OllamaAdapter(base_url=base_url)
        elif name == "openai" and config.api_key:
            adapter = OpenAIAdapter(api_key=config.api_key)
        elif name == "anthropic" and config.api_key:
            adapter = AnthropicAdapter(api_key=config.api_key)
        elif name == "groq" and config.api_key:
            adapter = GroqAdapter(api_key=config.api_key)
        else:
            return {"success": False, "error": f"Unknown provider or missing API key: {name}"}
        
        # Register the new provider
        provider_registry.register(adapter)
        
        # Test the connection
        health = await adapter.health_check()
        
        return {
            "success": health.status.value == "HEALTHY",
            "provider": name,
            "status": health.status.value,
            "error": health.error,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# =============================================================================
# Tasks API Endpoints
# =============================================================================


class TaskCreateRequest(BaseModel):
    """Request to create a task."""
    title: str
    description: str = ""
    due_date: str | None = None
    priority: str = "medium"
    tags: list[str] = []


class TaskUpdateRequest(BaseModel):
    """Request to update a task."""
    title: str | None = None
    description: str | None = None
    due_date: str | None = None
    priority: str | None = None
    status: str | None = None
    tags: list[str] | None = None


@app.get("/api/tasks")
async def list_tasks() -> dict[str, Any]:
    """List all tasks."""
    task_list_tool = tool_registry.get("TASK_LIST")
    if not task_list_tool:
        return {"tasks": []}
    
    result = await task_list_tool.execute()
    return {"tasks": result.data.get("tasks", [])}


@app.post("/api/tasks")
async def create_task(request: TaskCreateRequest) -> dict[str, Any]:
    """Create a new task."""
    task_create_tool = tool_registry.get("TASK_CREATE")
    if not task_create_tool:
        raise HTTPException(status_code=503, detail="Task tools not available")
    
    result = await task_create_tool.execute(
        title=request.title,
        description=request.description,
        due_date=request.due_date,
        priority=request.priority,
        tags=request.tags,
    )
    
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)
    
    return result.data


@app.get("/api/tasks/{task_id}")
async def get_task(task_id: str) -> dict[str, Any]:
    """Get a task by ID."""
    task_get_tool = tool_registry.get("TASK_GET")
    if not task_get_tool:
        raise HTTPException(status_code=503, detail="Task tools not available")
    
    result = await task_get_tool.execute(task_id=task_id)
    
    if not result.success:
        raise HTTPException(status_code=404, detail=result.error)
    
    return result.data.get("task", {})


@app.patch("/api/tasks/{task_id}")
async def update_task(task_id: str, request: TaskUpdateRequest) -> dict[str, Any]:
    """Update a task."""
    task_update_tool = tool_registry.get("TASK_UPDATE")
    if not task_update_tool:
        raise HTTPException(status_code=503, detail="Task tools not available")
    
    updates = {}
    if request.title is not None:
        updates["title"] = request.title
    if request.description is not None:
        updates["description"] = request.description
    if request.due_date is not None:
        updates["due_date"] = request.due_date
    if request.priority is not None:
        updates["priority"] = request.priority
    if request.status is not None:
        updates["status"] = request.status
    if request.tags is not None:
        updates["tags"] = request.tags
    
    result = await task_update_tool.execute(task_id=task_id, updates=updates)
    
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)
    
    return result.data


@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: str) -> dict[str, Any]:
    """Delete a task."""
    task_delete_tool = tool_registry.get("TASK_DELETE")
    if not task_delete_tool:
        raise HTTPException(status_code=503, detail="Task tools not available")
    
    result = await task_delete_tool.execute(task_id=task_id)
    
    if not result.success:
        raise HTTPException(status_code=404, detail=result.error)
    
    return {"deleted": True, "task_id": task_id}


# =============================================================================
# Skills & Tools Endpoints
# =============================================================================


@app.get("/api/skills")
async def list_skills() -> dict[str, Any]:
    """List all registered skills and their capabilities."""
    return {
        "skills": skill_registry.get_skill_info(),
        "total": len(skill_registry.list_skills()),
    }


@app.get("/api/tools")
async def list_tools() -> dict[str, Any]:
    """List all registered tools and their capabilities."""
    return {
        "tools": tool_registry.get_tool_info(),
        "total": len(tool_registry.list_tools()),
    }


# =============================================================================
# Execute Endpoint (v1)
# =============================================================================


@app.post("/v1/execute", response_model=ReceiptResponse)
async def execute_v1(request: ExecuteRequest) -> ReceiptResponse:
    """
    Execute a user request through the ATLAS pipeline.
    
    This is the main entry point for all user interactions.
    Pipeline: Router → Normalizer → Validator → Skill → Tools → Receipt
    
    ALWAYS returns a receipt, even on failure.
    """
    if not executor or not receipts_store:
        raise HTTPException(status_code=503, detail="Service not initialized")

    # Parse routing profile
    try:
        profile = RoutingProfile(request.routing_profile.upper())
    except ValueError:
        profile = RoutingProfile.BALANCED

    # Execute and get receipt
    receipt = await executor.execute(
        user_input=request.text,
        routing_profile=profile,
        profile_id=request.profile_id,
    )

    # ALWAYS persist the receipt
    await receipts_store.create(receipt)

    return ReceiptResponse.from_receipt(receipt)


# Legacy endpoint for backwards compatibility
@app.post("/api/execute", response_model=ReceiptResponse)
async def execute_legacy(request: ExecuteRequest) -> ReceiptResponse:
    """Legacy execute endpoint - redirects to v1."""
    return await execute_v1(request)


# =============================================================================
# Receipts Endpoints (v1)
# =============================================================================


@app.get("/v1/receipts", response_model=ReceiptsListResponse)
async def list_receipts_v1(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    status: str | None = Query(default=None),
) -> ReceiptsListResponse:
    """
    List execution receipts with pagination.
    
    Args:
        limit: Maximum number of receipts (1-200, default 50)
        offset: Number of receipts to skip
        status: Optional filter by status (SUCCESS, FAILED, PARTIAL, PENDING_CONFIRM)
    """
    if not receipts_store:
        raise HTTPException(status_code=503, detail="Service not initialized")

    # Parse status filter if provided
    status_filter = None
    if status:
        try:
            status_filter = ReceiptStatus(status.upper())
        except ValueError:
            pass  # Ignore invalid status

    receipts = await receipts_store.list(
        limit=limit,
        offset=offset,
        status=status_filter,
    )
    total = await receipts_store.count(status=status_filter)

    return ReceiptsListResponse(
        receipts=[ReceiptResponse.from_receipt(r) for r in receipts],
        total=total,
        limit=limit,
        offset=offset,
    )


@app.get("/v1/receipts/{receipt_id}", response_model=ReceiptResponse)
async def get_receipt_v1(receipt_id: str) -> ReceiptResponse:
    """Get a specific receipt by ID."""
    if not receipts_store:
        raise HTTPException(status_code=503, detail="Service not initialized")

    receipt = await receipts_store.get(receipt_id)
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")

    return ReceiptResponse.from_receipt(receipt)


@app.post("/v1/receipts/{receipt_id}/undo", response_model=UndoResponse)
async def undo_receipt_v1(receipt_id: str) -> UndoResponse:
    """
    Undo the changes from a receipt.
    
    Currently a stub - will execute undo steps in future weeks.
    """
    if not receipts_store:
        raise HTTPException(status_code=503, detail="Service not initialized")

    receipt = await receipts_store.get(receipt_id)
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")

    if not receipt.undo:
        return UndoResponse(
            success=False,
            receipt_id=receipt_id,
            message="No undo steps available for this receipt",
            undo_steps_executed=0,
        )

    # TODO: Actually execute undo steps in Week 7+
    # For now, just acknowledge the undo steps exist
    return UndoResponse(
        success=True,
        receipt_id=receipt_id,
        message=f"Undo requested for {len(receipt.undo)} steps (stub - not yet implemented)",
        undo_steps_executed=0,
    )


# Legacy endpoints for backwards compatibility
@app.get("/api/receipts")
async def list_receipts_legacy(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ReceiptsListResponse:
    """Legacy receipts list endpoint."""
    return await list_receipts_v1(limit=limit, offset=offset)


@app.get("/api/receipts/{receipt_id}")
async def get_receipt_legacy(receipt_id: str) -> ReceiptResponse:
    """Legacy get receipt endpoint."""
    return await get_receipt_v1(receipt_id)


@app.post("/api/receipts/{receipt_id}/undo")
async def undo_receipt_legacy(receipt_id: str) -> UndoResponse:
    """Legacy undo receipt endpoint."""
    return await undo_receipt_v1(receipt_id)
