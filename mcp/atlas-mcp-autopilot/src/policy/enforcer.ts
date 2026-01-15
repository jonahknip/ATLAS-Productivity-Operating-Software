/**
 * Policy Enforcement Module
 * Evaluates every tool call before execution.
 */

import { resolve, extname, normalize } from 'path';
import { v4 as uuidv4 } from 'uuid';
import { getDb } from '../db/index.js';
import {
  ALLOWED_ROOTS,
  SCRIPTS_DIR,
  ALLOWED_WRITE_EXTENSIONS,
  DENIED_WRITE_EXTENSIONS,
  ALLOWED_COMMANDS,
  BLOCKED_SUBSTRINGS,
  DESTRUCTIVE_COMMANDS,
  CONFIRMATION_TTL_MS,
} from './config.js';

export type PolicyDecision = 'ALLOWED' | 'DENIED' | 'PENDING_CONFIRM';

export interface PolicyResult {
  decision: PolicyDecision;
  reason: string;
  confirmationToken?: string;
  preview?: string;
}

/**
 * Check if a path is within allowed roots.
 */
export function isPathAllowed(inputPath: string): boolean {
  const normalized = normalize(resolve(inputPath)).toLowerCase();
  return ALLOWED_ROOTS.some(root => 
    normalized.startsWith(normalize(root).toLowerCase())
  );
}
/**
 * Check if a path is within scripts directory (for executables).
 */
export function isInScriptsDir(inputPath: string): boolean {
  const normalized = normalize(resolve(inputPath)).toLowerCase();
  return normalized.startsWith(normalize(SCRIPTS_DIR).toLowerCase());
}

/**
 * Check if file extension is allowed for writing.
 */
export function isExtensionAllowed(filePath: string, requireConfirm: boolean = false): PolicyResult {
  const ext = extname(filePath).toLowerCase();
  
  if (DENIED_WRITE_EXTENSIONS.includes(ext)) {
    // Executables only allowed in scripts dir with confirmation
    if (isInScriptsDir(filePath) && requireConfirm) {
      return { decision: 'PENDING_CONFIRM', reason: `Executable write to scripts dir requires confirmation: ${ext}` };
    }
    return { decision: 'DENIED', reason: `Extension not allowed: ${ext}` };
  }
  
  if (ALLOWED_WRITE_EXTENSIONS.includes(ext) || ext === '') {
    return { decision: 'ALLOWED', reason: 'Extension allowed' };
  }
  
  return { decision: 'DENIED', reason: `Unknown extension: ${ext}` };
}

/**
 * Validate shell command against allowlist and blocklist.
 */
export function validateShellCommand(command: string): PolicyResult {
  const trimmed = command.trim();
  const lower = trimmed.toLowerCase();
  
  // Check for blocked substrings
  for (const blocked of BLOCKED_SUBSTRINGS) {
    if (lower.includes(blocked.toLowerCase())) {
      return { decision: 'DENIED', reason: `Blocked pattern detected: ${blocked}` };
    }
  }

  // Extract base command (first word)
  const parts = trimmed.split(/\s+/);
  const baseCmd = parts[0].toLowerCase();
  
  // Remove path prefix if present (e.g., /usr/bin/git -> git)
  const cmdName = baseCmd.split(/[/\\]/).pop() || baseCmd;
  
  if (!ALLOWED_COMMANDS.includes(cmdName)) {
    return { decision: 'DENIED', reason: `Command not in allowlist: ${cmdName}` };
  }
  
  // Check for destructive operations
  for (const destructive of DESTRUCTIVE_COMMANDS) {
    if (lower.includes(destructive.toLowerCase())) {
      return { 
        decision: 'PENDING_CONFIRM', 
        reason: `Destructive operation requires confirmation: ${destructive}` 
      };
    }
  }
  
  return { decision: 'ALLOWED', reason: 'Command allowed' };
}

/**
 * Create a confirmation token and store it.
 */
export function createConfirmation(
  toolName: string,
  args: Record<string, unknown>,
  preview?: string
): string {
  const token = uuidv4();
  const expiresAt = new Date(Date.now() + CONFIRMATION_TTL_MS).toISOString();
  
  const db = getDb();
  db.prepare(`
    INSERT INTO confirmations (confirmation_token, tool_name, args_json, preview, expires_at)
    VALUES (?, ?, ?, ?, ?)
  `).run(token, toolName, JSON.stringify(args), preview || null, expiresAt);
  
  return token;
}

/**
 * Validate a confirmation token.
 */
export function validateConfirmation(
  token: string,
  toolName: string,
  args: Record<string, unknown>
): PolicyResult {
  const db = getDb();
  
  // Clean up expired confirmations
  db.prepare(`DELETE FROM confirmations WHERE expires_at < datetime('now')`).run();
  
  const row = db.prepare(`
    SELECT * FROM confirmations WHERE confirmation_token = ? AND used = 0
  `).get(token) as {
    tool_name: string;
    args_json: string;
    expires_at: string;
  } | undefined;
  
  if (!row) {
    return { decision: 'DENIED', reason: 'Invalid or expired confirmation token' };
  }
  
  if (row.tool_name !== toolName) {
    return { decision: 'DENIED', reason: 'Token does not match tool' };
  }
  
  // Mark token as used
  db.prepare(`UPDATE confirmations SET used = 1 WHERE confirmation_token = ?`).run(token);
  
  return { decision: 'ALLOWED', reason: 'Confirmation validated' };
}

/**
 * Evaluate filesystem write operation.
 */
export function evaluateFileWrite(
  path: string,
  confirm: boolean = false,
  confirmationToken?: string
): PolicyResult {
  if (!isPathAllowed(path)) {
    return { decision: 'DENIED', reason: `Path outside allowed roots: ${path}` };
  }
  
  const extResult = isExtensionAllowed(path, true);
  if (extResult.decision === 'DENIED') {
    return extResult;
  }
  
  if (extResult.decision === 'PENDING_CONFIRM') {
    if (confirm && confirmationToken) {
      return validateConfirmation(confirmationToken, 'fs.write_file', { path });
    }
    return extResult;
  }
  
  return { decision: 'ALLOWED', reason: 'File write allowed' };
}

/**
 * Evaluate shell command execution.
 */
export function evaluateShellCommand(
  command: string,
  cwd: string | null,
  dryRun: boolean,
  confirm: boolean,
  confirmationToken?: string
): PolicyResult {
  // Validate working directory if provided
  if (cwd && !isPathAllowed(cwd)) {
    return { decision: 'DENIED', reason: `Working directory outside allowed roots: ${cwd}` };
  }
  
  const cmdResult = validateShellCommand(command);
  
  if (cmdResult.decision === 'DENIED') {
    return cmdResult;
  }
  
  // Dry run always allowed for allowed commands
  if (dryRun) {
    return { decision: 'ALLOWED', reason: 'Dry run mode' };
  }
  
  if (cmdResult.decision === 'PENDING_CONFIRM') {
    if (confirm && confirmationToken) {
      return validateConfirmation(confirmationToken, 'shell.run', { command, cwd });
    }
    return cmdResult;
  }
  
  return { decision: 'ALLOWED', reason: 'Shell command allowed' };
}

/**
 * Evaluate git operation.
 */
export function evaluateGitOperation(
  repoPath: string,
  operation: 'status' | 'diff' | 'commit' | 'push',
  confirm: boolean = false,
  confirmationToken?: string
): PolicyResult {
  if (!isPathAllowed(repoPath)) {
    return { decision: 'DENIED', reason: `Repository outside allowed roots: ${repoPath}` };
  }
  
  // Operations that require confirmation
  const requiresConfirm = ['commit', 'push'].includes(operation);
  
  if (requiresConfirm) {
    if (confirm && confirmationToken) {
      return validateConfirmation(confirmationToken, `git.${operation}`, { repoPath });
    }
    return { 
      decision: 'PENDING_CONFIRM', 
      reason: `Git ${operation} requires confirmation` 
    };
  }
  
  return { decision: 'ALLOWED', reason: `Git ${operation} allowed` };
}
