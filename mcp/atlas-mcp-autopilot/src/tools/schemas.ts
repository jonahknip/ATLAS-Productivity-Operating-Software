/**
 * Zod schemas for all tool inputs/outputs.
 */

import { z } from 'zod';

// Common schemas
export const ConfirmSchema = z.object({
  confirm: z.boolean().default(false),
  confirmation_token: z.string().uuid().optional(),
});

// Filesystem schemas
export const FsListDirSchema = z.object({
  path: z.string().min(1),
});

export const FsReadFileSchema = z.object({
  path: z.string().min(1),
});

export const FsWriteFileSchema = z.object({
  path: z.string().min(1),
  content: z.string(),
  mode: z.enum(['overwrite', 'append']).default('overwrite'),
}).merge(ConfirmSchema);

export const FsSearchSchema = z.object({
  path: z.string().min(1),
  query: z.string().min(1),
  max_results: z.number().int().min(1).max(500).default(50),
});

export const FsStatSchema = z.object({
  path: z.string().min(1),
});

export const FsMakeDirSchema = z.object({
  path: z.string().min(1),
});

// Shell schemas
export const ShellRunSchema = z.object({
  command: z.string().min(1),
  cwd: z.string().nullable().default(null),
  timeout_sec: z.number().int().min(1).max(300).default(30),
  dry_run: z.boolean().default(true),
}).merge(ConfirmSchema);

// Git schemas
export const GitStatusSchema = z.object({
  repo_path: z.string().min(1),
});

export const GitDiffSchema = z.object({
  repo_path: z.string().min(1),
  staged: z.boolean().default(false),
});

export const GitCommitSchema = z.object({
  repo_path: z.string().min(1),
  message: z.string().min(1),
  add_all: z.boolean().default(false),
}).merge(ConfirmSchema);

export const GitPushSchema = z.object({
  repo_path: z.string().min(1),
  remote: z.string().default('origin'),
  branch: z.string().nullable().default(null),
}).merge(ConfirmSchema);

// Workflow schemas
export const WorkflowStepSchema = z.object({
  tool: z.string(),
  args: z.record(z.unknown()),
});

export const WorkflowSaveSchema = z.object({
  workflow_json: z.object({
    name: z.string().min(1),
    description: z.string().optional(),
    steps: z.array(WorkflowStepSchema).min(1),
  }),
});

export const WorkflowRunSchema = z.object({
  workflow_id: z.string().uuid(),
  dry_run: z.boolean().default(true),
});

export const WorkflowScheduleSchema = z.object({
  workflow_id: z.string().uuid(),
  cron: z.string().min(1),
}).merge(ConfirmSchema);

// Notification schemas
export const NotifyToastSchema = z.object({
  title: z.string().min(1),
  message: z.string().min(1),
  severity: z.enum(['INFO', 'WARN', 'ERROR']).default('INFO'),
});

// Receipts schemas
export const ReceiptsListSchema = z.object({
  limit: z.number().int().min(1).max(200).default(50),
});

export const ReceiptsGetSchema = z.object({
  receipt_id: z.string().uuid(),
});

export const ReceiptsUndoSchema = z.object({
  receipt_id: z.string().uuid(),
}).merge(ConfirmSchema);
