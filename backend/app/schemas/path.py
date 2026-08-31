from pydantic import BaseModel, Field


class PathRecommendRequest(BaseModel):
    target_concept_id: str = Field(min_length=1)
    mastered_concepts: list[str] = Field(default_factory=list)


class PathMeta(BaseModel):
    has_cycle: bool = False
    truncated: bool = False
    max_depth: int = 0
    node_count: int = 0
    edge_count: int = 0
    omitted_node_count: int = 0
    omitted_edge_count: int = 0
    skipped_mastered_count: int = 0
    planner_strategy: str = "cached_graph_ancestor_closure"
    dataset_hash: str | None = None


class PathRecommendResponse(BaseModel):
    target_concept_id: str
    path: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    graph_nodes: list[str] = Field(default_factory=list)
    graph_edges: list[tuple[str, str]] = Field(default_factory=list)
    reasoning_steps: list[str] = Field(default_factory=list)
    explanation: str
    has_cycle: bool = False
    truncated: bool = False
    max_depth: int = 0
    meta: PathMeta = Field(default_factory=PathMeta)
    explanation_source: str = "fallback"


class PathExplainRequest(BaseModel):
    target_concept_id: str = Field(min_length=1)
    path: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    has_cycle: bool = False


class PathExplainResponse(BaseModel):
    reasoning_steps: list[str] = Field(default_factory=list)
    explanation: str
    explanation_source: str = "fallback"


class StateUpdateRequest(BaseModel):
    user_id: str | None = None
    learned_concepts: list[str] = Field(default_factory=list)


class StateUpdateResponse(BaseModel):
    message: str
    payload: StateUpdateRequest
