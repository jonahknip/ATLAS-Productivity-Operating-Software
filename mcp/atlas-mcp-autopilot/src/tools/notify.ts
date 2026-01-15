/**
 * Notification Tools Implementation
 */

import { z } from 'zod';
import { NotifyToastSchema } from './schemas.js';
import { createReceipt } from '../receipts.js';
import type { ToolResult } from './filesystem.js';

/**
 * Show a toast notification.
 */
export async function showToast(args: z.infer<typeof NotifyToastSchema>): Promise<ToolResult> {
  const parsed = NotifyToastSchema.parse(args);
  
  // In a real implementation, this would trigger a native notification
  // For now, we just log it and return success
  console.log(`[TOAST][${parsed.severity}] ${parsed.title}: ${parsed.message}`);
  
  const receipt = createReceipt({
    tool_name: 'notify.toast',
    args: parsed,
    decision: 'ALLOWED',
    result: 'OK',
  });
  
  return {
    success: true,
    data: {
      title: parsed.title,
      message: parsed.message,
      severity: parsed.severity,
      displayed: true,
    },
    receipt_id: receipt.receipt_id,
  };
}
