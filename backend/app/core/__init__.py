"""Module skeletons.

Each package below is scaffolded to the target architecture from the Phase 6
spec and implemented in later phases. Every scafold class/docstring is
explicit about what is not implemented yet — no fake AI behavior.

- app.agent: planner, reasoner, capability_detector, task_manager (Phase: agent loop)
- app.tools: registry, generator, validator, versioning, composer (Phase: tool registry)
- app.sandbox: manager, executor, policy (Phase: sandbox)
- app.memory: tool_memory, experience_memory, capability_memory (Phase: memory)
- app.evaluation: evaluator, benchmark, test_runner (Phase: evaluation)
- app.services: llm, events bridge (Phase: LLM service)
- app.security: policies (Phase: security)