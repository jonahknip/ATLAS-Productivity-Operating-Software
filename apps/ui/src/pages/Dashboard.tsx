import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { api, Receipt } from '@/lib/api'
import './Dashboard.css'

type RoutingProfile = 'OFFLINE' | 'BALANCED' | 'ACCURACY'

function LastReceiptPreview({ receipt }: { receipt: Receipt }) {
  return (
    <div className="last-receipt-preview">
      <div className="preview-header">
        <span className={`badge badge-${receipt.status.toLowerCase()}`}>
          {receipt.status}
        </span>
        <span className="preview-time">
          {new Date(receipt.timestamp_utc).toLocaleTimeString()}
        </span>
      </div>
      <div className="preview-input">{receipt.user_input}</div>
      {receipt.intent_final && (
        <div className="preview-intent">
          <span className="intent-type">{receipt.intent_final.type}</span>
          <span className="intent-confidence">
            {Math.round(receipt.intent_final.confidence * 100)}%
          </span>
        </div>
      )}
      <div className="preview-models">
        {receipt.models_attempted
          .filter(m => m.success)
          .map((m, i) => (
            <span key={i} className="model-tag">
              {m.provider}:{m.model}
            </span>
          ))}
        {receipt.models_attempted.filter(m => m.success).length === 0 && (
          <span className="model-tag failed">No successful model</span>
        )}
      </div>
    </div>
  )
}

export default function Dashboard() {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [input, setInput] = useState('')
  const [profile, setProfile] = useState<RoutingProfile>('BALANCED')
  const [lastReceipt, setLastReceipt] = useState<Receipt | null>(null)

  const { data: status } = useQuery({
    queryKey: ['status'],
    queryFn: api.getStatus,
  })

  const executeMutation = useMutation({
    mutationFn: api.execute,
    onSuccess: (receipt) => {
      queryClient.invalidateQueries({ queryKey: ['receipts'] })
      setLastReceipt(receipt)
      setInput('')
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim()) return

    executeMutation.mutate({
      text: input.trim(),
      routing_profile: profile,
    })
  }

  // Count healthy providers
  const providers = status?.providers ?? {}
  const healthyCount = Object.values(providers).filter(
    (p) => p.status === 'HEALTHY'
  ).length

  return (
    <div className="dashboard">
      <div className="dashboard-header">
        <h2>Command Center</h2>
        <div className="status-badges">
          <span className={`badge ${healthyCount > 0 ? 'badge-success' : 'badge-warning'}`}>
            {healthyCount} Provider{healthyCount !== 1 ? 's' : ''} Online
          </span>
          {status?.receipts_count !== undefined && (
            <span className="badge badge-info">
              {status.receipts_count} Receipt{status.receipts_count !== 1 ? 's' : ''}
            </span>
          )}
        </div>
      </div>

      <form className="input-section card" onSubmit={handleSubmit}>
        <div className="profile-selector">
          <label>Routing Profile:</label>
          <div className="profile-buttons">
            {(['OFFLINE', 'BALANCED', 'ACCURACY'] as const).map((p) => (
              <button
                key={p}
                type="button"
                className={`profile-btn ${profile === p ? 'active' : ''}`}
                onClick={() => setProfile(p)}
              >
                {p.toLowerCase()}
              </button>
            ))}
          </div>
        </div>

        <textarea
          className="command-input"
          placeholder="Enter your command... (e.g., 'Capture: buy dog food, pay electric bill')"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          rows={3}
        />

        <div className="input-actions">
          <button
            type="submit"
            className="execute-btn"
            disabled={!input.trim() || executeMutation.isPending}
          >
            {executeMutation.isPending ? 'Processing...' : 'Execute'}
          </button>
        </div>

        {executeMutation.error && (
          <div className="error-message">
            {(executeMutation.error as Error).message}
          </div>
        )}
      </form>

      {lastReceipt && (
        <div className="last-receipt card">
          <div className="last-receipt-header">
            <h3>Last Execution</h3>
            <button
              className="view-receipt-btn"
              onClick={() => navigate('/receipts')}
            >
              View All Receipts
            </button>
          </div>
          <LastReceiptPreview receipt={lastReceipt} />
        </div>
      )}

      <div className="quick-actions card">
        <h3>Demo Prompts</h3>
        <div className="demo-grid">
          <button
            className="demo-btn"
            onClick={() =>
              setInput('Capture: buy dog food, pay electric bill, finish GIS module by Friday')
            }
          >
            Demo A: Capture Tasks
          </button>
          <button
            className="demo-btn"
            onClick={() =>
              setInput('Plan my day around my calendar and these tasks: review PR, write docs, team standup')
            }
          >
            Demo B: Plan Day
          </button>
          <button
            className="demo-btn"
            onClick={() =>
              setInput('Search my notes for project deadlines and summarize them')
            }
          >
            Demo C: Search & Summarize
          </button>
        </div>
      </div>
    </div>
  )
}
