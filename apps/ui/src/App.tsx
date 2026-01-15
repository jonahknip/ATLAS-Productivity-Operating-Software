import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Chat from './pages/Chat'
import Tasks from './pages/Tasks'
import Dashboard from './pages/Dashboard'
import Receipts from './pages/Receipts'
import Providers from './pages/Providers'
import Settings from './pages/Settings'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Chat />} />
          <Route path="tasks" element={<Tasks />} />
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="receipts" element={<Receipts />} />
          <Route path="providers" element={<Providers />} />
          <Route path="settings" element={<Settings />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
