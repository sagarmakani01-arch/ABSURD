/** /app/tools — tool registry. */
import { useNavigate } from 'react-router-dom'
import { useToolDisable, useTools, useToolsUsage } from '../../api/hooks'
import { PageHeader } from '../../app/AppUI'
import { Chip } from '../../components/ui/primitives'

const toneFor = (status: string) =>
  status === 'REGISTERED' ? 'ok' : status === 'REJECTED' || status === 'DEPRECATED' ? 'err' : 'neutral'

export function Tools() {
  const navigate = useNavigate()
  const tools = useTools()
  const usage = useToolsUsage()
  const toggleDisable = useToolDisable()

  return (
    <>
      <PageHeader
        code="02"
        title="TOOL REGISTRY"
        sub="Persistent capability library. Only verified tools enter this registry."
      />
      {tools.data === undefined ? (
        <div className="instr-panel" style={{ padding: 26 }}>
          <div className="sys-label" style={{ marginBottom: 8 }}>TOOL REGISTRY</div>
          <p style={{ color: 'var(--text-low)', margin: 0, fontFamily: 'var(--font-mono)', fontSize: 'var(--fs-11)' }}>
            LOADING…
          </p>
        </div>
      ) : tools.data.length === 0 ? (
        <div className="instr-panel" style={{ padding: 26 }}>
          <div className="sys-label" style={{ marginBottom: 8 }}>TOOL REGISTRY</div>
          <p style={{ color: 'var(--text-low)', margin: 0 }}>Registry is empty. Tool generation has not run yet.</p>
        </div>
      ) : (
        <div className="instr-panel" style={{ overflow: 'hidden' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontFamily: 'var(--font-mono)', fontSize: 'var(--fs-12)' }}>
            <thead>
              <tr style={{ textAlign: 'left' }}>
                {['NAME', 'VERSION', 'STATUS', 'CONF', 'CAPABILITIES', 'USAGE'].map((h) => (
                  <th key={h} className="sys-label" style={{ padding: '10px 16px', borderBottom: '1px solid var(--line-1)' }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {tools.data.map((t) => {
                const u = usage.data?.[t.id]
                const lowConf = t.confidence < 0.5
                return (
                  <tr
                    key={t.id}
                    onClick={() => navigate(`/app/tools/${t.id}`)}
                    style={{ cursor: 'pointer', borderBottom: '1px solid var(--line-0)', opacity: t.disabled ? 0.55 : 1 }}
                  >
                    <td style={{ padding: '10px 16px', color: 'var(--text-hi)', letterSpacing: '0.06em' }}>{t.name}</td>
                    <td style={{ padding: '10px 16px', color: 'var(--text-mid)' }}>{t.version}</td>
                    <td style={{ padding: '10px 16px' }}>
                      <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                        <Chip label={t.status} tone={toneFor(t.status)} />
                        {t.disabled && <Chip label="DISABLED" tone="warn" />}
                        {!t.disabled && t.status === 'REGISTERED' && lowConf && <Chip label="LOW CONF" tone="warn" />}
                      </div>
                    </td>
                    <td style={{ padding: '10px 16px', color: lowConf ? 'var(--warn)' : 'var(--text-mid)', fontSize: 'var(--fs-11)' }}>
                      {t.confidence.toFixed(2)}
                    </td>
                    <td style={{ padding: '10px 16px', color: 'var(--text-mid)', fontSize: 'var(--fs-11)' }}>
                      {t.capabilities.slice(0, 3).join(' · ')}
                    </td>
                    <td style={{ padding: '10px 16px', color: 'var(--text-low)' }}>
                      <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                        <span>{u ? `${u.usage_count} · ${Math.round(u.success_rate * 100)}%` : '—'}</span>
                        <button
                          type="button"
                          disabled={toggleDisable.isPending}
                          onClick={(e) => {
                            e.preventDefault()
                            e.stopPropagation()
                            toggleDisable.mutate({ id: t.id, disabled: !t.disabled })
                          }}
                          style={{
                            background: 'transparent',
                            border: '1px solid var(--line-1)',
                            color: 'var(--text-mid)',
                            borderRadius: 'var(--radius-1)',
                            fontFamily: 'var(--font-mono)',
                            fontSize: 'var(--fs-10)',
                            padding: '3px 8px',
                            cursor: 'pointer',
                          }}
                        >
                          {t.disabled ? 'ENABLE' : 'DISABLE'}
                        </button>
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}