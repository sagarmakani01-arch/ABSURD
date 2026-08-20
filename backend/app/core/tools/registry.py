"""Tool registry read model (v0).

Phase 7 completes the registry (registration, versioning, verification).
Phase 6 only needs a faithful read: list tools whose status is REGISTERED,
which is empty today — so the detector honestly reports every step as a gap.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.agent.detector import RegistryTool
from app.models import ToolRecord


class ToolRegistry:
    def list_all(self, session: Session) -> list[RegistryTool]:
        rows = session.scalars(
            select(ToolRecord).where(ToolRecord.status == "REGISTERED").order_by(ToolRecord.created_at)
        ).all()
        return [RegistryTool(id=r.id, name=r.name, capabilities=r.capabilities) for r in rows]


tool_registry = ToolRegistry()