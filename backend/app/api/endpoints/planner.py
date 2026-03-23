from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_graph_repository
from app.core.errors import RepositoryUnavailableError
from app.repositories.graph_repository import GraphRepository
from app.schemas.planner import PlannerInterpretRequest, PlannerInterpretResponse
from app.services.planner_service import interpret_learning_request

router = APIRouter(tags=["planner"])


@router.post("/planner/interpret", response_model=PlannerInterpretResponse)
def planner_interpret(
    payload: PlannerInterpretRequest,
    repo: GraphRepository = Depends(get_graph_repository),
) -> PlannerInterpretResponse:
    try:
        result = interpret_learning_request(payload.question, repo)
    except RepositoryUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return PlannerInterpretResponse(**result)
