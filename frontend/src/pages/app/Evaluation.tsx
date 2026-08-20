/** /app/evaluation — benchmarks and evaluations. */
import { PageHeader, ModulePending } from '../../app/AppUI'

export function Evaluation() {
  return (
    <>
      <PageHeader
        code="06"
        title="EVALUATION"
        sub="Verification pipelines, benchmark scores, reliability measurements."
      />
      <ModulePending
        name="VERIFICATION PIPELINE"
        shipsIn="PHASE 8 (EVALUATION)"
        contract={['tool_id', 'tests', 'benchmarks', 'verification_score', 'metrics']}
      />
    </>
  )
}