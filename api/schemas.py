"""Shared API request/response models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class DecisionResult(BaseModel):
    event_id: str
    event_type: str
    content: str
    made_by: list[str]
    affects: list[str]
    rationale: list[str]
    importance_score: float
    trust_score: float
    extraction_confidence: float
    source: str
    channel: str
    extracted_at: str
    status: str


class QueryRequest(BaseModel):
    query: str = Field(
        description="Natural language question about organizational decisions",
        min_length=3,
        max_length=1000,
        examples=["Why did we choose CockroachDB for payments?"],
    )
    workspace_id: str = Field(
        description="Workspace to search within",
        examples=["acme-corp"],
    )
    limit: int = Field(default=10, ge=1, le=50)
    event_types: list[str] = Field(default_factory=list)
    min_importance: float = Field(default=0.0, ge=0.0, le=1.0)
    min_trust: float = Field(default=0.0, ge=0.0, le=1.0)


class QueryResponse(BaseModel):
    query: str
    workspace_id: str
    results: list[DecisionResult]
    total: int
    latency_ms: float


class InjectRequest(BaseModel):
    context: str = Field(min_length=10, max_length=5000)
    workspace_id: str
    agent_id: str
    max_tokens: int = Field(default=4000, ge=100, le=16000)


class InjectResponse(BaseModel):
    agent_id: str
    workspace_id: str
    injected_decisions: list[DecisionResult]
    context_summary: str
    token_estimate: int
    latency_ms: float


class HealthResponse(BaseModel):
    status: str
    version: str
    uptime_seconds: float
    dependencies: dict[str, str]
