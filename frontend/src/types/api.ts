/** API DTOs mirroring the backend Pydantic/SQLAlchemy models. */

export interface HealthResponse {
  status: string
  service: string
  version: string
  event_bus: string
}

/** Registry tool record (backend Phase 7). */
export interface ToolDTO {
  id: string
  name: string
  description: string
  version: string
  status: string
  input_schema: Record<string, unknown>
  output_schema: Record<string, unknown>
  source_code: string
  dependencies: string[]
  capabilities: string[]
  tests: string[]
  benchmark_results: Record<string, unknown>
  security_metadata: Record<string, unknown>
  provenance: Record<string, unknown>
  parent_version: string | null
  created_at: string
  updated_at: string
}

/** Persisted task record (backend Phase 6). */
export interface TaskDTO {
  id: string
  goal: string
  status: string
  context: Record<string, unknown>
  result: Record<string, unknown> | null
  error: Record<string, unknown> | null
  created_at: string
  updated_at: string
}

/** Tool execution record (observability contract). */
export interface ExecutionDTO {
  id: string
  task_id: string
  tool_id: string
  tool_version: string
  status: string
  input: Record<string, unknown>
  output: Record<string, unknown> | null
  error: Record<string, unknown> | null
  metrics: Record<string, unknown>
  started_at: string
  finished_at: string | null
}

/** Canonical envelope emitted by the event bus → WS bridge. */
export interface SimEvent {
  type: string
  payload: Record<string, unknown>
  sequence: number
}

/** Append-only Experience Memory record (Phase 9). */
export interface ExperienceDTO {
  id: string
  kind: string
  task_id: string | null
  input: Record<string, unknown>
  outcome: string
  result: Record<string, unknown> | null
  lessons: string[]
  created_at: string
}

/** Knowledge Graph edge (Phase 9). */
export interface GraphEdgeDTO {
  id: string
  subject: string
  relation: string
  target: string
  payload: Record<string, unknown>
  created_at: string
}

/** Uncovered capability requirement per task (Phase 9). */
export interface CoverageGapDTO {
  task_id: string
  capability: string
  covered: boolean
}

/** Evolution loop dashboard metrics (Phase 9/10). */
export interface MetricsDTO {
  tasks_total: number
  tasks_failed: number
  task_failure_rate: number
  tools_registered: number
  tools_generated: number
  tools_quarantined: number
  executions: number
  experiences: number
  failures_by_kind: Record<string, number>
  gap_edges: number
  gap_close_rate: number | null
  revisions_total: number
  revision_available: boolean
}

/** POST /evaluations result: structural gate only (Phase 9). */
export interface EvalResultDTO {
  tool_id: string
  verification_score: number
  checks_passed: number
  checks_total: number
  checks: Array<{ name: string; passed: boolean; detail?: string }>
  behavioral: { available: boolean; reason: string }
}