/** /app — main ABSURD environment. */
import { Link } from 'react-router-dom'
import { useEventStream } from '../../lib/useEventStream'
import { useCapabilities, useHealth, useTasks, useTools } from '../../api/hooks'
import { PageHeader } from '../../app/AppUI'

export function Overview() {
  const health = useHealth()
  const { connected, events } = useEventStream()
  const tools = useTools()
  const tasks = useTasks()
  const capabilities = useCapabilities()

  const lastEvents = [...events].reverse().slice(0, 8)

  return (
    <>
      <PageHeader
        code="01"
        title="ENVIRONMENT"
        sub="One computational environment: gateway, event stream, registry, and task pipeline."
      />
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 14 }}>
        {/* Gateway */}
        <div className="instr-panel" style={{ padding: 20 }}>
          <div className="sys-label" style={{ marginBottom: 14 }}>GATEWAY</div>
          {health.isLoading ? (
            <div className="sys-label">PROBING…</div>
          ) : health.data ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {[
                ['STATUS', health.data.status.toUpperCase()],
                ['SERVICE', health.data.service.toUpperCase()],
                ['VERSION', `v${health.data.version}`],
                ['EVENT BUS', health.data.event_bus.toUpperCase()],
              ].map(([k, v]) => (
                <div key={k} style={{ display: 'flex', justifyContent: 'space-between', fontFamily: 'var(--font-mono)', fontSize: 'var(--fs-12)' }}>
                  <span style={{ color: 'var(--text-low)', letterSpacing: '0.1em' }}>{k}</span>
                  <span style={{ color: k === 'STATUS' ? 'var(--ok)' : 'var(--text-hi)' }}>{v}</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="sys-label" style={{ color: 'var(--err)' }}>GATEWAY OFFLINE</div>
          )}
        </div>

        {/* Event stream */}
        <div className="instr-panel" style={{ padding: 20 }}>
          <div className="sys-label" style={{ marginBottom: 14 }}>
            EVENT STREAM — {connected ? 'LIVE' : 'DOWN'}
          </div>
          <div
            style={{
              display: 'flex',
              flexDirection: 'column-reverse',
              maxHeight: 210,
              overflowY: 'auto',
              fontFamily: 'var(--font-mono)',
              fontSize: 'var(--fs-11)',
              gap: 6,
            }}
          >
            {events.length === 0 && <div className="sys-label" style={{ color: 'var(--text-low)' }}>NO EVENTS YET</div>}
            {lastEvents.map((e) => (
              <div key={`${e.sequence}-${e.type}`} style={{ display: 'flex', gap: 10 }}>
                <span style={{ color: 'var(--text-low)' }}>#{String(e.sequence).padStart(4, '0')}</span>
                <span style={{ color: 'var(--signal)' }}>{e.type}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Registry + pipeline summaries */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 14, marginTop: 14 }}>
        <div className="instr-panel" style={{ padding: 20 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <div className="sys-label">TOOL REGISTRY</div>
            <Link to="/app/tools" className="sys-label" style={{ textDecoration: 'none', color: 'var(--signal)' }}>
              OPEN →
            </Link>
          </div>
          {tools.data === undefined ? (
            <div className="sys-label" style={{ color: 'var(--text-low)' }}>LOADING…</div>
          ) : tools.data.length === 0 ? (
            <div className="sys-label" style={{ color: 'var(--text-low)' }}>
              EMPTY — NO TOOLS REGISTERED YET
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {tools.data.slice(0, 4).map((t) => (
                <Link
                  key={t.id}
                  to={`/app/tools/${t.id}`}
                  style={{ display: 'flex', justifyContent: 'space-between', gap: 12, textDecoration: 'none', fontFamily: 'var(--font-mono)', fontSize: 'var(--fs-11)' }}
                >
                  <span style={{ color: 'var(--text-hi)', letterSpacing: '0.06em' }}>{t.name}</span>
                  <span style={{ color: t.status === 'REGISTERED' ? 'var(--ok)' : 'var(--text-low)' }}>{t.status}</span>
                </Link>
              ))}
            </div>
          )}
        </div>

        <div className="instr-panel" style={{ padding: 20 }}>
          <div className="sys-label" style={{ marginBottom: 12 }}>CAPABILITY COVERAGE</div>
          {capabilities.data === undefined ? (
            <div className="sys-label" style={{ color: 'var(--text-low)' }}>LOADING…</div>
          ) : capabilities.data.length === 0 ? (
            <div className="sys-label" style={{ color: 'var(--text-low)' }}>
              NO CAPABILITIES KNOWN YET
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {capabilities.data.slice(0, 5).map((c) => (
                <div
                  key={c.capability}
                  style={{ display: 'flex', justifyContent: 'space-between', gap: 12, fontFamily: 'var(--font-mono)', fontSize: 'var(--fs-11)' }}
                >
                  <span style={{ color: 'var(--text-hi)', letterSpacing: '0.06em', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {c.capability}
                  </span>
                  <span style={{ color: c.covered ? 'var(--ok)' : c.disabled.length > 0 ? 'var(--warn)' : 'var(--err)' }}>
                    {c.covered ? 'COVERED' : c.disabled.length > 0 ? 'DISABLED' : 'GAP'}
                  </span>
                </div>
              ))}
              <div className="sys-label" style={{ color: 'var(--text-low)', marginTop: 6 }}>
                {capabilities.data.filter((c) => c.covered).length} COVERED / {capabilities.data.length} TOTAL
              </div>
            </div>
          )}
        </div>

        <div className="instr-panel" style={{ padding: 20 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <div className="sys-label">TASK PIPELINE</div>
            <Link to="/app/tasks" className="sys-label" style={{ textDecoration: 'none', color: 'var(--signal)' }}>
              OPEN →
            </Link>
          </div>
          {tasks.data === undefined ? (
            <div className="sys-label" style={{ color: 'var(--text-low)' }}>LOADING…</div>
          ) : tasks.data.length === 0 ? (
            <div className="sys-label" style={{ color: 'var(--text-low)' }}>
              IDLE — NO TASKS SUBMITTED
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {tasks.data.slice(0, 4).map((t) => (
                <Link
                  key={t.id}
                  to={`/app/tasks/${t.id}`}
                  style={{ display: 'flex', justifyContent: 'space-between', gap: 12, textDecoration: 'none', fontFamily: 'var(--font-mono)', fontSize: 'var(--fs-11)' }}
                >
                  <span style={{ color: 'var(--text-hi)', letterSpacing: '0.06em', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {t.goal}
                  </span>
                  <span style={{ color: t.status === 'COMPLETED' ? 'var(--ok)' : t.status === 'FAILED' ? 'var(--err)' : 'var(--signal)' }}>
                    {t.status}
                  </span>
                </Link>
              ))}
            </div>
          )}
        </div>
      </div>

      {tools.error && (tools.error as { status?: number }).status !== 404 && tools.error instanceof Error && (
        <pre style={{ color: 'var(--err)', fontSize: 'var(--fs-11)' }}>{tools.error.message}</pre>
      )}
      {tasks.error && (tasks.error as { status?: number }).status !== 404 && tasks.error instanceof Error && (
        <pre style={{ color: 'var(--err)', fontSize: 'var(--fs-11)' }}>{tasks.error.message}</pre>
      )}
    </>
  )
}