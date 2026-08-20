/** /app/evaluation — structural evaluation runs against registry tools. */
import { useState } from 'react'
import { useRunEvaluation, useTools } from '../../api/hooks'
import { PageHeader } from '../../app/AppUI'
import { Button, Chip, SpecRow } from '../../components/ui/primitives'

export function Evaluation() {
  const tools = useTools()
  const evaluate = useRunEvaluation()
  const [selected, setSelected] = useState('')

  return (
    <>
      <PageHeader
        code="06"
        title="EVALUATION"
        sub="Verification pipelines, benchmark scores, reliability measurements."
      />

      <div className="instr-panel" style={{ padding: 22, marginBottom: 18 }}>
        <div className="sys-label" style={{ marginBottom: 10 }}>STRUCTURAL GATE</div>
        <p style={{ color: 'var(--text-low)', fontSize: 'var(--fs-13)', margin: '0 0 14px', maxWidth: 560 }}>
          Runs the deterministic structural gate (required fields + schema sanity) and reports an
          honest score. Behavioral verification — executing a tool's own tests — ships with the
          sandbox and stays unavailable now.
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
            <option value="">SELECT TOOL…</option>
            {(tools.data ?? []).map((t) => (
              <option key={t.id} value={t.id}>
                {t.name} — {t.status}
              </option>
            ))}
          </select>
          <Button onClick={() => selected && evaluate.mutate(selected)} disabled={!selected || evaluate.isPending}>
            RUN EVALUATION
          </Button>
        </div>
        {evaluate.isError && evaluate.error instanceof Error && (
          <pre style={{ color: 'var(--err)', fontSize: 'var(--fs-11)', margin: '12px 0 0' }}>{evaluate.error.message}</pre>
        )}
      </div>

      {evaluate.data && (
        <div className="instr-panel" style={{ padding: 22 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <div className="sys-label">LAST RUN — {evaluate.data.tool_id}</div>
            <Chip label={`SCORE ${evaluate.data.verification_score.toFixed(3)}`} tone={evaluate.data.verification_score >= 1 ? 'ok' : 'warn'} />
          </div>
          <SpecRow label="checks">{evaluate.data.checks_passed} / {evaluate.data.checks_total} passed</SpecRow>
          <SpecRow label="behavioral">
            {evaluate.data.behavioral.available ? 'AVAILABLE' : 'NOT IMPLEMENTED'}
          </SpecRow>
          {evaluate.data.checks.map((c) => (
            <SpecRow key={c.name} label={c.name}>
              <span style={{ color: c.passed ? 'var(--ok)' : 'var(--err)' }}>
                {c.passed ? 'PASS' : 'FAIL'}
              </span>
            </SpecRow>
          ))}
        </div>
      )}
    </>
  )
}