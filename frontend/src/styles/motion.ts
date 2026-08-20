/**
 * ABSURD motion presets (Phase 3).
 *
 * Motion communicates system behavior — state transitions, structural
 * changes, verification sweeps. Never decoration. Honoring reduced motion
 * is a hard requirement: all consumer components must gate their animation
 * behind `useReducedMotion` or the global CSS override.
 */

export const EASE = {
  /** Standard transform easings — SwiftUI-style, restrained. */
  standard: [0.2, 0, 0, 1] as const,
  /** Exit / cinematic emphasis — used for movement that signals meaning. */
  emphasize: [0.16, 1, 0.3, 1] as const,
  /** Crawl — readouts, scanning lines. */
  linear: [0, 0, 1, 1] as const,
}

export const DUR = {
  fast: 120,
  med: 200,
  slow: 320,
  film: 800,
} as const

export const SPRING = {
  /** Interactive elements. */
  snappy: { type: 'spring', stiffness: 640, damping: 38, mass: 0.9 } as const,
  /** Structural transitions — modules seating/separating. */
  structural: { type: 'spring', stiffness: 300, damping: 26, mass: 1.1 } as const,
}

/** Consistent fade+rise for content that enters the viewport. */
export const rise = (delay = 0) => ({
  initial: { opacity: 0, y: 16 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: DUR.slow / 1000, ease: EASE.emphasize, delay },
})