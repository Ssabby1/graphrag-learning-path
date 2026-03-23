from fastapi import APIRouter

from app.api.endpoints.graphrag import router as graphrag_router
from app.api.endpoints.graph import router as graph_router
from app.api.endpoints.health import router as health_router
from app.api.endpoints.path import router as path_router
from app.api.endpoints.planner import router as planner_router
from app.api.endpoints.state import router as state_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(graph_router)
api_router.include_router(path_router)
api_router.include_router(planner_router)
api_router.include_router(state_router)
api_router.include_router(graphrag_router)
