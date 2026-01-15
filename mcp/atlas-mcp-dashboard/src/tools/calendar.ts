/**
 * Calendar Tools Implementation
 */

import { v4 as uuidv4 } from 'uuid';
import { z } from 'zod';
import { getDb } from '../db/index.js';
import {
  CalendarGetDaySchema,
  CalendarCreateBlocksSchema,
  CalendarDeleteBlocksSchema,
} from './schemas.js';
import type { ToolResult } from './tasks.js';

export async function calendarGetDay(args: z.infer<typeof CalendarGetDaySchema>): Promise<ToolResult> {
  const parsed = CalendarGetDaySchema.parse(args);
  const db = getDb();
  
  try {
    // Get blocks for the specified date
    const startOfDay = `${parsed.date}T00:00:00`;
    const endOfDay = `${parsed.date}T23:59:59`;
    
    const blocks = db.prepare(`
      SELECT * FROM calendar_blocks
      WHERE start_time >= ? AND start_time <= ?
      ORDER BY start_time ASC
    `).all(startOfDay, endOfDay) as Array<{
      block_id: string;
      title: string;
      start_time: string;
      end_time: string;
      block_type: string;
      source: string | null;
      created_at: string;
    }>;
    
    // Get tasks due on this date
    const tasks = db.prepare(`
      SELECT task_id, title, priority, status FROM tasks
      WHERE due_date = ? AND status != 'completed' AND status != 'cancelled'
      ORDER BY priority DESC
    `).all(parsed.date) as Array<{
      task_id: string;
      title: string;
      priority: string;
      status: string;
    }>;
    
    return {
      success: true,
      data: {
        date: parsed.date,
        blocks,
        tasks_due: tasks,
        total_blocks: blocks.length,
        total_tasks: tasks.length,
      },
    };
  } catch (err) {
    return { success: false, error: String(err) };
  }
}

export async function calendarCreateBlocks(args: z.infer<typeof CalendarCreateBlocksSchema>): Promise<ToolResult> {
  const parsed = CalendarCreateBlocksSchema.parse(args);
  const db = getDb();
  
  const createdIds: string[] = [];
  const now = new Date().toISOString();
  
  try {
    const stmt = db.prepare(`
      INSERT INTO calendar_blocks (block_id, title, start_time, end_time, block_type, source, created_at)
      VALUES (?, ?, ?, ?, ?, ?, ?)
    `);
    
    for (const block of parsed.blocks) {
      const blockId = `block_${uuidv4().slice(0, 12)}`;
      stmt.run(
        blockId,
        block.title,
        block.start_time,
        block.end_time,
        block.block_type,
        block.source,
        now
      );
      createdIds.push(blockId);
    }
    
    return {
      success: true,
      data: {
        created: createdIds.length,
        block_ids: createdIds,
      },
    };
  } catch (err) {
    return { success: false, error: String(err) };
  }
}

export async function calendarDeleteBlocks(args: z.infer<typeof CalendarDeleteBlocksSchema>): Promise<ToolResult> {
  const parsed = CalendarDeleteBlocksSchema.parse(args);
  const db = getDb();
  
  try {
    const placeholders = parsed.block_ids.map(() => '?').join(',');
    const result = db.prepare(`
      DELETE FROM calendar_blocks WHERE block_id IN (${placeholders})
    `).run(...parsed.block_ids);
    
    return {
      success: true,
      data: {
        deleted: result.changes,
        requested: parsed.block_ids.length,
      },
    };
  } catch (err) {
    return { success: false, error: String(err) };
  }
}
