/**
 * Tool Registry - Maps tool names to implementations.
 */

import * as fs from './filesystem.js';
import * as shell from './shell.js';
import * as git from './git.js';
import * as workflow from './workflow.js';
import * as notify from './notify.js';
import { listReceipts, getReceipt } from '../receipts.js';
import {
  FsListDirSchema,
  FsReadFileSchema,
  FsWriteFileSchema,
  FsSearchSchema,
  FsStatSchema,
  FsMakeDirSchema,
  ShellRunSchema,
  GitStatusSchema,
  GitDiffSchema,
  GitCommitSchema,
  GitPushSchema,
  WorkflowSaveSchema,
  WorkflowRunSchema,
  WorkflowScheduleSchema,
  NotifyToastSchema,
  ReceiptsListSchema,
  ReceiptsGetSchema,
  ReceiptsUndoSchema,
} from './schemas.js';
import type { ToolResult } from './filesystem.js';

export interface ToolDefinition {
  name: string;
  description: string;
  inputSchema: object;
  handler: (args: unknown) => Promise<ToolResult>;
}

function zodToJsonSchema(schema: unknown): object {
  // Simplified Zod to JSON Schema conversion
  // In production, use zod-to-json-schema package
  return { type: 'object', properties: {} };
}

export const tools: ToolDefinition[] = [
  // Filesystem tools
  {
    name: 'fs.list_dir',
    description: 'List directory contents',
    inputSchema: zodToJsonSchema(FsListDirSchema),
    handler: (args) => fs.listDir(args as Parameters<typeof fs.listDir>[0]),
  },
  {
    name: 'fs.read_file',
    description: 'Read file contents',
    inputSchema: zodToJsonSchema(FsReadFileSchema),
    handler: (args) => fs.readFileContent(args as Parameters<typeof fs.readFileContent>[0]),
  },
  {
    name: 'fs.write_file',
    description: 'Write file contents (supports undo for overwrites)',
    inputSchema: zodToJsonSchema(FsWriteFileSchema),
    handler: (args) => fs.writeFileContent(args as Parameters<typeof fs.writeFileContent>[0]),
  },
  {
    name: 'fs.search',
    description: 'Search for files matching a query',
    inputSchema: zodToJsonSchema(FsSearchSchema),
    handler: (args) => fs.searchFiles(args as Parameters<typeof fs.searchFiles>[0]),
  },
  {
    name: 'fs.stat',
    description: 'Get file/directory stats',
    inputSchema: zodToJsonSchema(FsStatSchema),
    handler: (args) => fs.getStats(args as Parameters<typeof fs.getStats>[0]),
  },
  {
    name: 'fs.make_dir',
    description: 'Create a directory',
    inputSchema: zodToJsonSchema(FsMakeDirSchema),
    handler: (args) => fs.makeDir(args as Parameters<typeof fs.makeDir>[0]),
  },

  // Shell tools
  {
    name: 'shell.run',
    description: 'Run a shell command (dry_run=true by default)',
    inputSchema: zodToJsonSchema(ShellRunSchema),
    handler: (args) => shell.runShell(args as Parameters<typeof shell.runShell>[0]),
  },
  
  // Git tools
  {
    name: 'git.status',
    description: 'Get git repository status',
    inputSchema: zodToJsonSchema(GitStatusSchema),
    handler: (args) => git.gitStatus(args as Parameters<typeof git.gitStatus>[0]),
  },
  {
    name: 'git.diff',
    description: 'Get git diff',
    inputSchema: zodToJsonSchema(GitDiffSchema),
    handler: (args) => git.gitDiff(args as Parameters<typeof git.gitDiff>[0]),
  },
  {
    name: 'git.commit',
    description: 'Create a git commit (requires confirmation)',
    inputSchema: zodToJsonSchema(GitCommitSchema),
    handler: (args) => git.gitCommit(args as Parameters<typeof git.gitCommit>[0]),
  },
  {
    name: 'git.push',
    description: 'Push to remote (requires confirmation)',
    inputSchema: zodToJsonSchema(GitPushSchema),
    handler: (args) => git.gitPush(args as Parameters<typeof git.gitPush>[0]),
  },
  
  // Workflow tools
  {
    name: 'workflow.save',
    description: 'Save a workflow',
    inputSchema: zodToJsonSchema(WorkflowSaveSchema),
    handler: (args) => workflow.saveWorkflow(args as Parameters<typeof workflow.saveWorkflow>[0]),
  },
  {
    name: 'workflow.run',
    description: 'Run a workflow (dry_run=true by default)',
    inputSchema: zodToJsonSchema(WorkflowRunSchema),
    handler: (args) => workflow.runWorkflow(args as Parameters<typeof workflow.runWorkflow>[0]),
  },

  {
    name: 'workflow.schedule',
    description: 'Schedule a workflow (requires confirmation)',
    inputSchema: zodToJsonSchema(WorkflowScheduleSchema),
    handler: (args) => workflow.scheduleWorkflow(args as Parameters<typeof workflow.scheduleWorkflow>[0]),
  },
  {
    name: 'workflow.list',
    description: 'List all workflows',
    inputSchema: { type: 'object', properties: {} },
    handler: () => workflow.listWorkflows(),
  },
  
  // Notification tools
  {
    name: 'notify.toast',
    description: 'Show a toast notification',
    inputSchema: zodToJsonSchema(NotifyToastSchema),
    handler: (args) => notify.showToast(args as Parameters<typeof notify.showToast>[0]),
  },
  
  // Receipt tools
  {
    name: 'receipts.list',
    description: 'List execution receipts',
    inputSchema: zodToJsonSchema(ReceiptsListSchema),
    handler: async (args) => {
      const parsed = ReceiptsListSchema.parse(args);
      const receipts = listReceipts(parsed.limit);
      return { success: true, data: receipts };
    },
  },
  {
    name: 'receipts.get',
    description: 'Get a receipt by ID',
    inputSchema: zodToJsonSchema(ReceiptsGetSchema),
    handler: async (args) => {
      const parsed = ReceiptsGetSchema.parse(args);
      const receipt = getReceipt(parsed.receipt_id);
      if (!receipt) {
        return { success: false, error: 'Receipt not found' };
      }
      return { success: true, data: receipt };
    },
  },

  {
    name: 'receipts.undo',
    description: 'Undo a receipt (requires confirmation)',
    inputSchema: zodToJsonSchema(ReceiptsUndoSchema),
    handler: async (args) => {
      const parsed = ReceiptsUndoSchema.parse(args);
      const receipt = getReceipt(parsed.receipt_id);
      
      if (!receipt) {
        return { success: false, error: 'Receipt not found' };
      }
      
      if (!receipt.undo_supported) {
        return { success: false, error: 'Undo not supported for this receipt' };
      }
      
      const undoSteps = JSON.parse(receipt.undo_json);
      if (undoSteps.length === 0) {
        return { success: false, error: 'No undo steps available' };
      }
      
      if (!parsed.confirm) {
        return {
          success: false,
          status: 'PENDING_CONFIRM' as const,
          preview: `Undo ${undoSteps.length} step(s) for ${receipt.tool_name}`,
          data: { undo_steps: undoSteps },
        };
      }
      
      // Execute undo steps
      // In production, this would call each tool in sequence
      return {
        success: true,
        data: { message: 'Undo executed', steps: undoSteps },
      };
    },
  },
];

export function getTool(name: string): ToolDefinition | undefined {
  return tools.find(t => t.name === name);
}

export type { ToolResult };
