/**
 * SQLite Database Setup for ATLAS MCP Autopilot
 * Handles receipts, confirmations, and workflows persistence.
 */

import Database from 'better-sqlite3';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const DB_PATH = join(__dirname, '..', '..', 'autopilot.db');

let db: Database.Database | null = null;

export function getDb(): Database.Database {
  if (!db) {
    db = new Database(DB_PATH);
    db.pragma('journal_mode = WAL');
    initSchema();
  }
  return db;
}

function initSchema(): void {
  const database = db!;

  // Receipts table
  database.exec(`
    CREATE TABLE IF NOT EXISTS receipts (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      receipt_id TEXT UNIQUE NOT NULL,
      timestamp_utc TEXT NOT NULL,
      tool_name TEXT NOT NULL,
      args_json TEXT NOT NULL,
      decision TEXT NOT NULL CHECK (decision IN ('ALLOWED', 'DENIED', 'PENDING_CONFIRM')),
      result TEXT NOT NULL CHECK (result IN ('OK', 'ERROR', 'PENDING_CONFIRM')),
      changes_json TEXT DEFAULT '[]',
      undo_json TEXT DEFAULT '[]',
      stdout TEXT,
      stderr TEXT,
      exit_code INTEGER,
      error_json TEXT,
      undo_supported INTEGER DEFAULT 0,
      created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
  `);

  database.exec(`
    CREATE INDEX IF NOT EXISTS idx_receipts_timestamp ON receipts(timestamp_utc DESC)
  `);

  database.exec(`
    CREATE INDEX IF NOT EXISTS idx_receipts_tool ON receipts(tool_name)
  `);

  // Confirmations table with TTL
  database.exec(`
    CREATE TABLE IF NOT EXISTS confirmations (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      confirmation_token TEXT UNIQUE NOT NULL,
      tool_name TEXT NOT NULL,
      args_json TEXT NOT NULL,
      preview TEXT,
      expires_at TEXT NOT NULL,
      used INTEGER DEFAULT 0,
      created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
  `);

  database.exec(`
    CREATE INDEX IF NOT EXISTS idx_confirmations_token ON confirmations(confirmation_token)
  `);

  // Workflows table
  database.exec(`
    CREATE TABLE IF NOT EXISTS workflows (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      workflow_id TEXT UNIQUE NOT NULL,
      name TEXT NOT NULL,
      description TEXT,
      steps_json TEXT NOT NULL,
      created_at TEXT DEFAULT CURRENT_TIMESTAMP,
      updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
  `);

  // Scheduled workflows table
  database.exec(`
    CREATE TABLE IF NOT EXISTS scheduled_workflows (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      schedule_id TEXT UNIQUE NOT NULL,
      workflow_id TEXT NOT NULL,
      cron_expression TEXT NOT NULL,
      enabled INTEGER DEFAULT 1,
      last_run TEXT,
      next_run TEXT,
      created_at TEXT DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (workflow_id) REFERENCES workflows(workflow_id) ON DELETE CASCADE
    )
  `);
}

export function closeDb(): void {
  if (db) {
    db.close();
    db = null;
  }
}
