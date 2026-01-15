"""
ATLAS API - Main FastAPI application.

Entry point for the ATLAS backend server.
"""

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
from atlas.providers import ProviderRegistry
from atlas.providers.ollama import OllamaAdapter
from atlas.providers.openai import OpenAIAdapter
from atlas.storage import ReceiptsStore, get_database, close_database


# Global instances
provider_registry = ProviderRegistry()
fallback_manager = FallbackManager()
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

    # Create executor
    executor = Executor(provider_registry, fallback_manager)

    # Initial health check
    await provider_registry.check_all_health()

    yield

    # Cleanup
    await provider_registry.close_all()
    await close_database()


app = FastAPI(
    title="ATLAS API",
    description="Provider-Agnostic Productivity OS",
    version=__version__,
    lifespan=lifespan,
)

# CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
