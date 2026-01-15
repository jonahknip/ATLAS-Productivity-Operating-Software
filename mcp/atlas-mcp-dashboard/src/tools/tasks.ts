/**
 * Task Tools Implementation
 */

import { v4 as uuidv4 } from 'uuid';
import { z } from 'zod';
import { getDb } from '../db/index.js';
import {
  TaskCreateSchema,
  TaskListSchema,
  TaskGetSchema,
  TaskUpdateSchema,
  TaskDeleteSchema,
} from './schemas.js';

export interface ToolResult {
  success: boolean;
  data?: unknown;
  error?: string;
}

export async function taskCreate(args: z.infer<typeof TaskCreateSchema>): Promise<ToolResult> {
  const parsed = TaskCreateSchema.parse(args);
  const db = getDb();
  
  const taskId = `task_${uuidv4().slice(0, 12)}`;
  const now = new Date().toISOString();
  
  try {
    db.prepare(`
      INSERT INTO tasks (task_id, title, description, due_date, priority, status, tags, created_at, updated_at)
      VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, ?)
    `).run(
      taskId,
      parsed.title,
      parsed.description,
      parsed.due_date,
      parsed.priority,
      JSON.stringify(parsed.tags),
      now,
      now
    );
    
    return {
      success: true,
      data: {
        task_id: taskId,
        title: parsed.title,
        created_at: now,
      },
    };
  } catch (err) {
    return { success: false, error: String(err) };
  }
}

export async function taskList(args: z.infer<typeof TaskListSchema>): Promise<ToolResult> {
  const parsed = TaskListSchema.parse(args);
  const db = getDb();
  
  let query = 'SELECT * FROM tasks WHERE 1=1';
  const params: unknown[] = [];
  
  if (parsed.status) {
    query += ' AND status = ?';
    params.push(parsed.status);
  }
  
  if (parsed.due_before) {
    query += ' AND due_date <= ?';
    params.push(parsed.due_before);
  }
  
  query += ' ORDER BY created_at DESC LIMIT ?';
  params.push(parsed.limit);
  
  try {
    const rows = db.prepare(query).all(...params) as Array<{
      task_id: string;
      title: string;
      description: string;
      due_date: string | null;
      priority: string;
      status: string;
      tags: string;
      created_at: string;
      updated_at: string;
    }>;
    
    const tasks = rows.map(row => ({
      ...row,
      tags: JSON.parse(row.tags),
    }));
    
    // Filter by tags if provided
    let filtered = tasks;
    if (parsed.tags && parsed.tags.length > 0) {
      filtered = tasks.filter(t => 
        parsed.tags!.some(tag => t.tags.includes(tag))
      );
    }
    
    return {
      success: true,
      data: { tasks: filtered, total: filtered.length },
    };
  } catch (err) {
    return { success: false, error: String(err) };
  }
}

export async function taskGet(args: z.infer<typeof TaskGetSchema>): Promise<ToolResult> {
  const parsed = TaskGetSchema.parse(args);
  const db = getDb();
  
  try {
    const row = db.prepare('SELECT * FROM tasks WHERE task_id = ?').get(parsed.task_id) as {
      task_id: string;
      title: string;
      description: string;
      due_date: string | null;
      priority: string;
      status: string;
      tags: string;
      created_at: string;
      updated_at: string;
    } | undefined;
    
    if (!row) {
      return { success: false, error: 'Task not found' };
    }
    
    return {
      success: true,
      data: { ...row, tags: JSON.parse(row.tags) },
    };
  } catch (err) {
    return { success: false, error: String(err) };
  }
}

export async function taskUpdate(args: z.infer<typeof TaskUpdateSchema>): Promise<ToolResult> {
  const parsed = TaskUpdateSchema.parse(args);
  const db = getDb();
  
  // Build update query
  const updates: string[] = [];
  const params: unknown[] = [];
  
  if (parsed.updates.title !== undefined) {
    updates.push('title = ?');
    params.push(parsed.updates.title);
  }
  if (parsed.updates.description !== undefined) {
    updates.push('description = ?');
    params.push(parsed.updates.description);
  }
  if (parsed.updates.due_date !== undefined) {
    updates.push('due_date = ?');
    params.push(parsed.updates.due_date);
  }
  if (parsed.updates.priority !== undefined) {
    updates.push('priority = ?');
    params.push(parsed.updates.priority);
  }
  if (parsed.updates.status !== undefined) {
    updates.push('status = ?');
    params.push(parsed.updates.status);
  }
  if (parsed.updates.tags !== undefined) {
    updates.push('tags = ?');
    params.push(JSON.stringify(parsed.updates.tags));
  }
  
  if (updates.length === 0) {
    return { success: false, error: 'No updates provided' };
  }
  
  updates.push('updated_at = ?');
  params.push(new Date().toISOString());
  params.push(parsed.task_id);
  
  try {
    const result = db.prepare(`
      UPDATE tasks SET ${updates.join(', ')} WHERE task_id = ?
    `).run(...params);
    
    if (result.changes === 0) {
      return { success: false, error: 'Task not found' };
    }
    
    return {
      success: true,
      data: { task_id: parsed.task_id, updated: true },
    };
  } catch (err) {
    return { success: false, error: String(err) };
  }
}

export async function taskDelete(args: z.infer<typeof TaskDeleteSchema>): Promise<ToolResult> {
  const parsed = TaskDeleteSchema.parse(args);
  const db = getDb();
  
  try {
    const result = db.prepare('DELETE FROM tasks WHERE task_id = ?').run(parsed.task_id);
    
    if (result.changes === 0) {
      return { success: false, error: 'Task not found' };
    }
    
    return {
      success: true,
      data: { task_id: parsed.task_id, deleted: true },
    };
  } catch (err) {
    return { success: false, error: String(err) };
  }
}
