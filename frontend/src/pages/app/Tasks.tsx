/** /app/tasks — task execution history + submission. */
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useCancelTask, useCreateTask, useExecutions, useTasks } from '../../api/hooks'
import { PageHeader } from '../../app/AppUI'
import { Button, Chip } from '../../components/ui/primitives'

const toneFor = (status: string) =>
  status === 'COMPLETED' ? 'ok' : status === 'FAILED' ? 'err' : status === 'CANCELLED' ? 'warn' : status === 'CREATED' || status === 'ANALYZED' ? 'signal' : 'neutral'

const TERMINAL = new Set(['COMPLETED', 'FAILED', 'CANCELLED'])

export function Tasks() {
  const tasks = useTasks()
  const executions = useExecutions()
  const createTask = useCreateTask()
  const cancelTask = useCancelTask()
  const [goal, setGoal] = useState('')

  const errorKind = (t: { error: Record<string, unknown> | null }) =>
    t.error && typeof t.error.kind === 'string' ? t.error.kind : null

  return (
    <>
      <PageHeader
        code="03"
        title="TASKS"
        sub="Every task, its lifecycle transitions, and the executions it triggered."
      />

      <form
        className="instr-panel"
        style={{ padding: 20, marginBottom: 22 }}
        onSubmit={(e) => {
          e.preventDefault()
          if (!goal.trim()) return
          createTask.mutate({ goal: goal.trim() })
          setGoal('')
        }}
      >
        <div className="sys-label" style={{ marginBottom: 10 }}>SUBMIT TASK</div>
        <div style={{ display: 'flex', gap: 10 }}>
          <input
            value={goal}
            onChange={(e) => setGoal(e.target.value)}
            placeholder="goal, e.g. fetch weather data"
            style={{
              flex: 1,
              background: 'var(--bg-2)',
              border: '1px solid var(--line-1)',
              color: 'var(--text-hi)',
              fontFamily: 'var(--font-mono)',
              fontSize: 'var(--fs-12)',
              padding: '0 14px',
              height: 36,
              borderRadius: 'var(--radius-1)',
              outline: 'none',
            }}
          />
          <Button type="submit" disabled={!goal.trim() || createTask.isPending}>RUN</Button>
        </div>
        {createTask.isError && createTask.error instanceof Error && (
          <pre style={{ color: 'var(--err)', fontSize: 'var(--fs-11)', margin: '10px 0 0' }}>
            {createTask.error.message}
          </pre>
        )}
      </form>

      {tasks.data === undefined ? (
        <div className="instr-panel" style={{ padding: 26 }}>
          <div className="sys-label" style={{ marginBottom: 8 }}>TASK HISTORY</div>
          <p style={{ color: 'var(--text-low)', margin: 0, fontFamily: 'var(--font-mono)', fontSize: 'var(--fs-11)' }}>
            LOADING…
          </p>
        </div>
      ) : tasks.data.length === 0 ? (
        <div className="instr-panel" style={{ padding: 26 }}>
          <div className="sys-label" style={{ marginBottom: 8 }}>TASK HISTORY</div>
          <p style={{ color: 'var(--text-low)', margin: 0 }}>No tasks submitted yet.</p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {tasks.data.map((t) => {
            const run = executions.data?.filter((e) => e.task_id === t.id) ?? []
            const kind = errorKind(t)
            return (
              <Link
                key={t.id}
                to={`/app/tasks/${t.id}`}
                style={{ textDecoration: 'none' }}
              >
                <div className="instr-panel" style={{ padding: '16px 20px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--fs-12)', letterSpacing: '0.06em', color: 'var(--text-hi)' }}>
                      {t.goal.slice(0, 90)}
                    </span>
                    <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                      {kind && <Chip label={kind} tone="warn" />}
                      <Chip label={t.status} tone={toneFor(t.status)} />
                      {!TERMINAL.has(t.status) && (
                        <button
                          type="button"
                          disabled={cancelTask.isPending}
                          onClick={(e) => {
                            e.preventDefault()
                            e.stopPropagation()
                            cancelTask.mutate(t.id)
                          }}
                          style={{
                            background: 'transparent',
                            border: '1px solid var(--line-1)',
                            color: 'var(--warn)',
                            borderRadius: 'var(--radius-1)',
                            fontFamily: 'var(--font-mono)',
                            fontSize: 'var(--fs-10)',
                            padding: '3px 8px',
                            cursor: 'pointer',
                          }}
                        >
                          CANCEL
                        </button>
                      )}
                    </div>
                  </div>
                  <div className="sys-label" style={{ marginTop: 10 }}>
                    {t.id} · {run.length} EXECUTIONS · {t.created_at}
                  </div>
                </div>
              </Link>
            )
          })}
        </div>
      )}
    </>
  )
}