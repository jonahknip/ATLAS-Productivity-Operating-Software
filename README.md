# ATLAS — Provider-Agnostic Productivity OS

Offline-first, bring-your-own-key, provider-agnostic productivity operating system that converts user intent into deterministic execution with receipts, undo, and shareable packs.

## Quick Start

```bash
# API (FastAPI + uv)
cd apps/api
uv sync
uv run uvicorn src.atlas.main:app --reload

# UI (React + Vite + pnpm)
cd apps/ui
pnpm install
pnpm dev
```

## Project Structure

```
atlas/
├── apps/
│   ├── api/          # FastAPI backend
│   └── ui/           # React + Vite frontend
├── packages/
│   └── schemas/      # Shared JSON schemas
└── docs/             # Specs and documentation
```

## Core Concepts

- **Provider-agnostic routing**: Local (Ollama) + Cloud (OpenAI) with fallback chains
- **Reliability engine**: Normalizer → Validator → Fallback manager
- **Skills as programs**: Deterministic execution, not chat
- **Receipts + Undo**: Every action is auditable and reversible
- **Packs**: Installable productivity modules

## Documentation

- [Intents Spec](docs/INTENTS.md)
- [Tools Spec](docs/TOOLS.md)
- [Architecture](docs/ARCHITECTURE.md)
