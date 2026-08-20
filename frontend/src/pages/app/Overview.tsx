/** /app — main GENESIS environment. */
import { useEventStream } from '../../lib/useEventStream'
import { useHealth, useTasks, useTools } from '../../api/hooks'
import { PageHeader, ModulePending } from '../../app/AppUI'

export function Overview() {
  const health = useHealth()
  const { connected, events } = useEventStream()
  const tools = useTools()
  const tasks = useTasks()

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
            {[...events].reverse().slice(-12).map((e) => (
              <div key={`${e.sequence}-${e.type}`} style={{ display: 'flex', gap: 10 }}>
                <span style={{ color: 'var(--text-low)' }}>#{String(e.sequence).padStart(4, '0')}</span>
                <span style={{ color: 'var(--signal)' }}>{e.type}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 14, marginTop: 14 }}>
        <ModulePending
          name="TOOL REGISTRY"
          shipsIn="PHASE 7"
          contract={['id', 'name', 'capabilities', 'status', 'version', 'provenance']}
        />
        <ModulePending
          name="TASK PIPELINE"
          shipsIn="PHASE 6"
          contract={['id', 'goal', 'status', 'executions', 'result']}
        />
      </div>

      {tools.error && (tools.error as { status?: number }).status !== 404 && (
        <pre style={{ color: 'var(--err)', fontSize: 'var(--fs-11)' }}>{String(tools.error)}</pre>
      )}
      {tasks.error && (tasks.error as { status?: number }).status !== 404 && (
        <pre style={{ color: 'var(--err)', fontSize: 'var(--fs-11)' }}>{String(tasks.error)}</pre>
      )}
    </>
  )
}