from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_graph_repository
from app.core.errors import RepositoryUnavailableError
from app.repositories.graph_repository import GraphRepository
from app.schemas.path import PathExplainRequest, PathExplainResponse, PathRecommendRequest, PathRecommendResponse
from app.services.explanation_service import generate_reasoning_payload
from app.services.path_service import recommend_path

router = APIRouter(tags=["path"])


@router.post("/path/recommend", response_model=PathRecommendResponse)
def path_recommend(
    payload: PathRecommendRequest,
    repo: GraphRepository = Depends(get_graph_repository),
) -> PathRecommendResponse:
    try:
        result = recommend_path(
            target_concept_id=payload.target_concept_id,
            mastered_concepts=payload.mastered_concepts,
            repo=repo,
        )
    except RepositoryUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return PathRecommendResponse(**result)


@router.post("/path/explain", response_model=PathExplainResponse)
def path_explain(payload: PathExplainRequest) -> PathExplainResponse:
    result = generate_reasoning_payload(
        target_concept_id=payload.target_concept_id,
        path=payload.path,
        evidence=payload.evidence,
        has_cycle=payload.has_cycle,
    )
    return PathExplainResponse(**result)
