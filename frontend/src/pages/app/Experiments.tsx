/** /app/experiments — evolution loop: generation, metrics, revisions. */
import { useState } from 'react'
import { useCoverageGaps, useGenerateTool, useMetrics, usePromote, useStartRevision, useTools } from '../../api/hooks'
import { PageHeader } from '../../app/AppUI'
import { Button, Chip, SpecRow } from '../../components/ui/primitives'

export function Experiments() {
  const metrics = useMetrics()
  const tools = useTools()
  const gaps = useCoverageGaps()
  const generate = useGenerateTool()
  const revise = useStartRevision()
  const promote = usePromote()
  const [selected, setSelected] = useState('')
  const [nameHint, setNameHint] = useState('')
  const [schemaJson, setSchemaJson] = useState('{"inputs": {}, "outputs": {}}')

  const tool = tools.data?.find((t) => t.id === selected)

  const generateFromGap = (capability: string) =>
    generate.mutate({
      name_hint: capability,
      description: `Generated candidate for ${capability}`,
    })

  const manualGenerate = () => {
    let parsed: { inputs: Record<string, string>; outputs: Record<string, string> }
    try {
      parsed = JSON.parse(schemaJson)
    } catch {
      return
    }
    generate.mutate({
      name_hint: nameHint.trim(),
      input_schema: parsed.inputs ?? {},
      output_schema: parsed.outputs ?? {},
    })
  }

  return (
    <>
      <PageHeader
        code="04"
        title="EXPERIMENTS"
        sub="Evolution loop controls: generation from gaps, metrics, revision attempts."
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
              <SpecRow label="generation_available">{metrics.data.generation_available ? 'TEMPLATE' : 'NONE'}</SpecRow>
            </>
          )}
          <div style={{ marginTop: 12, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {Object.entries(metrics.data?.failures_by_kind ?? {}).map(([kind, count]) => (
              <Chip key={kind} label={`${kind} × ${count}`} tone="warn" />
            ))}
          </div>
        </div>

        <div className="instr-panel" style={{ padding: 22 }}>
          <div className="sys-label" style={{ marginBottom: 12 }}>GENERATE FROM OPEN GAPS</div>
          <p style={{ color: 'var(--text-low)', fontSize: 'var(--fs-13)', margin: '0 0 14px' }}>
            Deterministic template generation: a DRAFT candidate is scaffolded for the missing
            capability and must still pass VERIFY → ACTIVATE.
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {gaps.data === undefined && <span className="sys-label" style={{ color: 'var(--text-low)' }}>LOADING…</span>}
            {gaps.data?.length === 0 && <span className="sys-label" style={{ color: 'var(--text-low)' }}>NO OPEN GAPS</span>}
            {gaps.data
              ?.filter((g) => !g.covered)
              .map((g) => (
                <div key={`${g.task_id}-${g.capability}`} style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'center' }}>
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--fs-11)', color: 'var(--text-mid)' }}>{g.capability}</span>
                  <Button
                    variant="ghost"
                    disabled={generate.isPending}
                    onClick={() => generateFromGap(g.capability)}
                  >
                    GENERATE
                  </Button>
                </div>
              ))}
          </div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 14, marginBottom: 18 }}>
        <div className="instr-panel" style={{ padding: 22 }}>
          <div className="sys-label" style={{ marginBottom: 12 }}>MANUAL GENERATION</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <input
              value={nameHint}
              onChange={(e) => setNameHint(e.target.value)}
              placeholder="name_hint, e.g. convert_csv_to_markdown"
              style={{
                background: 'var(--bg-2)',
                border: '1px solid var(--line-1)',
                color: 'var(--text-hi)',
                fontFamily: 'var(--font-mono)',
                fontSize: 'var(--fs-12)',
                padding: '0 14px',
                height: 36,
                borderRadius: 'var(--radius-1)',
                outline: 'none',
              }}
            />
            <textarea
              value={schemaJson}
              onChange={(e) => setSchemaJson(e.target.value)}
              rows={4}
              spellCheck={false}
              style={{
                background: 'var(--bg-2)',
                border: '1px solid var(--line-1)',
                color: 'var(--text-hi)',
                fontFamily: 'var(--font-mono)',
                fontSize: 'var(--fs-11)',
                padding: 10,
                borderRadius: 'var(--radius-1)',
                outline: 'none',
                resize: 'vertical',
              }}
            />
            <Button onClick={manualGenerate} disabled={!nameHint.trim() || generate.isPending}>
              GENERATE CANDIDATE
            </Button>
          </div>
          {generate.isError && generate.error instanceof Error && (
            <pre style={{ color: 'var(--err)', fontSize: 'var(--fs-11)', margin: '12px 0 0' }}>{generate.error.message}</pre>
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