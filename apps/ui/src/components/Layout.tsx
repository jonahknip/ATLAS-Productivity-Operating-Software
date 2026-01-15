import { Outlet, NavLink } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import './Layout.css'

export default function Layout() {
  const { data: status } = useQuery({
    queryKey: ['status'],
    queryFn: api.getStatus,
    refetchInterval: 30000, // Refresh every 30s
  })

  return (
    <div className="layout">
      <header className="header">
        <div className="header-left">
          <NavLink to="/" className="logo-link">
            <h1 className="logo">ATLAS</h1>
          </NavLink>
          <span className="version">v{status?.version ?? '...'}</span>
        </div>
        <nav className="nav">
          <NavLink to="/" className="nav-link" end>
            Chat
          </NavLink>
          <NavLink to="/dashboard" className="nav-link">
            Dashboard
          </NavLink>
          <NavLink to="/receipts" className="nav-link">
            History
          </NavLink>
          <NavLink to="/settings" className="nav-link">
            Settings
          </NavLink>
        </nav>
      </header>
      <main className="main">
        <Outlet />
      </main>
    </div>
  )
}
