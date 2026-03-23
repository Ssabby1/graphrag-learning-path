from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_graph_repository
from app.core.errors import RepositoryUnavailableError
from app.repositories.graph_repository import GraphRepository
from app.schemas.graphrag import GraphRagQueryRequest, GraphRagQueryResponse
from app.services.graphrag_service import query_graphrag

router = APIRouter(tags=["graphrag"])


@router.post("/graphrag/query", response_model=GraphRagQueryResponse)
def graphrag_query(
    payload: GraphRagQueryRequest,
    repo: GraphRepository = Depends(get_graph_repository),
) -> GraphRagQueryResponse:
    try:
        result = query_graphrag(
            question=payload.question,
            target_concept_id=payload.target_concept_id,
            mastered_concepts=payload.mastered_concepts,
            repo=repo,
        )
    except RepositoryUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return GraphRagQueryResponse(**result)
