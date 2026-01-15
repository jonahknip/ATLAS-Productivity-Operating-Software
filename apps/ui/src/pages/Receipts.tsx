import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api, Receipt, ModelAttempt, ToolCall, UndoStep, Change } from '@/lib/api'
import './Receipts.css'

function StatusBadge({ status }: { status: Receipt['status'] }) {
  const badgeClass = {
    SUCCESS: 'badge-success',
    PARTIAL: 'badge-warning',
    FAILED: 'badge-error',
    PENDING_CONFIRM: 'badge-info',
  }[status]

  return <span className={`badge ${badgeClass}`}>{status}</span>
}

function formatTime(isoString: string): string {
  return new Date(isoString).toLocaleString()
}

function formatLatency(ms: number | null): string {
  if (ms === null) return '-'
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(2)}s`
}

// Receipt list item (compact view)
function ReceiptListItem({
  receipt,
  isSelected,
  onClick,
}: {
  receipt: Receipt
  isSelected: boolean
  onClick: () => void
}) {
  const modelsSummary = receipt.models_attempted
    .filter(m => m.success)
    .map(m => `${m.provider}:${m.model}`)
    .join(', ') || 'No successful model'

  return (
    <div
      className={`receipt-list-item ${isSelected ? 'selected' : ''}`}
      onClick={onClick}
    >
      <div className="receipt-item-header">
        <StatusBadge status={receipt.status} />
        <time className="receipt-item-time">
          {formatTime(receipt.timestamp_utc)}
        </time>
      </div>
      <div className="receipt-item-input">{receipt.user_input}</div>
      <div className="receipt-item-meta">
        {receipt.intent_final && (
          <span className="intent-badge">{receipt.intent_final.type}</span>
        )}
        <span className="models-summary">{modelsSummary}</span>
      </div>
    </div>
  )
}

// Models Attempted Section
function ModelsSection({ attempts }: { attempts: ModelAttempt[] }) {
  if (attempts.length === 0) {
    return (
      <div className="detail-section">
        <h4>Models Attempted</h4>
        <p className="empty-state">No model attempts recorded</p>
      </div>
    )
  }

  return (
    <div className="detail-section">
      <h4>Models Attempted ({attempts.length})</h4>
      <div className="attempts-list">
        {attempts.map((attempt, i) => (
          <div key={i} className={`attempt-item ${attempt.success ? 'success' : 'failed'}`}>
            <div className="attempt-model">
              <span className="provider">{attempt.provider}</span>
              <span className="model">{attempt.model}</span>
              <span className="attempt-num">#{attempt.attempt_number}</span>
            </div>
            <div className="attempt-details">
              <span className={`attempt-status ${attempt.success ? 'success' : 'failed'}`}>
                {attempt.success ? 'SUCCESS' : 'FAILED'}
              </span>
              {attempt.fallback_trigger && (
                <span className="fallback-trigger">{attempt.fallback_trigger}</span>
              )}
              <span className="latency">{formatLatency(attempt.latency_ms)}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// Intent Section
function IntentSection({ intent }: { intent: Receipt['intent_final'] }) {
  if (!intent) {
    return (
      <div className="detail-section">
        <h4>Intent</h4>
        <p className="empty-state">No intent classified</p>
      </div>
    )
  }

  return (
    <div className="detail-section">
      <h4>Intent</h4>
      <div className="intent-detail">
        <div className="intent-row">
          <span className="label">Type:</span>
          <span className="intent-type-badge">{intent.type}</span>
        </div>
        <div className="intent-row">
          <span className="label">Confidence:</span>
          <span className="confidence">{Math.round(intent.confidence * 100)}%</span>
        </div>
        {intent.raw_entities.length > 0 && (
          <div className="intent-row">
            <span className="label">Entities:</span>
            <div className="entities-list">
              {intent.raw_entities.map((entity, i) => (
                <span key={i} className="entity-tag">{entity}</span>
              ))}
            </div>
          </div>
        )}
        {Object.keys(intent.parameters).length > 0 && (
          <div className="intent-row">
            <span className="label">Parameters:</span>
            <pre className="params-json">{JSON.stringify(intent.parameters, null, 2)}</pre>
          </div>
        )}
      </div>
    </div>
  )
}

// Tool Calls Section
function ToolCallsSection({ toolCalls }: { toolCalls: ToolCall[] }) {
  if (toolCalls.length === 0) {
    return (
      <div className="detail-section">
        <h4>Tool Calls</h4>
        <p className="empty-state">No tools executed</p>
      </div>
    )
  }

  return (
    <div className="detail-section">
      <h4>Tool Calls ({toolCalls.length})</h4>
      <div className="tool-calls-list">
        {toolCalls.map((tc, i) => (
          <div key={i} className={`tool-call-item ${tc.status.toLowerCase()}`}>
            <div className="tool-call-header">
              <span className="tool-name">{tc.tool_name}</span>
              <span className={`tool-status ${tc.status.toLowerCase()}`}>{tc.status}</span>
            </div>
            {Object.keys(tc.args).length > 0 && (
              <div className="tool-args">
                <span className="label">Args:</span>
                <pre>{JSON.stringify(tc.args, null, 2)}</pre>
              </div>
            )}
            {tc.result && (
              <div className="tool-result">
                <span className="label">Result:</span>
                <pre>{JSON.stringify(tc.result, null, 2)}</pre>
              </div>
            )}
            {tc.error && (
              <div className="tool-error">{tc.error}</div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

// Changes Section
function ChangesSection({ changes }: { changes: Change[] }) {
  if (changes.length === 0) {
    return (
      <div className="detail-section">
        <h4>Changes</h4>
        <p className="empty-state">No changes recorded</p>
      </div>
    )
  }

  return (
    <div className="detail-section">
      <h4>Changes ({changes.length})</h4>
      <div className="changes-list">
        {changes.map((change, i) => (
          <div key={i} className="change-item">
            <span className="change-action">{change.action}</span>
            <span className="change-type">{change.entity_type}</span>
            <code className="change-id">{change.entity_id}</code>
          </div>
        ))}
      </div>
    </div>
  )
}

// Undo Section
function UndoSection({
  undoSteps,
  receiptId,
  onUndo,
  isUndoing,
}: {
  undoSteps: UndoStep[]
  receiptId: string
  onUndo: () => void
  isUndoing: boolean
}) {
  const hasUndoSteps = undoSteps.length > 0

  return (
    <div className="detail-section undo-section">
      <h4>Undo</h4>
      {!hasUndoSteps ? (
        <p className="empty-state">No undo steps available</p>
      ) : (
        <>
          <div className="undo-steps-list">
            {undoSteps.map((step, i) => (
              <div key={i} className="undo-step">
                <span className="undo-tool">{step.tool_name}</span>
                <span className="undo-desc">{step.description}</span>
              </div>
            ))}
          </div>
          <button
            className="undo-btn"
            onClick={onUndo}
            disabled={isUndoing}
          >
            {isUndoing ? 'Undoing...' : `Undo ${undoSteps.length} Step${undoSteps.length > 1 ? 's' : ''}`}
          </button>
        </>
      )}
    </div>
  )
}

// Warnings/Errors Section
function IssuesSection({ warnings, errors }: { warnings: string[]; errors: string[] }) {
  if (warnings.length === 0 && errors.length === 0) {
    return null
  }

  return (
    <div className="detail-section issues-section">
      <h4>Issues</h4>
      {errors.length > 0 && (
        <div className="errors-list">
          {errors.map((err, i) => (
            <div key={i} className="error-item">{err}</div>
          ))}
        </div>
      )}
      {warnings.length > 0 && (
        <div className="warnings-list">
          {warnings.map((warn, i) => (
            <div key={i} className="warning-item">{warn}</div>
          ))}
        </div>
      )}
    </div>
  )
}

// Receipt Detail Panel
function ReceiptDetail({
  receipt,
  onClose,
}: {
  receipt: Receipt
  onClose: () => void
}) {
  const queryClient = useQueryClient()

  const undoMutation = useMutation({
    mutationFn: () => api.undoReceipt(receipt.receipt_id),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['receipts'] })
      alert(data.message)
    },
  })

  return (
    <div className="receipt-detail">
      <div className="detail-header">
        <div className="detail-title">
          <StatusBadge status={receipt.status} />
          <h3>Receipt Detail</h3>
        </div>
        <button className="close-btn" onClick={onClose}>×</button>
      </div>

      <div className="detail-meta">
        <div className="meta-row">
          <span className="label">ID:</span>
          <code>{receipt.receipt_id}</code>
        </div>
        <div className="meta-row">
          <span className="label">Time:</span>
          <span>{formatTime(receipt.timestamp_utc)}</span>
        </div>
        {receipt.profile_id && (
          <div className="meta-row">
            <span className="label">Profile:</span>
            <span>{receipt.profile_id}</span>
          </div>
        )}
      </div>

      <div className="detail-input">
        <h4>User Input</h4>
        <div className="input-text">{receipt.user_input}</div>
      </div>

      <div className="detail-body">
        <ModelsSection attempts={receipt.models_attempted} />
        <IntentSection intent={receipt.intent_final} />
        <ToolCallsSection toolCalls={receipt.tool_calls} />
        <ChangesSection changes={receipt.changes} />
        <UndoSection
          undoSteps={receipt.undo}
          receiptId={receipt.receipt_id}
          onUndo={() => undoMutation.mutate()}
          isUndoing={undoMutation.isPending}
        />
        <IssuesSection warnings={receipt.warnings} errors={receipt.errors} />
      </div>
    </div>
  )
}

// Main Receipts Page
export default function Receipts() {
  const [selectedId, setSelectedId] = useState<string | null>(null)
  
  const { data, isLoading, error } = useQuery({
    queryKey: ['receipts'],
    queryFn: () => api.getReceipts({ limit: 50 }),
    refetchInterval: 5000, // Auto-refresh every 5 seconds
  })

  if (isLoading) {
    return <div className="receipts-loading">Loading receipts...</div>
  }

  if (error) {
    return (
      <div className="receipts-error">
        Error loading receipts: {(error as Error).message}
      </div>
    )
  }

  const receipts = data?.receipts ?? []
  const selectedReceipt = receipts.find(r => r.receipt_id === selectedId)

  return (
    <div className="receipts-page">
      <div className="receipts-header">
        <h2>Execution Receipts</h2>
        <span className="receipt-count">{data?.total ?? 0} total</span>
      </div>

      <div className="receipts-layout">
        <div className="receipts-list-panel">
          {receipts.length === 0 ? (
            <div className="receipts-empty">
              <p>No receipts yet.</p>
              <p>Execute a command to generate your first receipt.</p>
            </div>
          ) : (
            <div className="receipts-list">
              {receipts.map((receipt) => (
                <ReceiptListItem
                  key={receipt.receipt_id}
                  receipt={receipt}
                  isSelected={receipt.receipt_id === selectedId}
                  onClick={() => setSelectedId(
                    receipt.receipt_id === selectedId ? null : receipt.receipt_id
                  )}
                />
              ))}
            </div>
          )}
        </div>

        {selectedReceipt && (
          <div className="receipts-detail-panel">
            <ReceiptDetail
              receipt={selectedReceipt}
              onClose={() => setSelectedId(null)}
            />
          </div>
        )}
      </div>
    </div>
  )
}
