/**
 * ABSURD hero — the computational object (Phase 4).
 *
 * An engineered lattice: a runtime core, three node rings (memory,
 * capability, tool), deterministic connectors, an evaluation chamber, and
 * the capability-gap module with its synthesis → verification → reassembly
 * journey. Everything is computed from the scroll timeline — nothing
 * random. Renders to a canvas with instanced-ish low-poly meshes.
 */
import { useMemo, useRef } from 'react'
import type { MotionValue } from 'framer-motion'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import * as THREE from 'three'
import {
  buildLattice,
  CHAMBER_POS,
  moduleState,
  nodeState,
  timeline,
  smoothstep,
  type NodeDef,
} from './structure'

const C = {
  bg: '#08080a',
  signal: '#e0b15c',
  ok: '#8fae83',
  err: '#c65f66',
  info: '#8fa3c2',
  grey: '#9aa0ab',
  dim: '#2a2e37',
}

/* ------------------------------------------------------------ Node */

function NodeMesh({ def, progress }: { def: NodeDef; progress: MotionValue<number> }) {
  const ref = useRef<THREE.Mesh>(null)
  const mat = useMemo(
    () =>
      new THREE.MeshBasicMaterial({
        color: def.kind === 'memory' ? C.info : def.kind === 'capability' ? C.signal : C.grey,
        transparent: true,
        opacity: 0.12,
      }),
    [def],
  )

  const geometry = useMemo(() => {
    if (def.kind === 'memory') return new THREE.TetrahedronGeometry(0.1)
    if (def.kind === 'capability') return new THREE.BoxGeometry(0.11, 0.11, 0.11)
    return new THREE.IcosahedronGeometry(0.085, 0)
  }, [def])

  useFrame((state, delta) => {
    const t = progress.get()
    const tl = timeline(t)
    const s = nodeState(def, t, tl)
    ref.current?.position.set(...s.position)
    ref.current?.scale.setScalar(s.scale)

    // Dormant: slow breathing, near-zero motion. Active: full opacity.
    const breathe = 1 + Math.sin(state.clock.elapsedTime * 0.6 + def.index) * 0.04
    mat.opacity = s.lit * breathe
    if (ref.current) ref.current.rotation.y += delta * (0.05 + s.lit * 0.35) * def.dir
  })

  return <mesh ref={ref} geometry={geometry} material={mat} />
}

/* -------------------------------------------------------- Connectors */

function ConnectorGroup({ progress }: { progress: MotionValue<number> }) {
  const lineRef = useRef<THREE.LineSegments>(null)
  const { nodes } = useMemo(() => buildLattice(), [])

  // 2 verts per node (node -> core), 3 floats each.
  const positions = useMemo(() => new Float32Array(nodes.length * 2 * 3), [nodes.length])
  const geometry = useMemo(() => {
    const g = new THREE.BufferGeometry()
    g.setAttribute('position', new THREE.BufferAttribute(positions, 3))
    return g
  }, [positions])
  const material = useMemo(
    () =>
      new THREE.LineBasicMaterial({
        color: C.dim,
        transparent: true,
        opacity: 0.5,
      }),
    [],
  )

  useFrame(() => {
    const t = progress.get()
    const tl = timeline(t)
    let idx = 0
    for (const def of nodes) {
      const s = nodeState(def, t, tl)
      positions[idx++] = s.position[0]
      positions[idx++] = s.position[1]
      positions[idx++] = s.position[2]
      positions[idx++] = 0
      positions[idx++] = 0
      positions[idx++] = 0
    }
    geometry.attributes.position.needsUpdate = true
    material.opacity = 0.05 + 0.3 * tl.act
  })

  return <lineSegments ref={lineRef} geometry={geometry} material={material} />
}

/* --------------------------------------------------------------- Core */

function Core({ progress }: { progress: MotionValue<number> }) {
  const outer = useRef<THREE.Mesh>(null)
  const inner = useRef<THREE.Mesh>(null)
  const shellMat = useMemo(
    () =>
      new THREE.MeshBasicMaterial({ color: C.signal, transparent: true, opacity: 0.22, wireframe: true }),
    [],
  )
  const coreMat = useMemo(
    () =>
      new THREE.MeshBasicMaterial({
        color: '#1c1f26',
        transparent: true,
        opacity: 0.9,
        wireframe: false,
      }),
    [],
  )
  const edgeMat = useMemo(
    () => new THREE.LineBasicMaterial({ color: C.signal, transparent: true, opacity: 0.35 }),
    [],
  )

  useFrame((_, delta) => {
    const t = progress.get()
    const tl = timeline(t)
    const o = outer.current
    const i = inner.current
    if (!o || !i) return
    const compress = 1 - tl.d * 0.28 + tl.m * 0.06
    o.rotation.y += delta * 0.12
    i.rotation.y -= delta * 0.08
    i.rotation.x += delta * 0.05
    o.scale.setScalar(compress)
    i.scale.setScalar(compress)
    shellMat.opacity = 0.14 + tl.act * 0.16 + tl.s * 0.18
  })

  return (
    <group position={[0, 0, 0]}>
      <mesh ref={outer}>
        <icosahedronGeometry args={[0.62, 0]} />
        <primitive object={shellMat} attach="material" />
      </mesh>
      <mesh ref={inner}>
        <octahedronGeometry args={[0.34, 0]} />
        <primitive object={coreMat} attach="material" />
        <lineSegments>
          {/* octahedron edges overlay */}
          <edgesGeometry args={[new THREE.OctahedronGeometry(0.34, 0)]} />
          <primitive object={edgeMat} attach="material" />
        </lineSegments>
      </mesh>
    </group>
  )
}

/* --------------------------------------------------------- ScanRing */

/** Analysis sweep: a thin ring traces the capability ring during ANALYSIS. */
function ScanRing({ progress }: { progress: MotionValue<number> }) {
  const ref = useRef<THREE.Mesh>(null)
  const mat = useMemo(
    () =>
      new THREE.MeshBasicMaterial({
        color: C.info,
        transparent: true,
        opacity: 0,
        side: THREE.DoubleSide,
      }),
    [],
  )

  useFrame(() => {
    const t = progress.get()
    const tl = timeline(t)
    const trace = smoothstep(0.28, 0.5, t)
    if (ref.current) ref.current.rotation.y = -trace * Math.PI * 3
    mat.opacity = tl.ana * 0.5
  })

  return (
    <mesh ref={ref} position={[0, -0.02, 0]} rotation={[Math.PI / 2, 0, 0]}>
      <torusGeometry args={[1.82, 0.008, 8, 96]} />
      <primitive object={mat} attach="material" />
    </mesh>
  )
}

/* ---------------------------------------------------- Gap slot ring */

/** The empty slot: an err-colored wireframe shell marking the missing capability.
 *  Present from GAP detection until the new module is born. */
function GapSlotMarker({ progress }: { progress: MotionValue<number> }) {
  const ref = useRef<THREE.Mesh>(null)
  const mat = useMemo(
    () =>
      new THREE.MeshBasicMaterial({
        color: C.err,
        transparent: true,
        opacity: 0.3,
        wireframe: true,
      }),
    [],
  )
  const gapSlot: [number, number, number] = useMemo(() => {
    const angle = (7 / 8) * Math.PI * 2
    return [Math.cos(angle) * 1.82, -0.02, Math.sin(angle) * 1.82]
  }, [])

  useFrame((state) => {
    const t = progress.get()
    const tl = timeline(t)
    const gapVis = smoothstep(0.36, 0.44, t) * (1 - tl.s)
    if (ref.current) {
      ref.current.visible = gapVis > 0.01
      ref.current.position.set(...gapSlot)
      ref.current.rotation.y += state.clock.elapsedTime < 0 ? 0 : 0.008
    }
    mat.opacity = 0.18 + gapVis * 0.55 + Math.sin(state.clock.elapsedTime * 2.4) * 0.06 * gapVis
  })

  return (
    <mesh ref={ref} material={mat}>
      <octahedronGeometry args={[0.13, 0]} />
    </mesh>
  )
}

/* ------------------------------------------------- The gap module */

function GapModule({ progress }: { progress: MotionValue<number> }) {
  const ref = useRef<THREE.Mesh>(null)
  const frameRef = useRef<THREE.Mesh>(null)
  const bodyMat = useMemo(
    () =>
      new THREE.MeshBasicMaterial({ color: C.signal, transparent: true, opacity: 0.9 }),
    [],
  )
  const frameMat = useMemo(
    () =>
      new THREE.MeshBasicMaterial({
        color: C.grey,
        transparent: true,
        opacity: 0.5,
        wireframe: true,
      }),
    [],
  )

  useFrame(() => {
    const t = progress.get()
    const tl = timeline(t)
    const st = moduleState(t, tl)

    // The gap module exists as a shell below synthesis; only render once born.
    const born = tl.s > 0.01
    if (ref.current) ref.current.visible = born
    if (frameRef.current) frameRef.current.visible = born
    if (born) {
      ref.current?.position.set(...st.position)
      frameRef.current?.position.set(...st.position)

      // Body engages during verification, cools during reassembly.
      const engage = 1 - smoothstep(0, 1, Math.abs(0.5 - tl.v) * 2) * 0.5
      bodyMat.opacity = st.lit + 0.15 * engage
      const pop = st.scale * (tl.v > 0 ? 1.12 : 1)
      ref.current?.scale.setScalar(pop)
      frameRef.current?.scale.setScalar(pop * 1.18)
    }
  })

  return (
    <group>
      <mesh ref={ref} geometry={new THREE.OctahedronGeometry(0.12, 0)} material={bodyMat} />
      <mesh ref={frameRef} geometry={new THREE.BoxGeometry(0.26, 0.26, 0.26)} material={frameMat} />
    </group>
  )
}

/* ------------------------------------------------------- Fragments */

/** A dozen shards converge on the gap slot during SYNTHESIS. */
function Fragments({ progress }: { progress: MotionValue<number> }) {
  const group = useRef<THREE.Group>(null)
  const mat = useMemo(
    () => new THREE.MeshBasicMaterial({ color: C.signal, transparent: true, opacity: 0.7 }),
    [],
  )
  const dirs = useMemo(() => {
    const out: [number, number, number][] = []
    for (let i = 0; i < 12; i++) {
      const phi = Math.acos(1 - (2 * (i + 0.5)) / 12)
      const theta = Math.PI * (1 + Math.sqrt(5)) * i
      out.push([Math.sin(phi) * Math.cos(theta), Math.cos(phi), Math.sin(phi) * Math.sin(theta)])
    }
    return out
  }, [])

useFrame(() => {
    const t = progress.get()
    const tl = timeline(t)
    const s = tl.s
    if (!group.current) return
    group.current.visible = s > 0.01 && s < 0.99
    if (s <= 0.01 || s >= 0.99) return
    // Fragments converge on the gap slot during synthesis.
    const slot: [number, number, number] = [
      Math.cos((7 / 8) * Math.PI * 2) * 1.82,
      -0.02,
      Math.sin((7 / 8) * Math.PI * 2) * 1.82,
    ]
    group.current.position.set(...slot)
    group.current.children.forEach((child, i) => {
      const r = 0.55 * (1 - smoothstep(0.0, 0.85, s))
      const d = dirs[i]
      child.position.set(d[0] * r, d[1] * r, d[2] * r)
      child.scale.setScalar(0.05 + s * 0.02)
    })
  })

  return (
    <group ref={group}>
      {dirs.map((_, i) => (
        <mesh key={i} material={mat}>
          <tetrahedronGeometry args={[0.045, 0]} />
        </mesh>
      ))}
    </group>
  )
}

/* --------------------------------------------------------- Chamber */

function Chamber({ progress }: { progress: MotionValue<number> }) {
  const frameRef = useRef<THREE.Mesh>(null)
  const wallRef = useRef<THREE.Mesh>(null)
  const sweepRef = useRef<THREE.Mesh>(null)
  const sweepMat = useMemo(
    () =>
      new THREE.MeshBasicMaterial({
        color: C.ok,
        transparent: true,
        opacity: 0,
        side: THREE.DoubleSide,
      }),
    [],
  )
  const frameMat = useMemo(
    () =>
      new THREE.MeshBasicMaterial({
        color: C.ok,
        transparent: true,
        opacity: 0,
        wireframe: true,
      }),
    [],
  )
  const wallMat = useMemo(
    () =>
      new THREE.MeshBasicMaterial({
        color: C.ok,
        transparent: true,
        opacity: 0,
        wireframe: true,
      }),
    [],
  )

  useFrame((state) => {
    const t = progress.get()
    const tl = timeline(t)
    const open = tl.v * (1 - tl.m * 0.4)
    frameMat.opacity = open * 0.55
    wallMat.opacity = open * 0.12
    frameRef.current?.scale.setScalar(0.6 + open * 0.4)
    wallRef.current?.scale.setScalar(0.6 + open * 0.4)

    // Verification sweep: a plane scans the volume while the module tests.
    const sweep = tl.v > 0 ? Math.sin(state.clock.elapsedTime * 1.8) * 0.34 : 0
    if (sweepRef.current) sweepRef.current.visible = tl.v > 0.02
    sweepMat.opacity = tl.v * 0.22
    sweepRef.current?.position.set(sweep, 0, 0)
  })

  return (
    <group position={CHAMBER_POS}>
      <mesh ref={frameRef} geometry={new THREE.BoxGeometry(0.85, 0.85, 0.85)} material={frameMat} />
      <mesh ref={wallRef} geometry={new THREE.BoxGeometry(0.82, 0.4, 0.82)} material={wallMat} />
      <mesh ref={sweepRef} rotation={[0, Math.PI / 4, 0]} material={sweepMat}>
        <planeGeometry args={[0.7, 0.7]} />
      </mesh>
    </group>
  )
}

/* ----------------------------------------------------------- Scene */

function Scene({ progress }: { progress: MotionValue<number> }) {
  const { nodes } = useMemo(() => buildLattice(), [])
  const glRef = useThree((s) => s.gl)

  // NaN guard: progress may briefly be NaN before the browser settles.
  useFrame(() => {
    if (Number.isNaN(progress.get())) progress.set(0)
  })
  void glRef

  return (
    <>
      <ambientLight intensity={0.6} />
      <directionalLight position={[4, 6, 5]} intensity={0.4} />
      <Core progress={progress} />
      <ScanRing progress={progress} />
      <ConnectorGroup progress={progress} />
      {nodes.map((def) => (
        <NodeMesh key={def.id} def={def} progress={progress} />
      ))}
      <GapSlotMarker progress={progress} />
      <GapModule progress={progress} />
      <Fragments progress={progress} />
      <Chamber progress={progress} />
    </>
  )
}

/* ----------------------------------------------------------- Export */

export function ComputationalCore({
  progress,
  reduced,
}: {
  progress: MotionValue<number>
  reduced: boolean
}) {
  return (
    <Canvas
      dpr={[1, 1.75]}
      camera={{ position: [0, 0.55, 5.4], fov: 42 }}
      gl={{ antialias: true, alpha: true }}
      style={{ background: 'transparent' }}
      frameloop={reduced ? 'demand' : 'always'}
    >
      <Scene progress={progress} />
    </Canvas>
  )
}