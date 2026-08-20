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

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (res.status === 404) throw new ApiError(404, 'not_found', `${path} not found`)
  if (!res.ok) {
    let body: { detail?: string; code?: string } = {}
    try {
      body = await res.json()
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, body.code ?? 'error', body.detail ?? res.statusText)
  }
  return (await res.json()) as T
}

export const api = {
  health: () => request<import('../types/api').HealthResponse>('/health'),
  events: () => request<import('../types/api').SimEvent[]>('/events'),
  tools: (params?: { q?: string; tag?: string }) => {
    const q = new URLSearchParams(params as Record<string, string>).toString()
    return request<import('../types/api').ToolDTO[]>(`/tools${q ? `?${q}` : ''}`)
  },
  tool: (id: string) => request<import('../types/api').ToolDTO>(`/tools/${id}`),
  tasks: (params?: Record<string, string>) => {
    const q = new URLSearchParams(params ?? {}).toString()
    return request<import('../types/api').TaskDTO[]>(`/tasks${q ? `?${q}` : ''}`)
  },
  task: (id: string) => request<import('../types/api').TaskDTO>(`/tasks/${id}`),
  executions: (taskId?: string) =>
    request<import('../types/api').ExecutionDTO[]>(`/executions${taskId ? `?task_id=${taskId}` : ''}`),
}