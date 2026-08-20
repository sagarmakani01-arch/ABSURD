"""API routes."""

from app.api.routes.agents import router as agents_router
from app.api.routes.events import router as events_router
from app.api.routes.evolution import router as evolution_router
from app.api.routes.health import router as health_router
from app.api.routes.memory import router as memory_router
from app.api.routes.tasks import router as tasks_router
from app.api.routes.tools import router as tools_router
from app.api.routes.evaluation import router as evaluation_router

all_routers = [
    health_router,
    events_router,
    tasks_router,
    tools_router,
    evaluation_router,
    memory_router,
    evolution_router,
    agents_router,
]