/**
 * ATLAS MCP Autopilot Server
 * Local Operations MCP Server with security policy enforcement.
 */

import express from 'express';
import { z } from 'zod';
import { tools, getTool, type ToolResult } from './tools/index.js';
import { getDb, closeDb } from './db/index.js';

const app = express();
app.use(express.json());

const PORT = process.env.PORT || 3100;

// Request schemas
const CallRequestSchema = z.object({
  tool: z.string().min(1),
  args: z.record(z.unknown()).default({}),
});

// Health check
app.get('/health', (_req, res) => {
  res.json({ ok: true, server: 'atlas-mcp-autopilot', timestamp: new Date().toISOString() });
});

// List available tools
app.get('/mcp/tools', (_req, res) => {
  const toolList = tools.map(t => ({
    name: t.name,
    description: t.description,
    inputSchema: t.inputSchema,
  }));
  res.json({ tools: toolList });
});
