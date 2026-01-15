# ATLAS API

FastAPI backend for the ATLAS Productivity OS.

## Quick Start

```bash
# Install dependencies
uv sync

# Copy environment config
cp .env.example .env

# Run the server
uv run uvicorn src.atlas.main:app --reload
```

The API will be available at `http://localhost:8000`.

## API Endpoints

### Health & Status
- `GET /health` - Basic health check
- `GET /api/status` - Detailed status with providers and receipt count

### Providers
- `GET /api/providers` - List all registered providers
- `POST /api/providers/{name}/health` - Trigger health check
- `GET /api/providers/{name}/models` - List available models

### Execute (v1)
- `POST /v1/execute` - Execute a command (always produces a receipt)

### Receipts (v1)
- `GET /v1/receipts` - List receipts (with pagination)
- `GET /v1/receipts/{id}` - Get receipt details
- `POST /v1/receipts/{id}/undo` - Undo receipt changes (stub)

## Architecture

```
src/atlas/
├── main.py           # FastAPI app and routes
├── config.py         # Settings (pydantic-settings)
├── core/
│   ├── models.py     # Domain models (Intent, Receipt, etc.)
│   ├── normalizer/   # JSON extraction and repair
│   ├── validator/    # Schema and entity validation
│   └── fallback/     # Retry/fallback manager
├── engine/
│   └── executor.py   # Main execution pipeline
├── providers/
│   ├── base.py       # Provider adapter interface
│   ├── registry.py   # Provider registry
│   ├── ollama.py     # Ollama adapter
│   └── openai.py     # OpenAI adapter
└── storage/
    ├── database.py   # SQLite connection management
    └── receipts.py   # Receipts CRUD operations
```

## Running Tests

```bash
uv run pytest tests/ -v
```

## Configuration

All configuration is via environment variables (see `.env.example`):

| Variable | Description | Default |
|----------|-------------|---------|
| `DEBUG` | Enable debug mode | `false` |
| `DATABASE_URL` | SQLite database path | `sqlite+aiosqlite:///./atlas.db` |
| `OLLAMA_BASE_URL` | Ollama server URL | `http://localhost:11434` |
| `OPENAI_API_KEY` | OpenAI API key (optional) | - |
