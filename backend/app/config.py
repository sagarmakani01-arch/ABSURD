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