from pydantic import BaseModel, Field


class GraphRagQueryRequest(BaseModel):
    question: str = Field(min_length=1)
    target_concept_id: str = Field(min_length=1)
    mastered_concepts: list[str] = Field(default_factory=list)


class GraphRagCitation(BaseModel):
    concept_id: str
    kind: str = "concept"
    score: float | None = None
    source: str | None = None


class GraphRagMeta(BaseModel):
    has_cycle: bool = False
    source: str = "path_service"
    model: str = "fallback"
    retrieval_strategy: str = "graph_only"
    vector_backend: str = "none"
    fusion: str = "none"
    reranker: str = "none"


class GraphRagQueryResponse(BaseModel):
    answer: str
    path: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    citations: list[GraphRagCitation] = Field(default_factory=list)
    meta: GraphRagMeta
