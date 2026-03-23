from pydantic import BaseModel, Field


class PathRecommendRequest(BaseModel):
    target_concept_id: str = Field(min_length=1)
    mastered_concepts: list[str] = Field(default_factory=list)


class PathRecommendResponse(BaseModel):
    target_concept_id: str
    path: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    reasoning_steps: list[str] = Field(default_factory=list)
    explanation: str
    has_cycle: bool = False
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
