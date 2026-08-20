/**
 * ABSURD hero — HUD + story stage manager (Phase 4).
 *
 * One coherent scroll-driven state machine. The scroll progress (0..1)
 * drives both the 3D structure and the instrument-style readouts; text,
 * structure, and ticks always agree on where the system is.
 */
import { useRef, useState } from 'react'
import { AnimatePresence, motion, useMotionValueEvent, useScroll, useMotionValue } from 'framer-motion'
import { ArrowRight } from 'lucide-react'
import { ComputationalCore } from './ComputationalCore'
import { Button, Chip } from '../ui/primitives'
import { DUR, EASE } from '../../styles/motion'
import { usePrefersReducedMotion } from '../../lib/prefersReducedMotion'

export const STAGES = [
  { code: 'SYS-01', title: 'DORMANT', sub: 'A structured capability space exists. Waiting for a problem.' },
  { code: 'SYS-02', title: 'ACTIVATION', sub: 'Runtime core online. Nodes sequencing onto the lattice.' },
  { code: 'SYS-03', title: 'ANALYSIS', sub: 'Scanning the capability space against the task.' },
  { code: 'SYS-04', title: 'CAPABILITY GAP DETECTED', sub: 'No registered tool can perform: ANOMALY_DETECTION.' },
  { code: 'SYS-05', title: 'DECONSTRUCTION', sub: 'Modules separate along computed trajectories for synthesis.' },
  { code: 'SYS-06', title: 'SYNTHESIZING CAPABILITY', sub: 'Tool specification → implementation → candidate module.' },
  { code: 'SYS-07', title: 'VERIFICATION', sub: 'Candidate enters the evaluation chamber.' },
  { code: 'SYS-08', title: 'REASSEMBLY', sub: 'Verified module returns. Lattice reconfigures.' },
  { code: 'SYS-09', title: 'CAPABILITY ACQUIRED', sub: 'New capability registered into permanent memory.' },
  { code: 'SYS-10', title: 'CAPABILITY SPACE EXPANDED', sub: 'An AI that creates the capabilities it needs.' },
] as const

const BOUNDS = [0.0, 0.1, 0.28, 0.4, 0.5, 0.62, 0.74, 0.86, 0.94, 1.0]

function stageFor(t: number): number {
  for (let i = 0; i < BOUNDS.length - 1; i++) if (t >= BOUNDS[i] && t < BOUNDS[i + 1]) return i
  return BOUNDS.length - 2
}

const MANIFEST: Array<{ name: string; state: 'ok' | 'missing' }> = [
  { name: 'data_loading', state: 'ok' },
  { name: 'normalization', state: 'ok' },
  { name: 'clustering', state: 'ok' },
  { name: 'anomaly_detection', state: 'missing' },
  { name: 'visualization', state: 'ok' },
]

const VERIFY_STEPS = ['GENERATED', 'TESTING', 'BENCHMARKING', 'VALIDATING']

export function HeroStage() {
  const trackRef = useRef<HTMLDivElement>(null)
  const reduced = usePrefersReducedMotion()
  const progress = useMotionValue(0)
  const { scrollYProgress } = useScroll({
    target: trackRef,
    offset: ['start start', 'end start'],
  })
  const [stage, setStage] = useState(0)
  const [verif, setVerif] = useState(0)

  useMotionValueEvent(scrollYProgress, 'change', (v) => {
    const t = reduced ? 1 : v
    progress.set(t)
    setStage(stageFor(t))
    setVerif(t)
  })

  if (reduced) {
    progress.set(1)
  }

  const s = STAGES[stage]
  const verifStep = Math.min(3, Math.max(0, Math.floor(((verif - 0.74) / 0.12) * 4)))
  const showManifest = stage === 2 || stage === 3

  return (
    <>
      {/* Scroll track */}
      <div ref={trackRef} style={{ height: '900vh' }} aria-hidden />
      {/* Sticky stage */}
      <div
        style={{
          position: 'sticky',
          top: 0,
          height: '100vh',
          overflow: 'hidden',
          background: 'var(--bg-0)',
        }}
      >
        <ComputationalCore progress={progress} reduced={reduced} />

        {/* Top instrumentation bar */}
        <header
          style={{
            position: 'absolute',
            inset: '0 0 auto 0',
            padding: '18px 26px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 16,
            zIndex: 5,
          }}
        >
          <div style={{ fontFamily: 'var(--font-display)', fontWeight: 600, fontSize: 15, letterSpacing: '0.22em' }}>
            ABSURD
          </div>
          <div className="sys-label" style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
            <span>{s.code}</span>
            <span style={{ width: 1, height: 12, background: 'var(--line-2)' }} />
            <span>{s.title}</span>
          </div>
          <Button to="/app" variant="ghost">
            ENTER ABSURD
          </Button>
        </header>

        {/* Center stage readout */}
        <div
          style={{
            position: 'absolute',
            left: '50%',
            top: '50%',
            transform: 'translate(-50%, -50%)',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: 14,
            textAlign: 'center',
            zIndex: 3,
            pointerEvents: 'none',
            width: 'min(680px, 86vw)',
          }}
        >
          <AnimatePresence mode="wait">
            <motion.div
              key={s.code}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: DUR.slow / 1000, ease: EASE.emphasize }}
              style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 14 }}
            >
              <div className="sys-label sys-label--signal">{s.code}</div>
              <h1
                style={{
                  fontSize: 'clamp(1.6rem, 4.6vw, 3.2rem)',
                  fontWeight: 600,
                  color: 'var(--text-hi)',
                  maxWidth: 640,
                  lineHeight: 1.06,
                }}
              >
                {s.title}
              </h1>
              <p style={{ color: 'var(--text-mid)', fontSize: 'var(--fs-14)', maxWidth: 460, margin: 0 }}>
                {s.sub}
              </p>
            </motion.div>
          </AnimatePresence>

          {/* Verification sub-steps */}
          {stage === 6 && (
            <div
              style={{
                display: 'flex',
                gap: 10,
                marginTop: 8,
                flexWrap: 'wrap',
                justifyContent: 'center',
              }}
            >
              {VERIFY_STEPS.map((label, i) => (
                <Chip key={label} label={label} tone={i < verifStep ? 'ok' : i === verifStep ? 'signal' : 'neutral'} pulse={i === verifStep} />
              ))}
            </div>
          )}

          {/* Final CTAs */}
          {stage >= 8 && (
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.25, duration: DUR.slow / 1000, ease: EASE.emphasize }}
              style={{ display: 'flex', gap: 14, marginTop: 18, pointerEvents: 'auto' }}
            >
              <Button to="/app" icon={ArrowRight}>
                ENTER ABSURD
              </Button>
              <Button to="/app/system" variant="ghost">
                VIEW THE SYSTEM
              </Button>
            </motion.div>
          )}
        </div>

        {/* Capability manifest (ANALYSIS + GAP stages) */}
        <AnimatePresence>
          {showManifest && (
            <motion.aside
              initial={{ opacity: 0, x: -14 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -14 }}
              transition={{ duration: DUR.med / 1000, ease: EASE.standard }}
              className="instr-panel"
              style={{
                position: 'absolute',
                left: 30,
                bottom: 60,
                padding: '14px 16px',
                width: 232,
                zIndex: 4,
              }}
            >
              <div className="sys-label" style={{ marginBottom: 10 }}>
                CAPABILITY REQUIRED
              </div>
              {MANIFEST.map((m) => (
                <div
                  key={m.name}
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    gap: 12,
                    padding: '5px 0',
                    fontFamily: 'var(--font-mono)',
                    fontSize: 'var(--fs-11)',
                    letterSpacing: '0.08em',
                    borderTop: '1px solid var(--line-0)',
                    color: m.state === 'ok' ? 'var(--text-mid)' : 'var(--err)',
                  }}
                >
                  <span>{m.name}</span>
                  <span>{m.state === 'ok' ? 'OK' : 'MISSING'}</span>
                </div>
              ))}
            </motion.aside>
          )}
        </AnimatePresence>

        {/* Stage ticks */}
        <div
          style={{
            position: 'absolute',
            left: 30,
            bottom: 34,
            display: 'none',
            gap: 6,
            zIndex: 4,
          }}
          className="sys-label"
        >
          {STAGES.map((st, i) => (
            <span
              key={st.code}
              style={{
                color: i === stage ? 'var(--signal)' : 'var(--text-low)',
                marginRight: 4,
              }}
            >
              {String(i + 1).padStart(2, '0')}
            </span>
          ))}
        </div>

        {/* Scroll progress rail */}
        <div
          style={{
            position: 'absolute',
            right: 26,
            top: '50%',
            transform: 'translateY(-50%)',
            height: '38vh',
            width: 1,
            background: 'var(--line-1)',
            zIndex: 4,
          }}
        >
          <motion.div
            style={{
              width: 1,
              background: 'var(--signal)',
              height: '100%',
              scaleY: scrollYProgress,
              transformOrigin: 'top',
            }}
          />
          <div className="sys-label" style={{ position: 'absolute', top: -28, right: 4 }}>
            SCROLL
          </div>
        </div>
      </div>
    </>
  )
}