/** /app/tools/:id — tool details. */
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { useTool } from '../../api/hooks'
import { ModulePending } from '../../app/AppUI'
import { Chip, SpecRow } from '../../components/ui/primitives'

export function ToolDetail() {
  const { id = '' } = useParams()
  const tool = useTool(id)

  return (
    <div>
      <Link to="/app/tools" className="sys-label" style={{ textDecoration: 'none', color: 'var(--text-low)', display: 'inline-flex', gap: 8, alignItems: 'center', marginBottom: 18 }}>
        <ArrowLeft size={12} strokeWidth={1.5} /> TOOL REGISTRY
      </Link>

      {tool.data === undefined ? (
        <ModulePending
          name={`TOOL ${id.toUpperCase()}`}
          shipsIn="PHASE 7"
          contract={['source_code', 'tests', 'benchmark_results', 'security_metadata', 'provenance', 'parent_version']}
        />
      ) : (
        <>
          <div style={{ display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap', marginBottom: 24 }}>
            <h1 style={{ fontSize: 'var(--fs-32)', fontWeight: 600, fontFamily: 'var(--font-mono)', letterSpacing: '0.04em' }}>
              {tool.data.name}
            </h1>
            <Chip label={tool.data.status} tone={tool.data.status === 'REGISTERED' ? 'ok' : 'neutral'} />
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 14 }}>
            <div className="instr-panel" style={{ padding: 22 }}>
              <div className="sys-label" style={{ marginBottom: 12 }}>DEFINITION</div>
              <SpecRow label="version">{tool.data.version}</SpecRow>
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
          </div>
        </>
      )}
    </div>
  )
}