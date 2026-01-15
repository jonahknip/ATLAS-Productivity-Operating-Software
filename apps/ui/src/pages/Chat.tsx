import { useState, useRef, useEffect } from 'react'
import { useMutation } from '@tanstack/react-query'
import { api, Receipt } from '@/lib/api'
import './Chat.css'

interface Message {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: Date
  receipt?: Receipt
  isStreaming?: boolean
}

function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === 'user'
  const isSystem = message.role === 'system'

  return (
    <div className={`message ${message.role}`}>
      <div className="message-header">
        <span className="message-role">
          {isUser ? 'You' : isSystem ? 'System' : 'ATLAS'}
        </span>
        <span className="message-time">
          {message.timestamp.toLocaleTimeString()}
        </span>
      </div>
      <div className="message-content">
        {message.content}
        {message.isStreaming && <span className="typing-indicator">...</span>}
      </div>
      {message.receipt && (
        <div className="message-receipt">
          <div className="receipt-summary">
            <span className={`receipt-status status-${message.receipt.status.toLowerCase()}`}>
              {message.receipt.status}
            </span>
            {message.receipt.intent_final && (
              <span className="receipt-intent">
                {message.receipt.intent_final.type}
              </span>
            )}
          </div>
          {message.receipt.tool_calls.length > 0 && (
            <div className="receipt-tools">
              <strong>Actions taken:</strong>
              <ul>
                {message.receipt.tool_calls.map((tc, i) => (
                  <li key={i} className={`tool-call status-${tc.status.toLowerCase()}`}>
                    {tc.tool_name}
                    {tc.status === 'OK' && ' - Done'}
                    {tc.status === 'FAILED' && ` - Failed: ${tc.error}`}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {message.receipt.changes.length > 0 && (
            <div className="receipt-changes">
              <strong>Changes made:</strong>
              <ul>
                {message.receipt.changes.map((c, i) => (
                  <li key={i}>
                    {c.action} {c.entity_type}: {c.entity_id}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {message.receipt.warnings.length > 0 && (
            <div className="receipt-warnings">
              {message.receipt.warnings.map((w, i) => (
                <div key={i} className="warning">{w}</div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 'welcome',
      role: 'system',
      content: 'Welcome to ATLAS. I can help you manage tasks, plan your day, take notes, and more. Just tell me what you need in plain English.',
      timestamp: new Date(),
    },
  ])
  const [input, setInput] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const executeMutation = useMutation({
    mutationFn: api.execute,
    onMutate: () => {
      // Add assistant "thinking" message
      const thinkingId = `thinking-${Date.now()}`
      setMessages((prev) => [
        ...prev,
        {
          id: thinkingId,
          role: 'assistant',
          content: 'Thinking...',
          timestamp: new Date(),
          isStreaming: true,
        },
      ])
      return { thinkingId }
    },
    onSuccess: (receipt, _variables, context) => {
      // Remove thinking message and add real response
      setMessages((prev) => {
        const filtered = prev.filter((m) => m.id !== context?.thinkingId)
        return [
          ...filtered,
          {
            id: receipt.receipt_id,
            role: 'assistant',
            content: formatResponse(receipt),
            timestamp: new Date(),
            receipt,
          },
        ]
      })
    },
    onError: (error, _variables, context) => {
      // Remove thinking message and add error
      setMessages((prev) => {
        const filtered = prev.filter((m) => m.id !== context?.thinkingId)
        return [
          ...filtered,
          {
            id: `error-${Date.now()}`,
            role: 'assistant',
            content: `Sorry, I encountered an error: ${(error as Error).message}`,
            timestamp: new Date(),
          },
        ]
      })
    },
  })

  const formatResponse = (receipt: Receipt): string => {
    if (receipt.status === 'FAILED') {
      return `I couldn't complete that request. ${receipt.errors.join(' ')}`
    }

    const intent = receipt.intent_final?.type || 'UNKNOWN'
    const toolsExecuted = receipt.tool_calls.filter((t) => t.status === 'OK').length
    const changesCount = receipt.changes.length

    let response = ''

    switch (intent) {
      case 'CAPTURE_TASKS':
        response = `I've captured ${changesCount} task(s) for you.`
        break
      case 'PLAN_DAY':
        response = `I've created a plan for your day with ${changesCount} time block(s).`
        break
      case 'SEARCH_SUMMARIZE':
        response = `I found and summarized the relevant information.`
        break
      case 'PROCESS_MEETING_NOTES':
        response = `I've processed your meeting notes and extracted ${changesCount} action item(s).`
        break
      case 'BUILD_WORKFLOW':
        response = `I've created a new workflow for you.`
        break
      default:
        response = toolsExecuted > 0
          ? `Done. I executed ${toolsExecuted} action(s).`
          : `I understood your request but no actions were needed.`
    }

    if (receipt.warnings.length > 0) {
      response += ` Note: ${receipt.warnings[0]}`
    }

    return response
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || executeMutation.isPending) return

    const userMessage: Message = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: input.trim(),
      timestamp: new Date(),
    }

    setMessages((prev) => [...prev, userMessage])
    executeMutation.mutate({ text: input.trim(), routing_profile: 'BALANCED' })
    setInput('')
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e)
    }
  }

  const suggestions = [
    'Create a task to review the quarterly report by Friday',
    'Plan my day tomorrow around my meetings',
    'Search my notes for project deadlines',
    'Capture these tasks: call client, send invoice, update docs',
  ]

  return (
    <div className="chat-page">
      <div className="chat-container">
        <div className="chat-messages">
          {messages.map((message) => (
            <MessageBubble key={message.id} message={message} />
          ))}
          <div ref={messagesEndRef} />
        </div>

        {messages.length === 1 && (
          <div className="chat-suggestions">
            <p>Try saying:</p>
            <div className="suggestions-grid">
              {suggestions.map((s, i) => (
                <button
                  key={i}
                  className="suggestion-btn"
                  onClick={() => setInput(s)}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        <form className="chat-input-form" onSubmit={handleSubmit}>
          <textarea
            ref={inputRef}
            className="chat-input"
            placeholder="Tell me what you need..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={1}
            disabled={executeMutation.isPending}
          />
          <button
            type="submit"
            className="chat-send-btn"
            disabled={!input.trim() || executeMutation.isPending}
          >
            {executeMutation.isPending ? 'Sending...' : 'Send'}
          </button>
        </form>
      </div>
    </div>
  )
}
