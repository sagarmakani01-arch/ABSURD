/** /app/memory — experience memory, knowledge graph, coverage gaps, usage. */
import { useCoverageGaps, useExperiences, useGraphEdges, useToolsUsage } from '../../api/hooks'
import { PageHeader } from '../../app/AppUI'
import { Chip, SpecRow } from '../../components/ui/primitives'

const toneFor = (outcome: string) =>
  outcome === 'success' ? 'ok' : outcome === 'failure' ? 'err' : 'neutral'

export function Memory() {
  const experiences = useExperiences({ limit: '40' })
  const gaps = useCoverageGaps()
  const edges = useGraphEdges({ limit: '60' })
  const usage = useToolsUsage()

  return (
    <>
      <PageHeader
        code="05"
        title="MEMORY"
        sub="Tool memory, experience memory, capability memory, provenance."
      />

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 14, marginBottom: 14 }}>
        <div className="instr-panel" style={{ padding: 22 }}>
          <div className="sys-label" style={{ marginBottom: 12 }}>END-TO-END METRICS</div>
          <SpecRow label="experiences">{experiences.data?.length ?? '—'}</SpecRow>
          <SpecRow label="requires_edges">
            {edges.data?.filter((e) => e.relation === 'requires').length ?? '—'}
          </SpecRow>
          <SpecRow label="enables_edges">
            {edges.data?.filter((e) => e.relation === 'enables').length ?? '—'}
          </SpecRow>
          <SpecRow label="open_gaps">
            {gaps.data === undefined ? '—' : gaps.data.filter((g) => !g.covered).length}
          </SpecRow>
          <SpecRow label="tools_used">{Object.keys(usage.data ?? {}).length}</SpecRow>
        </div>

        <div className="instr-panel" style={{ padding: 22 }}>
          <div className="sys-label" style={{ marginBottom: 12 }}>KNOWLEDGE GRAPH EDGES</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, maxHeight: 300, overflowY: 'auto', fontFamily: 'var(--font-mono)', fontSize: 'var(--fs-11)' }}>
            {edges.data === undefined && <span style={{ color: 'var(--text-low)' }}>LOADING…</span>}
            {edges.data?.length === 0 && <span style={{ color: 'var(--text-low)' }}>NO EDGES YET</span>}
            {edges.data?.map((e) => (
              <div key={e.id} style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <span style={{ color: 'var(--text-mid)' }}>{e.subject}</span>
                <span style={{ color: 'var(--signal)' }}>─{e.relation.toUpperCase()}→</span>
                <span style={{ color: 'var(--text-hi)' }}>{e.target}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 14, marginBottom: 14 }}>
        <div className="instr-panel" style={{ padding: 22 }}>
          <div className="sys-label" style={{ marginBottom: 12 }}>COVERAGE GAPS</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, fontFamily: 'var(--font-mono)', fontSize: 'var(--fs-11)' }}>
            {gaps.data === undefined && <span style={{ color: 'var(--text-low)' }}>LOADING…</span>}
            {gaps.data?.length === 0 && <span style={{ color: 'var(--text-low)' }}>NO GAPS RECORDED</span>}
            {gaps.data?.map((g) => (
              <div key={`${g.task_id}-${g.capability}`} style={{ display: 'flex', justifyContent: 'space-between', gap: 10 }}>
                <span style={{ color: 'var(--text-mid)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {g.capability}
                </span>
                <Chip
                  label={g.covered ? 'COVERED' : 'OPEN'}
                  tone={g.covered ? 'ok' : 'warn'}
                />
              </div>
            ))}
          </div>
        </div>

        <div className="instr-panel" style={{ padding: 22 }}>
          <div className="sys-label" style={{ marginBottom: 12 }}>EXPERIENCE MEMORY — FAILURES</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10, fontFamily: 'var(--font-mono)', fontSize: 'var(--fs-11)' }}>
            {experiences.data === undefined && <span style={{ color: 'var(--text-low)' }}>LOADING…</span>}
            {experiences.data?.length === 0 && <span style={{ color: 'var(--text-low)' }}>NO EXPERIENCES YET</span>}
            {experiences.data?.slice(0, 10).map((x) => (
              <div key={x.id}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10 }}>
                  <span style={{ color: 'var(--text-hi)' }}>{x.kind.toUpperCase()}</span>
                  <Chip label={x.outcome} tone={toneFor(x.outcome)} />
                </div>
                <div style={{ color: 'var(--text-low)', marginTop: 4 }}>
                  {x.lessons.length > 0 ? x.lessons.join(' · ') : x.task_id ?? '—'}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </>
  )
}