/**
 * Shell Tools Implementation
 */

import { exec } from 'child_process';
import { promisify } from 'util';
import { z } from 'zod';
import { ShellRunSchema } from './schemas.js';
import { evaluateShellCommand, createConfirmation } from '../policy/index.js';
import { createReceipt } from '../receipts.js';
import type { ToolResult } from './filesystem.js';

const execAsync = promisify(exec);

/**
 * Run a shell command.
 */
export async function runShell(args: z.infer<typeof ShellRunSchema>): Promise<ToolResult> {
  const parsed = ShellRunSchema.parse(args);
  
  const policy = evaluateShellCommand(
    parsed.command,
    parsed.cwd,
    parsed.dry_run,
    parsed.confirm,
    parsed.confirmation_token
  );
  
  if (policy.decision === 'DENIED') {
    const receipt = createReceipt({
      tool_name: 'shell.run',
      args: parsed,
      decision: 'DENIED',
      result: 'ERROR',
      error: { message: policy.reason },
    });
    return { success: false, error: policy.reason, receipt_id: receipt.receipt_id };
  }
  
  if (policy.decision === 'PENDING_CONFIRM') {
    const token = createConfirmation('shell.run', parsed, `Execute: ${parsed.command}`);
    const receipt = createReceipt({
      tool_name: 'shell.run',
      args: parsed,
      decision: 'PENDING_CONFIRM',
      result: 'PENDING_CONFIRM',
    });
    return {
      success: false,
      status: 'PENDING_CONFIRM',
      confirmation_token: token,
      preview: `Execute: ${parsed.command}`,
      receipt_id: receipt.receipt_id,
    };
  }

  // Dry run - just show what would be executed
  if (parsed.dry_run) {
    const receipt = createReceipt({
      tool_name: 'shell.run',
      args: parsed,
      decision: 'ALLOWED',
      result: 'OK',
    });
    return {
      success: true,
      data: {
        dry_run: true,
        command: parsed.command,
        cwd: parsed.cwd,
        message: 'Dry run - command not executed',
      },
      receipt_id: receipt.receipt_id,
    };
  }
  
  // Execute the command
  try {
    const options: { cwd?: string; timeout: number } = {
      timeout: parsed.timeout_sec * 1000,
    };
    
    if (parsed.cwd) {
      options.cwd = parsed.cwd;
    }
    
    const { stdout, stderr } = await execAsync(parsed.command, options);
    
    const receipt = createReceipt({
      tool_name: 'shell.run',
      args: parsed,
      decision: 'ALLOWED',
      result: 'OK',
      stdout,
      stderr,
      exit_code: 0,
      undo_supported: false,
    });
    
    return {
      success: true,
      data: { stdout, stderr, exit_code: 0 },
      receipt_id: receipt.receipt_id,
    };
  } catch (err: unknown) {
    const execError = err as { stdout?: string; stderr?: string; code?: number; message?: string };
    
    const receipt = createReceipt({
      tool_name: 'shell.run',
      args: parsed,
      decision: 'ALLOWED',
      result: 'ERROR',
      stdout: execError.stdout,
      stderr: execError.stderr,
      exit_code: execError.code,
      error: { message: execError.message },
      undo_supported: false,
    });
    
    return {
      success: false,
      error: execError.message || String(err),
      data: {
        stdout: execError.stdout,
        stderr: execError.stderr,
        exit_code: execError.code,
      },
      receipt_id: receipt.receipt_id,
    };
  }
}
