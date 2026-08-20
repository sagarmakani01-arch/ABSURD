"""Memory system services.

Three stores, one event stream as the system of record (docs/memory-system.md):

- Tool Memory       — state lives on ToolRecord (registry + aggregates).
- Experience Memory — append-only `experiences` table
- Knowledge Graph   — directed `kg_edges` table.

Writes happen through small projector functions attached to the bus in
main.py; request handlers never write memory directly.
"""

from __future__ import annotations

import copy
import re
from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

import app.config as config
from app.models import ExecutionRecord, ExperienceRecord, KgEdge, ToolRecord

# Edge relation vocabulary.
REL_ENABLES = "enables"
REL_COVERS = "covers"
REL_REQUIRES = "requires"
REL_BLOCKS = "blocks"
REL_SATISFIES = "satisfies"
REL_UNFILLABLE = "unfillable"

# Keys whose values never enter Experience Memory (memory-system.md §5).
_PII_KEY_RE = re.compile(r"(password|secret|token|api[_-]?key|authorization|credential)", re.IGNORECASE)


def redact_pii(value: object) -> object:
    """Deep-copy with PII-looking keys masked. Pure, never raises."""

    def _walk(node: object) -> object:
        if isinstance(node, dict):
            return {
                key: "[REDACTED]" if _PII_KEY_RE.search(str(key)) else _walk(child)
                for key, child in node.items()
            }
        if isinstance(node, list):
            return [_walk(item) for item in node]
        return copy.deepcopy(node)

    return _walk(value)


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
            input=redact_pii(input_data),  # type: ignore[arg-type]
            outcome=outcome,
            result=redact_pii(result),  # type: ignore[arg-type]
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

    def record_unfillable(
        self,
        session: Session,
        *,
        capability: str,
        task_id: str,
        rejected_count: int,
    ) -> KgEdge:
        """Persist the unfillable-gap signal as a KG node (convergence rule).

        `capability:<slug> -unfillable-> task:<id>` warns later runs to skip
        generation so the loop stops producing candidates it cannot land.
        """
        return self.add_edge(
            session,
            subject=f"capability:{capability}",
            relation=REL_UNFILLABLE,
            target=f"task:{task_id}",
            payload={"rejected_count": rejected_count},
        )

    def prune(self, session: Session, days: int | None = None) -> int:
        """Delete aged edges whose nodes have no newer edge at all.

        A node that has not been touched within the prune window is pruned
        (memory-system.md §5: nodes with no edge for 90 days are removed).
        """
        days = days if days is not None else config.KG_PRUNE_DAYS
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        candidates = list(session.scalars(select(KgEdge).where(KgEdge.created_at < cutoff)))
        kept_nodes: set[str] = set()
        for edge in session.scalars(
            select(KgEdge).where(KgEdge.created_at >= cutoff)
        ):
            kept_nodes.add(edge.subject)
            kept_nodes.add(edge.target)
        doomed = [
            edge
            for edge in candidates
            if edge.subject not in kept_nodes and edge.target not in kept_nodes
        ]
        if not doomed:
            return 0
        for edge in doomed:
            session.delete(edge)
        session.commit()
        return len(doomed)


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

    def apply_confidence_decay(self, session: Session, days: int | None = None) -> list[ToolRecord]:
        """Halve the confidence of REGISTERED tools unused for a full window.

        Deterministic (memory-system.md / evolution-loop.md §3): a tool whose
        `updated_at` is older than the decay window loses half its confidence
        per elapsed window, so stale capabilities don't outrank fresh ones.
        """
        days = days if days is not None else config.CONFIDENCE_DECAY_DAYS
        now = datetime.now(timezone.utc)
        affected: list[ToolRecord] = []
        for tool in session.scalars(
            select(ToolRecord).where(ToolRecord.status == "REGISTERED")
        ):
            last_used = tool.updated_at
            if last_used.tzinfo is None:  # SQLite drops tzinfo on read
                last_used = last_used.replace(tzinfo=timezone.utc)
            elapsed = now - last_used
            if elapsed < timedelta(days=days):
                continue
            periods = int(elapsed.total_seconds() // (days * 86400))
            tool.confidence = round(tool.confidence * (0.5 ** periods), 3)
            affected.append(tool)
        if affected:
            session.commit()
        return affected

    def purge_deprecated(self, session: Session, days: int | None = None) -> int:
        """Retention: hard-delete DEPRECATED tools older than the window.

        Executions and experiences are append-only by design and stay; the
        tool record itself is removed so a stale registry entry cannot be
        revived (memory-system.md §5, default 180 days).
        """
        days = days if days is not None else config.TOOL_RETENTION_DAYS
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        doomed = list(
            session.scalars(
                select(ToolRecord).where(ToolRecord.status == "DEPRECATED").where(ToolRecord.updated_at < cutoff)
            )
        )
        if not doomed:
            return 0
        for tool in doomed:
            session.delete(tool)
        session.commit()
        return len(doomed)


experience_memory = ExperienceMemory()
knowledge_graph = KnowledgeGraph()
tool_memory = ToolMemory()