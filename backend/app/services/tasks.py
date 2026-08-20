"""Task management — persistence and lifecycle entry for tasks."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.agent.engine import agent_engine
from app.events import EventType, bus
from app.models import TaskRecord


class TaskManager:
    def create(
        self,
        session: Session,
        goal: str,
        context: dict[str, object],
        agent_id: str | None = None,
    ) -> TaskRecord:
        task = TaskRecord(
            id=uuid4().hex,
            goal=goal,
            context=context,
            status="CREATED",
            agent_id=agent_id,
        )
        session.add(task)
        session.commit()
        session.refresh(task)
        bus.publish(EventType.TASK_CREATED, {"task_id": task.id, "goal": goal[:200]})
        return task

    def run(self, session: Session, task: TaskRecord) -> TaskRecord:
        return agent_engine.run(session, task)

    def cancel(self, session: Session, task_id: str) -> TaskRecord | None:
        """Request cancellation for a task that has not finished.

        The engine honours the flag between steps; a task already in a
        terminal state cannot be cancelled.
        """
        task = session.get(TaskRecord, task_id)
        if task is None:
            return None
        if task.status in {"COMPLETED", "FAILED", "CANCELLED"}:
            return task
        task.status = "CANCELLED"
        task.updated_at = datetime.now(timezone.utc)
        session.add(task)
        session.commit()
        session.refresh(task)
        bus.publish(EventType.TASK_CANCELLED, {"task_id": task.id, "status": task.status})
        return task

    def list(self, session: Session, limit: int, q: str | None = None) -> list[TaskRecord]:
        stmt = select(TaskRecord).order_by(TaskRecord.created_at.desc()).limit(limit)
        if q:
            stmt = stmt.where(or_(TaskRecord.goal.ilike(f"%{q}%"), TaskRecord.id.ilike(f"%{q}%")))
        return list(session.scalars(stmt))

    def get(self, session: Session, task_id: str) -> TaskRecord | None:
        return session.get(TaskRecord, task_id)


task_manager = TaskManager()