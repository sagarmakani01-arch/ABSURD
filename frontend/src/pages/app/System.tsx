/** /app/system — operational status + live event log. */
import { useEventStream } from '../../lib/useEventStream'
import { useHealth } from '../../api/hooks'
import { PageHeader } from '../../app/AppUI'

export function System() {
  const health = useHealth()
  const { connected, events } = useEventStream()

  const rows: Array<[string, string]> = [
    ['SERVICE', health.data?.service.toUpperCase() ?? '—'],
    ['VERSION', health.data ? `v${health.data.version}` : '—'],
    ['STATUS', health.data?.status.toUpperCase() ?? (health.isLoading ? 'PROBING…' : 'OFFLINE')],
    ['STREAM', connected ? 'LIVE' : 'DOWN'],
    ['EVENT COUNT', String(events.length)],
  ]

  return (
    <>
      <PageHeader
        code="07"
        title="SYSTEM"
        sub="Operational status of the ABSURD gateway and its event stream."
      />
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 14 }}>
        <div className="instr-panel" style={{ padding: 22 }}>
          <div className="sys-label" style={{ marginBottom: 14 }}>GATEWAY STATUS</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {rows.map(([k, v]) => (
              <div key={k} style={{ display: 'flex', justifyContent: 'space-between', fontFamily: 'var(--font-mono)', fontSize: 'var(--fs-12)' }}>
                <span style={{ color: 'var(--text-low)', letterSpacing: '0.1em' }}>{k}</span>
                <span
                  style={{
                    color:
                      k === 'STATUS'
                        ? health.data?.status === 'ok'
                          ? 'var(--ok)'
                          : 'var(--err)'
                        : k === 'STREAM'
                          ? connected
                            ? 'var(--ok)'
                            : 'var(--err)'
                          : 'var(--text-hi)',
                  }}
                >
                  {v}
                </span>
              </div>
            ))}
            {(!health.data && !health.isLoading) && (
              <p style={{ color: 'var(--err)', fontFamily: 'var(--font-mono)', fontSize: 'var(--fs-11)', margin: 0 }}>
                {String(health.error)}
              </p>
            )}
          </div>
        </div>

        <div className="instr-panel" style={{ padding: 22 }}>
          <div className="sys-label" style={{ marginBottom: 14 }}>LIVE EVENT LOG</div>
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              maxHeight: 320,
              overflowY: 'auto',
              fontFamily: 'var(--font-mono)',
              fontSize: 'var(--fs-11)',
              gap: 6,
            }}
          >
            {events.length === 0 && <div className="sys-label" style={{ color: 'var(--text-low)' }}>WAITING FOR EVENTS…</div>}
            {[...events].reverse().map((e) => (
              <div key={`${e.sequence}-${e.type}`} style={{ display: 'flex', gap: 10 }}>
                <span style={{ color: 'var(--text-low)' }}>#{String(e.sequence).padStart(4, '0')}</span>
                <span style={{ color: 'var(--signal)' }}>{e.type}</span>
                <span style={{ color: 'var(--text-mid)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {JSON.stringify(e.payload)}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </>
  )
}