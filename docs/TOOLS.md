# ATLAS Tools Specification

> Single source of truth for deterministic tool definitions.

## Tool Design Principles

1. **Deterministic**: Same input → same output (no randomness)
2. **Atomic**: Each tool does one thing well
3. **Reversible**: Critical tools provide undo information
4. **Logged**: Every invocation is recorded in receipts

## Tool Categories

### Task Tools

#### TASK_CREATE

Creates a new task.

```json
{
  "tool": "TASK_CREATE",
  "args": {
    "title": "Buy dog food",
    "description": "Get the large bag from PetSmart",
    "due_date": "2024-01-20",
    "priority": "medium",
    "tags": ["errands", "pets"]
  },
  "returns": {
    "task_id": "task_abc123",
    "created_at": "2024-01-15T10:30:00Z"
  }
}
```

**Risk Level**: LOW  
**Undo**: TASK_DELETE with task_id

#### TASK_LIST

Lists tasks with optional filters.

```json
{
  "tool": "TASK_LIST",
  "args": {
    "status": "pending",
    "due_before": "2024-01-31",
    "tags": ["work"],
    "limit": 50
  },
  "returns": {
    "tasks": [...],
    "total": 15
  }
}
```

**Risk Level**: LOW (read-only)  
**Undo**: N/A

#### TASK_UPDATE

Updates an existing task.

```json
{
  "tool": "TASK_UPDATE",
  "args": {
    "task_id": "task_abc123",
    "updates": {
      "status": "completed",
      "completed_at": "2024-01-15T14:00:00Z"
    }
  },
  "returns": {
    "task_id": "task_abc123",
    "before": { "status": "pending" },
    "after": { "status": "completed" }
  }
}
```

**Risk Level**: LOW  
**Undo**: TASK_UPDATE with `before` values

---

### Note Tools

#### NOTE_CREATE

Creates a new note.

```json
{
  "tool": "NOTE_CREATE",
  "args": {
    "title": "Meeting Notes - Q1 Planning",
    "content": "# Attendees\n- Alice\n- Bob\n\n# Decisions\n...",
    "tags": ["meetings", "q1"]
  },
  "returns": {
    "note_id": "note_xyz789",
    "created_at": "2024-01-15T10:30:00Z"
  }
}
```

**Risk Level**: LOW  
**Undo**: NOTE_DELETE with note_id

#### NOTE_SEARCH

Searches notes by content or tags.

```json
{
  "tool": "NOTE_SEARCH",
  "args": {
    "query": "project deadlines",
    "tags": ["work"],
    "limit": 20
  },
  "returns": {
    "notes": [
      {
        "note_id": "note_xyz789",
        "title": "Q1 Deadlines",
        "snippet": "...project deadlines for January...",
        "relevance": 0.92
      }
    ],
    "total": 5
  }
}
```

**Risk Level**: LOW (read-only)  
**Undo**: N/A

#### NOTE_GET

Retrieves a full note by ID.

```json
{
  "tool": "NOTE_GET",
  "args": {
    "note_id": "note_xyz789"
  },
  "returns": {
    "note_id": "note_xyz789",
    "title": "Meeting Notes - Q1 Planning",
    "content": "...",
    "tags": ["meetings"],
    "created_at": "2024-01-15T10:30:00Z",
    "updated_at": "2024-01-15T10:30:00Z"
  }
}
```

**Risk Level**: LOW (read-only)  
**Undo**: N/A

---

### Calendar Tools

#### CALENDAR_GET_DAY

Gets calendar events for a specific day.

```json
{
  "tool": "CALENDAR_GET_DAY",
  "args": {
    "date": "2024-01-15"
  },
  "returns": {
    "date": "2024-01-15",
    "blocks": [
      {
        "block_id": "block_001",
        "title": "Team Standup",
        "start": "09:00",
        "end": "09:30",
        "type": "meeting"
      },
      {
        "block_id": "block_002",
        "title": "Focus Time",
        "start": "10:00",
        "end": "12:00",
        "type": "focus"
      }
    ],
    "free_slots": [
      { "start": "09:30", "end": "10:00" },
      { "start": "12:00", "end": "17:00" }
    ]
  }
}
```

**Risk Level**: LOW (read-only)  
**Undo**: N/A

#### CALENDAR_CREATE_BLOCKS

Creates calendar blocks. **Requires confirmation.**

```json
{
  "tool": "CALENDAR_CREATE_BLOCKS",
  "args": {
    "date": "2024-01-15",
    "blocks": [
      {
        "title": "Deep Work: Project X",
        "start": "14:00",
        "end": "16:00",
        "type": "focus"
      },
      {
        "title": "Review PRs",
        "start": "16:00",
        "end": "17:00",
        "type": "task"
      }
    ]
  },
  "returns": {
    "created": [
      { "block_id": "block_003", "title": "Deep Work: Project X" },
      { "block_id": "block_004", "title": "Review PRs" }
    ]
  }
}
```

**Risk Level**: MEDIUM  
**Confirmation**: Required before execution  
**Undo**: CALENDAR_DELETE_BLOCKS with block IDs

#### CALENDAR_DELETE_BLOCKS

Deletes calendar blocks by ID.

```json
{
  "tool": "CALENDAR_DELETE_BLOCKS",
  "args": {
    "block_ids": ["block_003", "block_004"]
  },
  "returns": {
    "deleted": ["block_003", "block_004"],
    "deleted_data": [
      { "block_id": "block_003", "title": "Deep Work: Project X", ... }
    ]
  }
}
```

**Risk Level**: MEDIUM  
**Confirmation**: Required for >1 block  
**Undo**: CALENDAR_CREATE_BLOCKS with deleted_data

---

### Workflow Tools

#### WORKFLOW_SAVE

Saves a workflow definition. Does NOT enable it.

```json
{
  "tool": "WORKFLOW_SAVE",
  "args": {
    "name": "Daily Standup Reminder",
    "trigger": {
      "type": "schedule",
      "cron": "0 9 * * 1-5"
    },
    "actions": [
      {
        "type": "notify",
        "message": "Time for standup!"
      }
    ],
    "enabled": false
  },
  "returns": {
    "workflow_id": "wf_001",
    "status": "saved",
    "enabled": false
  }
}
```

**Risk Level**: LOW (just saves, doesn't enable)  
**Undo**: WORKFLOW_DELETE with workflow_id

#### WORKFLOW_ENABLE

Enables a saved workflow. **Always requires confirmation.**

```json
{
  "tool": "WORKFLOW_ENABLE",
  "args": {
    "workflow_id": "wf_001",
    "enabled": true
  },
  "returns": {
    "workflow_id": "wf_001",
    "enabled": true,
    "next_run": "2024-01-16T09:00:00Z"
  }
}
```

**Risk Level**: HIGH  
**Confirmation**: Always required  
**Undo**: WORKFLOW_ENABLE with enabled=false

#### WORKFLOW_RUN

Manually triggers a workflow run.

```json
{
  "tool": "WORKFLOW_RUN",
  "args": {
    "workflow_id": "wf_001"
  },
  "returns": {
    "run_id": "run_abc123",
    "status": "completed",
    "actions_executed": 1
  }
}
```

**Risk Level**: MEDIUM  
**Confirmation**: Required  
**Undo**: Depends on workflow actions

#### WORKFLOW_LOGS

Gets execution logs for a workflow.

```json
{
  "tool": "WORKFLOW_LOGS",
  "args": {
    "workflow_id": "wf_001",
    "limit": 10
  },
  "returns": {
    "logs": [
      {
        "run_id": "run_abc123",
        "timestamp": "2024-01-15T09:00:00Z",
        "status": "completed",
        "actions": [...]
      }
    ]
  }
}
```

**Risk Level**: LOW (read-only)  
**Undo**: N/A

---

### Utility Tools

#### LOG_EVENT

Logs an event for analytics/debugging.

```json
{
  "tool": "LOG_EVENT",
  "args": {
    "event_type": "intent_classified",
    "data": {
      "intent": "CAPTURE_TASKS",
      "confidence": 0.95
    }
  },
  "returns": {
    "logged": true
  }
}
```

**Risk Level**: LOW  
**Undo**: N/A

#### NOTIFY_USER

Sends a notification to the user.

```json
{
  "tool": "NOTIFY_USER",
  "args": {
    "message": "Your day has been planned!",
    "type": "success",
    "actions": [
      { "label": "View Plan", "action": "open_calendar" }
    ]
  },
  "returns": {
    "notified": true
  }
}
```

**Risk Level**: LOW  
**Undo**: N/A

---

## Undo Requirements (MVP)

The following undo operations **must** work in MVP:

| Operation                | Undo Method                        |
| ------------------------ | ---------------------------------- |
| CALENDAR_CREATE_BLOCKS   | CALENDAR_DELETE_BLOCKS with IDs    |
| TASK_UPDATE              | TASK_UPDATE with previous values   |
| WORKFLOW_ENABLE (true)   | WORKFLOW_ENABLE (false)            |

## Tool Invocation in Receipts

Every tool call is recorded in the receipt:

```json
{
  "tool_calls": [
    {
      "tool_name": "CALENDAR_GET_DAY",
      "args": { "date": "2024-01-15" },
      "status": "OK",
      "result": { "blocks": [...] },
      "timestamp_utc": "2024-01-15T10:30:00Z"
    },
    {
      "tool_name": "CALENDAR_CREATE_BLOCKS",
      "args": { "date": "2024-01-15", "blocks": [...] },
      "status": "PENDING_CONFIRM",
      "result": null,
      "timestamp_utc": "2024-01-15T10:30:01Z"
    }
  ]
}
```

## Tool Status Lifecycle

```
PENDING_CONFIRM → OK (after user confirms)
PENDING_CONFIRM → SKIPPED (if user cancels)
* → FAILED (on error)
```
