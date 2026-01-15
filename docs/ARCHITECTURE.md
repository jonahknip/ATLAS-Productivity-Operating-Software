# ATLAS Architecture

> System architecture and data flow documentation.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                           UI Layer                               │
│  ┌─────────┐  ┌──────────┐  ┌───────────┐  ┌─────────────────┐  │
│  │Dashboard│  │ Receipts │  │ Providers │  │ Packs/Settings  │  │
│  └────┬────┘  └────┬─────┘  └─────┬─────┘  └───────┬─────────┘  │
└───────┼────────────┼──────────────┼────────────────┼────────────┘
        │            │              │                │
        └────────────┴──────────────┴────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         API Layer (FastAPI)                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │   /execute  │  │  /receipts  │  │  /providers  /packs     │  │
│  └──────┬──────┘  └──────┬──────┘  └───────────┬─────────────┘  │
└─────────┼────────────────┼─────────────────────┼────────────────┘
          │                │                     │
          ▼                ▼                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Core Engine                                 │
│                                                                  │
│  ┌────────────┐    ┌────────────┐    ┌────────────────────────┐ │
│  │   Router   │───▶│ Normalizer │───▶│      Validator         │ │
│  └────────────┘    └────────────┘    └───────────┬────────────┘ │
│                                                  │               │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                    Fallback Manager                         │ │
│  │   • 2 attempts/model  • max 3 models  • deterministic       │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                  │               │
│                                                  ▼               │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                    Skill Engine                             │ │
│  │   CAPTURE_TASKS │ PLAN_DAY │ MEETING │ SEARCH │ WORKFLOW   │ │
│  └───────────────────────────────┬────────────────────────────┘ │
│                                  │                               │
│                                  ▼                               │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                    Tools Layer                              │ │
│  │   Tasks │ Notes │ Calendar │ Workflows │ Notifications     │ │
│  └───────────────────────────────┬────────────────────────────┘ │
└──────────────────────────────────┼──────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Storage Layer                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │   SQLite    │  │  Receipts   │  │   Provider Registry     │  │
│  │  (entities) │  │   Store     │  │      (runtime)          │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Provider Layer                              │
│  ┌─────────────────────────┐  ┌─────────────────────────────┐   │
│  │      Ollama (Local)     │  │      OpenAI (Cloud)         │   │
│  │  llama3.2, mistral, phi │  │   gpt-4o, gpt-4o-mini       │   │
│  └─────────────────────────┘  └─────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

## Request Flow

### 1. User Input → Intent Classification

```
User: "Plan my day around these tasks: A, B, C"
                    │
                    ▼
┌─────────────────────────────────────┐
│           Intent Router             │
│  • Select model based on profile    │
│  • Job class: INTENT_ROUTING        │
└──────────────────┬──────────────────┘
                   │
                   ▼
┌─────────────────────────────────────┐
│           Model Call                │
│  Prompt: "Classify this input..."   │
│  Output: Raw JSON (maybe malformed) │
└──────────────────┬──────────────────┘
                   │
                   ▼
┌─────────────────────────────────────┐
│          JSON Normalizer            │
│  • Extract from markdown            │
│  • Repair common issues             │
│  • Return clean JSON or error       │
└──────────────────┬──────────────────┘
                   │
                   ▼
┌─────────────────────────────────────┐
│            Validator                │
│  • Schema validation                │
│  • Entity validation                │
│  • Risk level assignment            │
└──────────────────┬──────────────────┘
                   │
           ┌──────┴──────┐
           │             │
        Success       Failure
           │             │
           ▼             ▼
     Intent Envelope   Fallback Manager
                       (retry/next model)
```

### 2. Intent → Skill Execution

```
Intent: PLAN_DAY (MEDIUM risk)
                    │
                    ▼
┌─────────────────────────────────────┐
│         Skill: PLAN_DAY             │
│  1. CALENDAR_GET_DAY (read)         │
│  2. TASK_LIST (read)                │
│  3. Generate plan (model call)      │
│  4. CALENDAR_CREATE_BLOCKS (write)  │
└──────────────────┬──────────────────┘
                   │
                   ▼
┌─────────────────────────────────────┐
│      Confirmation Gate              │
│  Calendar writes need confirmation  │
│  Status: PENDING_CONFIRM            │
└──────────────────┬──────────────────┘
                   │
            User confirms
                   │
                   ▼
┌─────────────────────────────────────┐
│       Tool Execution                │
│  • Create calendar blocks           │
│  • Record changes                   │
│  • Generate undo steps              │
└──────────────────┬──────────────────┘
                   │
                   ▼
┌─────────────────────────────────────┐
│         Receipt Created             │
│  • All attempts logged              │
│  • Tool calls recorded              │
│  • Undo steps available             │
└─────────────────────────────────────┘
```

## Component Details

### Provider Registry

```python
class ProviderRegistry:
    """Central management of model providers."""
    
    providers: dict[str, ProviderAdapter]
    health_cache: dict[str, ProviderHealth]
    
    def register(provider: ProviderAdapter)
    def get(name: str) -> ProviderAdapter
    def check_health(name: str) -> ProviderHealth
    def get_capabilities(provider: str, model: str) -> Capabilities
```

### Fallback Manager

```python
class FallbackManager:
    """Deterministic retry and fallback logic."""
    
    max_attempts_per_model: int = 2  # locked
    max_models_per_request: int = 3  # locked
    
    def get_model_chain(profile, job_class) -> list[Model]
    def decide(trigger, attempts, profile) -> FallbackDecision
```

Fallback triggers:
- `INVALID_JSON` - Model output not valid JSON
- `VALIDATION_ERROR` - JSON doesn't match schema
- `TIMEOUT` - Model response too slow
- `RATE_LIMIT` - Provider rate limited
- `PROVIDER_DOWN` - Provider unavailable
- `CAPABILITY_MISMATCH` - Model can't do required task

### Skill Engine

```python
class Skill(ABC):
    """Base class for skills."""
    
    name: str
    risk_level: RiskLevel
    required_capabilities: list[str]
    
    @abstractmethod
    async def execute(intent: Intent, context: Context) -> SkillResult
```

Skills are deterministic programs, not prompts. They:
1. Receive a validated intent
2. Call tools in a defined sequence
3. Make model calls only for specific sub-tasks
4. Return structured results with undo information

### Tools Layer

```python
class Tool(ABC):
    """Base class for tools."""
    
    name: str
    risk_level: RiskLevel
    
    @abstractmethod
    async def execute(args: dict) -> ToolResult
    
    @abstractmethod
    def get_undo_args(result: ToolResult) -> dict | None
```

Tools are pure, deterministic functions. They:
- Take validated arguments
- Perform a single operation
- Return results with undo information
- Never make model calls

## Data Models

### Receipt Structure

```json
{
  "receipt_id": "uuid",
  "timestamp_utc": "2024-01-15T10:30:00Z",
  "profile_id": "user_123",
  "status": "SUCCESS",
  
  "user_input": "Plan my day...",
  
  "models_attempted": [
    {
      "provider": "ollama",
      "model": "llama3.2",
      "attempt_number": 1,
      "success": false,
      "fallback_trigger": "INVALID_JSON"
    },
    {
      "provider": "ollama",
      "model": "llama3.2",
      "attempt_number": 2,
      "success": true
    }
  ],
  
  "intent_final": {
    "type": "PLAN_DAY",
    "confidence": 0.92,
    "parameters": { "date": "2024-01-15" }
  },
  
  "tool_calls": [
    { "tool_name": "CALENDAR_GET_DAY", "status": "OK" },
    { "tool_name": "CALENDAR_CREATE_BLOCKS", "status": "OK" }
  ],
  
  "changes": [
    { "entity_type": "calendar_block", "entity_id": "block_001", "action": "created" }
  ],
  
  "undo": [
    { "tool_name": "CALENDAR_DELETE_BLOCKS", "args": { "block_ids": ["block_001"] } }
  ]
}
```

## Routing Profiles

### OFFLINE

```
Model chain: ollama:llama3.2 → ollama:mistral → ollama:phi3
Use case: Privacy, no internet, low latency
Trade-off: Lower accuracy
```

### BALANCED

```
Model chain: ollama:llama3.2 → openai:gpt-4o-mini → openai:gpt-4o
Use case: Default, good balance of speed and accuracy
Trade-off: May use cloud on fallback
```

### ACCURACY

```
Model chain: openai:gpt-4o → openai:gpt-4o-mini → ollama:llama3.2
Use case: Important tasks, complex queries
Trade-off: Higher latency, cloud costs
```

## Security Boundaries

1. **API keys never leave backend** - Frontend only knows provider status
2. **Receipts don't store raw outputs** - Only validated intents
3. **Protocol export excludes secrets** - Keys, tokens, credentials
4. **Confirmation gates are enforced server-side** - Can't bypass via API
