# ATLAS MCP Autopilot

Local operations MCP (Model Context Protocol) server for ATLAS. Provides secure filesystem, shell, and git operations with policy enforcement and receipt tracking.

## Features

- **Filesystem Tools**: Read, write, search files with path restrictions
- **Shell Execution**: Run allowed commands with dry-run mode and confirmation
- **Git Operations**: Status, diff, commit, push with confirmation workflow
- **Policy Enforcement**: Allowlist-based command and path restrictions
- **Receipt Tracking**: Full audit trail with undo support

## Installation

```bash
cd mcp/atlas-mcp-autopilot
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

The server uses environment variables and policy configuration:

- `PORT` - Server port (default: 3100)
- Policy settings in `src/policy/config.ts`:
  - `ALLOWED_ROOTS` - Directories the server can access
  - `ALLOWED_COMMANDS` - Shell commands that can be executed
  - `BLOCKED_SUBSTRINGS` - Dangerous patterns that are always blocked

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

### Filesystem

| Tool | Description | Risk |
|------|-------------|------|
| `fs.list_dir` | List directory contents | LOW |
| `fs.read_file` | Read file contents | LOW |
| `fs.write_file` | Write to file | MEDIUM |
| `fs.search` | Search files by name | LOW |
| `fs.stat` | Get file/dir stats | LOW |
| `fs.make_dir` | Create directory | LOW |

### Shell

| Tool | Description | Risk |
|------|-------------|------|
| `shell.run` | Execute shell command | MEDIUM-HIGH |

Shell commands run in dry-run mode by default. Set `dry_run: false` and `confirm: true` with a valid `confirmation_token` to execute.

### Git

| Tool | Description | Risk |
|------|-------------|------|
| `git.status` | Get repository status | LOW |
| `git.diff` | Get diff (staged or unstaged) | LOW |
| `git.commit` | Create commit | MEDIUM |
| `git.push` | Push to remote | MEDIUM |

Git commit and push require confirmation.

### Receipts

| Tool | Description |
|------|-------------|
| `receipts.list` | List recent operation receipts |
| `receipts.get` | Get specific receipt by ID |

## Confirmation Flow

Operations marked as MEDIUM or HIGH risk require a two-step confirmation:

1. **Request**: Call the tool without `confirm: true`
2. **Response**: Receive `status: "PENDING_CONFIRM"` with a `confirmation_token`
3. **Confirm**: Call again with `confirm: true` and the token

Example:
```json
// Step 1: Request
POST /tools/git.commit
{
  "repo_path": "/path/to/repo",
  "message": "feat: add feature"
}

// Response: Pending confirmation
{
  "success": false,
  "status": "PENDING_CONFIRM",
  "confirmation_token": "abc-123-...",
  "preview": "Commit: feat: add feature"
}

// Step 2: Confirm
POST /tools/git.commit
{
  "repo_path": "/path/to/repo",
  "message": "feat: add feature",
  "confirm": true,
  "confirmation_token": "abc-123-..."
}
```

## Undo Support

Many operations record undo steps in their receipts. Use `receipts.get` to retrieve undo information:

```json
{
  "receipt_id": "...",
  "undo_supported": true,
  "undo_json": "[{\"tool\": \"fs.write_file\", \"args\": {...}}]"
}
```

## Security Notes

- All paths are validated against `ALLOWED_ROOTS`
- Commands must be in the allowlist
- Dangerous patterns (rm -rf, etc.) are blocked
- Confirmation tokens expire after 5 minutes
- All operations are logged to SQLite database

## License

MIT - Part of the ATLAS Productivity OS
