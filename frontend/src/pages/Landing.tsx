/**
 * ABSURD — landing page (Phase 4).
 *
 * Scroll-driven cinematic hero followed by four quiet research sections:
 * the limit, the loop, security, and the entry point. The voice is a
 * systems laboratory — precise, restrained, no hype.
 */
import { Suspense, lazy, useMemo } from 'react'
import { ShieldCheck, Cpu, Boxes, RefreshCw, MemoryStick, FlaskConical } from 'lucide-react'
import { Button, Reveal, SectionTag, SpecRow } from '../components/ui/primitives'
import { usePrefersReducedMotion } from '../lib/prefersReducedMotion'

const LandingHero = lazy(() =>
  import('./LandingHero').then((m) => ({ default: m.default })),
)

const LOOP = [
  { n: '01', label: 'UNDERSTAND', icon: Cpu },
  { n: '02', label: 'DECOMPOSE', icon: Boxes },
  { n: '03', label: 'CHECK CAPABILITIES', icon: MemoryStick },
  { n: '04', label: 'SYNTHESIZE TOOL', icon: FlaskConical },
  { n: '05', label: 'VERIFY IN SANDBOX', icon: ShieldCheck },
  { n: '06', label: 'REGISTER', icon: RefreshCw },
  { n: '07', label: 'COMPOSE', icon: Boxes },
  { n: '08', label: 'EXECUTE', icon: Cpu },
  { n: '09', label: 'EVALUATE', icon: FlaskConical },
  { n: '10', label: 'REMEMBER', icon: MemoryStick },
]

const TRUST = [
  { name: 'GENERATED TOOL', state: 'UNKNOWN' },
  { name: 'STATIC + SECURITY ANALYSIS', state: 'EXAMINED' },
  { name: 'TESTS + BENCHMARKS', state: 'TESTED' },
  { name: 'SANDBOX VERIFIED', state: 'VERIFIED' },
  { name: 'REGISTRY', state: 'TRUSTED' },
]

export function Landing() {
  const reduced = usePrefersReducedMotion()
  const hero = useMemo(
    () => (
      <Suspense fallback={<div style={{ height: '100vh' }} />}>
        <LandingHero reduced={reduced} />
      </Suspense>
    ),
    [reduced],
  )

  return (
    <main style={{ background: 'var(--bg-0)', minHeight: '100vh' }}>
      {hero}

      {/* 01 — The limit */}
      <section style={{ maxWidth: 1080, margin: '0 auto', padding: '140px 26px' }}>
        <Reveal>
          <SectionTag index="01" label="THE LIMIT" />
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 40, marginTop: 34 }}>
            <div>
              <h2 style={{ fontSize: 'var(--fs-32)', fontWeight: 500, marginBottom: 18 }}>
                Every agent is sealed inside its toolkit.
              </h2>
              <p style={{ color: 'var(--text-mid)', fontSize: 'var(--fs-16)', lineHeight: 1.75 }}>
                A capable LLM can reason, but it cannot act beyond the tools a developer shipped
                with it. When a new problem arrives — anomaly detection, graph building, an
                unfamiliar format — a fixed-tool agent has three options: fail, prompt its way
                around the gap, or wait for a human to write a new tool.
              </p>
            </div>
            <div className="instr-panel" style={{ padding: 24, alignSelf: 'start' }}>
              <div className="sys-label" style={{ marginBottom: 8 }}>FIXED-TOOL AGENT</div>
              <SpecRow label="New problem">requires new tool</SpecRow>
              <SpecRow label="Response">fails or improvises</SpecRow>
              <SpecRow label="New capability">manual, human-written</SpecRow>
              <SpecRow label="Compound knowledge">lost after the session</SpecRow>
            </div>
          </div>
        </Reveal>
      </section>

      {/* 02 — The loop */}
      <section style={{ background: 'var(--bg-1)', borderTop: '1px solid var(--line-1)', borderBottom: '1px solid var(--line-1)' }}>
        <div style={{ maxWidth: 1080, margin: '0 auto', padding: '110px 26px' }}>
          <Reveal>
            <SectionTag index="02" label="THE LOOP" />
            <p style={{ color: 'var(--text-hi)', fontSize: 'var(--fs-20)', maxWidth: 620, margin: '18px 0 40px' }}>
              ABSURD treats missing capabilities as problems to solve, not walls to hit.
            </p>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(185px, 1fr))', gap: 10 }}>
              {LOOP.map((step) => (
                <div
                  key={step.n}
                  className="instr-panel"
                  style={{ padding: '16px 18px', display: 'flex', flexDirection: 'column', gap: 10 }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span className="sys-label sys-label--signal">{step.n}</span>
                    <step.icon size={15} strokeWidth={1.5} color="var(--text-low)" />
                  </div>
                  <span
                    style={{
                      fontFamily: 'var(--font-mono)',
                      fontSize: 'var(--fs-12)',
                      letterSpacing: '0.1em',
                      color: 'var(--text-mid)',
                    }}
                  >
                    {step.label}
                  </span>
                </div>
              ))}
            </div>
          </Reveal>
        </div>
      </section>

      {/* 03 — Security */}
      <section style={{ maxWidth: 1080, margin: '0 auto', padding: '120px 26px' }}>
        <Reveal>
          <SectionTag index="03" label="SECURITY" />
        </Reveal>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 48, marginTop: 34 }}>
          <Reveal>
            <div>
              <h2 style={{ fontSize: 'var(--fs-32)', fontWeight: 500, marginBottom: 18 }}>
                Generated code never touches the host.
              </h2>
              <p style={{ color: 'var(--text-mid)', fontSize: 'var(--fs-16)', lineHeight: 1.75 }}>
                Every synthesized tool runs inside a fail-closed sandbox: isolated filesystem,
                network disabled by default, hard CPU/memory/time limits, no credentials. If the
                sandbox is unavailable, execution is blocked — never degraded to running on the
                host. Only tools that pass tests, benchmarks, and verification enter the registry.
              </p>
            </div>
          </Reveal>
          <Reveal delay={0.08}>
            <div className="instr-panel" style={{ padding: 24 }}>
              <div className="sys-label" style={{ marginBottom: 8 }}>TRUST LADDER</div>
              {TRUST.map((r, i) => (
                <div
                  key={r.name}
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    gap: 16,
                    padding: '8px 0',
                    borderTop: '1px solid var(--line-0)',
                    fontFamily: 'var(--font-mono)',
                    fontSize: 'var(--fs-11)',
                    letterSpacing: '0.08em',
                  }}
                >
                  <span style={{ color: i === TRUST.length - 1 ? 'var(--ok)' : 'var(--text-mid)' }}>{r.name}</span>
                  <span style={{ color: i === TRUST.length - 1 ? 'var(--ok)' : 'var(--text-low)' }}>{r.state}</span>
                </div>
              ))}
            </div>
          </Reveal>
        </div>
      </section>

      {/* 04 — Enter */}
      <section style={{ background: 'var(--bg-1)', borderTop: '1px solid var(--line-1)' }}>
        <div style={{ maxWidth: 1080, margin: '0 auto', padding: '110px 26px 90px', textAlign: 'center' }}>
          <Reveal>
            <div className="sys-label sys-label--signal" style={{ marginBottom: 16 }}>
              RESEARCH INSTRUMENT — PRE-ALPHA
            </div>
            <h2 style={{ fontSize: 'clamp(2rem, 5vw, 3.4rem)', fontWeight: 600, marginBottom: 16 }}>
              Enter the system.
            </h2>
            <p style={{ color: 'var(--text-mid)', margin: '0 auto 34px', maxWidth: 520 }}>
              Watch ABSURD detect a gap, synthesize a tool, verify it, and acquire
              the capability — live, event by event.
            </p>
            <div style={{ display: 'flex', gap: 14, justifyContent: 'center' }}>
              <Button to="/app">ENTER ABSURD</Button>
              <Button to="/app/tasks" variant="ghost">
                EVENTS
              </Button>
            </div>
          </Reveal>
        </div>
      </section>

      <footer
        style={{
          maxWidth: 1080,
          margin: '0 auto',
          padding: '26px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: 16,
          flexWrap: 'wrap',
        }}
      >
        <span className="sys-label">ABSURD // SELF-EXTENDING INTELLIGENCE</span>
        <a
          href="https://github.com/sagarmakani01-arch/ABSURD"
          target="_blank"
          rel="noreferrer"
          className="sys-label"
          style={{ display: 'inline-flex', alignItems: 'center', gap: 8, color: 'var(--text-mid)', textDecoration: 'none' }}
        >
          <svg width="13" height="13" viewBox="0 0 16 16" fill="currentColor" aria-hidden>
            <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27s1.36.09 2 .27c1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8Z" />
          </svg>{' '}
          github.com/sagarmakani01-arch/ABSURD
        </a>
      </footer>
    </main>
  )
}