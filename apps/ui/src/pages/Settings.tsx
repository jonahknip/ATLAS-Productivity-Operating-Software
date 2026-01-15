import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import './Settings.css'

interface ProviderConfig {
  name: string
  displayName: string
  description: string
  keyPlaceholder: string
  docsUrl: string
  isLocal?: boolean
}

const PROVIDERS: ProviderConfig[] = [
  {
    name: 'ollama',
    displayName: 'Ollama',
    description: 'Local AI models - runs on your machine, completely free and private.',
    keyPlaceholder: 'http://localhost:11434',
    docsUrl: 'https://ollama.ai',
    isLocal: true,
  },
  {
    name: 'openai',
    displayName: 'OpenAI',
    description: 'GPT-4, GPT-3.5 - high quality cloud models with excellent reasoning.',
    keyPlaceholder: 'sk-...',
    docsUrl: 'https://platform.openai.com/api-keys',
  },
  {
    name: 'anthropic',
    displayName: 'Anthropic',
    description: 'Claude 3 models - excellent for analysis and long-form content.',
    keyPlaceholder: 'sk-ant-...',
    docsUrl: 'https://console.anthropic.com/settings/keys',
  },
  {
    name: 'groq',
    displayName: 'Groq',
    description: 'Ultra-fast inference - great for quick responses.',
    keyPlaceholder: 'gsk_...',
    docsUrl: 'https://console.groq.com/keys',
  },
]

function ProviderSetup({ config }: { config: ProviderConfig }) {
  const queryClient = useQueryClient()
  const [apiKey, setApiKey] = useState('')
  const [showKey, setShowKey] = useState(false)
  const [saved, setSaved] = useState(false)

  const { data: providers } = useQuery({
    queryKey: ['providers'],
    queryFn: api.getProviders,
  })

  const isConnected = providers?.providers?.[config.name]?.status === 'HEALTHY'
  const currentStatus = providers?.providers?.[config.name]?.status || 'NOT_CONFIGURED'

  const saveMutation = useMutation({
    mutationFn: async (key: string) => {
      // Configure the provider on the backend
      const result = await api.configureProvider(config.name, { api_key: key })
      if (!result.success) {
        throw new Error(result.error || 'Failed to configure provider')
      }
      // Also store locally for UI state
      localStorage.setItem(`atlas_${config.name}_key`, key)
      return result
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['providers'] })
      queryClient.invalidateQueries({ queryKey: ['status'] })
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    },
  })

  const testMutation = useMutation({
    mutationFn: () => api.checkProviderHealth(config.name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['providers'] })
    },
  })

  useEffect(() => {
    const storedKey = localStorage.getItem(`atlas_${config.name}_key`)
    if (storedKey) {
      setApiKey(storedKey)
    }
  }, [config.name])

  return (
    <div className={`provider-setup card ${isConnected ? 'connected' : ''}`}>
      <div className="provider-header">
        <div className="provider-info">
          <h3>{config.displayName}</h3>
          <p>{config.description}</p>
        </div>
        <div className={`status-indicator status-${currentStatus.toLowerCase()}`}>
          {currentStatus === 'HEALTHY' ? 'Connected' : 
           currentStatus === 'UNHEALTHY' ? 'Error' : 
           currentStatus === 'NOT_CONFIGURED' ? 'Not Configured' : currentStatus}
        </div>
      </div>

      <div className="provider-config">
        {config.isLocal ? (
          <div className="local-provider-info">
            <p>Ollama runs locally on your machine. Make sure it's running:</p>
            <code>ollama serve</code>
            <p>Then pull a model:</p>
            <code>ollama pull llama3.2</code>
          </div>
        ) : (
          <div className="api-key-input">
            <label htmlFor={`${config.name}-key`}>API Key</label>
            <div className="key-input-wrapper">
              <input
                id={`${config.name}-key`}
                type={showKey ? 'text' : 'password'}
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder={config.keyPlaceholder}
              />
              <button
                type="button"
                className="toggle-visibility"
                onClick={() => setShowKey(!showKey)}
              >
                {showKey ? 'Hide' : 'Show'}
              </button>
            </div>
            <a href={config.docsUrl} target="_blank" rel="noopener noreferrer" className="get-key-link">
              Get your API key →
            </a>
          </div>
        )}
      </div>

      <div className="provider-actions">
        {!config.isLocal && (
          <button
            className="save-btn"
            onClick={() => saveMutation.mutate(apiKey)}
            disabled={!apiKey || saveMutation.isPending}
          >
            {saveMutation.isPending ? 'Saving...' : saved ? 'Saved!' : 'Save Key'}
          </button>
        )}
        <button
          className="test-btn"
          onClick={() => testMutation.mutate()}
          disabled={testMutation.isPending}
        >
          {testMutation.isPending ? 'Testing...' : 'Test Connection'}
        </button>
      </div>

      {testMutation.error && (
        <div className="provider-error">
          Connection failed: {(testMutation.error as Error).message}
        </div>
      )}
    </div>
  )
}

export default function Settings() {
  const [activeTab, setActiveTab] = useState<'providers' | 'general'>('providers')

  return (
    <div className="settings-page">
      <div className="settings-header">
        <h2>Settings</h2>
        <p>Configure your ATLAS instance</p>
      </div>

      <div className="settings-tabs">
        <button
          className={`tab ${activeTab === 'providers' ? 'active' : ''}`}
          onClick={() => setActiveTab('providers')}
        >
          AI Providers
        </button>
        <button
          className={`tab ${activeTab === 'general' ? 'active' : ''}`}
          onClick={() => setActiveTab('general')}
        >
          General
        </button>
      </div>

      <div className="settings-content">
        {activeTab === 'providers' && (
          <div className="providers-settings">
            <div className="settings-section-header">
              <h3>Connect AI Providers</h3>
              <p>
                ATLAS can use multiple AI providers with automatic fallback. 
                Configure at least one provider to get started.
              </p>
            </div>
            <div className="providers-list">
              {PROVIDERS.map((provider) => (
                <ProviderSetup key={provider.name} config={provider} />
              ))}
            </div>
          </div>
        )}

        {activeTab === 'general' && (
          <div className="general-settings">
            <div className="settings-section card">
              <h3>Routing Profile</h3>
              <p>Choose how ATLAS selects AI models for your requests.</p>
              <div className="profile-options">
                <label className="profile-option">
                  <input type="radio" name="profile" value="OFFLINE" />
                  <div className="profile-details">
                    <strong>Offline</strong>
                    <span>Local models only (Ollama) - completely private</span>
                  </div>
                </label>
                <label className="profile-option">
                  <input type="radio" name="profile" value="BALANCED" defaultChecked />
                  <div className="profile-details">
                    <strong>Balanced</strong>
                    <span>Local first, cloud fallback - best of both worlds</span>
                  </div>
                </label>
                <label className="profile-option">
                  <input type="radio" name="profile" value="ACCURACY" />
                  <div className="profile-details">
                    <strong>Accuracy</strong>
                    <span>Cloud first - highest quality results</span>
                  </div>
                </label>
              </div>
            </div>

            <div className="settings-section card">
              <h3>Data & Privacy</h3>
              <div className="setting-item">
                <label>
                  <input type="checkbox" defaultChecked />
                  Store execution history locally
                </label>
              </div>
              <div className="setting-item">
                <label>
                  <input type="checkbox" />
                  Enable telemetry (anonymous usage data)
                </label>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
