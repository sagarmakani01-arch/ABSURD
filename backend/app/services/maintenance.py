"""Maintenance sweeps: confidence decay, retention purge, KG pruning.

Runs on gateway startup (lifespan) and is callable on demand; every sweep is
deterministic and safe to re-run. The sweeps implement the convergence and
retention rules from docs/evolution-loop.md §3 and docs/memory-system.md §5.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.services.memory import knowledge_graph, tool_memory


def run_maintenance(session: Session) -> dict[str, int]:
    """Apply all sweeps; returns counts of affected rows."""
    decayed = tool_memory.apply_confidence_decay(session)
    purged = tool_memory.purge_deprecated(session)
    pruned = knowledge_graph.prune(session)
    return {
        "confidence_decayed": len(decayed),
        "tools_purged": purged,
        "kg_edges_pruned": pruned,
    }
