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
  error: string | null
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