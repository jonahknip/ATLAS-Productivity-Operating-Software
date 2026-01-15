import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api, ProviderStatus } from '@/lib/api'
import './Providers.css'

function ProviderCard({
  name,
  status,
  onRefresh,
  isRefreshing,
}: {
  name: string
  status: ProviderStatus
  onRefresh: () => void
  isRefreshing: boolean
}) {
  const statusClass = {
    HEALTHY: 'badge-success',
    DEGRADED: 'badge-warning',
    UNHEALTHY: 'badge-error',
    UNKNOWN: 'badge-info',
  }[status.status]

  return (
    <div className="provider-card card">
      <div className="provider-header">
        <h3 className="provider-name">{name}</h3>
        <span className={`badge ${statusClass}`}>{status.status}</span>
      </div>

      <div className="provider-details">
        {status.latency_ms != null && (
          <div className="detail-row">
            <span className="detail-label">Latency</span>
            <span className="detail-value">{status.latency_ms}ms</span>
          </div>
        )}

        {status.last_check && (
          <div className="detail-row">
            <span className="detail-label">Last Check</span>
            <span className="detail-value">
              {new Date(status.last_check).toLocaleTimeString()}
            </span>
          </div>
        )}

        {status.error && (
          <div className="provider-error">{status.error}</div>
        )}
      </div>

      <div className="provider-actions">
        <button
          className="refresh-btn"
          onClick={onRefresh}
          disabled={isRefreshing}
        >
          {isRefreshing ? 'Checking...' : 'Refresh'}
        </button>
      </div>
    </div>
  )
}

export default function Providers() {
  const queryClient = useQueryClient()

  const { data, isLoading, error } = useQuery({
    queryKey: ['providers'],
    queryFn: api.getProviders,
    refetchInterval: 60000, // Refresh every minute
  })

  const healthMutation = useMutation({
    mutationFn: (name: string) => api.checkProviderHealth(name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['providers'] })
      queryClient.invalidateQueries({ queryKey: ['status'] })
    },
  })

  if (isLoading) {
    return <div className="providers-loading">Loading providers...</div>
  }

  if (error) {
    return (
      <div className="providers-error">
        Error loading providers: {(error as Error).message}
      </div>
    )
  }

  const providers = data?.providers ?? {}

  return (
    <div className="providers-page">
      <div className="providers-header">
        <h2>Model Providers</h2>
        <p className="providers-description">
          Configure and monitor your AI model providers. ATLAS supports local
          (Ollama) and cloud (OpenAI) providers with automatic fallback.
        </p>
      </div>

      {Object.keys(providers).length === 0 ? (
        <div className="providers-empty card">
          <p>No providers configured. Add your API keys to get started.</p>
        </div>
      ) : (
        <div className="providers-grid">
          {Object.entries(providers).map(([name, status]) => (
            <ProviderCard
              key={name}
              name={name}
              status={status}
              onRefresh={() => healthMutation.mutate(name)}
              isRefreshing={
                healthMutation.isPending &&
                healthMutation.variables === name
              }
            />
          ))}
        </div>
      )}

      <div className="providers-info card">
        <h3>Routing Profiles</h3>
        <div className="profile-info">
          <div className="profile-item">
            <strong>Offline</strong>
            <span>Local models only (Ollama)</span>
          </div>
          <div className="profile-item">
            <strong>Balanced</strong>
            <span>Local first, cloud fallback</span>
          </div>
          <div className="profile-item">
            <strong>Accuracy</strong>
            <span>Cloud first for best results</span>
          </div>
        </div>
      </div>
    </div>
  )
}
