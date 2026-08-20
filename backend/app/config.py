"""Application configuration.

All values may be overridden via environment variables.
"""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DATABASE_URL = os.getenv("ABSURD_DATABASE_URL", f"sqlite:///{BASE_DIR / 'absurd.db'}")

# CORS origins for the Vite dev server.
CORS_ORIGINS = os.getenv("ABSURD_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")

# API auth token. Empty string disables auth (development only).
API_TOKEN = os.getenv("ABSURD_API_TOKEN", "")

# Optional LLM transport (OpenAI-compatible chat completions). When all three
# are set, tool generation uses the model and revisions become available;
# otherwise ABSURD degrades to the deterministic template strategy.
LLM_BASE_URL = os.getenv("ABSURD_LLM_BASE_URL", "")
LLM_API_TOKEN = os.getenv("ABSURD_LLM_API_TOKEN", "")
LLM_MODEL = os.getenv("ABSURD_LLM_MODEL", "")
LLM_TIMEOUT_SECONDS = float(os.getenv("ABSURD_LLM_TIMEOUT_SECONDS", "60"))