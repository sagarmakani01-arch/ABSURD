"""ABSURD backend.

FastAPI gateway. REST for synchronous operations, WebSocket for the live
event stream. The core intelligence modules (agent, tools, sandbox, memory,
evaluation) are scaffolded and implemented incrementally; nothing here
pretends to be an AI it is not.
"""

from __future__ import annotations

__version__ = "0.1.0"