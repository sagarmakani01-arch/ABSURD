"""Memory system services.

Three stores, one event stream as the system of record (docs/memory-system.md):

- Tool Memory       — state lives on ToolRecord (registry + aggregates).
- Experience Memory — append-only `experiences` table
- Knowledge Graph   — directed `kg_edges` table.

Writes happen through small projector functions attached to the bus in
main.py; request handlers never write memory directly.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import ExecutionRecord, ExperienceRecord, KgEdge, ToolRecord

# Edge relation vocabulary.
REL_ENABLES = "enables"
REL_COVERS = "covers"
REL_REQUIRES = "requires"
REL_BLOCKS = "blocks"
REL_SATISFIES = "satisfies"


class ExperienceMemory:
    def add(
        self,
        session: Session,
        *,
        kind: str,
        outcome: str,
        input_data: dict[str, object],
        task_id: str | None = None,
        result: dict[str, object] | None = None,
        lessons: list[str] | None = None,
    ) -> ExperienceRecord:
        record = ExperienceRecord(
            id=uuid4().hex,
            kind=kind,
            task_id=task_id,
            input=input_data,
            outcome=outcome,
            result=result,
            lessons=lessons or [],
        )
        session.add(record)
        session.commit()
        session.refresh(record)
        return record

    def query(
        self,
        session: Session,
        *,
        kind: str | None = None,
        outcome: str | None = None,
        task_id: str | None = None,
        limit: int = 100,
    ) -> list[ExperienceRecord]:
        stmt = select(ExperienceRecord).order_by(ExperienceRecord.created_at.desc()).limit(limit)
        if kind:
            stmt = stmt.where(ExperienceRecord.kind == kind)
        if outcome:
            stmt = stmt.where(ExperienceRecord.outcome == outcome)
        if task_id:
            stmt = stmt.where(ExperienceRecord.task_id == task_id)
        return list(session.scalars(stmt))


class KnowledgeGraph:
    def add_edge(
        self,
        session: Session,
        *,
        subject: str,
        relation: str,
        target: str,
        payload: dict[str, object] | None = None,
    ) -> KgEdge:
        edge = KgEdge(id=uuid4().hex, subject=subject, relation=relation, target=target, payload=payload or {})
        session.add(edge)
        session.commit()
        session.refresh(edge)
        return edge

    def query(
        self,
        session: Session,
        *,
        relation: str | None = None,
        subject: str | None = None,
        target: str | None = None,
        limit: int = 200,
    ) -> list[KgEdge]:
        stmt = select(KgEdge).order_by(KgEdge.created_at.desc()).limit(limit)
        if relation:
            stmt = stmt.where(KgEdge.relation == relation)
        if subject:
            stmt = stmt.where(KgEdge.subject == subject)
        if target:
            stmt = stmt.where(KgEdge.target == target)
        return list(session.scalars(stmt))

    def coverage_gaps(self, session: Session) -> list[dict[str, object]]:
        """Goals that require a capability but have no covering registered tool.

        Assumes edges `task:<id> -requires-> capability:<slug>`. A registered
        tool with a matching capability closes the gap.
        """
        available = {
            capability
            for tool in session.scalars(select(ToolRecord).where(ToolRecord.status == "REGISTERED"))
            for capability in (tool.capabilities or [])
        }
        required_edges = self.query(session, relation=REL_REQUIRES)
        return [
            {
                "task_id": edge.subject.removeprefix("task:"),
                "capability": edge.target.removeprefix("capability:"),
                "covered": edge.target.split(":", 1)[1] in available,
            }
            for edge in required_edges
            if edge.target.startswith("capability:")
        ]


class ToolMemory:
    """Aggregates over ToolRecord + ExecutionRecord (computed, read-only)."""

    def usage(self, session: Session) -> dict[str, dict[str, object]]:
        """Per-tool usage count and success rate from execution history."""
        rows = session.scalars(select(ExecutionRecord)).all()
        counts: defaultdict[str, list[bool]] = defaultdict(list)
        for row in rows:
            counts[row.tool_id].append(row.status == "COMPLETED")
        return {
            tool_id: {"usage_count": len(oks), "success_rate": round(sum(oks) / len(oks), 3)}
            for tool_id, oks in counts.items()
        }

    def stale(self, session: Session, days: int = 30) -> list[ToolRecord]:
        """Tools whose confidence decays: no REGISTERED match for a while."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        return list(
            session.scalars(
                select(ToolRecord).where(ToolRecord.status == "REGISTERED").where(ToolRecord.updated_at < cutoff)
            )
        )


experience_memory = ExperienceMemory()
knowledge_graph = KnowledgeGraph()
tool_memory = ToolMemory()