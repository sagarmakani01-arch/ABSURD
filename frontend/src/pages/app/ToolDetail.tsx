/** /app/tools/:id — tool details + lifecycle actions. */
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { useRunEvaluation, useTool, useToolDisable, useToolTransition } from '../../api/hooks'
import { PageHeader } from '../../app/AppUI'
import { Button, Chip, SpecRow } from '../../components/ui/primitives'

const ACTIONS: Array<{ verb: 'verify' | 'activate' | 'reject' | 'deprecate'; label: string; when: string }> = [
  { verb: 'verify', label: 'VERIFY', when: 'DRAFT' },
  { verb: 'activate', label: 'ACTIVATE', when: 'VERIFIED' },
  { verb: 'reject', label: 'REJECT', when: 'DRAFT' },
  { verb: 'deprecate', label: 'DEPRECATE', when: 'REGISTERED' },
]

const toneFor = (status: string) =>
  status === 'REGISTERED' ? 'ok' : status === 'REJECTED' || status === 'DEPRECATED' ? 'err' : 'neutral'

export function ToolDetail() {
  const { id = '' } = useParams()
  const tool = useTool(id)
  const transition = useToolTransition()
  const toggleDisable = useToolDisable()
  const evaluate = useRunEvaluation()

  return (
    <div>
      <Link to="/app/tools" className="sys-label" style={{ textDecoration: 'none', color: 'var(--text-low)', display: 'inline-flex', gap: 8, alignItems: 'center', marginBottom: 18 }}>
        <ArrowLeft size={12} strokeWidth={1.5} /> TOOL REGISTRY
      </Link>

      {tool.data === undefined ? (
        <PageHeader code="02" title="TOOL" sub="" />
      ) : (
        <>
          <div style={{ display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap', marginBottom: 24 }}>
            <h1 style={{ fontSize: 'var(--fs-32)', fontWeight: 600, fontFamily: 'var(--font-mono)', letterSpacing: '0.04em' }}>
              {tool.data.name}
            </h1>
            <Chip label={tool.data.status} tone={toneFor(tool.data.status)} />
            {tool.data.disabled && <Chip label="DISABLED" tone="warn" />}
            {!tool.data.disabled && tool.data.status === 'REGISTERED' && tool.data.confidence < 0.5 && (
              <Chip label="LOW CONF" tone="warn" />
            )}
          </div>

          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 18 }}>
            {ACTIONS.filter((a) => a.when === tool.data?.status).map((a) => (
              <Button
                key={a.verb}
                variant={a.verb === 'deprecate' ? 'ghost' : 'primary'}
                onClick={() => transition.mutate({ id, verb: a.verb })}
                disabled={transition.isPending}
              >
                {a.label}
              </Button>
            ))}
            <Button
              variant="ghost"
              onClick={() => toggleDisable.mutate({ id, disabled: !tool.data!.disabled })}
              disabled={toggleDisable.isPending}
            >
              {tool.data!.disabled ? 'ENABLE' : 'DISABLE'}
            </Button>
            <Button
              variant="ghost"
              onClick={() => evaluate.mutate(id)}
              disabled={evaluate.isPending}
            >
              RUN STRUCTURAL EVALUATION
            </Button>
          </div>

          {transition.isError && transition.error instanceof Error && (
            <pre style={{ color: 'var(--err)', fontSize: 'var(--fs-11)', margin: '0 0 14px' }}>{transition.error.message}</pre>
          )}
          {evaluate.isError && evaluate.error instanceof Error && (
            <pre style={{ color: 'var(--err)', fontSize: 'var(--fs-11)', margin: '0 0 14px' }}>{evaluate.error.message}</pre>
          )}

          {evaluate.data && (
            <div className="instr-panel" style={{ padding: 22, marginBottom: 18 }}>
              <div className="sys-label" style={{ marginBottom: 12 }}>STRUCTURAL GATE</div>
              <SpecRow label="verification_score">
                {evaluate.data.verification_score.toFixed(3)}
              </SpecRow>
              <SpecRow label="checks">
                {evaluate.data.checks_passed} / {evaluate.data.checks_total}
              </SpecRow>
              <SpecRow label="behavioral">
                {evaluate.data.behavioral.available
                  ? `${evaluate.data.behavioral.tests_passed} / ${evaluate.data.behavioral.tests_total} TESTS PASSED`
                  : 'UNAVAILABLE'}
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

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 14 }}>
            <div className="instr-panel" style={{ padding: 22 }}>
              <div className="sys-label" style={{ marginBottom: 12 }}>DEFINITION</div>
              <SpecRow label="version">{tool.data.version}</SpecRow>
              <SpecRow label="confidence">{tool.data.confidence.toFixed(3)}</SpecRow>
              <SpecRow label="description">{tool.data.description || '—'}</SpecRow>
              <SpecRow label="capabilities">{tool.data.capabilities.join(' · ') || '—'}</SpecRow>
              <SpecRow label="parent_version">{tool.data.parent_version ?? '—'}</SpecRow>
              <SpecRow label="dependencies">{tool.data.dependencies.join(' · ') || '—'}</SpecRow>
            </div>
            <div className="instr-panel" style={{ padding: 22 }}>
              <div className="sys-label" style={{ marginBottom: 12 }}>VERIFICATION & PROVENANCE</div>
              <SpecRow label="benchmark">{JSON.stringify(tool.data.benchmark_results)}</SpecRow>
              <SpecRow label="security">{JSON.stringify(tool.data.security_metadata)}</SpecRow>
              <SpecRow label="created">{tool.data.created_at}</SpecRow>
            </div>
            <div className="instr-panel" style={{ padding: 22 }}>
              <div className="sys-label" style={{ marginBottom: 12 }}>SCHEMA & SOURCE</div>
              <SpecRow label="input_schema">{JSON.stringify(tool.data.input_schema)}</SpecRow>
              <SpecRow label="output_schema">{JSON.stringify(tool.data.output_schema)}</SpecRow>
              <SpecRow label="source_code">{tool.data.source_code ? `${tool.data.source_code.length} chars` : '—'}</SpecRow>
              <SpecRow label="tests">{tool.data.tests.length}</SpecRow>
            </div>
          </div>
        </>
      )}
    </div>
  )
}