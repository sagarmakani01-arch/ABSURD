/**
 * ABSURD component primitives (Phase 3).
 *
 * Minimal, deterministic, engineering-grade. No decorative elevation,
 * no gradients — surfaces are layered, borders carry structure, and the
 * single amber signal color marks active states only.
 */
import { Link } from 'react-router-dom'
import type { LucideIcon } from 'lucide-react'
import { motion } from 'framer-motion'
import { DUR, EASE } from '../../styles/motion'
import type { ReactNode } from 'react'

export type Tone = 'signal' | 'ok' | 'warn' | 'err' | 'neutral'

const TONE_COLOR: Record<Tone, string> = {
  signal: 'var(--signal)',
  ok: 'var(--ok)',
  warn: 'var(--warn)',
  err: 'var(--err)',
  neutral: 'var(--text-low)',
}

/* ---------------------------------------------------------- Button */

type ButtonProps = {
  children: ReactNode
  variant?: 'primary' | 'ghost' | 'bare'
  to?: string
  onClick?: () => void
  type?: 'button' | 'submit'
  disabled?: boolean
  icon?: LucideIcon
  className?: string
}

export function Button({
  children,
  variant = 'primary',
  to,
  onClick,
  type = 'button',
  disabled,
  icon: Icon,
  className = '',
}: ButtonProps) {
  const base: React.CSSProperties = {
    fontFamily: 'var(--font-mono)',
    fontSize: 'var(--fs-12)',
    letterSpacing: 'var(--tracking-mono)',
    textTransform: 'uppercase',
    height: 36,
    padding: '0 18px',
    display: 'inline-flex',
    alignItems: 'center',
    gap: 8,
    cursor: disabled ? 'not-allowed' : 'pointer',
    opacity: disabled ? 0.4 : 1,
    borderRadius: 'var(--radius-1)',
    transition: `background var(--dur-fast) var(--ease-standard), border-color var(--dur-fast) var(--ease-standard), color var(--dur-fast) var(--ease-standard)`,
    textDecoration: 'none',
  }

  const styles: React.CSSProperties =
    variant === 'primary'
      ? {
          ...base,
          background: 'var(--signal)',
          color: '#17130b',
          border: '1px solid transparent',
        }
      : variant === 'ghost'
        ? {
            ...base,
            background: 'transparent',
            color: 'var(--text-mid)',
            border: '1px solid var(--line-2)',
          }
        : { ...base, background: 'none', border: 'none', color: 'var(--text-mid)', padding: 0 }

  const hoverStyle: React.CSSProperties =
    variant === 'primary'
      ? { background: '#ecc97c' }
      : variant === 'ghost'
        ? { color: 'var(--text-hi)', borderColor: 'var(--signal)', background: 'var(--bg-2)' }
        : { color: 'var(--text-hi)' }

  const inner = (
    <>
      {Icon && <Icon size={14} strokeWidth={1.6} />}
      <span>{children}</span>
    </>
  )

  const hoverHandlers = {
    onMouseEnter: (e: React.MouseEvent<HTMLElement>) => {
      Object.assign(e.currentTarget.style, hoverStyle)
    },
    onMouseLeave: (e: React.MouseEvent<HTMLElement>) => {
      Object.assign(e.currentTarget.style, styles)
    },
  }

  if (to)
    return (
      <Link to={to} style={styles} className={className} {...hoverHandlers}>
        {inner}
      </Link>
    )
  return (
    <button type={type} onClick={onClick} disabled={disabled} style={styles} className={className} {...hoverHandlers}>
      {inner}
    </button>
  )
}

/* ------------------------------------------------------------- Chip */

/** Status / state code — the visual language of system states. */
export function Chip({ label, tone = 'neutral', pulse = false }: { label: string; tone?: Tone; pulse?: boolean }) {
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 7,
        fontFamily: 'var(--font-mono)',
        fontSize: 'var(--fs-11)',
        letterSpacing: 'var(--tracking-mono)',
        textTransform: 'uppercase',
        color: TONE_COLOR[tone],
        border: `1px solid color-mix(in srgb, ${TONE_COLOR[tone]} 32%, transparent)`,
        background: `color-mix(in srgb, ${TONE_COLOR[tone]} 7%, transparent)`,
        padding: '2px 9px',
        borderRadius: 'var(--radius-1)',
        whiteSpace: 'nowrap',
      }}
    >
      <motion.span
        aria-hidden
        animate={pulse ? { opacity: [1, 0.25, 1] } : undefined}
        transition={{ duration: 1.6, repeat: Infinity, ease: 'easeInOut' }}
        style={{
          width: 5,
          height: 5,
          borderRadius: '50%',
          background: TONE_COLOR[tone],
          display: 'inline-block',
        }}
      />
      {label}
    </span>
  )
}

/* ------------------------------------------------------- SectionTag */

/** Numbered mono section marker — Swiss index, like "01 — CAPABILITY". */
export function SectionTag({ index, label }: { index: string; label: string }) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        fontFamily: 'var(--font-mono)',
        fontSize: 'var(--fs-11)',
        letterSpacing: 'var(--tracking-mono)',
        textTransform: 'uppercase',
        color: 'var(--text-low)',
      }}
    >
      <span style={{ color: 'var(--signal)' }}>{index}</span>
      <span style={{ width: 32, height: 1, background: 'var(--line-2)' }} />
      <span>{label}</span>
    </div>
  )
}

/* ---------------------------------------------------------- SpecRow */

/** Engineering readout: label / value pair on a hairline row. */
export function SpecRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'baseline',
        gap: 24,
        padding: '9px 0',
        borderTop: '1px solid var(--line-0)',
        fontFamily: 'var(--font-mono)',
        fontSize: 'var(--fs-12)',
      }}
    >
      <span style={{ color: 'var(--text-low)', letterSpacing: 'var(--tracking-mono)', textTransform: 'uppercase' }}>
        {label}
      </span>
      <span style={{ color: 'var(--text-mid)', textAlign: 'right' }}>{children}</span>
    </div>
  )
}

/* --------------------------------------------------------- Reveal */

/** Standard content entry. Respects reduced motion at the CSS level. */
export function Reveal({
  children,
  delay = 0,
  y = 14,
}: {
  children: ReactNode
  delay?: number
  y?: number
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '-64px' }}
      transition={{ duration: DUR.slow / 1000, ease: EASE.emphasize, delay }}
    >
      {children}
    </motion.div>
  )
}