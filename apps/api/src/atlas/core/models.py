"""Core domain models and contracts for ATLAS.

These models define the strict contracts that make ATLAS reliable:
- Intent envelope v2.1
- Receipts with undo support
- Tool calls with confirmation gates
"""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


# =============================================================================
# Enums (locked per spec)
# =============================================================================


class IntentType(str, Enum):
    """Allowed intent types. Hard fail on unknown."""

    CAPTURE_TASKS = "CAPTURE_TASKS"
    PLAN_DAY = "PLAN_DAY"
    PROCESS_MEETING_NOTES = "PROCESS_MEETING_NOTES"
    SEARCH_SUMMARIZE = "SEARCH_SUMMARIZE"
    BUILD_WORKFLOW = "BUILD_WORKFLOW"
    UNKNOWN = "UNKNOWN"


class RiskLevel(str, Enum):
    """Risk levels for confirmation policy."""

    LOW = "LOW"  # Auto-allowed
    MEDIUM = "MEDIUM"  # Confirm (calendar writes, bulk edits)
    HIGH = "HIGH"  # Always confirm (workflow enabling, destructive)


class JobClass(str, Enum):
    """Job classification for routing."""

    INTENT_ROUTING = "INTENT_ROUTING"
    PLANNING = "PLANNING"
    EXTRACTION = "EXTRACTION"
    SUMMARIZATION = "SUMMARIZATION"
    WORKFLOW_BUILDING = "WORKFLOW_BUILDING"


class RoutingProfile(str, Enum):
    """Provider routing profiles."""

    OFFLINE = "OFFLINE"  # Local only
    BALANCED = "BALANCED"  # Local-first, cloud fallback
    ACCURACY = "ACCURACY"  # Cloud-first for best results


class FallbackTrigger(str, Enum):
    """Triggers that cause fallback to next model."""

    INVALID_JSON = "INVALID_JSON"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    TIMEOUT = "TIMEOUT"
    RATE_LIMIT = "RATE_LIMIT"
    PROVIDER_DOWN = "PROVIDER_DOWN"
    CAPABILITY_MISMATCH = "CAPABILITY_MISMATCH"


class ToolCallStatus(str, Enum):
    """Status of a tool call."""

    PENDING_CONFIRM = "PENDING_CONFIRM"
    OK = "OK"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class ReceiptStatus(str, Enum):
    """Overall receipt status."""

    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    PENDING_CONFIRM = "PENDING_CONFIRM"


# =============================================================================
# Intent Models
# =============================================================================


class Intent(BaseModel):
    """Parsed intent from user input."""

    type: IntentType
    confidence: float = Field(ge=0.0, le=1.0)
    parameters: dict[str, Any] = Field(default_factory=dict)
    raw_entities: list[str] = Field(default_factory=list)

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        """Ensure confidence is in valid range."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        return v


class IntentEnvelope(BaseModel):
    """Intent envelope v2.1 - the contract between UI and core."""

    version: str = "2.1"
    intent: Intent
    user_input: str
    timestamp_utc: datetime = Field(default_factory=datetime.utcnow)
    profile_id: str | None = None
    routing_profile: RoutingProfile = RoutingProfile.BALANCED

    @field_validator("version")
    @classmethod
    def validate_version(cls, v: str) -> str:
        """Ensure we're on the correct envelope version."""
        if v != "2.1":
            raise ValueError(f"Unsupported envelope version: {v}")
        return v


# =============================================================================
# Tool Call Models
# =============================================================================


class ToolCall(BaseModel):
    """Record of a tool invocation."""

    tool_name: str
    args: dict[str, Any] = Field(default_factory=dict)
    status: ToolCallStatus = ToolCallStatus.PENDING_CONFIRM
    result: Any | None = None
    error: str | None = None
    timestamp_utc: datetime = Field(default_factory=datetime.utcnow)


class Change(BaseModel):
    """Record of a state change made by a tool."""

    entity_type: str  # e.g., "task", "calendar_block", "workflow"
    entity_id: str
    action: str  # e.g., "created", "updated", "deleted"
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None


class UndoStep(BaseModel):
    """Instructions to reverse a change."""

    tool_name: str
    args: dict[str, Any]
    description: str


# =============================================================================
# Model Attempt Tracking
# =============================================================================


class ModelAttempt(BaseModel):
    """Record of a model invocation attempt."""

    provider: str  # e.g., "ollama", "openai"
    model: str  # e.g., "llama3.2", "gpt-4o"
    attempt_number: int = 1
    success: bool = False
    fallback_trigger: FallbackTrigger | None = None
    latency_ms: int | None = None
    timestamp_utc: datetime = Field(default_factory=datetime.utcnow)


# =============================================================================
# Receipt Model
# =============================================================================


class Receipt(BaseModel):
    """
    Complete audit record of a request execution.

    Receipts are the trust layer - they prove what happened,
    enable undo, and make ATLAS auditable.
    """

    receipt_id: UUID = Field(default_factory=uuid4)
    timestamp_utc: datetime = Field(default_factory=datetime.utcnow)
    profile_id: str | None = None
    status: ReceiptStatus = ReceiptStatus.PENDING_CONFIRM

    # What user asked
    user_input: str

    # What models were tried
    models_attempted: list[ModelAttempt] = Field(default_factory=list)

    # What intent was finalized
    intent_final: Intent | None = None

    # What tools ran
    tool_calls: list[ToolCall] = Field(default_factory=list)

    # What changed
    changes: list[Change] = Field(default_factory=list)

    # How to undo
    undo: list[UndoStep] = Field(default_factory=list)

    # Issues
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)

    def has_pending_confirmations(self) -> bool:
        """Check if any tool calls need confirmation."""
        return any(tc.status == ToolCallStatus.PENDING_CONFIRM for tc in self.tool_calls)

    def get_pending_tool_calls(self) -> list[ToolCall]:
        """Get tool calls that need confirmation."""
        return [tc for tc in self.tool_calls if tc.status == ToolCallStatus.PENDING_CONFIRM]
