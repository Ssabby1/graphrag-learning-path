from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.evidence import EvidencePack
from app.schemas.status import PathStatus


class GraphRagQueryRequest(BaseModel):
    question: str = Field(min_length=1)
    target_concept_id: str = Field(min_length=1)
    mastered_concepts: list[str] = Field(default_factory=list)
    response_language: Literal["auto", "zh", "en"] = "auto"


class GraphRagCitation(BaseModel):
    evidence_id: str
    concept_id: str | None = None
    kind: str = "relationship"
    score: float | None = None
    source: str | None = None


class GraphRagMeta(BaseModel):
    has_cycle: bool = False
    truncated: bool = False
    max_depth: int = 0
    planner_strategy: str = "cached_graph_ancestor_closure"
    dataset_hash: str | None = None
    source: str = "path_service"
    model: str = "fallback"
    retrieval_strategy: str = "graph_only"
    vector_backend: str = "none"
    embedding_model: str = "none"
    embedding_degraded: bool = False
    embedding_degradation_reason: str | None = None
    embedding_cache_status: str = "not_used"
    fusion: str = "none"
    reranker: str = "none"
    reranker_degraded: bool = False
    reranker_degradation_reason: str | None = None
    evidence_retrieval_strategy: str = "graph_scoped_vector"
    evidence_count: int = 0
    answer_evidence_count: int = 0
    path_edge_count: int = 0
    path_edge_evidence_count: int = 0
    missing_path_evidence_count: int = 0
    path_edge_evidence_coverage: float = 1.0
    citation_integrity: float = 1.0
    invalid_evidence_id_count: int = 0
    answer_source: str = "fallback"
    answer_language: str = "zh"
    generation_model: str = "deterministic-evidence-fallback-v1"
    generation_latency_ms: float = 0.0
    structured_output_success: bool = False
    llm_structured_output_success: bool = False
    response_schema_valid: bool = True
    fallback_reason: str | None = None
    discarded_invalid_citation_count: int = 0
    citation_completeness: float = 1.0
    answer_evidence_citation_coverage: float = 1.0


class GraphRagQueryResponse(BaseModel):
    status: PathStatus = "ok"
    answer: str
    cited_evidence_ids: list[str] = Field(default_factory=list)
    answer_source: str = "fallback"
    answer_language: str = "zh"
    path: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    full_evidence_pack: EvidencePack
    selected_answer_evidence: EvidencePack
    citations: list[GraphRagCitation] = Field(default_factory=list)
    meta: GraphRagMeta
