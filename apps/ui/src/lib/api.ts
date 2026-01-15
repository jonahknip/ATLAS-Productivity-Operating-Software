/**
 * ATLAS API client
 * 
 * Uses v1 API endpoints for all operations.
 */

const API_BASE = '/api'
const V1_BASE = '/v1'

export interface StatusResponse {
  version: string
  providers: Record<string, ProviderStatus>
  receipts_count: number
  config: {
    routing_caps: {
      max_attempts_per_model: number
      max_models_per_request: number
    }
  }
}

export interface ProviderStatus {
  registered: boolean
  status: 'HEALTHY' | 'DEGRADED' | 'UNHEALTHY' | 'UNKNOWN'
  last_check: string | null
  latency_ms: number | null
  error: string | null
}

export interface ProviderHealthResponse {
  provider: string
  status: string
  latency_ms: number | null
  models_available: string[] | null
  error: string | null
}

export interface Receipt {
  receipt_id: string
  timestamp_utc: string
  profile_id: string | null
  status: 'SUCCESS' | 'PARTIAL' | 'FAILED' | 'PENDING_CONFIRM'
  user_input: string
  models_attempted: ModelAttempt[]
  intent_final: Intent | null
  tool_calls: ToolCall[]
  changes: Change[]
  undo: UndoStep[]
  warnings: string[]
  errors: string[]
}

export interface ModelAttempt {
  provider: string
  model: string
  attempt_number: number
  success: boolean
  fallback_trigger: string | null
  latency_ms: number | null
  timestamp_utc: string
}

export interface Intent {
  type: string
  confidence: number
  parameters: Record<string, unknown>
  raw_entities: string[]
}

export interface ToolCall {
  tool_name: string
  args: Record<string, unknown>
  status: 'PENDING_CONFIRM' | 'OK' | 'FAILED' | 'SKIPPED'
  result: unknown
  error: string | null
  timestamp_utc: string
}

export interface Change {
  entity_type: string
  entity_id: string
  action: string
  before: Record<string, unknown> | null
  after: Record<string, unknown> | null
}

export interface UndoStep {
  tool_name: string
  args: Record<string, unknown>
  description: string
}

export interface ReceiptsListResponse {
  receipts: Receipt[]
  total: number
  limit: number
  offset: number
}

export interface UndoResponse {
  success: boolean
  receipt_id: string
  message: string
  undo_steps_executed: number
}

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  })

  if (!response.ok) {
    const errorText = await response.text().catch(() => response.statusText)
    throw new Error(`API error: ${response.status} - ${errorText}`)
  }

  return response.json()
}

export const api = {
  // Status & Health (legacy /api endpoints)
  getStatus: () => fetchJson<StatusResponse>(`${API_BASE}/status`),

  getProviders: () =>
    fetchJson<{ providers: Record<string, ProviderStatus> }>(`${API_BASE}/providers`),

  checkProviderHealth: (name: string) =>
    fetchJson<ProviderHealthResponse>(`${API_BASE}/providers/${name}/health`, {
      method: 'POST',
    }),

  getProviderModels: (name: string) =>
    fetchJson<{ provider: string; models: string[] }>(`${API_BASE}/providers/${name}/models`),

  // Receipts (v1 API)
  getReceipts: (params?: { limit?: number; offset?: number; status?: string }) => {
    const searchParams = new URLSearchParams()
    if (params?.limit) searchParams.set('limit', params.limit.toString())
    if (params?.offset) searchParams.set('offset', params.offset.toString())
    if (params?.status) searchParams.set('status', params.status)
    const query = searchParams.toString()
    return fetchJson<ReceiptsListResponse>(`${V1_BASE}/receipts${query ? `?${query}` : ''}`)
  },

  getReceipt: (id: string) => fetchJson<Receipt>(`${V1_BASE}/receipts/${id}`),

  undoReceipt: (id: string) =>
    fetchJson<UndoResponse>(`${V1_BASE}/receipts/${id}/undo`, {
      method: 'POST',
    }),

  // Execute (v1 API)
  execute: (input: { text: string; routing_profile?: string; profile_id?: string }) =>
    fetchJson<Receipt>(`${V1_BASE}/execute`, {
      method: 'POST',
      body: JSON.stringify(input),
    }),
}
