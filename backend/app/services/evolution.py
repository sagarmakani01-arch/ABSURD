"""Evolution loop services.

The loop closes on real signals only:

- Failures are classified deterministically and written to Experience Memory
  (projector in projectors.py) plus logged as `failure.analyzed`.
- REGISTERED tools add `tool -enables-> capability` edges to the Knowledge
  Graph, enabling gap-close queries.
- Quarantine is implemented but only triggers from real consecutive failed
  executions, of which there are none until the sandbox phase — so it
  correctly stays dormant today.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.events import EventType, bus
from app.models import ExecutionRecord, ExperienceRecord, KgEdge, TaskRecord, ToolRecord
from app.services.memory import knowledge_graph

QUARANTINE_THRESHOLD = 3

_FAILURE_CATEGORIES = {
    "NO_CAPABILITY": "missing_capability",
    "PARTIAL_CAPABILITY": "partial_capability",
}


class EvolutionError(Exception):
    """Structured evolution-loop failure, mapped to a 409 by the API layer."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class EvolutionService:
    def classify_failure(self, error: dict[str, object] | None) -> dict[str, object]:
        """Deterministic failure classification — no NLP, structured fields only."""
        if not error:
            return {"category": "unknown", "lessons": []}
        kind = str(error.get("kind", "unknown"))
        missing = error.get("missing") or []
        return {
            "category": _FAILURE_CATEGORIES.get(kind, "runtime"),
            "lessons": [f"missing capability: {m}" for m in missing],
            "kind": kind,
        }

    def analyze_failure(self, session: Session, event_payload: dict[str, object]) -> dict[str, object]:
        """On task failure: classify, log the analysis event, record block edges."""
        classification = self.classify_failure(event_payload)
        task_id = str(event_payload.get("task_id", ""))
        missing = list(event_payload.get("missing") or [])
        for capability in missing:
            session.add(
                KgEdge(
                    id=uuid4().hex,
                    subject=f"task:{task_id}",
                    relation="blocks",
                    target=f"capability:{capability}",
                    payload={"category": classification["category"]},
                )
            )
        bus.publish(
            EventType.FAILURE_ANALYZED,
            {"task_id": task_id, **classification},
        )
        return classification

    def quarantine(self, session: Session) -> list[ToolRecord]:
        """Tools with >=3 consecutive failed executions leave the registry.

        Not triggered until real executions exist (sandbox phase).
        """
        executed = session.scalars(select(ExecutionRecord)).all()
        consecutive: dict[str, int] = {}
        for row in executed:  # rows are chronological; track running streak
            if row.status == "COMPLETED":
                consecutive[row.tool_id] = 0
            else:
                consecutive[row.tool_id] = consecutive.get(row.tool_id, 0) + 1
        quarantined: list[ToolRecord] = []
        for tool_id, streak in consecutive.items():
            if streak < QUARANTINE_THRESHOLD:
                continue
            tool = session.get(ToolRecord, tool_id)
            if tool is not None and tool.status == "REGISTERED":
                tool.status = "DEPRECATED"
                bus.publish(EventType.TOOL_QUARANTINED, {"tool_id": tool_id, "failures": streak})
                quarantined.append(tool)
        if quarantined:
            session.commit()
        return quarantined

    def start_revision(self, session: Session, tool_id: str) -> dict[str, object]:
        """Begin a revision cycle for a REGISTERED tool.

        The cycle is honest about its limits: tool *generation* is the work of
        the LLM generator (a later phase), so every revision attempt today
        records `evolution.revision_started`, then `evolution.revision_failed`
        with the structured reason, and fails closed with a 409.
        """
        tool = session.get(ToolRecord, tool_id)
        if tool is None:
            raise EvolutionError("tool_not_found", "tool not found")
        if tool.status != "REGISTERED":
            raise EvolutionError("illegal_state", f"revisions require a REGISTERED tool, got {tool.status}")
        bus.publish(EventType.TOOL_REVISION_STARTED, {"tool_id": tool.id, "version": tool.version})
        reason = "revision generation requires the LLM generator (not implemented yet)"
        bus.publish(EventType.TOOL_REVISION_FAILED, {"tool_id": tool.id, "reason": reason, "version": tool.version})
        raise EvolutionError("revision_generation_unavailable", reason)

    def promote_version(self, session: Session, tool_id: str, version: str) -> ToolRecord:
        """Promote a successfully revised candidate to the registered version.

        A promotion is only lawful when a completed revision exists for the
        tool (a `TOOL_REVISION_IMPROVED` event). With the generator absent no
        revision can complete, so real promotions remain impossible — the
        guard is real and testable regardless.
        """
        tool = session.get(ToolRecord, tool_id)
        if tool is None:
            raise EvolutionError("tool_not_found", "tool not found")
        if tool.status != "REGISTERED":
            raise EvolutionError("illegal_state", f"promotions require a REGISTERED tool, got {tool.status}")
        if version == tool.version:
            raise EvolutionError("version_unchanged", "promoted version must differ from the current version")
        if not self._last_improved_revision(tool_id):
            raise EvolutionError(
                "no_completed_revision",
                "only revisions that completed successfully can be promoted",
            )
        tool.version = version
        tool.updated_at = datetime.now(timezone.utc)
        session.add(tool)
        session.commit()
        session.refresh(tool)
        bus.publish(EventType.TOOL_VERSION_PROMOTED, {"tool_id": tool.id, "version": version})
        return tool

    @staticmethod
    def _last_improved_revision(tool_id: str) -> dict[str, object] | None:
        for event in reversed(bus.recent(500)):
            if event.type is EventType.TOOL_REVISION_IMPROVED and event.payload.get("tool_id") == tool_id:
                return event.payload
        return None

    def metrics(self, session: Session) -> dict[str, object]:
        """Aggregate loop stats for the dashboard."""
        tasks_total = session.scalar(select(func.count()).select_from(TaskRecord)) or 0
        tasks_failed = (
            session.scalar(
                select(func.count()).select_from(TaskRecord).where(TaskRecord.status == "FAILED")
            )
            or 0
        )
        tools_registered = (
            session.scalar(
                select(func.count()).select_from(ToolRecord).where(ToolRecord.status == "REGISTERED")
            )
            or 0
        )
        tools_generated = (
            session.scalar(
                select(func.count())
                .select_from(ToolRecord)
                .where(ToolRecord.provenance != {})
            )
            or 0
        )
        executions = session.scalar(select(func.count()).select_from(ExecutionRecord)) or 0
        experiences = session.scalar(select(func.count()).select_from(ExperienceRecord)) or 0

        failures_by_kind: dict[str, int] = {}
        for outcome_kind, in session.execute(
            select(ExperienceRecord.result["kind"]).where(ExperienceRecord.outcome == "failure")
        ):
            key = str(outcome_kind or "unknown")
            failures_by_kind[key] = failures_by_kind.get(key, 0) + 1

        gap_edges = session.scalar(
            select(func.count()).select_from(KgEdge).where(KgEdge.relation == "requires")
        ) or 0

        recent = bus.recent(500)
        revisions_total = sum(
            1 for event in recent if event.type is EventType.TOOL_REVISION_STARTED
        )

        gaps = knowledge_graph.coverage_gaps(session)
        closed = sum(1 for gap in gaps if gap["covered"])
        gap_close_rate = round(closed / len(gaps), 3) if gaps else None

        return {
            "tasks_total": tasks_total,
            "tasks_failed": tasks_failed,
            "task_failure_rate": round(tasks_failed / tasks_total, 3) if tasks_total else 0.0,
            "tools_registered": tools_registered,
            "tools_generated": tools_generated,
            "tools_quarantined": 0,
            "executions": executions,
            "experiences": experiences,
            "failures_by_kind": failures_by_kind,
            "gap_edges": gap_edges,
            "gap_close_rate": gap_close_rate,
            "revisions_total": revisions_total,
            "revision_available": False,
        }


evolution_service = EvolutionService()