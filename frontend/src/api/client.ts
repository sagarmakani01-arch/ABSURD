/** Typed REST client for the ABSURD gateway. */

const BASE = '/api/v1'

export class ApiError extends Error {
  status: number
  code: string

  constructor(status: number, code: string, message: string) {
    super(message)
    this.status = status
    this.code = code
  }
}

/** Token is read from localStorage (set by the UI) or baked-in at build time. */
function authHeaders(): Record<string, string> {
  const token =
    typeof localStorage !== 'undefined'
      ? (localStorage.getItem('absurd_api_token') ?? import.meta.env.VITE_API_TOKEN)
      : import.meta.env.VITE_API_TOKEN
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...authHeaders(), ...init?.headers },
  })
  if (res.status === 404) throw new ApiError(404, 'not_found', `${path} not found`)
  if (!res.ok) {
    let body: { detail?: unknown; code?: string } = {}
    try {
      body = await res.json()
    } catch {
      /* non-JSON error body */
    }
    const detail = body.detail
    const message =
      typeof detail === 'string'
        ? detail
        : detail && typeof detail === 'object'
          ? JSON.stringify(detail)
          : res.statusText
    const code =
      typeof detail === 'object' && detail !== null && 'code' in detail
        ? String((detail as { code: unknown }).code)
        : body.code ?? 'error'
    throw new ApiError(res.status, code, message)
  }
  return (await res.json()) as T
}

function json<T>(path: string, body: unknown, method: 'POST' | 'PATCH' | 'DELETE' = 'POST'): Promise<T> {
  return request<T>(path, { method, body: JSON.stringify(body) })
}

export const api = {
  health: () => request<import('../types/api').HealthResponse>('/health'),
  events: () => request<import('../types/api').SimEvent[]>('/events'),

  /* ---------------- tools ---------------- */
  tools: (params?: { q?: string; tag?: string }) => {
    const q = new URLSearchParams(params as Record<string, string>).toString()
    return request<import('../types/api').ToolDTO[]>(`/tools${q ? `?${q}` : ''}`)
  },
  tool: (id: string) => request<import('../types/api').ToolDTO>(`/tools/${id}`),
  createTool: (body: Record<string, unknown>) =>
    json<import('../types/api').ToolDTO>('/tools', body),
  generateTool: (body: {
    name_hint: string
    description?: string
    input_schema?: Record<string, string>
    output_schema?: Record<string, string>
  }) => json<import('../types/api').ToolDTO>('/tools/generate', body),
  toolTransition: (id: string, verb: 'verify' | 'activate' | 'reject' | 'deprecate') =>
    json<import('../types/api').ToolDTO>(`/tools/${id}/${verb}`, {}),
  disableTool: (id: string) => json<import('../types/api').ToolDTO>(`/tools/${id}/disable`, {}),
  enableTool: (id: string) => json<import('../types/api').ToolDTO>(`/tools/${id}/enable`, {}),
  capabilities: () => request<import('../types/api').CapabilityDTO[]>('/capabilities'),

  /* ---------------- agents ---------------- */
  agents: () => request<import('../types/api').AgentDTO[]>('/agents'),
  createAgent: (body: { name: string; planner_strategy?: string; max_retries?: number }) =>
    json<import('../types/api').AgentDTO>('/agents', body),

  /* ---------------- tasks ---------------- */
  tasks: (params?: Record<string, string>) => {
    const q = new URLSearchParams(params ?? {}).toString()
    return request<import('../types/api').TaskDTO[]>(`/tasks${q ? `?${q}` : ''}`)
  },
  task: (id: string) => request<import('../types/api').TaskDTO>(`/tasks/${id}`),
  createTask: (body: { goal: string; context?: Record<string, unknown> }) =>
    json<import('../types/api').TaskDTO>('/tasks', body),
  cancelTask: (id: string) => json<import('../types/api').TaskDTO>(`/tasks/${id}/cancel`, {}),
  executions: (taskId?: string) =>
    request<import('../types/api').ExecutionDTO[]>(`/executions${taskId ? `?task_id=${taskId}` : ''}`),

  /* ---------------- memory ---------------- */
  experiences: (params?: Record<string, string>) => {
    const q = new URLSearchParams(params ?? {}).toString()
    return request<import('../types/api').ExperienceDTO[]>(`/memory/experience${q ? `?${q}` : ''}`)
  },
  graphEdges: (params?: Record<string, string>) => {
    const q = new URLSearchParams(params ?? {}).toString()
    return request<import('../types/api').GraphEdgeDTO[]>(`/memory/graph${q ? `?${q}` : ''}`)
  },
  coverageGaps: () => request<import('../types/api').CoverageGapDTO[]>('/memory/graph/coverage-gaps'),
  toolsUsage: () =>
    request<Record<string, { usage_count: number; success_rate: number }>>('/memory/tools-usage'),

  /* ---------------- evaluation ---------------- */
  runEvaluation: (tool_id: string) =>
    json<import('../types/api').EvalResultDTO>('/evaluations', { tool_id }),

  /* ---------------- evolution ---------------- */
  metrics: () => request<import('../types/api').MetricsDTO>('/evolution/metrics'),
  startRevision: (tool_id: string) => json<unknown>('/evolution/revisions', { tool_id }),
  promote: (tool_id: string, version: string) =>
    json<{ tool_id: string; version: string; status: string }>('/evolution/promotions', { tool_id, version }),
}