/** /app/experiments — evolution loop: metrics, revision attempts, promotions. */
import { useState } from 'react'
import { useMetrics, usePromote, useStartRevision, useTools } from '../../api/hooks'
import { PageHeader } from '../../app/AppUI'
import { Button, Chip, SpecRow } from '../../components/ui/primitives'

export function Experiments() {
  const metrics = useMetrics()
  const tools = useTools()
  const revise = useStartRevision()
  const promote = usePromote()
  const [selected, setSelected] = useState('')

  const tool = tools.data?.find((t) => t.id === selected)

  return (
    <>
      <PageHeader
        code="04"
        title="EXPERIMENTS"
        sub="Evolution loop controls: metrics, revision attempts, version promotion."
      />

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 14, marginBottom: 18 }}>
        <div className="instr-panel" style={{ padding: 22 }}>
          <div className="sys-label" style={{ marginBottom: 12 }}>LOOP METRICS</div>
          {metrics.data === undefined ? (
            <span className="sys-label" style={{ color: 'var(--text-low)' }}>LOADING…</span>
          ) : (
            <>
              <SpecRow label="tasks">{metrics.data.tasks_total} ({metrics.data.tasks_failed} failed)</SpecRow>
              <SpecRow label="failure_rate">{metrics.data.task_failure_rate.toFixed(3)}</SpecRow>
              <SpecRow label="tools_registered">{metrics.data.tools_registered}</SpecRow>
              <SpecRow label="tools_generated">{metrics.data.tools_generated}</SpecRow>
              <SpecRow label="quarantined">{metrics.data.tools_quarantined}</SpecRow>
              <SpecRow label="gap_edges">{metrics.data.gap_edges}</SpecRow>
              <SpecRow label="gap_close_rate">
                {metrics.data.gap_close_rate === null ? 'NO GAPS' : metrics.data.gap_close_rate.toFixed(3)}
              </SpecRow>
              <SpecRow label="revisions_total">{metrics.data.revisions_total}</SpecRow>
            </>
          )}
        </div>

        <div className="instr-panel" style={{ padding: 22 }}>
          <div className="sys-label" style={{ marginBottom: 12 }}>REVISION / PROMOTION</div>
          <p style={{ color: 'var(--text-low)', fontSize: 'var(--fs-13)', margin: '0 0 14px' }}>
            Revision generation is not implemented yet — attempts fail closed with an honest 409
            and are recorded on the event stream.
          </p>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            <select
              value={selected}
              onChange={(e) => setSelected(e.target.value)}
              style={{
                background: 'var(--bg-2)',
                border: '1px solid var(--line-1)',
                color: 'var(--text-hi)',
                fontFamily: 'var(--font-mono)',
                fontSize: 'var(--fs-12)',
                height: 36,
                padding: '0 10px',
                borderRadius: 'var(--radius-1)',
                outline: 'none',
              }}
            >
              <option value="">SELECT REGISTERED TOOL…</option>
              {(tools.data ?? []).filter((t) => t.status === 'REGISTERED').map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name} — v{t.version}
                </option>
              ))}
            </select>
            <Button
              variant="ghost"
              onClick={() => selected && revise.mutate(selected)}
              disabled={!selected || revise.isPending}
            >
              START REVISION
            </Button>
            <Button
              variant="ghost"
              onClick={() => tool && promote.mutate({ id: tool.id, version: nextVersion(tool.version) })}
              disabled={!tool || promote.isPending}
            >
              PROMOTE {tool ? `v${nextVersion(tool.version)}` : ''}
            </Button>
          </div>
          {revise.isError && revise.error instanceof Error && (
            <pre style={{ color: 'var(--err)', fontSize: 'var(--fs-11)', margin: '12px 0 0' }}>{revise.error.message}</pre>
          )}
          {promote.isError && promote.error instanceof Error && (
            <pre style={{ color: 'var(--err)', fontSize: 'var(--fs-11)', margin: '12px 0 0' }}>{promote.error.message}</pre>
          )}
          <div style={{ marginTop: 14, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {Object.entries(metrics.data?.failures_by_kind ?? {}).map(([kind, count]) => (
              <Chip key={kind} label={`${kind} × ${count}`} tone="warn" />
            ))}
          </div>
        </div>
      </div>
    </>
  )
}

function nextVersion(version: string): string {
  const parts = version.split('.').map((p) => Number.parseInt(p, 10) || 0)
  parts[2] += 1
  return parts.join('.')
}