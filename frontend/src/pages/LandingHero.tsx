/**
 * Landing hero dispatcher — the whole WebGL hero lives behind a single
 * lazy chunk, so the landing shell paints instantly and the three.js
 * workload loads after first paint. Reduced-motion users get the static
 * final-state structure instead of the scroll-driven sequence.
 */
import { useMotionValue } from 'framer-motion'
import { memo } from 'react'
import { ComputationalCore } from '../components/hero/ComputationalCore'
import { HeroStage } from '../components/hero/HeroStage'
import { Button } from '../components/ui/primitives'

const StaticStructure = memo(function StaticStructure() {
  const progress = useMotionValue(1)
  return (
    <div style={{ position: 'absolute', inset: 0 }}>
      <ComputationalCore progress={progress} reduced />
    </div>
  )
})

export default function LandingHero({ reduced }: { reduced: boolean }) {
  if (reduced) {
    return (
      <div style={{ height: '86vh', position: 'relative' }}>
        <StaticStructure />
        <div
          style={{
            position: 'absolute',
            inset: 0,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'flex-end',
            paddingBottom: '9vh',
            gap: 10,
            textAlign: 'center',
            pointerEvents: 'none',
          }}
        >
          <div className="sys-label sys-label--signal">SYS-10</div>
          <h1 style={{ fontSize: 'clamp(1.6rem, 4.6vw, 3rem)', fontWeight: 600 }}>
            CAPABILITY SPACE EXPANDED
          </h1>
          <p style={{ color: 'var(--text-mid)', fontSize: 'var(--fs-13)', maxWidth: 440, margin: '8px 0 22px' }}>
            An AI that creates the capabilities it needs.
          </p>
          <div style={{ display: 'flex', gap: 14, pointerEvents: 'auto' }}>
            <Button to="/app">ENTER ABSURD</Button>
            <Button to="/app/system" variant="ghost">
              VIEW THE SYSTEM
            </Button>
          </div>
        </div>
      </div>
    )
  }

  return <HeroStage />
}