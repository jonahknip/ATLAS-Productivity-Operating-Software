/**
 * Dashboard Snapshot Tool
 */

import { z } from 'zod';
import { getDb } from '../db/index.js';
import { DashboardSnapshotSchema } from './schemas.js';
import type { ToolResult } from './tasks.js';

export async function dashboardGetSnapshot(args: z.infer<typeof DashboardSnapshotSchema>): Promise<ToolResult> {
  const parsed = DashboardSnapshotSchema.parse(args);
  const db = getDb();
  
  // Default to today
  const date = parsed.date || new Date().toISOString().split('T')[0];
  
  try {
    // Get task summary
    const taskStats = db.prepare(`
      SELECT 
        status,
        COUNT(*) as count
      FROM tasks
      GROUP BY status
    `).all() as Array<{ status: string; count: number }>;
    
    const taskSummary = {
      pending: 0,
      in_progress: 0,
      completed: 0,
      cancelled: 0,
      total: 0,
    };
    
    for (const stat of taskStats) {
      if (stat.status in taskSummary) {
        (taskSummary as Record<string, number>)[stat.status] = stat.count;
      }
      taskSummary.total += stat.count;
    }
    
    // Get tasks due today
    const tasksDueToday = db.prepare(`
      SELECT task_id, title, priority, status FROM tasks
      WHERE due_date = ? AND status NOT IN ('completed', 'cancelled')
      ORDER BY priority DESC
      LIMIT 10
    `).all(date) as Array<{
      task_id: string;
      title: string;
      priority: string;
      status: string;
    }>;
    
    // Get overdue tasks
    const overdueTasks = db.prepare(`
      SELECT task_id, title, due_date, priority FROM tasks
      WHERE due_date < ? AND status NOT IN ('completed', 'cancelled')
      ORDER BY due_date ASC
      LIMIT 5
    `).all(date) as Array<{
      task_id: string;
      title: string;
      due_date: string;
      priority: string;
    }>;
    
    // Get today's calendar blocks
    const startOfDay = `${date}T00:00:00`;
    const endOfDay = `${date}T23:59:59`;
    
    const calendarBlocks = db.prepare(`
      SELECT block_id, title, start_time, end_time, block_type FROM calendar_blocks
      WHERE start_time >= ? AND start_time <= ?
      ORDER BY start_time ASC
    `).all(startOfDay, endOfDay) as Array<{
      block_id: string;
      title: string;
      start_time: string;
      end_time: string;
      block_type: string;
    }>;
    
    // Get recent notes
    const recentNotes = db.prepare(`
      SELECT note_id, title, updated_at FROM notes
      ORDER BY updated_at DESC
      LIMIT 5
    `).all() as Array<{
      note_id: string;
      title: string;
      updated_at: string;
    }>;
    
    // Calculate focus time (sum of focus blocks)
    const focusMinutes = calendarBlocks
      .filter(b => b.block_type === 'focus')
      .reduce((sum, b) => {
        const start = new Date(b.start_time).getTime();
        const end = new Date(b.end_time).getTime();
        return sum + (end - start) / (1000 * 60);
      }, 0);
    
    return {
      success: true,
      data: {
        date,
        tasks: {
          summary: taskSummary,
          due_today: tasksDueToday,
          overdue: overdueTasks,
        },
        calendar: {
          blocks: calendarBlocks,
          total_blocks: calendarBlocks.length,
          focus_minutes: Math.round(focusMinutes),
        },
        notes: {
          recent: recentNotes,
        },
      },
    };
  } catch (err) {
    return { success: false, error: String(err) };
  }
}
