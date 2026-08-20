/**
 * APP shell layout — one coherent computational environment.
 * Left rail navigation, live status header, section content outlet.
 */
import { NavLink, Outlet, Link } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { useEventStream } from '../lib/useEventStream'

const SECTIONS = [
  { to: '/app', label: 'OVERVIEW', code: '01', end: true },
  { to: '/app/tools', label: 'TOOL REGISTRY', code: '02' },
  { to: '/app/tasks', label: 'TASKS', code: '03' },
  { to: '/app/experiments', label: 'EXPERIMENTS', code: '04' },
  { to: '/app/memory', label: 'MEMORY', code: '05' },
  { to: '/app/evaluation', label: 'EVALUATION', code: '06' },
  { to: '/app/system', label: 'SYSTEM', code: '07' },
]

export function AppLayout() {
  const { connected, lastEvent } = useEventStream()

  return (
    <div style={{ display: 'flex', minHeight: '100vh', background: 'var(--bg-0)' }}>
      {/* Rail */}
      <aside
        style={{
          width: 224,
          flexShrink: 0,
          borderRight: '1px solid var(--line-1)',
          background: 'var(--bg-1)',
          display: 'flex',
          flexDirection: 'column',
          position: 'sticky',
          top: 0,
          height: '100vh',
          padding: '20px 14px',
        }}
      >
        <Link to="/" style={{ textDecoration: 'none', display: 'flex', alignItems: 'baseline', gap: 10, padding: '2px 10px 18px' }}>
          <span style={{ fontFamily: 'var(--font-display)', fontWeight: 600, fontSize: 15, letterSpacing: '0.22em', color: 'var(--text-hi)' }}>
            ABSURD
          </span>
          <span className="sys-label">v0.1</span>
        </Link>

        <nav style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          {SECTIONS.map((s) => (
            <NavLink
              key={s.to}
              to={s.to}
              end={s.end}
              style={({ isActive }) => ({
                display: 'flex',
                alignItems: 'center',
                gap: 12,
                padding: '8px 10px',
                borderRadius: 'var(--radius-1)',
                textDecoration: 'none',
                fontFamily: 'var(--font-mono)',
                fontSize: 'var(--fs-11)',
                letterSpacing: '0.12em',
                color: isActive ? 'var(--text-hi)' : 'var(--text-low)',
                background: isActive ? 'var(--bg-2)' : 'transparent',
                border: isActive ? '1px solid var(--line-2)' : '1px solid transparent',
              })}
            >
              <span style={{ color: 'var(--signal)', fontSize: 'var(--fs-11)' }}>{s.code}</span>
              <span>{s.label}</span>
            </NavLink>
          ))}
        </nav>

        <div style={{ marginTop: 'auto', padding: '0 10px', display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div className="sys-label" style={{ display: 'flex', alignItems: 'center', gap: 8, color: connected ? 'var(--ok)' : 'var(--err)' }}>
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: connected ? 'var(--ok)' : 'var(--err)' }} />
            {connected ? 'EVENT STREAM LIVE' : 'EVENT STREAM DOWN'}
          </div>
          <div className="sys-label" style={{ color: 'var(--text-low)' }}>
            LAST: {lastEvent ? lastEvent.type : '—'}
          </div>
        </div>
      </aside>

      {/* Content column */}
      <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column' }}>
        <header
          style={{
            height: 52,
            borderBottom: '1px solid var(--line-1)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '0 26px',
            background: 'var(--bg-0)',
            position: 'sticky',
            top: 0,
            zIndex: 5,
          }}
        >
          <Link to="/" className="sys-label" style={{ textDecoration: 'none', color: 'var(--text-low)', display: 'inline-flex', gap: 8, alignItems: 'center' }}>
            <ArrowLeft size={12} strokeWidth={1.5} /> LANDING
          </Link>
          <div className="sys-label" id="section-clock">
            {new Date().toISOString().slice(0, 19).replace('T', ' ')}Z
          </div>
        </header>

        <main style={{ flex: 1, padding: '34px 34px 60px', maxWidth: 1200, width: '100%' }}>
          <Outlet />
        </main>
      </div>
    </div>
  )
}