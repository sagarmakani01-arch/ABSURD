import { useQuery } from '@tanstack/react-query'

/**
 * Landing page — placeholder shell verified in Phase 1.
 * The full scroll-driven computational hero lands in Phase 4.
 */
export function Landing() {
  const health = useQuery({
    queryKey: ['health'],
    queryFn: () => fetch('/api/v1/health').then((r) => r.json()),
  })

  return (
    <main
      style={{
        minHeight: '100vh',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '1rem',
        background: '#0a0a0b',
        color: '#e8e6e1',
        fontFamily:
          "'Space Grotesk', 'Inter', system-ui, sans-serif",
      }}
    >
      <h1 style={{ fontSize: '3rem', letterSpacing: '0.4em', fontWeight: 600, margin: 0 }}>
        ABSURD
      </h1>
      <p style={{ color: '#8a877f', letterSpacing: '0.2em', textTransform: 'uppercase', fontSize: '0.7rem' }}>
        Self-Extending Intelligence
      </p>
      <p style={{ color: '#6e6a63', fontSize: '0.85rem' }}>
        gateway: {health.isLoading ? 'probing…' : health.isError ? 'offline' : health.data?.status}
      </p>
    </main>
  )
}