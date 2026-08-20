/** TanStack Query hooks per resource. */

import { useQuery } from '@tanstack/react-query'
import { api } from './client'

export function useHealth(enabled = true) {
  return useQuery({
    queryKey: ['health'],
    queryFn: api.health,
    enabled,
    retry: 2,
    refetchInterval: 15_000,
  })
}

export function useTools(params?: { q?: string; tag?: string }) {
  return useQuery({
    queryKey: ['tools', params],
    queryFn: () => api.tools(params),
    retry: 1,
  })
}

export function useTool(id: string) {
  return useQuery({
    queryKey: ['tools', id],
    queryFn: () => api.tool(id),
    retry: 1,
  })
}

export function useTasks(params?: Record<string, string>) {
  return useQuery({
    queryKey: ['tasks', params],
    queryFn: () => api.tasks(params),
    retry: 1,
    refetchInterval: 5_000,
  })
}

export function useExecutions(taskId?: string) {
  return useQuery({
    queryKey: ['executions', taskId],
    queryFn: () => api.executions(taskId),
    retry: 1,
    refetchInterval: 5_000,
  })
}