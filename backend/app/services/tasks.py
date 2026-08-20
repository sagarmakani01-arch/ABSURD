"""Task management — persistence and lifecycle entry for tasks."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.agent.engine import agent_engine
from app.events import EventType, bus
from app.models import TaskRecord


class TaskManager:
    def create(self, session: Session, goal: str, context: dict[str, object]) -> TaskRecord:
        task = TaskRecord(id=uuid4().hex, goal=goal, context=context, status="CREATED")
        session.add(task)
        session.commit()
        session.refresh(task)
        bus.publish(EventType.TASK_CREATED, {"task_id": task.id, "goal": goal[:200]})
        return task

    def run(self, session: Session, task: TaskRecord) -> TaskRecord:
        return agent_engine.run(session, task)

    def list(self, session: Session, limit: int, q: str | None = None) -> list[TaskRecord]:
        stmt = select(TaskRecord).order_by(TaskRecord.created_at.desc()).limit(limit)
        if q:
            stmt = stmt.where(or_(TaskRecord.goal.ilike(f"%{q}%"), TaskRecord.id.ilike(f"%{q}%")))
        return list(session.scalars(stmt))

    def get(self, session: Session, task_id: str) -> TaskRecord | None:
        return session.get(TaskRecord, task_id)


task_manager = TaskManager()