import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import './Tasks.css'

interface Task {
  task_id: string
  title: string
  description?: string
  due_date?: string
  priority: 'low' | 'medium' | 'high'
  status: 'pending' | 'in_progress' | 'completed' | 'cancelled'
  tags?: string[]
  created_at: string
  updated_at?: string
}

// API base URL
const API_URL = import.meta.env.VITE_ATLAS_API_URL || ''
const API_BASE = `${API_URL}/api`

async function fetchTasks(): Promise<{ tasks: Task[] }> {
  const response = await fetch(`${API_BASE}/tasks`)
  if (!response.ok) {
    // If API doesn't have this endpoint yet, return empty
    return { tasks: [] }
  }
  return response.json()
}

async function createTask(task: Partial<Task>): Promise<Task> {
  const response = await fetch(`${API_BASE}/tasks`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(task),
  })
  return response.json()
}

async function updateTask(taskId: string, updates: Partial<Task>): Promise<Task> {
  const response = await fetch(`${API_BASE}/tasks/${taskId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(updates),
  })
  return response.json()
}

async function deleteTask(taskId: string): Promise<void> {
  await fetch(`${API_BASE}/tasks/${taskId}`, { method: 'DELETE' })
}

function TaskCard({ 
  task, 
  onToggleComplete, 
  onDelete 
}: { 
  task: Task
  onToggleComplete: (task: Task) => void
  onDelete: (taskId: string) => void
}) {
  const isCompleted = task.status === 'completed'
  
  return (
    <div className={`task-card ${isCompleted ? 'completed' : ''} priority-${task.priority}`}>
      <div className="task-checkbox">
        <input
          type="checkbox"
          checked={isCompleted}
          onChange={() => onToggleComplete(task)}
        />
      </div>
      <div className="task-content">
        <div className="task-title">{task.title}</div>
        {task.description && (
          <div className="task-description">{task.description}</div>
        )}
        <div className="task-meta">
          {task.due_date && (
            <span className="task-due-date">Due: {task.due_date}</span>
          )}
          <span className={`task-priority priority-${task.priority}`}>
            {task.priority}
          </span>
          {task.tags && task.tags.length > 0 && (
            <div className="task-tags">
              {task.tags.map((tag, i) => (
                <span key={i} className="task-tag">{tag}</span>
              ))}
            </div>
          )}
        </div>
      </div>
      <button className="task-delete" onClick={() => onDelete(task.task_id)}>
        ×
      </button>
    </div>
  )
}

export default function Tasks() {
  const queryClient = useQueryClient()
  const [newTaskTitle, setNewTaskTitle] = useState('')
  const [filter, setFilter] = useState<'all' | 'pending' | 'completed'>('all')

  const { data, isLoading, error } = useQuery({
    queryKey: ['tasks'],
    queryFn: fetchTasks,
    refetchInterval: 5000, // Refresh every 5 seconds to see new tasks
  })

  const createMutation = useMutation({
    mutationFn: createTask,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks'] })
      setNewTaskTitle('')
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ taskId, updates }: { taskId: string; updates: Partial<Task> }) =>
      updateTask(taskId, updates),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks'] })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: deleteTask,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks'] })
    },
  })

  const handleAddTask = (e: React.FormEvent) => {
    e.preventDefault()
    if (!newTaskTitle.trim()) return
    createMutation.mutate({ title: newTaskTitle.trim(), priority: 'medium', status: 'pending' })
  }

  const handleToggleComplete = (task: Task) => {
    const newStatus = task.status === 'completed' ? 'pending' : 'completed'
    updateMutation.mutate({ taskId: task.task_id, updates: { status: newStatus } })
  }

  const handleDelete = (taskId: string) => {
    deleteMutation.mutate(taskId)
  }

  const tasks = data?.tasks || []
  const filteredTasks = tasks.filter((task) => {
    if (filter === 'pending') return task.status !== 'completed'
    if (filter === 'completed') return task.status === 'completed'
    return true
  })

  const pendingCount = tasks.filter((t) => t.status !== 'completed').length
  const completedCount = tasks.filter((t) => t.status === 'completed').length

  return (
    <div className="tasks-page">
      <div className="tasks-header">
        <h2>Tasks</h2>
        <p>Manage your tasks and to-dos. Create tasks using the chat or add them here.</p>
      </div>

      <form className="add-task-form card" onSubmit={handleAddTask}>
        <input
          type="text"
          placeholder="Add a new task..."
          value={newTaskTitle}
          onChange={(e) => setNewTaskTitle(e.target.value)}
        />
        <button type="submit" disabled={!newTaskTitle.trim() || createMutation.isPending}>
          Add
        </button>
      </form>

      <div className="tasks-filters">
        <button
          className={`filter-btn ${filter === 'all' ? 'active' : ''}`}
          onClick={() => setFilter('all')}
        >
          All ({tasks.length})
        </button>
        <button
          className={`filter-btn ${filter === 'pending' ? 'active' : ''}`}
          onClick={() => setFilter('pending')}
        >
          Pending ({pendingCount})
        </button>
        <button
          className={`filter-btn ${filter === 'completed' ? 'active' : ''}`}
          onClick={() => setFilter('completed')}
        >
          Completed ({completedCount})
        </button>
      </div>

      {isLoading && <div className="tasks-loading">Loading tasks...</div>}

      {error && (
        <div className="tasks-empty card">
          <p>Tasks will appear here when you create them via chat.</p>
          <p>Try saying: "Create a task to review the quarterly report"</p>
        </div>
      )}

      {!isLoading && !error && filteredTasks.length === 0 && (
        <div className="tasks-empty card">
          <p>No tasks yet. Create some via chat or add them above!</p>
          <p>Try: "Capture: buy groceries, call mom, finish project"</p>
        </div>
      )}

      <div className="tasks-list">
        {filteredTasks.map((task) => (
          <TaskCard
            key={task.task_id}
            task={task}
            onToggleComplete={handleToggleComplete}
            onDelete={handleDelete}
          />
        ))}
      </div>
    </div>
  )
}
