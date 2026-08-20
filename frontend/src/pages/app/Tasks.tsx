/** /app/tasks — task execution history. */
import { Link } from 'react-router-dom'
import { useExecutions, useTasks } from '../../api/hooks'
import { PageHeader, ModulePending } from '../../app/AppUI'
import { Chip } from '../../components/ui/primitives'

const toneFor = (status: string) =>
  status === 'COMPLETED' ? 'ok' : status === 'FAILED' ? 'err' : status === 'CREATED' || status === 'PLANNING' ? 'signal' : 'neutral'

export function Tasks() {
  const tasks = useTasks()
  const executions = useExecutions()

  return (
    <>
      <PageHeader
        code="03"
        title="TASKS"
        sub="Every task, its lifecycle transitions, and the executions it triggered."
      />
      {tasks.data === undefined ? (
        <ModulePending
          name="TASK HISTORY"
          shipsIn="PHASE 6"
          contract={['id', 'goal', 'status', 'context', 'result', 'error']}
        />
      ) : tasks.data.length === 0 ? (
        <div className="instr-panel" style={{ padding: 26 }}>
          <div className="sys-label" style={{ marginBottom: 8 }}>TASK HISTORY</div>
          <p style={{ color: 'var(--text-low)', margin: 0 }}>No tasks submitted yet.</p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {tasks.data.map((t) => {
            const run = executions.data?.filter((e) => e.task_id === t.id) ?? []
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
                    <Chip label={t.status} tone={toneFor(t.status)} />
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