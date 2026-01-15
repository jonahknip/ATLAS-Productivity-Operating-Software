/**
 * Filesystem Tools Implementation
 */

import { readdir, readFile, writeFile, stat, mkdir } from 'fs/promises';
import { existsSync } from 'fs';
import { join, resolve } from 'path';
import { z } from 'zod';
import {
  FsListDirSchema,
  FsReadFileSchema,
  FsWriteFileSchema,
  FsSearchSchema,
  FsStatSchema,
  FsMakeDirSchema,
} from './schemas.js';
import {
  isPathAllowed,
  evaluateFileWrite,
  createConfirmation,
  MAX_UNDO_FILE_SIZE,
} from '../policy/index.js';
import { createReceipt, type ReceiptInput } from '../receipts.js';

export interface ToolResult {
  success: boolean;
  data?: unknown;
  error?: string;
  status?: 'PENDING_CONFIRM';
  confirmation_token?: string;
  preview?: string;
  receipt_id?: string;
}

/**
 * List directory contents.
 */
export async function listDir(args: z.infer<typeof FsListDirSchema>): Promise<ToolResult> {
  const parsed = FsListDirSchema.parse(args);
  const fullPath = resolve(parsed.path);
  
  if (!isPathAllowed(fullPath)) {
    const receipt = createReceipt({
      tool_name: 'fs.list_dir',
      args: parsed,
      decision: 'DENIED',
      result: 'ERROR',
      error: { message: 'Path outside allowed roots' },
    });
    return { success: false, error: 'Path outside allowed roots', receipt_id: receipt.receipt_id };
  }
  
  try {
    const entries = await readdir(fullPath, { withFileTypes: true });
    const items = entries.map(e => ({
      name: e.name,
      type: e.isDirectory() ? 'directory' : 'file',
      path: join(fullPath, e.name),
    }));
    
    const receipt = createReceipt({
      tool_name: 'fs.list_dir',
      args: parsed,
      decision: 'ALLOWED',
      result: 'OK',
    });
    
    return { success: true, data: items, receipt_id: receipt.receipt_id };
  } catch (err) {
    const receipt = createReceipt({
      tool_name: 'fs.list_dir',
      args: parsed,
      decision: 'ALLOWED',
      result: 'ERROR',
      error: err,
    });
    return { success: false, error: String(err), receipt_id: receipt.receipt_id };
  }
}

/**
 * Read file contents.
 */
export async function readFileContent(args: z.infer<typeof FsReadFileSchema>): Promise<ToolResult> {
  const parsed = FsReadFileSchema.parse(args);
  const fullPath = resolve(parsed.path);
  
  if (!isPathAllowed(fullPath)) {
    const receipt = createReceipt({
      tool_name: 'fs.read_file',
      args: parsed,
      decision: 'DENIED',
      result: 'ERROR',
      error: { message: 'Path outside allowed roots' },
    });
    return { success: false, error: 'Path outside allowed roots', receipt_id: receipt.receipt_id };
  }
  
  try {
    const content = await readFile(fullPath, 'utf-8');
    const receipt = createReceipt({
      tool_name: 'fs.read_file',
      args: parsed,
      decision: 'ALLOWED',
      result: 'OK',
    });
    return { success: true, data: { content, path: fullPath }, receipt_id: receipt.receipt_id };
  } catch (err) {
    const receipt = createReceipt({
      tool_name: 'fs.read_file',
      args: parsed,
      decision: 'ALLOWED',
      result: 'ERROR',
      error: err,
    });
    return { success: false, error: String(err), receipt_id: receipt.receipt_id };
  }
}

/**
 * Write file contents with undo support.
 */
export async function writeFileContent(args: z.infer<typeof FsWriteFileSchema>): Promise<ToolResult> {
  const parsed = FsWriteFileSchema.parse(args);
  const fullPath = resolve(parsed.path);
  
  const policy = evaluateFileWrite(fullPath, parsed.confirm, parsed.confirmation_token);
  
  if (policy.decision === 'DENIED') {
    const receipt = createReceipt({
      tool_name: 'fs.write_file',
      args: parsed,
      decision: 'DENIED',
      result: 'ERROR',
      error: { message: policy.reason },
    });
    return { success: false, error: policy.reason, receipt_id: receipt.receipt_id };
  }
  
  if (policy.decision === 'PENDING_CONFIRM') {
    const token = createConfirmation('fs.write_file', parsed, `Write to ${fullPath}`);
    const receipt = createReceipt({
      tool_name: 'fs.write_file',
      args: parsed,
      decision: 'PENDING_CONFIRM',
      result: 'PENDING_CONFIRM',
    });
    return {
      success: false,
      status: 'PENDING_CONFIRM',
      confirmation_token: token,
      preview: `Write to ${fullPath}`,
      receipt_id: receipt.receipt_id,
    };
  }
  
  try {
    // Store previous content for undo if file exists and is small enough
    let previousContent: string | null = null;
    let undoSupported = false;
    
    if (parsed.mode === 'overwrite' && existsSync(fullPath)) {
      const stats = await stat(fullPath);
      if (stats.size < MAX_UNDO_FILE_SIZE) {
        previousContent = await readFile(fullPath, 'utf-8');
        undoSupported = true;
      }
    }

    // Write the file
    if (parsed.mode === 'append') {
      await writeFile(fullPath, parsed.content, { flag: 'a' });
    } else {
      await writeFile(fullPath, parsed.content);
    }
    
    const changes = [{ type: 'file_write', path: fullPath, mode: parsed.mode }];
    const undo = undoSupported && previousContent !== null
      ? [{ tool: 'fs.write_file', args: { path: fullPath, content: previousContent, mode: 'overwrite' } }]
      : [];
    
    const receipt = createReceipt({
      tool_name: 'fs.write_file',
      args: parsed,
      decision: 'ALLOWED',
      result: 'OK',
      changes,
      undo,
      undo_supported: undoSupported,
    });
    
    return { success: true, data: { path: fullPath, mode: parsed.mode }, receipt_id: receipt.receipt_id };
  } catch (err) {
    const receipt = createReceipt({
      tool_name: 'fs.write_file',
      args: parsed,
      decision: 'ALLOWED',
      result: 'ERROR',
      error: err,
    });
    return { success: false, error: String(err), receipt_id: receipt.receipt_id };
  }
}

/**
 * Search for files matching a query.
 */
export async function searchFiles(args: z.infer<typeof FsSearchSchema>): Promise<ToolResult> {
  const parsed = FsSearchSchema.parse(args);
  const fullPath = resolve(parsed.path);
  
  if (!isPathAllowed(fullPath)) {
    const receipt = createReceipt({
      tool_name: 'fs.search',
      args: parsed,
      decision: 'DENIED',
      result: 'ERROR',
      error: { message: 'Path outside allowed roots' },
    });
    return { success: false, error: 'Path outside allowed roots', receipt_id: receipt.receipt_id };
  }
  
  const results: Array<{ path: string; name: string; type: string }> = [];
  const query = parsed.query.toLowerCase();
  
  async function searchDir(dir: string): Promise<void> {
    if (results.length >= parsed.max_results) return;
    
    try {
      const entries = await readdir(dir, { withFileTypes: true });
      for (const entry of entries) {
        if (results.length >= parsed.max_results) break;
        
        const entryPath = join(dir, entry.name);
        if (entry.name.toLowerCase().includes(query)) {
          results.push({
            path: entryPath,
            name: entry.name,
            type: entry.isDirectory() ? 'directory' : 'file',
          });
        }
        
        if (entry.isDirectory()) {
          await searchDir(entryPath);
        }
      }
    } catch {
      // Skip directories we can't read
    }
  }
  
  await searchDir(fullPath);
  
  const receipt = createReceipt({
    tool_name: 'fs.search',
    args: parsed,
    decision: 'ALLOWED',
    result: 'OK',
  });
  
  return { success: true, data: results, receipt_id: receipt.receipt_id };
}

/**
 * Get file/directory stats.
 */
export async function getStats(args: z.infer<typeof FsStatSchema>): Promise<ToolResult> {
  const parsed = FsStatSchema.parse(args);
  const fullPath = resolve(parsed.path);
  
  if (!isPathAllowed(fullPath)) {
    const receipt = createReceipt({
      tool_name: 'fs.stat',
      args: parsed,
      decision: 'DENIED',
      result: 'ERROR',
      error: { message: 'Path outside allowed roots' },
    });
    return { success: false, error: 'Path outside allowed roots', receipt_id: receipt.receipt_id };
  }
  
  try {
    const stats = await stat(fullPath);
    const data = {
      path: fullPath,
      size: stats.size,
      isDirectory: stats.isDirectory(),
      isFile: stats.isFile(),
      created: stats.birthtime.toISOString(),
      modified: stats.mtime.toISOString(),
      accessed: stats.atime.toISOString(),
    };
    
    const receipt = createReceipt({
      tool_name: 'fs.stat',
      args: parsed,
      decision: 'ALLOWED',
      result: 'OK',
    });
    
    return { success: true, data, receipt_id: receipt.receipt_id };
  } catch (err) {
    const receipt = createReceipt({
      tool_name: 'fs.stat',
      args: parsed,
      decision: 'ALLOWED',
      result: 'ERROR',
      error: err,
    });
    return { success: false, error: String(err), receipt_id: receipt.receipt_id };
  }
}

/**
 * Create a directory.
 */
export async function makeDir(args: z.infer<typeof FsMakeDirSchema>): Promise<ToolResult> {
  const parsed = FsMakeDirSchema.parse(args);
  const fullPath = resolve(parsed.path);
  
  if (!isPathAllowed(fullPath)) {
    const receipt = createReceipt({
      tool_name: 'fs.make_dir',
      args: parsed,
      decision: 'DENIED',
      result: 'ERROR',
      error: { message: 'Path outside allowed roots' },
    });
    return { success: false, error: 'Path outside allowed roots', receipt_id: receipt.receipt_id };
  }
  
  try {
    await mkdir(fullPath, { recursive: true });
    
    const changes = [{ type: 'dir_create', path: fullPath }];
    const undo = [{ 
      tool: 'shell.run', 
      args: { command: `rmdir "${fullPath}"`, confirm: true },
      description: 'Remove created directory (requires confirmation)'
    }];
    
    const receipt = createReceipt({
      tool_name: 'fs.make_dir',
      args: parsed,
      decision: 'ALLOWED',
      result: 'OK',
      changes,
      undo,
      undo_supported: true,
    });
    
    return { success: true, data: { path: fullPath }, receipt_id: receipt.receipt_id };
  } catch (err) {
    const receipt = createReceipt({
      tool_name: 'fs.make_dir',
      args: parsed,
      decision: 'ALLOWED',
      result: 'ERROR',
      error: err,
    });
    return { success: false, error: String(err), receipt_id: receipt.receipt_id };
  }
}
