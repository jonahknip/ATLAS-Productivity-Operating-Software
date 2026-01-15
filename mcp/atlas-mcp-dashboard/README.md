# ATLAS MCP Dashboard

Productivity data MCP (Model Context Protocol) server for ATLAS. Provides task, note, and calendar management with a unified dashboard snapshot for AI context.

## Features

- **Task Management**: Create, list, update, delete tasks with priorities and due dates
- **Note Management**: Create, search, update notes with full-text search
- **Calendar Blocks**: Schedule focus time, meetings, and events
- **Dashboard Snapshot**: Get a comprehensive view for AI context

## Installation

```bash
cd mcp/atlas-mcp-dashboard
npm install
```

## Development

```bash
# Run in development mode with hot reload
npm run dev

# Build for production
npm run build

# Run tests
npm test
```

## Configuration

- `PORT` - Server port (default: 3101)
- `ATLAS_DATA_DIR` - Data directory (default: ~/.atlas)

## API Endpoints

### Health Check
```
GET /health
```

### List Available Tools
```
GET /tools
```

### Execute Tool
```
POST /tools/:name
POST /call
```

## Available Tools

### Tasks

| Tool | Description |
|------|-------------|
| `task.create` | Create a new task |
| `task.list` | List tasks with filters |
| `task.get` | Get task by ID |
| `task.update` | Update task properties |
| `task.delete` | Delete a task |

### Notes

| Tool | Description |
|------|-------------|
| `note.create` | Create a new note |
| `note.search` | Full-text search notes |
| `note.get` | Get note by ID |
| `note.update` | Update note |
| `note.delete` | Delete a note |

### Calendar

| Tool | Description |
|------|-------------|
| `calendar.get_day` | Get blocks and tasks for a day |
| `calendar.create_blocks` | Create time blocks |
| `calendar.delete_blocks` | Delete blocks by ID |

### Dashboard

| Tool | Description |
|------|-------------|
| `dashboard.get_snapshot` | Get comprehensive day view |

## Example Usage

### Create a Task
```json
POST /tools/task.create
{
  "title": "Review PR #123",
  "due_date": "2025-01-15",
  "priority": "high",
  "tags": ["code-review", "urgent"]
}
```

### Search Notes
```json
POST /tools/note.search
{
  "query": "meeting notes",
  "tags": ["project-x"],
  "limit": 10
}
```

### Get Dashboard Snapshot
```json
POST /tools/dashboard.get_snapshot
{
  "date": "2025-01-15"
}
```

Response:
```json
{
  "success": true,
  "data": {
    "date": "2025-01-15",
    "tasks": {
      "summary": { "pending": 5, "in_progress": 2, "completed": 10, "total": 17 },
      "due_today": [...],
      "overdue": [...]
    },
    "calendar": {
      "blocks": [...],
      "focus_minutes": 180
    },
    "notes": {
      "recent": [...]
    }
  }
}
```

## Data Storage

All data is stored in SQLite at `~/.atlas/dashboard.db`. Tables:
- `tasks` - Task records
- `notes` - Note records  
- `calendar_blocks` - Calendar time blocks

## License

MIT - Part of the ATLAS Productivity OS
