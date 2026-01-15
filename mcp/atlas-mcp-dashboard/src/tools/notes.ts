/**
 * Notes Tools Implementation
 */

import { v4 as uuidv4 } from 'uuid';
import { z } from 'zod';
import { getDb } from '../db/index.js';
import {
  NoteCreateSchema,
  NoteSearchSchema,
  NoteGetSchema,
  NoteUpdateSchema,
  NoteDeleteSchema,
} from './schemas.js';
import type { ToolResult } from './tasks.js';

export async function noteCreate(args: z.infer<typeof NoteCreateSchema>): Promise<ToolResult> {
  const parsed = NoteCreateSchema.parse(args);
  const db = getDb();
  
  const noteId = `note_${uuidv4().slice(0, 12)}`;
  const now = new Date().toISOString();
  
  try {
    db.prepare(`
      INSERT INTO notes (note_id, title, content, tags, created_at, updated_at)
      VALUES (?, ?, ?, ?, ?, ?)
    `).run(
      noteId,
      parsed.title,
      parsed.content,
      JSON.stringify(parsed.tags),
      now,
      now
    );
    
    return {
      success: true,
      data: {
        note_id: noteId,
        title: parsed.title,
        created_at: now,
      },
    };
  } catch (err) {
    return { success: false, error: String(err) };
  }
}

export async function noteSearch(args: z.infer<typeof NoteSearchSchema>): Promise<ToolResult> {
  const parsed = NoteSearchSchema.parse(args);
  const db = getDb();
  
  try {
    // Simple search - match title or content
    const query = `
      SELECT * FROM notes 
      WHERE title LIKE ? OR content LIKE ?
      ORDER BY updated_at DESC
      LIMIT ?
    `;
    const searchPattern = `%${parsed.query}%`;
    
    const rows = db.prepare(query).all(searchPattern, searchPattern, parsed.limit) as Array<{
      note_id: string;
      title: string;
      content: string;
      tags: string;
      created_at: string;
      updated_at: string;
    }>;
    
    let notes = rows.map(row => ({
      ...row,
      tags: JSON.parse(row.tags),
      // Add snippet for search results
      snippet: row.content.slice(0, 200) + (row.content.length > 200 ? '...' : ''),
    }));
    
    // Filter by tags if provided
    if (parsed.tags && parsed.tags.length > 0) {
      notes = notes.filter(n => 
        parsed.tags!.some(tag => n.tags.includes(tag))
      );
    }
    
    return {
      success: true,
      data: { notes, total: notes.length, query: parsed.query },
    };
  } catch (err) {
    return { success: false, error: String(err) };
  }
}

export async function noteGet(args: z.infer<typeof NoteGetSchema>): Promise<ToolResult> {
  const parsed = NoteGetSchema.parse(args);
  const db = getDb();
  
  try {
    const row = db.prepare('SELECT * FROM notes WHERE note_id = ?').get(parsed.note_id) as {
      note_id: string;
      title: string;
      content: string;
      tags: string;
      created_at: string;
      updated_at: string;
    } | undefined;
    
    if (!row) {
      return { success: false, error: 'Note not found' };
    }
    
    return {
      success: true,
      data: { ...row, tags: JSON.parse(row.tags) },
    };
  } catch (err) {
    return { success: false, error: String(err) };
  }
}

export async function noteUpdate(args: z.infer<typeof NoteUpdateSchema>): Promise<ToolResult> {
  const parsed = NoteUpdateSchema.parse(args);
  const db = getDb();
  
  const updates: string[] = [];
  const params: unknown[] = [];
  
  if (parsed.updates.title !== undefined) {
    updates.push('title = ?');
    params.push(parsed.updates.title);
  }
  if (parsed.updates.content !== undefined) {
    updates.push('content = ?');
    params.push(parsed.updates.content);
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
  params.push(parsed.note_id);
  
  try {
    const result = db.prepare(`
      UPDATE notes SET ${updates.join(', ')} WHERE note_id = ?
    `).run(...params);
    
    if (result.changes === 0) {
      return { success: false, error: 'Note not found' };
    }
    
    return {
      success: true,
      data: { note_id: parsed.note_id, updated: true },
    };
  } catch (err) {
    return { success: false, error: String(err) };
  }
}

export async function noteDelete(args: z.infer<typeof NoteDeleteSchema>): Promise<ToolResult> {
  const parsed = NoteDeleteSchema.parse(args);
  const db = getDb();
  
  try {
    const result = db.prepare('DELETE FROM notes WHERE note_id = ?').run(parsed.note_id);
    
    if (result.changes === 0) {
      return { success: false, error: 'Note not found' };
    }
    
    return {
      success: true,
      data: { note_id: parsed.note_id, deleted: true },
    };
  } catch (err) {
    return { success: false, error: String(err) };
  }
}
