/** Shared app-shell page furniture. */

export function PageHeader({ code, title, sub }: { code: string; title: string; sub: string }) {
  return (
    <header style={{ marginBottom: 30 }}>
      <div className="sys-label sys-label--signal" style={{ marginBottom: 10 }}>
        MODULE {code}
      </div>
      <h1 style={{ fontSize: 'var(--fs-32)', fontWeight: 600, letterSpacing: '-0.01em' }}>{title}</h1>
      <p style={{ color: 'var(--text-mid)', fontSize: 'var(--fs-13)', margin: '8px 0 0', maxWidth: 640 }}>{sub}</p>
    </header>
  )
}

/**
 * Honest placeholder: this module's backend endpoint is not implemented yet
 * (or returns 404). We state exactly which phase ships it and never fake
 * data. The panel still shows the data contract shape.
 */
export function ModulePending({
  name,
  shipsIn,
  contract,
}: {
  name: string
  shipsIn: string
  contract?: string[]
}) {
  return (
    <div className="instr-panel" style={{ padding: 26 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap' }}>
        <div>
          <div className="sys-label" style={{ marginBottom: 6 }}>{name}</div>
        </div>
        <span
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 'var(--fs-11)',
            letterSpacing: '0.1em',
            color: 'var(--warn)',
            border: '1px solid var(--line-2)',
            padding: '3px 10px',
            borderRadius: 'var(--radius-1)',
          }}
        >
          PENDING — SHIPS {shipsIn}
        </span>
      </div>
      <p style={{ color: 'var(--text-low)', fontSize: 'var(--fs-13)', margin: '14px 0 10px' }}>
        Backend endpoint not implemented yet. No fabricated data will be shown here.
      </p>
      {contract && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          {contract.map((f) => (
            <code
              key={f}
              style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 'var(--fs-11)',
                color: 'var(--text-mid)',
                background: 'var(--bg-2)',
                border: '1px solid var(--line-1)',
                padding: '2px 8px',
                borderRadius: 2,
              }}
            >
              {f}
            </code>
          ))}
        </div>
      )}
    </div>
  )
}