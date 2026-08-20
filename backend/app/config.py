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

# Optional embedding service for the semantic matching tier (Phase 13e).
EMBEDDINGS_BASE_URL = os.getenv("ABSURD_EMBEDDINGS_BASE_URL", "")
EMBEDDINGS_API_TOKEN = os.getenv("ABSURD_EMBEDDINGS_API_TOKEN", "")
EMBEDDINGS_MODEL = os.getenv("ABSURD_EMBEDDINGS_MODEL", "")
EMBEDDINGS_TIMEOUT_SECONDS = float(os.getenv("ABSURD_EMBEDDINGS_TIMEOUT_SECONDS", "30"))
EMBEDDING_THRESHOLD = float(os.getenv("ABSURD_EMBEDDING_THRESHOLD", "0.5"))

# Convergence & maintenance (Phase 14).
UNFILLABLE_GAP_THRESHOLD = int(os.getenv("ABSURD_UNFILLABLE_GAP_THRESHOLD", "2"))
REPLAN_MAX_RETRIES = int(os.getenv("ABSURD_REPLAN_MAX_RETRIES", "2"))
CONFIDENCE_DECAY_DAYS = int(os.getenv("ABSURD_CONFIDENCE_DECAY_DAYS", "30"))
TOOL_RETENTION_DAYS = int(os.getenv("ABSURD_TOOL_RETENTION_DAYS", "180"))
KG_PRUNE_DAYS = int(os.getenv("ABSURD_KG_PRUNE_DAYS", "90"))

# Gateway hardening (Phase 14). Zero disables the limit/cap. Rate limiting
# is opt-in: it protects a deployed gateway, not a local dev loop.
RATE_LIMIT_PER_MINUTE = int(os.getenv("ABSURD_RATE_LIMIT_PER_MINUTE", "0"))
MAX_REQUEST_BYTES = int(os.getenv("ABSURD_MAX_REQUEST_BYTES", "262144"))