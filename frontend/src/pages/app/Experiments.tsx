/** /app/experiments — tool-generation experiments. */
import { PageHeader, ModulePending } from '../../app/AppUI'

export function Experiments() {
  return (
    <>
      <PageHeader
        code="04"
        title="EXPERIMENTS"
        sub="Reproducible research experiments: hypothesis, task set, config, results."
      />
      <ModulePending
        name="EXPERIMENT ENGINE"
        shipsIn="PHASE 8 (EVOLUTION)"
        contract={['id', 'hypothesis', 'task_set', 'initial_capabilities', 'configuration', 'metrics', 'results']}
      />
    </>
  )
}