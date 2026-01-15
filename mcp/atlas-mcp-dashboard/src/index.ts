/**
 * ATLAS MCP Dashboard Server
 * 
 * Productivity data MCP server that provides:
 * - Task management (CRUD)
 * - Note management (CRUD + search)
 * - Calendar block management
 * - Dashboard snapshot for AI context
 */

import express, { Request, Response, NextFunction } from 'express';
import { initDb } from './db/index.js';

// Tools
import { taskCreate, taskList, taskGet, taskUpdate, taskDelete } from './tools/tasks.js';
import { noteCreate, noteSearch, noteGet, noteUpdate, noteDelete } from './tools/notes.js';
import { calendarGetDay, calendarCreateBlocks, calendarDeleteBlocks } from './tools/calendar.js';
import { dashboardGetSnapshot } from './tools/dashboard.js';

// Schemas
import {
  TaskCreateSchema,
  TaskListSchema,
  TaskGetSchema,
  TaskUpdateSchema,
  TaskDeleteSchema,
  NoteCreateSchema,
  NoteSearchSchema,
  NoteGetSchema,
  NoteUpdateSchema,
  NoteDeleteSchema,
  CalendarGetDaySchema,
  CalendarCreateBlocksSchema,
  CalendarDeleteBlocksSchema,
  DashboardSnapshotSchema,
} from './tools/schemas.js';

const PORT = process.env.PORT || 3101;

// Initialize database
initDb();

const app = express();
app.use(express.json());

// Tool definitions for MCP protocol
const TOOLS = [
  // Task tools
  {
    name: 'task.create',
    description: 'Create a new task',
    inputSchema: {
      type: 'object',
      properties: {
        title: { type: 'string' },
        description: { type: 'string' },
        due_date: { type: 'string', description: 'YYYY-MM-DD format' },
        priority: { type: 'string', enum: ['low', 'medium', 'high'] },
        tags: { type: 'array', items: { type: 'string' } },
      },
      required: ['title'],
    },
  },
  {
    name: 'task.list',
    description: 'List tasks with optional filters',
    inputSchema: {
      type: 'object',
      properties: {
        status: { type: 'string', enum: ['pending', 'in_progress', 'completed', 'cancelled'] },
        due_before: { type: 'string' },
        tags: { type: 'array', items: { type: 'string' } },
        limit: { type: 'number', default: 50 },
      },
    },
  },
  {
    name: 'task.get',
    description: 'Get a task by ID',
    inputSchema: {
      type: 'object',
      properties: { task_id: { type: 'string' } },
      required: ['task_id'],
    },
  },
  {
    name: 'task.update',
    description: 'Update a task',
    inputSchema: {
      type: 'object',
      properties: {
        task_id: { type: 'string' },
        updates: {
          type: 'object',
          properties: {
            title: { type: 'string' },
            description: { type: 'string' },
            due_date: { type: 'string' },
            priority: { type: 'string' },
            status: { type: 'string' },
            tags: { type: 'array' },
          },
        },
      },
      required: ['task_id', 'updates'],
    },
  },
  {
    name: 'task.delete',
    description: 'Delete a task',
    inputSchema: {
      type: 'object',
      properties: { task_id: { type: 'string' } },
      required: ['task_id'],
    },
  },
  // Note tools
  {
    name: 'note.create',
    description: 'Create a new note',
    inputSchema: {
      type: 'object',
      properties: {
        title: { type: 'string' },
        content: { type: 'string' },
        tags: { type: 'array', items: { type: 'string' } },
      },
      required: ['title'],
    },
  },
  {
    name: 'note.search',
    description: 'Search notes by content',
    inputSchema: {
      type: 'object',
      properties: {
        query: { type: 'string' },
        tags: { type: 'array', items: { type: 'string' } },
        limit: { type: 'number', default: 20 },
      },
      required: ['query'],
    },
  },
  {
    name: 'note.get',
    description: 'Get a note by ID',
    inputSchema: {
      type: 'object',
      properties: { note_id: { type: 'string' } },
      required: ['note_id'],
    },
  },
  {
    name: 'note.update',
    description: 'Update a note',
    inputSchema: {
      type: 'object',
      properties: {
        note_id: { type: 'string' },
        updates: {
          type: 'object',
          properties: {
            title: { type: 'string' },
            content: { type: 'string' },
            tags: { type: 'array' },
          },
        },
      },
      required: ['note_id', 'updates'],
    },
  },
  {
    name: 'note.delete',
    description: 'Delete a note',
    inputSchema: {
      type: 'object',
      properties: { note_id: { type: 'string' } },
      required: ['note_id'],
    },
  },
  // Calendar tools
  {
    name: 'calendar.get_day',
    description: 'Get calendar blocks and tasks for a specific day',
    inputSchema: {
      type: 'object',
      properties: { date: { type: 'string', description: 'YYYY-MM-DD format' } },
      required: ['date'],
    },
  },
  {
    name: 'calendar.create_blocks',
    description: 'Create calendar blocks (focus time, meetings, etc.)',
    inputSchema: {
      type: 'object',
      properties: {
        blocks: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              title: { type: 'string' },
              start_time: { type: 'string', description: 'ISO 8601 datetime' },
              end_time: { type: 'string' },
              block_type: { type: 'string', enum: ['focus', 'meeting', 'break', 'event'] },
              source: { type: 'string' },
            },
            required: ['title', 'start_time', 'end_time'],
          },
        },
      },
      required: ['blocks'],
    },
  },
  {
    name: 'calendar.delete_blocks',
    description: 'Delete calendar blocks by ID',
    inputSchema: {
      type: 'object',
      properties: {
        block_ids: { type: 'array', items: { type: 'string' } },
      },
      required: ['block_ids'],
    },
  },
  // Dashboard tool
  {
    name: 'dashboard.get_snapshot',
    description: 'Get a dashboard snapshot with tasks, calendar, and notes summary',
    inputSchema: {
      type: 'object',
      properties: {
        date: { type: 'string', description: 'YYYY-MM-DD format, defaults to today' },
      },
    },
  },
];

// Tool handlers
const toolHandlers: Record<string, (args: unknown) => Promise<unknown>> = {
  'task.create': async (args) => taskCreate(TaskCreateSchema.parse(args)),
  'task.list': async (args) => taskList(TaskListSchema.parse(args)),
  'task.get': async (args) => taskGet(TaskGetSchema.parse(args)),
  'task.update': async (args) => taskUpdate(TaskUpdateSchema.parse(args)),
  'task.delete': async (args) => taskDelete(TaskDeleteSchema.parse(args)),
  'note.create': async (args) => noteCreate(NoteCreateSchema.parse(args)),
  'note.search': async (args) => noteSearch(NoteSearchSchema.parse(args)),
  'note.get': async (args) => noteGet(NoteGetSchema.parse(args)),
  'note.update': async (args) => noteUpdate(NoteUpdateSchema.parse(args)),
  'note.delete': async (args) => noteDelete(NoteDeleteSchema.parse(args)),
  'calendar.get_day': async (args) => calendarGetDay(CalendarGetDaySchema.parse(args)),
  'calendar.create_blocks': async (args) => calendarCreateBlocks(CalendarCreateBlocksSchema.parse(args)),
  'calendar.delete_blocks': async (args) => calendarDeleteBlocks(CalendarDeleteBlocksSchema.parse(args)),
  'dashboard.get_snapshot': async (args) => dashboardGetSnapshot(DashboardSnapshotSchema.parse(args)),
};

// Health check
app.get('/health', (_req: Request, res: Response) => {
  res.json({ status: 'healthy', version: '1.0.0' });
});

// List tools
app.get('/tools', (_req: Request, res: Response) => {
  res.json({ tools: TOOLS });
});

// Execute tool
app.post('/tools/:name', async (req: Request, res: Response, next: NextFunction) => {
  try {
    const { name } = req.params;
    const args = req.body;
    
    const handler = toolHandlers[name];
    if (!handler) {
      res.status(404).json({ success: false, error: `Tool not found: ${name}` });
      return;
    }
    
    const result = await handler(args);
    res.json(result);
  } catch (error) {
    next(error);
  }
});

// Generic tool call endpoint (MCP style)
app.post('/call', async (req: Request, res: Response, next: NextFunction) => {
  try {
    const { name, arguments: args } = req.body;
    
    const handler = toolHandlers[name];
    if (!handler) {
      res.status(404).json({ success: false, error: `Tool not found: ${name}` });
      return;
    }
    
    const result = await handler(args);
    res.json(result);
  } catch (error) {
    next(error);
  }
});

// Error handler
app.use((err: Error, _req: Request, res: Response, _next: NextFunction) => {
  console.error('Error:', err);
  res.status(500).json({ 
    success: false, 
    error: err.message || 'Internal server error' 
  });
});

app.listen(PORT, () => {
  console.log(`ATLAS MCP Dashboard Server running on port ${PORT}`);
  console.log(`Available tools: ${TOOLS.map(t => t.name).join(', ')}`);
});

export { app };
