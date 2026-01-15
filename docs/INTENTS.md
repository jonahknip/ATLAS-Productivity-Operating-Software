# ATLAS Intent Specification

> Single source of truth for intent classification and routing.

## Intent Envelope v2.1

Every user request is classified into an Intent Envelope before processing.

```json
{
  "version": "2.1",
  "intent": {
    "type": "CAPTURE_TASKS",
    "confidence": 0.95,
    "parameters": {},
    "raw_entities": ["buy dog food", "pay electric bill"]
  },
  "user_input": "Capture: buy dog food, pay electric bill",
  "timestamp_utc": "2024-01-15T10:30:00Z",
  "routing_profile": "BALANCED"
}
```

## Allowed Intent Types

| Intent Type            | Risk Level | Description                                |
| ---------------------- | ---------- | ------------------------------------------ |
| `CAPTURE_TASKS`        | LOW        | Extract and create tasks from input        |
| `SEARCH_SUMMARIZE`     | LOW        | Search notes/data and summarize results    |
| `PLAN_DAY`             | MEDIUM     | Generate a day plan with calendar blocks   |
| `PROCESS_MEETING_NOTES`| MEDIUM     | Extract tasks and follow-ups from notes    |
| `BUILD_WORKFLOW`       | HIGH       | Create or modify automation workflows      |
| `UNKNOWN`              | LOW        | Unclassified intent (fallback)             |

## Hard Validation Rules

The validator will **hard fail** if:

1. **Missing required fields**: `type` and `confidence` are required
2. **Invalid confidence**: Must be a float in range `[0.0, 1.0]`
3. **Invalid intent type**: Must be one of the allowed types above
4. **Invalid date format**: Dates must be ISO 8601 (`YYYY-MM-DD` or `YYYY-MM-DDTHH:MM:SS`)

## Intent Parameters by Type

### CAPTURE_TASKS

```json
{
  "type": "CAPTURE_TASKS",
  "parameters": {
    "tasks": [
      { "title": "Buy dog food", "due_date": null, "priority": "medium" },
      { "title": "Pay electric bill", "due_date": "2024-01-20", "priority": "high" }
    ]
  },
  "raw_entities": ["buy dog food", "pay electric bill", "by Friday"]
}
```

### PLAN_DAY

```json
{
  "type": "PLAN_DAY",
  "parameters": {
    "date": "2024-01-15",
    "tasks_to_schedule": ["task_id_1", "task_id_2"],
    "preferences": {
      "focus_hours": "morning",
      "meeting_buffer": 15
    }
  }
}
```

### PROCESS_MEETING_NOTES

```json
{
  "type": "PROCESS_MEETING_NOTES",
  "parameters": {
    "content": "Meeting with team...",
    "meeting_date": "2024-01-15",
    "attendees": ["alice@example.com", "bob@example.com"]
  }
}
```

### SEARCH_SUMMARIZE

```json
{
  "type": "SEARCH_SUMMARIZE",
  "parameters": {
    "query": "project deadlines",
    "sources": ["notes", "tasks"],
    "time_range": {
      "start": "2024-01-01",
      "end": "2024-01-31"
    }
  }
}
```

### BUILD_WORKFLOW

```json
{
  "type": "BUILD_WORKFLOW",
  "parameters": {
    "name": "Daily standup reminder",
    "trigger": {
      "type": "schedule",
      "cron": "0 9 * * 1-5"
    },
    "actions": [
      { "type": "notify", "message": "Time for standup!" }
    ]
  }
}
```

## Risk Levels and Confirmation Policy

| Risk Level | Policy                                           |
| ---------- | ------------------------------------------------ |
| `LOW`      | Auto-allowed, no confirmation needed             |
| `MEDIUM`   | Requires confirmation for writes (calendar, bulk)|
| `HIGH`     | Always requires confirmation                     |

### Confirmation Gates (Non-negotiable)

- **Calendar writes**: Always confirm before creating/deleting blocks
- **Workflow enabling**: Always confirm before enabling automation
- **Bulk operations**: Confirm if affecting >3 entities

## Job Classes for Routing

Each intent maps to a job class that determines the model routing chain:

| Job Class           | Description                          | Typical Intents          |
| ------------------- | ------------------------------------ | ------------------------ |
| `INTENT_ROUTING`    | Classify user input into intent      | All (first step)         |
| `PLANNING`          | Generate plans and schedules         | PLAN_DAY                 |
| `EXTRACTION`        | Extract structured data from text    | CAPTURE_TASKS, MEETING   |
| `SUMMARIZATION`     | Summarize and synthesize information | SEARCH_SUMMARIZE         |
| `WORKFLOW_BUILDING` | Create automation logic              | BUILD_WORKFLOW           |

## Routing Profiles

Users select a routing profile that determines model selection:

| Profile     | Strategy                              |
| ----------- | ------------------------------------- |
| `OFFLINE`   | Local models only (Ollama)            |
| `BALANCED`  | Local-first, cloud fallback           |
| `ACCURACY`  | Cloud-first for maximum accuracy      |

## Example Intent Classification Prompt

```
Classify the following user input into one of these intent types:
- CAPTURE_TASKS: User wants to create or capture tasks
- PLAN_DAY: User wants to plan their day/schedule
- PROCESS_MEETING_NOTES: User has meeting notes to process
- SEARCH_SUMMARIZE: User wants to search or summarize information
- BUILD_WORKFLOW: User wants to create automation
- UNKNOWN: Cannot classify

User input: "{input}"

Respond in JSON:
{
  "type": "<INTENT_TYPE>",
  "confidence": <0.0-1.0>,
  "parameters": {},
  "raw_entities": ["entity1", "entity2"]
}
```
