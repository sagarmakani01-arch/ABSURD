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