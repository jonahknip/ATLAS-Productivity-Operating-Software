/**
 * Zod schemas for dashboard tools
 */

import { z } from 'zod';

// Task schemas
export const TaskCreateSchema = z.object({
  title: z.string().min(1),
  description: z.string().default(''),
  due_date: z.string().nullable().default(null),
  priority: z.enum(['low', 'medium', 'high']).default('medium'),
  tags: z.array(z.string()).default([]),
});

export const TaskListSchema = z.object({
  status: z.enum(['pending', 'in_progress', 'completed', 'cancelled']).nullable().default(null),
  due_before: z.string().nullable().default(null),
  tags: z.array(z.string()).nullable().default(null),
  limit: z.number().int().min(1).max(200).default(50),
});

export const TaskGetSchema = z.object({
  task_id: z.string().min(1),
});

export const TaskUpdateSchema = z.object({
  task_id: z.string().min(1),
  updates: z.object({
    title: z.string().optional(),
    description: z.string().optional(),
    due_date: z.string().nullable().optional(),
    priority: z.enum(['low', 'medium', 'high']).optional(),
    status: z.enum(['pending', 'in_progress', 'completed', 'cancelled']).optional(),
    tags: z.array(z.string()).optional(),
  }),
});

export const TaskDeleteSchema = z.object({
  task_id: z.string().min(1),
});

// Note schemas
export const NoteCreateSchema = z.object({
  title: z.string().min(1),
  content: z.string().default(''),
  tags: z.array(z.string()).default([]),
});

export const NoteSearchSchema = z.object({
  query: z.string().min(1),
  tags: z.array(z.string()).nullable().default(null),
  limit: z.number().int().min(1).max(100).default(20),
});

export const NoteGetSchema = z.object({
  note_id: z.string().min(1),
});

export const NoteUpdateSchema = z.object({
  note_id: z.string().min(1),
  updates: z.object({
    title: z.string().optional(),
    content: z.string().optional(),
    tags: z.array(z.string()).optional(),
  }),
});

export const NoteDeleteSchema = z.object({
  note_id: z.string().min(1),
});

// Calendar schemas
export const CalendarGetDaySchema = z.object({
  date: z.string().min(1), // YYYY-MM-DD format
});

export const CalendarBlockSchema = z.object({
  title: z.string().min(1),
  start_time: z.string().min(1), // ISO 8601 datetime
  end_time: z.string().min(1),
  block_type: z.enum(['focus', 'meeting', 'break', 'event']).default('event'),
  source: z.string().nullable().default(null),
});

export const CalendarCreateBlocksSchema = z.object({
  blocks: z.array(CalendarBlockSchema).min(1),
});

export const CalendarDeleteBlocksSchema = z.object({
  block_ids: z.array(z.string()).min(1),
});

// Dashboard snapshot
export const DashboardSnapshotSchema = z.object({
  date: z.string().nullable().default(null), // Optional, defaults to today
});
