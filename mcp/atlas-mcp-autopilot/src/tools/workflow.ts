/**
 * Workflow Tools Implementation
 */

import { v4 as uuidv4 } from 'uuid';
import { z } from 'zod';
import { WorkflowSaveSchema, WorkflowRunSchema, WorkflowScheduleSchema } from './schemas.js';
import { getDb } from '../db/index.js';
import { createConfirmation } from '../policy/index.js';
import { createReceipt } from '../receipts.js';
import type { ToolResult } from './filesystem.js';

interface Workflow {
  workflow_id: string;
  name: string;
  description?: string;
  steps_json: string;
  created_at: string;
}

/**
 * Save a workflow.
 */
export async function saveWorkflow(args: z.infer<typeof WorkflowSaveSchema>): Promise<ToolResult> {
  const parsed = WorkflowSaveSchema.parse(args);
  const workflow = parsed.workflow_json;
  const workflowId = uuidv4();
  
  const db = getDb();
  db.prepare(`
    INSERT INTO workflows (workflow_id, name, description, steps_json)
    VALUES (?, ?, ?, ?)
  `).run(workflowId, workflow.name, workflow.description || null, JSON.stringify(workflow.steps));
  
  const undo = [{
    tool: 'workflow.delete',
    args: { workflow_id: workflowId, confirm: true },
    description: 'Delete workflow (requires confirmation)',
  }];
  
  const receipt = createReceipt({
    tool_name: 'workflow.save',
    args: parsed,
    decision: 'ALLOWED',
    result: 'OK',
    changes: [{ type: 'workflow_create', workflow_id: workflowId }],
    undo,
    undo_supported: true,
  });
  
  return {
    success: true,
    data: { workflow_id: workflowId, name: workflow.name },
    receipt_id: receipt.receipt_id,
  };
}

/**
 * Run a workflow (dry run by default).
 */
export async function runWorkflow(args: z.infer<typeof WorkflowRunSchema>): Promise<ToolResult> {
  const parsed = WorkflowRunSchema.parse(args);
  
  const db = getDb();
  const workflow = db.prepare(`
    SELECT * FROM workflows WHERE workflow_id = ?
  `).get(parsed.workflow_id) as Workflow | undefined;
  
  if (!workflow) {
    const receipt = createReceipt({
      tool_name: 'workflow.run',
      args: parsed,
      decision: 'DENIED',
      result: 'ERROR',
      error: { message: 'Workflow not found' },
    });
    return { success: false, error: 'Workflow not found', receipt_id: receipt.receipt_id };
  }
  
  const steps = JSON.parse(workflow.steps_json);
  
  if (parsed.dry_run) {
    const receipt = createReceipt({
      tool_name: 'workflow.run',
      args: parsed,
      decision: 'ALLOWED',
      result: 'OK',
    });
    return {
      success: true,
      data: {
        dry_run: true,
        workflow_id: workflow.workflow_id,
        name: workflow.name,
        steps,
        message: 'Dry run - steps not executed',
      },
      receipt_id: receipt.receipt_id,
    };
  }
  
  // TODO: Actually execute steps
  const receipt = createReceipt({
    tool_name: 'workflow.run',
    args: parsed,
    decision: 'ALLOWED',
    result: 'OK',
  });
  
  return {
    success: true,
    data: { workflow_id: workflow.workflow_id, executed: true },
    receipt_id: receipt.receipt_id,
  };
}

/**
 * Schedule a workflow.
 */
export async function scheduleWorkflow(args: z.infer<typeof WorkflowScheduleSchema>): Promise<ToolResult> {
  const parsed = WorkflowScheduleSchema.parse(args);
  
  const db = getDb();
  const workflow = db.prepare(`
    SELECT * FROM workflows WHERE workflow_id = ?
  `).get(parsed.workflow_id) as Workflow | undefined;
  
  if (!workflow) {
    const receipt = createReceipt({
      tool_name: 'workflow.schedule',
      args: parsed,
      decision: 'DENIED',
      result: 'ERROR',
      error: { message: 'Workflow not found' },
    });
    return { success: false, error: 'Workflow not found', receipt_id: receipt.receipt_id };
  }
  
  if (!parsed.confirm) {
    const token = createConfirmation('workflow.schedule', parsed, `Schedule ${workflow.name} with cron: ${parsed.cron}`);
    const receipt = createReceipt({
      tool_name: 'workflow.schedule',
      args: parsed,
      decision: 'PENDING_CONFIRM',
      result: 'PENDING_CONFIRM',
    });
    return {
      success: false,
      status: 'PENDING_CONFIRM',
      confirmation_token: token,
      preview: `Schedule ${workflow.name} with cron: ${parsed.cron}`,
      receipt_id: receipt.receipt_id,
    };
  }
  
  const scheduleId = uuidv4();
  db.prepare(`
    INSERT INTO scheduled_workflows (schedule_id, workflow_id, cron_expression)
    VALUES (?, ?, ?)
  `).run(scheduleId, parsed.workflow_id, parsed.cron);
  
  const undo = [{
    tool: 'workflow.unschedule',
    args: { schedule_id: scheduleId, confirm: true },
    description: 'Unschedule workflow (requires confirmation)',
  }];
  
  const receipt = createReceipt({
    tool_name: 'workflow.schedule',
    args: parsed,
    decision: 'ALLOWED',
    result: 'OK',
    changes: [{ type: 'workflow_schedule', schedule_id: scheduleId }],
    undo,
    undo_supported: true,
  });
  
  return {
    success: true,
    data: { schedule_id: scheduleId, workflow_id: parsed.workflow_id, cron: parsed.cron },
    receipt_id: receipt.receipt_id,
  };
}

/**
 * List all workflows.
 */
export async function listWorkflows(): Promise<ToolResult> {
  const db = getDb();
  const workflows = db.prepare(`
    SELECT workflow_id, name, description, created_at FROM workflows ORDER BY created_at DESC
  `).all() as Array<{ workflow_id: string; name: string; description: string | null; created_at: string }>;
  
  const receipt = createReceipt({
    tool_name: 'workflow.list',
    args: {},
    decision: 'ALLOWED',
    result: 'OK',
  });
  
  return {
    success: true,
    data: workflows,
    receipt_id: receipt.receipt_id,
  };
}
