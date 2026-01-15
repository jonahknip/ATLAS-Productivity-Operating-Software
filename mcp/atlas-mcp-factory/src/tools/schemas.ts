/**
 * Zod schemas for factory tools
 */

import { z } from 'zod';

// Project initialization
export const ProjectInitSchema = z.object({
  name: z.string().min(1).max(100),
  template: z.enum(['basic', 'webapp', 'api', 'cli', 'monorepo']).default('basic'),
  output_dir: z.string().min(1),
  options: z.object({
    typescript: z.boolean().default(true),
    git: z.boolean().default(true),
    docker: z.boolean().default(false),
    ci: z.boolean().default(false),
  }).default({}),
});

// Asset writing
export const AssetWriteSchema = z.object({
  path: z.string().min(1),
  content: z.string(),
  overwrite: z.boolean().default(false),
});

export const AssetWriteBatchSchema = z.object({
  base_dir: z.string().min(1),
  assets: z.array(z.object({
    relative_path: z.string().min(1),
    content: z.string(),
  })).min(1),
  overwrite: z.boolean().default(false),
});

// Bundle generation
export const BundleGenerateSchema = z.object({
  name: z.string().min(1),
  source_dir: z.string().min(1),
  output_path: z.string().min(1),
  format: z.enum(['zip', 'tar', 'tar.gz']).default('zip'),
  include: z.array(z.string()).default(['**/*']),
  exclude: z.array(z.string()).default(['node_modules/**', '.git/**', 'dist/**']),
});

// Template listing
export const TemplateListSchema = z.object({
  category: z.enum(['project', 'file', 'component']).nullable().default(null),
});

// Template application
export const TemplateApplySchema = z.object({
  template_id: z.string().min(1),
  output_dir: z.string().min(1),
  variables: z.record(z.string()).default({}),
});
