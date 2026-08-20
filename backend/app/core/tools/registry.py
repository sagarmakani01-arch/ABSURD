"""Tool registry service.

Phase 7: full lifecycle — create (DRAFT), structural verification (VERIFIED),
activation (REGISTERED), deprecation. Behavioral verification via the sandbox
attaches in the sandbox phase; until then activation errors on missing
structural requirements and the API says verification is structural-only.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.agent.detector import RegistryTool
from app.core.tools.model import ACTIVATE_REQUIRES, VERIFY_REQUIRES, ToolStatus, VALID_TRANSITIONS
from app.events import EventType, bus
from app.models import ToolRecord


class RegistryError(Exception):
    """Raised on invalid tool submissions or illegal transitions."""

    def __init__(self, message: str, code: str = "registry_error") -> None:
        super().__init__(message)
        self.code = code


class ToolRegistry:
    def create(
        self,
        session: Session,
        name: str,
        description: str,
        source_code: str,
        capabilities: list[str],
        tests: list[str],
        input_schema: dict[str, object],
        output_schema: dict[str, object],
        dependencies: list[str],
    ) -> ToolRecord:
        name = name.strip()
        if not name:
            raise RegistryError("tool name must not be empty", "invalid_name")
        tool = ToolRecord(
            id=uuid4().hex,
            name=name,
            description=description or "",
            version="0.1.0",
            status=ToolStatus.DRAFT.value,
            input_schema=input_schema,
            output_schema=output_schema,
            source_code=source_code,
            dependencies=dependencies,
            capabilities=capabilities,
            tests=tests,
        )
        session.add(tool)
        session.commit()
        session.refresh(tool)
        return tool

    def list(self, session: Session, status: str | None = None) -> list[ToolRecord]:
        stmt = select(ToolRecord).order_by(ToolRecord.created_at)
        if status:
            stmt = stmt.where(ToolRecord.status == status.upper())
        return list(session.scalars(stmt))

    def registered_tools(self, session: Session) -> list[RegistryTool]:
        """Read model backing the capability detector (REGISTERED only)."""
        rows = self.list(session, status=ToolStatus.REGISTERED.value)
        return [
            RegistryTool(
                id=r.id,
                name=r.name,
                capabilities=r.capabilities,
                input_schema={k: str(v) for k, v in (r.input_schema or {}).items()},
                output_schema={k: str(v) for k, v in (r.output_schema or {}).items()},
            )
            for r in rows
        ]

    def get(self, session: Session, tool_id: str) -> ToolRecord | None:
        return session.get(ToolRecord, tool_id)

    def transition(self, session: Session, tool: ToolRecord, target: ToolStatus) -> ToolRecord:
        """Validate and apply a status transition, emitting the matching event."""
        current = ToolStatus(tool.status)
        if target not in VALID_TRANSITIONS[current]:
            raise RegistryError(
                f"illegal transition {current.value} -> {target.value}",
                "illegal_transition",
            )

        if target is ToolStatus.VERIFIED:
            self._require(tool, VERIFY_REQUIRES)
            bus.publish(EventType.TOOL_VERIFIED, {"tool_id": tool.id, "scope": "structural"})
        elif target is ToolStatus.REGISTERED:
            self._require(tool, ACTIVATE_REQUIRES)
            bus.publish(
                EventType.TOOL_REGISTERED,
                {"tool_id": tool.id, "version": tool.version, "capabilities": tool.capabilities},
            )
        elif target is ToolStatus.REJECTED:
            bus.publish(EventType.TOOL_REJECTED, {"tool_id": tool.id})
        elif target is ToolStatus.DEPRECATED:
            bus.publish(EventType.TOOL_DEPRECATED, {"tool_id": tool.id})

        tool.status = target.value
        tool.updated_at = datetime.now(timezone.utc)
        session.add(tool)
        session.commit()
        session.refresh(tool)
        return tool

    def activate(self, session: Session, tool: ToolRecord) -> ToolRecord:
        """VERIFIED -> REGISTERED. Transition validation forbids double activation."""
        return self.transition(session, tool, ToolStatus.REGISTERED)

    @staticmethod
    def _require(tool: ToolRecord, fields: set[str]) -> None:
        missing = [
            field
            for field in sorted(fields)
            if not ToolRegistry._has_content(getattr(tool, field))
        ]
        if missing:
            raise RegistryError(
                f"missing required fields: {', '.join(missing)}",
                "incomplete_tool",
            )

    @staticmethod
    def _has_content(value: object) -> bool:
        if isinstance(value, str):
            return value.strip() != ""
        if isinstance(value, (list, dict)):
            return len(value) > 0
        return bool(value)


tool_registry = ToolRegistry()