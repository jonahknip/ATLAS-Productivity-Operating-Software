/**
 * Receipts Management
 * Creates, stores, and retrieves execution receipts.
 */

import { v4 as uuidv4 } from 'uuid';
import { getDb } from '../db/index.js';

export interface Receipt {
  receipt_id: string;
  timestamp_utc: string;
  tool_name: string;
  args_json: string;
  decision: 'ALLOWED' | 'DENIED' | 'PENDING_CONFIRM';
  result: 'OK' | 'ERROR' | 'PENDING_CONFIRM';
  changes_json: string;
  undo_json: string;
  stdout?: string;
  stderr?: string;
  exit_code?: number;
  error_json?: string;
  undo_supported: boolean;
}

export interface CreateReceiptParams {
  tool_name: string;
  args: Record<string, unknown>;
  decision: 'ALLOWED' | 'DENIED' | 'PENDING_CONFIRM';
  result: 'OK' | 'ERROR' | 'PENDING_CONFIRM';
  changes?: unknown[];
  undo?: unknown[];
  stdout?: string;
  stderr?: string;
  exit_code?: number;
  error?: unknown;
  undo_supported?: boolean;
}

export function createReceipt(params: CreateReceiptParams): Receipt {
  const receipt: Receipt = {
    receipt_id: uuidv4(),
    timestamp_utc: new Date().toISOString(),
    tool_name: params.tool_name,
    args_json: JSON.stringify(params.args),
    decision: params.decision,
    result: params.result,
    changes_json: JSON.stringify(params.changes || []),
    undo_json: JSON.stringify(params.undo || []),
    stdout: params.stdout,
    stderr: params.stderr,
    exit_code: params.exit_code,
    error_json: params.error ? JSON.stringify(params.error) : undefined,
    undo_supported: params.undo_supported ?? false,
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

export function listReceipts(limit: number = 50): Receipt[] {
  const db = getDb();
  const rows = db.prepare(`
    SELECT * FROM receipts ORDER BY timestamp_utc DESC LIMIT ?
  `).all(limit) as Array<Record<string, unknown>>;

  return rows.map(row => ({
    receipt_id: row.receipt_id as string,
    timestamp_utc: row.timestamp_utc as string,
    tool_name: row.tool_name as string,
    args_json: row.args_json as string,
    decision: row.decision as 'ALLOWED' | 'DENIED' | 'PENDING_CONFIRM',
    result: row.result as 'OK' | 'ERROR' | 'PENDING_CONFIRM',
    changes_json: row.changes_json as string,
    undo_json: row.undo_json as string,
    stdout: row.stdout as string | undefined,
    stderr: row.stderr as string | undefined,
    exit_code: row.exit_code as number | undefined,
    error_json: row.error_json as string | undefined,
    undo_supported: Boolean(row.undo_supported),
  }));
}

export function getReceipt(receiptId: string): Receipt | null {
  const db = getDb();
  const row = db.prepare(`
    SELECT * FROM receipts WHERE receipt_id = ?
  `).get(receiptId) as Record<string, unknown> | undefined;

  if (!row) return null;

  return {
    receipt_id: row.receipt_id as string,
    timestamp_utc: row.timestamp_utc as string,
    tool_name: row.tool_name as string,
    args_json: row.args_json as string,
    decision: row.decision as 'ALLOWED' | 'DENIED' | 'PENDING_CONFIRM',
    result: row.result as 'OK' | 'ERROR' | 'PENDING_CONFIRM',
    changes_json: row.changes_json as string,
    undo_json: row.undo_json as string,
    stdout: row.stdout as string | undefined,
    stderr: row.stderr as string | undefined,
    exit_code: row.exit_code as number | undefined,
    error_json: row.error_json as string | undefined,
    undo_supported: Boolean(row.undo_supported),
  };
}

export function updateReceiptUndo(receiptId: string, undone: boolean): void {
  const db = getDb();
  db.prepare(`
    UPDATE receipts SET result = ? WHERE receipt_id = ?
  `).run(undone ? 'OK' : 'ERROR', receiptId);
}
