from typing import Literal

from pydantic import BaseModel, Field


class PlannerInterpretRequest(BaseModel):
    question: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)
    response_language: Literal["auto", "zh", "en"] = "auto"


class TargetCandidate(BaseModel):
    concept_id: str
    score: float
    rank: int
    source: str
    vector_score: float | None = None


class PlannerInterpretResponse(BaseModel):
    target_concept_id: str | None = None
    mastered_concepts: list[str] = Field(default_factory=list)
    matched_concepts: list[str] = Field(default_factory=list)
    summary: str = ""
    interpretation_source: str = "fallback"
    candidates: list[TargetCandidate] = Field(default_factory=list)
    resolution_source: str = "fallback"
    query_language: str = "zh"
    rejected: bool = False
    rejection_reason: str | None = None
    resolver_meta: dict = Field(default_factory=dict)
