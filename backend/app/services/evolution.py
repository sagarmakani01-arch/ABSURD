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

from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.events import EventType, bus
from app.models import ExecutionRecord, ExperienceRecord, KgEdge, TaskRecord, ToolRecord

QUARANTINE_THRESHOLD = 3

_FAILURE_CATEGORIES = {
    "NO_CAPABILITY": "missing_capability",
    "PARTIAL_CAPABILITY": "partial_capability",
}


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
            "gap_close_rate": None,
        }


evolution_service = EvolutionService()