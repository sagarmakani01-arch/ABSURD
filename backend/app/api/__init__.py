"""API routes."""

from app.api.routes.health import router as health_router

all_routers = [health_router]