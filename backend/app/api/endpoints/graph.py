from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_graph_repository
from app.core.errors import RepositoryUnavailableError
from app.repositories.graph_repository import GraphRepository
from app.schemas.graph import ConceptCorpusResponse, ConceptDetailResponse, GraphOverviewResponse

router = APIRouter(tags=["graph"])


@router.get("/graph/overview", response_model=GraphOverviewResponse)
def graph_overview(repo: GraphRepository = Depends(get_graph_repository)) -> GraphOverviewResponse:
    try:
        return GraphOverviewResponse(**repo.get_graph_overview())
    except RepositoryUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/concept/{concept_id}", response_model=ConceptDetailResponse)
def concept_detail(concept_id: str, repo: GraphRepository = Depends(get_graph_repository)) -> ConceptDetailResponse:
    try:
        data = repo.get_concept_detail(concept_id=concept_id)
    except RepositoryUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if data is None:
        raise HTTPException(status_code=404, detail=f"Concept not found: {concept_id}")
    return ConceptDetailResponse(**data)


@router.get("/concepts", response_model=ConceptCorpusResponse)
def concept_corpus(
    limit: int = 2000,
    repo: GraphRepository = Depends(get_graph_repository),
) -> ConceptCorpusResponse:
    try:
        items = repo.get_concept_corpus(limit=limit)
    except RepositoryUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return ConceptCorpusResponse(items=items)
