/** /app/system — operational status + live event log. */
import { useState } from 'react'
import { useEventStream } from '../../lib/useEventStream'
import { useHealth } from '../../api/hooks'
import { PageHeader } from '../../app/AppUI'

const TOKEN_KEY = 'absurd_api_token'

function TokenControl() {
  const [value, setValue] = useState(() => localStorage.getItem(TOKEN_KEY) ?? '')

  const save = () => {
    if (value) localStorage.setItem(TOKEN_KEY, value.trim())
    else localStorage.removeItem(TOKEN_KEY)
    setValue(value.trim())
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div className="sys-label">API TOKEN (ABSURD_API_TOKEN)</div>
      <div style={{ display: 'flex', gap: 8 }}>
        <input
          aria-label="API token"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && save()}
          placeholder="Bearer token, if the gateway requires one"
          style={{
            flex: 1,
            background: 'transparent',
            border: '1px solid var(--line)',
            color: 'var(--text-hi)',
            padding: '8px 10px',
            fontFamily: 'var(--font-mono)',
            fontSize: 'var(--fs-12)',
            outline: 'none',
          }}
        />
        <button
          onClick={save}
          style={{
            background: 'transparent',
            border: '1px solid var(--line)',
            color: 'var(--text-hi)',
            padding: '8px 14px',
            fontFamily: 'var(--font-mono)',
            fontSize: 'var(--fs-11)',
            cursor: 'pointer',
          }}
        >
          {value ? 'SAVE' : 'CLEAR'}
        </button>
      </div>
      <p style={{ margin: 0, color: 'var(--text-low)', fontFamily: 'var(--font-mono)', fontSize: 'var(--fs-11)' }}>
        Sent as <code>Authorization: Bearer</code> on REST and <code>?token=</code> on the websocket.
      </p>
    </div>
  )
}

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
          <TokenControl />
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