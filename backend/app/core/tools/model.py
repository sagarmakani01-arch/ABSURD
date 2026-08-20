"""Tool model — canonical statuses and versioning rules.

Status lifecycle (deterministic, enforced by the registry):

    DRAFT ──verify──► VERIFIED ──activate──► REGISTERED ──deprecate──► DEPRECATED
      │                    │
      └──────reject───────► REJECTED ─────────────────────────────────► (dead)

Verification in this phase is structural: schema + capability metadata +
source/tests presence. Behavioral verification (running tests in the sandbox)
attaches in the sandbox phase; until then REGISTERED means "structurally
verified", which is stated explicitly in the API responses.
"""

from __future__ import annotations

from enum import StrEnum


class ToolStatus(StrEnum):
    DRAFT = "DRAFT"
    VERIFIED = "VERIFIED"
    REGISTERED = "REGISTERED"
    REJECTED = "REJECTED"
    DEPRECATED = "DEPRECATED"


# Transitions allowed per state.
VALID_TRANSITIONS: dict[ToolStatus, set[ToolStatus]] = {
    ToolStatus.DRAFT: {ToolStatus.VERIFIED, ToolStatus.REJECTED},
    ToolStatus.VERIFIED: {ToolStatus.REGISTERED, ToolStatus.REJECTED},
    ToolStatus.REGISTERED: {ToolStatus.DEPRECATED},
    ToolStatus.REJECTED: set(),
    ToolStatus.DEPRECATED: set(),
}

# Structural verification: which fields must be non-empty for each gate.
VERIFY_REQUIRES = {"description", "source_code", "tests"}
ACTIVATE_REQUIRES = {"description", "source_code", "tests", "capabilities", "input_schema", "output_schema"}