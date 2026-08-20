"""API routes."""

from app.api.routes.events import router as events_router
from app.api.routes.health import router as health_router
from app.api.routes.tasks import router as tasks_router
from app.api.routes.tools import router as tools_router

all_routers = [health_router, events_router, tasks_router, tools_router]