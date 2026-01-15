/**
 * SQLite Database for Dashboard Data
 */

import Database from 'better-sqlite3';
import { join } from 'path';
import { homedir } from 'os';
import { mkdirSync, existsSync } from 'fs';

let db: Database.Database | null = null;

export function initDb(): Database.Database {
  if (db) return db;
  
  // Create data directory
  const dataDir = process.env.ATLAS_DATA_DIR || join(homedir(), '.atlas');
  if (!existsSync(dataDir)) {
    mkdirSync(dataDir, { recursive: true });
  }
  
  const dbPath = join(dataDir, 'dashboard.db');
  db = new Database(dbPath);
  
  // Create tables
  db.exec(`
    -- Tasks table
    CREATE TABLE IF NOT EXISTS tasks (
      task_id TEXT PRIMARY KEY,
      title TEXT NOT NULL,
      description TEXT DEFAULT '',
      due_date TEXT,
      priority TEXT DEFAULT 'medium',
      status TEXT DEFAULT 'pending',
      tags TEXT DEFAULT '[]',
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL
    );
    
    -- Notes table
    CREATE TABLE IF NOT EXISTS notes (
      note_id TEXT PRIMARY KEY,
      title TEXT NOT NULL,
      content TEXT DEFAULT '',
      tags TEXT DEFAULT '[]',
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL
    );
    
    -- Calendar blocks table
    CREATE TABLE IF NOT EXISTS calendar_blocks (
      block_id TEXT PRIMARY KEY,
      title TEXT NOT NULL,
      start_time TEXT NOT NULL,
      end_time TEXT NOT NULL,
      block_type TEXT DEFAULT 'event',
      source TEXT,
      created_at TEXT NOT NULL
    );
    
    -- Create indexes
    CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
    CREATE INDEX IF NOT EXISTS idx_tasks_due_date ON tasks(due_date);
    CREATE INDEX IF NOT EXISTS idx_notes_updated ON notes(updated_at);
    CREATE INDEX IF NOT EXISTS idx_calendar_start ON calendar_blocks(start_time);
  `);
  
  return db;
}

export function getDb(): Database.Database {
  if (!db) {
    return initDb();
  }
  return db;
}

export function closeDb(): void {
  if (db) {
    db.close();
    db = null;
  }
}
