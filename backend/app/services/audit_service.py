"""Audit service — single writer for :class:`AuditLog` rows.

Every state-transition service writes one or more audit entries alongside
its mutation, so admin dashboards + security review have a reliable record
of what happened and who did it.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog


def _json_safe(value: Any) -> Any:
    """Make a value JSONB-safe: UUIDs → strings, datetimes → isoformat."""

    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_json_safe(v) for v in value]
    try:
        json.dumps(value)
    except TypeError:
        return str(value)
    return value


async def write(
    session: AsyncSession,
    *,
    actor_user_id: uuid.UUID | None,
    action: str,
    target_type: str,
    target_id: uuid.UUID | None,
    diff: dict[str, Any] | None = None,
) -> AuditLog:
    row = AuditLog(
        actor_user_id=actor_user_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        diff=_json_safe(dict(diff or {})),
        occurred_at=datetime.now(UTC),
    )
    session.add(row)
    await session.flush()
    return row
