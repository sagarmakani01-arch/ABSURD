/**
 * ABSURD hero — deterministic structure math (Phase 4).
 *
 * Pure functions describing the computational object and its scroll-driven
 * timeline. Everything is calculated, never random: nodes occupy fixed
 * lattice positions, deconstruction follows radial trajectories, and the
 * capability ring reconfigures from 8 to 9 slots when the new capability
 * is acquired.
 */

export type NodeKind = 'memory' | 'capability' | 'tool'

export interface NodeDef {
  id: string
  kind: NodeKind
  ring: number
  index: number
  ringSize: number
  radius: number
  y: number
  dir: number // deterministic drift direction for deconstruction
}

/** Ring 1 (capability ring) — index 7 is the missing capability slot. */
export const GAP_RING = 1
export const GAP_INDEX = 7

/** Where the evaluation chamber lives. */
export const CHAMBER_POS: [number, number, number] = [2.75, -0.45, 0.5]

export function clamp01(x: number): number {
  return Math.min(1, Math.max(0, x))
}

export function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t
}

export function smoothstep(a: number, b: number, x: number): number {
  const t = clamp01((x - a) / (b - a))
  return t * t * (3 - 2 * t)
}

export function easeOutBack(t: number): number {
  const c1 = 1.70158
  const c3 = c1 + 1
  const x = clamp01(t)
  return 1 + c3 * Math.pow(x - 1, 3) + c1 * Math.pow(x - 1, 2)
}

/* ---------------- The lattice (computed once) ---------------- */

export function buildLattice(): {
  nodes: NodeDef[]
  gapDef: NodeDef
} {
  const rings = [
    { kind: 'memory' as const, count: 4, radius: 1.18, y: 0.22 },
    { kind: 'capability' as const, count: 8, radius: 1.82, y: -0.02 },
    { kind: 'tool' as const, count: 12, radius: 2.38, y: -0.44 },
  ]
  const nodes: NodeDef[] = []
  for (const [ring, r] of rings.entries()) {
    for (let i = 0; i < r.count; i++) {
      nodes.push({
        id: `n${ring}-${i}`,
        kind: r.kind,
        ring,
        index: i,
        ringSize: r.count,
        radius: r.radius,
        y: r.y,
        dir: i % 2 === 0 ? 1 : -1,
      })
    }
  }
  const ring1 = rings[1]
  const gapDef: NodeDef = {
    id: 'cap-gap',
    kind: 'capability',
    ring: GAP_RING,
    index: GAP_INDEX,
    ringSize: ring1.count,
    radius: ring1.radius,
    y: ring1.y,
    dir: 1,
  }
  return { nodes, gapDef }
}

/* ---------------- Timeline segments (t ∈ [0,1]) ---------------- */

export interface Timeline {
  act: number // activation
  ana: number // analysis / scan
  d: number // deconstruction
  s: number // synthesis
  v: number // verification
  m: number // reassembly
  e: number // expanded
}

export function timeline(t: number): Timeline {
  return {
    act: smoothstep(0.1, 0.3, t),
    ana: smoothstep(0.28, 0.4, t),
    d: smoothstep(0.5, 0.62, t),
    s: smoothstep(0.62, 0.74, t),
    v: smoothstep(0.74, 0.86, t),
    m: smoothstep(0.86, 0.94, t),
    e: smoothstep(0.94, 1, t),
  }
}

/* ---------------- Node placement ---------------- */

/** Angle on the capability ring: 8 slots, then 9 after reassembly. */
export function ring1Angle(index: number, m: number): number {
  const before = (index / 8) * Math.PI * 2
  const after = (index / 9) * Math.PI * 2
  return lerp(before, after, m)
}

export interface NodeState {
  position: [number, number, number]
  scale: number
  /** 0..1 how "lit" this node is; below 0.15 the node is dormant. */
  lit: number
  connectorAlpha: number
}

/**
 * Transform for an existing node at time t.
 * Deconstruction pushes nodes outward along their radial direction with a
 * deterministic per-node offset — every movement is a calculated trajectory.
 */
export function nodeState(def: NodeDef, _t: number, tl: Timeline): NodeState {
  let angle: number
  if (def.ring === GAP_RING) {
    angle = ring1Angle(def.index, tl.m)
  } else {
    angle = (def.index / def.ringSize) * Math.PI * 2
  }

  const drift = def.ring === GAP_RING ? tl.d : tl.d * (0.72 + 0.3 * (def.index % 3))
  angle += tl.d * def.dir * 0.55
  const radius = def.radius * (1 + drift * 1.55)

  const position: [number, number, number] = [
    Math.cos(angle) * radius,
    def.y,
    Math.sin(angle) * radius,
  ]

  // Sequential activation sweeps around the structure: sorted by angle.
  const order = (def.index / def.ringSize + def.ring * 0.13) % 1
  const lit = tl.act * clamp01(1 - Math.max(0, order * 1.6 - 1.35)) * 0.9 + (1 - tl.act) * 0.12

  const dScale = 1 - drift * 0.22
  return { position, scale: dScale, lit, connectorAlpha: lit * (1 - tl.d) }
}

export interface ModuleState {
  /** Where the gap module sits this frame: 'slot' | 'chamber' | 'home' */
  position: [number, number, number]
  scale: number
  lit: number
}

/**
 * The gap module: born at the empty slot during synthesis, travels to the
 * evaluation chamber during verification, returns home during reassembly.
 */
export function moduleState(_t: number, tl: Timeline): ModuleState {
  const slotAngle = ring1Angle(GAP_INDEX, tl.m)
  const home: [number, number, number] = [
    Math.cos(slotAngle) * 1.82 * (1 + tl.d * 0.4),
    -0.02,
    Math.sin(slotAngle) * 1.82 * (1 + tl.d * 0.4),
  ]
  const slot: [number, number, number] = [
    Math.cos(slotAngle) * 1.82,
    -0.02,
    Math.sin(slotAngle) * 1.82,
  ]
  const chamber = CHAMBER_POS

  // Synthesis→chamber transition (eject), chamber→home (return, spring-like).
  const eject = smoothstep(0, 0.72, tl.v)
  const returnPath = smoothstep(0, 0.85, tl.m)
  const position: [number, number, number] =
    tl.v > 0
      ? chamber.map((c, i) => lerp(lerp(slot[i], c, eject), home[i], returnPath)) as [
          number,
          number,
          number,
        ]
      : (slot.map((s, i) => lerp(s, home[i], tl.m)) as [number, number, number])

  const appears = easeOutBack(tl.s)
  const scale = tl.s > 0 ? appears : 0.62 // dormant gap marker scale
  const lit = tl.s * 0.9 + 0.08
  return { position, scale, lit }
}