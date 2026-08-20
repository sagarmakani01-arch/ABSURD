/** TanStack Query hooks per resource. */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
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

export function useExperiences(params?: Record<string, string>) {
  return useQuery({
    queryKey: ['experiences', params],
    queryFn: () => api.experiences(params),
    retry: 1,
    refetchInterval: 5_000,
  })
}

export function useGraphEdges(params?: Record<string, string>) {
  return useQuery({
    queryKey: ['graph-edges', params],
    queryFn: () => api.graphEdges(params),
    retry: 1,
    refetchInterval: 5_000,
  })
}

export function useCoverageGaps() {
  return useQuery({
    queryKey: ['coverage-gaps'],
    queryFn: api.coverageGaps,
    retry: 1,
    refetchInterval: 5_000,
  })
}

export function useToolsUsage() {
  return useQuery({
    queryKey: ['tools-usage'],
    queryFn: api.toolsUsage,
    retry: 1,
  })
}

export function useMetrics() {
  return useQuery({
    queryKey: ['metrics'],
    queryFn: api.metrics,
    retry: 1,
    refetchInterval: 5_000,
  })
}

/* ---------------- mutations ---------------- */

export function useCreateTask() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (body: { goal: string; context?: Record<string, unknown> }) => api.createTask(body),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ['tasks'] })
      client.invalidateQueries({ queryKey: ['metrics'] })
    },
  })
}

export function useCreateTool() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => api.createTool(body),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ['tools'] })
    },
  })
}

export function useToolTransition() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ id, verb }: { id: string; verb: 'verify' | 'activate' | 'reject' | 'deprecate' }) =>
      api.toolTransition(id, verb),
    onSuccess: (tool) => {
      client.invalidateQueries({ queryKey: ['tools'] })
      client.invalidateQueries({ queryKey: ['tools', tool.id] })
      client.invalidateQueries({ queryKey: ['graph-edges'] })
      client.invalidateQueries({ queryKey: ['metrics'] })
    },
  })
}

export function useRunEvaluation() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (tool_id: string) => api.runEvaluation(tool_id),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ['experiences'] })
    },
  })
}

export function useStartRevision() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (tool_id: string) => api.startRevision(tool_id),
    onSettled: () => {
      client.invalidateQueries({ queryKey: ['metrics'] })
    },
  })
}

export function usePromote() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ id, version }: { id: string; version: string }) => api.promote(id, version),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ['tools'] })
      client.invalidateQueries({ queryKey: ['metrics'] })
    },
  })
}