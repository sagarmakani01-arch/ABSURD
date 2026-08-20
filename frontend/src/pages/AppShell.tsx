/**
 * ABSURD application shell — Phase 5 placeholder.
 * The full navigation environment lands in Phase 5.
 */
import { Link } from 'react-router-dom'
import { Button } from '../components/ui/primitives'

export function AppShell() {
  return (
    <main
      style={{
        minHeight: '100vh',
        background: 'var(--bg-0)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 12,
      }}
    >
      <div className="sys-label sys-label--signal">MODULE LOADED</div>
      <h1 style={{ fontSize: 'var(--fs-44)', fontWeight: 600 }}>ABSURD</h1>
      <p style={{ color: 'var(--text-mid)', fontSize: 'var(--fs-13)', marginBottom: 20 }}>
        Application shell ships in Phase 5 — runtime, tools, tasks, memory, evaluation.
      </p>
      <Button to="/" variant="ghost">
        BACK TO LANDING
      </Button>
      <nav style={{ display: 'flex', gap: 16, marginTop: 26 }} className="sys-label">
        <Link to="/app/tools" style={{ color: 'var(--text-low)' }}>TOOLS</Link>
        <Link to="/app/tasks" style={{ color: 'var(--text-low)' }}>TASKS</Link>
        <Link to="/app/system" style={{ color: 'var(--text-low)' }}>SYSTEM</Link>
      </nav>
    </main>
  )
}