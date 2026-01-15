/**
 * Receipts Module - Audit trail for all tool executions.
 */

import { v4 as uuidv4 } from 'uuid';
import { getDb } from '../db/index.js';
import type { PolicyDecision } from '../policy/index.js';

export interface Receipt {
  receipt_id: string;
  timestamp_utc: string;
  tool_name: string;
  args_json: string;
  decision: PolicyDecision;
  result: 'OK' | 'ERROR' | 'PENDING_CONFIRM';
  changes_json: string;
  undo_json: string;
  stdout?: string;
  stderr?: string;
  exit_code?: number;
  error_json?: string;
  undo_supported: boolean;
}

export interface ReceiptInput {
  tool_name: string;
  args: Record<string, unknown>;
  decision: PolicyDecision;
  result: 'OK' | 'ERROR' | 'PENDING_CONFIRM';
  changes?: unknown[];
  undo?: unknown[];
  stdout?: string;
  stderr?: string;
  exit_code?: number;
  error?: unknown;
  undo_supported?: boolean;
}

/**
 * Create and store a new receipt.
 */
export function createReceipt(input: ReceiptInput): Receipt {
  const receipt: Receipt = {
    receipt_id: uuidv4(),
    timestamp_utc: new Date().toISOString(),
    tool_name: input.tool_name,
    args_json: JSON.stringify(input.args),
    decision: input.decision,
    result: input.result,
    changes_json: JSON.stringify(input.changes || []),
    undo_json: JSON.stringify(input.undo || []),
    stdout: input.stdout,
    stderr: input.stderr,
    exit_code: input.exit_code,
    error_json: input.error ? JSON.stringify(input.error) : undefined,
    undo_supported: input.undo_supported ?? false,
  };
  
  const db = getDb();
  db.prepare(`
    INSERT INTO receipts (
      receipt_id, timestamp_utc, tool_name, args_json, decision, result,
      changes_json, undo_json, stdout, stderr, exit_code, error_json, undo_supported
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
  `).run(
    receipt.receipt_id,
    receipt.timestamp_utc,
    receipt.tool_name,
    receipt.args_json,
    receipt.decision,
    receipt.result,
    receipt.changes_json,
    receipt.undo_json,
    receipt.stdout || null,
    receipt.stderr || null,
    receipt.exit_code ?? null,
    receipt.error_json || null,
    receipt.undo_supported ? 1 : 0
  );
  
  return receipt;
}

/**
 * List receipts with optional limit.
 */
export function listReceipts(limit: number = 50): Receipt[] {
  const db = getDb();
  const rows = db.prepare(`
    SELECT * FROM receipts ORDER BY timestamp_utc DESC LIMIT ?
  `).all(limit) as Array<{
    receipt_id: string;
    timestamp_utc: string;
    tool_name: string;
    args_json: string;
    decision: PolicyDecision;
    result: 'OK' | 'ERROR' | 'PENDING_CONFIRM';
    changes_json: string;
    undo_json: string;
    stdout: string | null;
    stderr: string | null;
    exit_code: number | null;
    error_json: string | null;
    undo_supported: number;
  }>;
  
  return rows.map(row => ({
    ...row,
    stdout: row.stdout || undefined,
    stderr: row.stderr || undefined,
    exit_code: row.exit_code ?? undefined,
    error_json: row.error_json || undefined,
    undo_supported: Boolean(row.undo_supported),
  }));
}

/**
 * Get a receipt by ID.
 */
export function getReceipt(receiptId: string): Receipt | null {
  const db = getDb();
  const row = db.prepare(`
    SELECT * FROM receipts WHERE receipt_id = ?
  `).get(receiptId) as {
    receipt_id: string;
    timestamp_utc: string;
    tool_name: string;
    args_json: string;
    decision: PolicyDecision;
    result: 'OK' | 'ERROR' | 'PENDING_CONFIRM';
    changes_json: string;
    undo_json: string;
    stdout: string | null;
    stderr: string | null;
    exit_code: number | null;
    error_json: string | null;
    undo_supported: number;
  } | undefined;
  
  if (!row) return null;
  
  return {
    ...row,
    stdout: row.stdout || undefined,
    stderr: row.stderr || undefined,
    exit_code: row.exit_code ?? undefined,
    error_json: row.error_json || undefined,
    undo_supported: Boolean(row.undo_supported),
  };
}
