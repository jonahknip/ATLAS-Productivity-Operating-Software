/**
 * Git Tools Implementation
 */

import { exec } from 'child_process';
import { promisify } from 'util';
import { existsSync } from 'fs';
import { join, resolve } from 'path';
import { z } from 'zod';
import { GitStatusSchema, GitDiffSchema, GitCommitSchema, GitPushSchema } from './schemas.js';
import { evaluateGitOperation, createConfirmation, isPathAllowed } from '../policy/index.js';
import { createReceipt } from '../receipts.js';
import type { ToolResult } from './filesystem.js';

const execAsync = promisify(exec);

function isGitRepo(repoPath: string): boolean {
  return existsSync(join(resolve(repoPath), '.git'));
}

/**
 * Get git status.
 */
export async function gitStatus(args: z.infer<typeof GitStatusSchema>): Promise<ToolResult> {
  const parsed = GitStatusSchema.parse(args);
  const fullPath = resolve(parsed.repo_path);
  
  if (!isPathAllowed(fullPath)) {
    const receipt = createReceipt({
      tool_name: 'git.status',
      args: parsed,
      decision: 'DENIED',
      result: 'ERROR',
      error: { message: 'Repository outside allowed roots' },
    });
    return { success: false, error: 'Repository outside allowed roots', receipt_id: receipt.receipt_id };
  }
  
  if (!isGitRepo(fullPath)) {
    const receipt = createReceipt({
      tool_name: 'git.status',
      args: parsed,
      decision: 'DENIED',
      result: 'ERROR',
      error: { message: 'Not a git repository' },
    });
    return { success: false, error: 'Not a git repository', receipt_id: receipt.receipt_id };
  }

  try {
    const { stdout } = await execAsync('git status --porcelain', { cwd: fullPath });
    const { stdout: branch } = await execAsync('git branch --show-current', { cwd: fullPath });
    
    const receipt = createReceipt({
      tool_name: 'git.status',
      args: parsed,
      decision: 'ALLOWED',
      result: 'OK',
    });
    
    return {
      success: true,
      data: {
        branch: branch.trim(),
        status: stdout.trim(),
        clean: stdout.trim() === '',
      },
      receipt_id: receipt.receipt_id,
    };
  } catch (err) {
    const receipt = createReceipt({
      tool_name: 'git.status',
      args: parsed,
      decision: 'ALLOWED',
      result: 'ERROR',
      error: err,
    });
    return { success: false, error: String(err), receipt_id: receipt.receipt_id };
  }
}

/**
 * Get git diff.
 */
export async function gitDiff(args: z.infer<typeof GitDiffSchema>): Promise<ToolResult> {
  const parsed = GitDiffSchema.parse(args);
  const fullPath = resolve(parsed.repo_path);
  
  if (!isPathAllowed(fullPath)) {
    const receipt = createReceipt({
      tool_name: 'git.diff',
      args: parsed,
      decision: 'DENIED',
      result: 'ERROR',
      error: { message: 'Repository outside allowed roots' },
    });
    return { success: false, error: 'Repository outside allowed roots', receipt_id: receipt.receipt_id };
  }
  
  if (!isGitRepo(fullPath)) {
    const receipt = createReceipt({
      tool_name: 'git.diff',
      args: parsed,
      decision: 'DENIED',
      result: 'ERROR',
      error: { message: 'Not a git repository' },
    });
    return { success: false, error: 'Not a git repository', receipt_id: receipt.receipt_id };
  }

  try {
    const cmd = parsed.staged ? 'git diff --staged' : 'git diff';
    const { stdout } = await execAsync(cmd, { cwd: fullPath });
    
    const receipt = createReceipt({
      tool_name: 'git.diff',
      args: parsed,
      decision: 'ALLOWED',
      result: 'OK',
    });
    
    return { success: true, data: { diff: stdout, staged: parsed.staged }, receipt_id: receipt.receipt_id };
  } catch (err) {
    const receipt = createReceipt({
      tool_name: 'git.diff',
      args: parsed,
      decision: 'ALLOWED',
      result: 'ERROR',
      error: err,
    });
    return { success: false, error: String(err), receipt_id: receipt.receipt_id };
  }
}

/**
 * Git commit with confirmation.
 */
export async function gitCommit(args: z.infer<typeof GitCommitSchema>): Promise<ToolResult> {
  const parsed = GitCommitSchema.parse(args);
  const fullPath = resolve(parsed.repo_path);
  
  const policy = evaluateGitOperation(fullPath, 'commit', parsed.confirm, parsed.confirmation_token);
  
  if (policy.decision === 'DENIED') {
    const receipt = createReceipt({
      tool_name: 'git.commit',
      args: parsed,
      decision: 'DENIED',
      result: 'ERROR',
      error: { message: policy.reason },
    });
    return { success: false, error: policy.reason, receipt_id: receipt.receipt_id };
  }
  
  if (policy.decision === 'PENDING_CONFIRM') {
    const token = createConfirmation('git.commit', parsed, `Commit: ${parsed.message}`);
    const receipt = createReceipt({
      tool_name: 'git.commit',
      args: parsed,
      decision: 'PENDING_CONFIRM',
      result: 'PENDING_CONFIRM',
    });
    return {
      success: false,
      status: 'PENDING_CONFIRM',
      confirmation_token: token,
      preview: `Commit: ${parsed.message}`,
      receipt_id: receipt.receipt_id,
    };
  }
  
  if (!isGitRepo(fullPath)) {
    const receipt = createReceipt({
      tool_name: 'git.commit',
      args: parsed,
      decision: 'DENIED',
      result: 'ERROR',
      error: { message: 'Not a git repository' },
    });
    return { success: false, error: 'Not a git repository', receipt_id: receipt.receipt_id };
  }
  
  try {
    if (parsed.add_all) {
      await execAsync('git add -A', { cwd: fullPath });
    }
    
    const { stdout: commitOut } = await execAsync(
      `git commit -m "${parsed.message.replace(/"/g, '\\"')}"`,
      { cwd: fullPath }
    );
    
    const { stdout: hashOut } = await execAsync('git rev-parse HEAD', { cwd: fullPath });
    const commitHash = hashOut.trim();
    
    const receipt = createReceipt({
      tool_name: 'git.commit',
      args: parsed,
      decision: 'ALLOWED',
      result: 'OK',
      changes: [{ type: 'git_commit', hash: commitHash, message: parsed.message }],
      undo: [{ tool: 'shell.run', args: { command: 'git reset --soft HEAD~1', cwd: fullPath, confirm: true } }],
      undo_supported: true,
    });
    
    return {
      success: true,
      data: { commit_hash: commitHash, message: parsed.message, output: commitOut },
      receipt_id: receipt.receipt_id,
    };
  } catch (err) {
    const receipt = createReceipt({
      tool_name: 'git.commit',
      args: parsed,
      decision: 'ALLOWED',
      result: 'ERROR',
      error: err,
    });
    return { success: false, error: String(err), receipt_id: receipt.receipt_id };
  }
}

/**
 * Git push with confirmation.
 */
export async function gitPush(args: z.infer<typeof GitPushSchema>): Promise<ToolResult> {
  const parsed = GitPushSchema.parse(args);
  const fullPath = resolve(parsed.repo_path);
  
  const policy = evaluateGitOperation(fullPath, 'push', parsed.confirm, parsed.confirmation_token);
  
  if (policy.decision === 'DENIED') {
    const receipt = createReceipt({
      tool_name: 'git.push',
      args: parsed,
      decision: 'DENIED',
      result: 'ERROR',
      error: { message: policy.reason },
    });
    return { success: false, error: policy.reason, receipt_id: receipt.receipt_id };
  }
  
  if (policy.decision === 'PENDING_CONFIRM') {
    const token = createConfirmation('git.push', parsed, `Push to ${parsed.remote}/${parsed.branch || 'current'}`);
    const receipt = createReceipt({
      tool_name: 'git.push',
      args: parsed,
      decision: 'PENDING_CONFIRM',
      result: 'PENDING_CONFIRM',
    });
    return {
      success: false,
      status: 'PENDING_CONFIRM',
      confirmation_token: token,
      preview: `Push to ${parsed.remote}/${parsed.branch || 'current'}`,
      receipt_id: receipt.receipt_id,
    };
  }
  
  if (!isGitRepo(fullPath)) {
    const receipt = createReceipt({
      tool_name: 'git.push',
      args: parsed,
      decision: 'DENIED',
      result: 'ERROR',
      error: { message: 'Not a git repository' },
    });
    return { success: false, error: 'Not a git repository', receipt_id: receipt.receipt_id };
  }
  
  try {
    const branchArg = parsed.branch ? ` ${parsed.branch}` : '';
    const { stdout, stderr } = await execAsync(`git push ${parsed.remote}${branchArg}`, { cwd: fullPath });
    
    const receipt = createReceipt({
      tool_name: 'git.push',
      args: parsed,
      decision: 'ALLOWED',
      result: 'OK',
      stdout,
      stderr,
      undo_supported: false,
    });
    
    return {
      success: true,
      data: { remote: parsed.remote, branch: parsed.branch, output: stdout || stderr },
      receipt_id: receipt.receipt_id,
    };
  } catch (err: unknown) {
    const execError = err as { stdout?: string; stderr?: string; message?: string };
    const receipt = createReceipt({
      tool_name: 'git.push',
      args: parsed,
      decision: 'ALLOWED',
      result: 'ERROR',
      stdout: execError.stdout,
      stderr: execError.stderr,
      error: { message: execError.message },
    });
    return { success: false, error: execError.message || String(err), receipt_id: receipt.receipt_id };
  }
}
  if (!isGitRepo(fullPath)) {
    const receipt = createReceipt({
      tool_name: 'git.commit',
      args: parsed,
      decision: 'DENIED',
      result: 'ERROR',
      error: { message: 'Not a git repository' },
    });
    return { success: false, error: 'Not a git repository', receipt_id: receipt.receipt_id };
  }
  
  if (policy.decision === 'PENDING_CONFIRM') {
    const token = createConfirmation('git.commit', parsed, `Commit: ${parsed.message}`);
    const receipt = createReceipt({
      tool_name: 'git.commit',
      args: parsed,
      decision: 'PENDING_CONFIRM',
      result: 'PENDING_CONFIRM',
    });
    return {
      success: false,
      status: 'PENDING_CONFIRM',
      confirmation_token: token,
      preview: `Commit: ${parsed.message}`,
      receipt_id: receipt.receipt_id,
    };
  }
  
  try {
    if (parsed.add_all) {
      await execAsync('git add -A', { cwd: fullPath });
    }
    
    const { stdout } = await execAsync(`git commit -m "${parsed.message.replace(/"/g, '\\"')}"`, { cwd: fullPath });
    
    const receipt = createReceipt({
      tool_name: 'git.commit',
      args: parsed,
      decision: 'ALLOWED',
      result: 'OK',
      undo_supported: false,
    });
    
    return { success: true, data: { output: stdout }, receipt_id: receipt.receipt_id };
  } catch (err) {
    const receipt = createReceipt({
      tool_name: 'git.commit',
      args: parsed,
      decision: 'ALLOWED',
      result: 'ERROR',
      error: err,
      undo_supported: false,
    });
    return { success: false, error: String(err), receipt_id: receipt.receipt_id };
  }
}

/**
 * Git push with confirmation.
 */
export async function gitPush(args: z.infer<typeof GitPushSchema>): Promise<ToolResult> {
  const parsed = GitPushSchema.parse(args);
  const fullPath = resolve(parsed.repo_path);
  
  const policy = evaluateGitOperation(fullPath, 'push', parsed.confirm, parsed.confirmation_token);
  
  if (policy.decision === 'DENIED') {
    const receipt = createReceipt({
      tool_name: 'git.push',
      args: parsed,
      decision: 'DENIED',
      result: 'ERROR',
      error: { message: policy.reason },
    });
    return { success: false, error: policy.reason, receipt_id: receipt.receipt_id };
  }
  
  if (!isGitRepo(fullPath)) {
    const receipt = createReceipt({
      tool_name: 'git.push',
      args: parsed,
      decision: 'DENIED',
      result: 'ERROR',
      error: { message: 'Not a git repository' },
    });
    return { success: false, error: 'Not a git repository', receipt_id: receipt.receipt_id };
  }
  
  if (policy.decision === 'PENDING_CONFIRM') {
    const token = createConfirmation('git.push', parsed, `Push to ${parsed.remote}`);
    const receipt = createReceipt({
      tool_name: 'git.push',
      args: parsed,
      decision: 'PENDING_CONFIRM',
      result: 'PENDING_CONFIRM',
    });
    return {
      success: false,
      status: 'PENDING_CONFIRM',
      confirmation_token: token,
      preview: `Push to ${parsed.remote}`,
      receipt_id: receipt.receipt_id,
    };
  }

  try {
    const branch = parsed.branch || '';
    const { stdout } = await execAsync(`git push ${parsed.remote} ${branch}`.trim(), { cwd: fullPath });
    
    const receipt = createReceipt({
      tool_name: 'git.push',
      args: parsed,
      decision: 'ALLOWED',
      result: 'OK',
      undo_supported: false,
    });
    
    return { success: true, data: { output: stdout }, receipt_id: receipt.receipt_id };
  } catch (err) {
    const receipt = createReceipt({
      tool_name: 'git.push',
      args: parsed,
      decision: 'ALLOWED',
      result: 'ERROR',
      error: err,
      undo_supported: false,
    });
    return { success: false, error: String(err), receipt_id: receipt.receipt_id };
  }
}
