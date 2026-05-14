"""Cortex FastAPI application — Context API (Layer 5).

Architecture: Layer 5 — Context API.
Decision: D-001 — REST API is read-only interface to graph (writes go via Kafka).

Endpoints:
  GET  /health          — liveness + dependency check
  POST /query           — cortex.query() — semantic search over graph + vector store
  POST /inject          — active context injection for MCP server

All write paths (connector webhooks) are in connectors/*/producer.py, not here.
"""

from __future__ import annotations

import os
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Header, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from api.contradictions import router as contradictions_router
from api.memory import MemoryService
from api.webhooks import router as webhooks_router

log = structlog.get_logger(__name__)

_start_time = time.time()
_memory_service: MemoryService | None = None


# ─────────────────────────────────────────────────────────────────────────────
# Application lifecycle
# ─────────────────────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup and shutdown lifecycle."""
    global _memory_service
    _memory_service = MemoryService()
    log.info(
        "cortex.api.starting",
        version=app.version,
        environment=os.environ.get("ENVIRONMENT", "development"),
    )
    yield
    if _memory_service is not None:
        await _memory_service.close()
    log.info("cortex.api.shutdown")


app = FastAPI(
    title="Cortex API",
    description="Organizational Memory Operating System — Context API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(webhooks_router)
app.include_router(contradictions_router)


def _memory() -> MemoryService:
    if _memory_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Memory service is not initialized",
        )
    return _memory_service


def _caller_roles(x_cortex_roles: str | None) -> list[str]:
    if not x_cortex_roles:
        return ["authenticated"]
    return [role.strip() for role in x_cortex_roles.split(",") if role.strip()]


# ─────────────────────────────────────────────────────────────────────────────
# Request / response schemas
# ─────────────────────────────────────────────────────────────────────────────


class HealthResponse(BaseModel):
    status: str
    version: str
    uptime_seconds: float
    dependencies: dict[str, str]


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
    limit: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of results to return",
    )
    event_types: list[str] = Field(
        default_factory=list,
        description="Filter by event types: decision, exception, rationale, update, escalation",
    )
    min_importance: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Minimum importance score filter",
    )
    min_trust: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Minimum trust score filter",
    )


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


class QueryResponse(BaseModel):
    query: str
    workspace_id: str
    results: list[DecisionResult]
    total: int
    latency_ms: float


class InjectRequest(BaseModel):
    context: str = Field(
        description="Current task context — what the AI agent is working on",
        min_length=10,
        max_length=5000,
    )
    workspace_id: str
    agent_id: str = Field(description="Requesting agent identifier (DID or service name)")
    max_tokens: int = Field(
        default=4000,
        ge=100,
        le=16000,
        description="Maximum tokens for injected context",
    )


class InjectResponse(BaseModel):
    agent_id: str
    workspace_id: str
    injected_decisions: list[DecisionResult]
    context_summary: str
    token_estimate: int
    latency_ms: float


# ─────────────────────────────────────────────────────────────────────────────
# Dependency check helpers
# ─────────────────────────────────────────────────────────────────────────────


def _check_neo4j() -> str:
    """Ping Neo4j and return 'ok' or 'unreachable'."""
    try:
        from neo4j import GraphDatabase
        uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
        user = os.environ.get("NEO4J_USER", "neo4j")
        password = os.environ.get("NEO4J_PASSWORD", "cortex_local")
        driver = GraphDatabase.driver(uri, auth=(user, password))
        driver.verify_connectivity()
        driver.close()
        return "ok"
    except Exception:
        return "unreachable"


def _check_redis() -> str:
    """Ping Redis and return 'ok' or 'unreachable'."""
    try:
        import redis
        r = redis.Redis(
            host=os.environ.get("REDIS_HOST", "localhost"),
            port=int(os.environ.get("REDIS_PORT", "6379")),
            password=os.environ.get("REDIS_PASSWORD"),
            socket_connect_timeout=1,
        )
        r.ping()
        return "ok"
    except Exception:
        return "unreachable"


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────


@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Liveness and dependency health check",
    tags=["ops"],
)
async def health() -> HealthResponse:
    """Returns API status and dependency connectivity.

    Always returns HTTP 200 — callers should inspect `dependencies` field.
    Used by Docker healthcheck and Kubernetes liveness probes.
    """
    neo4j_status = _check_neo4j()
    redis_status = _check_redis()

    log.info(
        "health.check",
        neo4j=neo4j_status,
        redis=redis_status,
    )

    return HealthResponse(
        status="ok",
        version=app.version,
        uptime_seconds=round(time.time() - _start_time, 2),
        dependencies={
            "neo4j": neo4j_status,
            "redis": redis_status,
        },
    )


@app.post(
    "/query",
    response_model=QueryResponse,
    summary="Query organizational memory",
    tags=["memory"],
)
async def query(
    request: QueryRequest,
    x_cortex_roles: str | None = Header(default=None, alias="X-Cortex-Roles"),
) -> QueryResponse:
    """Search organizational decisions by natural language query.

    Phase 3 implementation: full semantic search via Qdrant + Neo4j graph traversal.
    Current implementation (Phase 2): Neo4j keyword/text search stub.

    Decision: D-004 — Active context injection, not passive retrieval.
    RBAC: workspace_id scoped — cross-workspace results never returned.
    """
    t0 = time.time()

    log.info(
        "query.received",
        query=request.query[:100],
        workspace_id=request.workspace_id,
        limit=request.limit,
    )

    try:
        records = await _memory().query_decisions(
            query=request.query,
            workspace_id=request.workspace_id,
            limit=request.limit,
            min_importance=request.min_importance,
            min_trust=request.min_trust,
            event_types=request.event_types,
            caller_roles=_caller_roles(x_cortex_roles),
        )
        results = [DecisionResult(**record) for record in records]
    except Exception as exc:
        log.error("query.failed", error=str(exc), query=request.query[:100])
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Graph query failed — Neo4j may be unavailable",
        ) from exc

    latency_ms = round((time.time() - t0) * 1000, 2)
    log.info(
        "query.complete",
        result_count=len(results),
        latency_ms=latency_ms,
        workspace_id=request.workspace_id,
    )

    return QueryResponse(
        query=request.query,
        workspace_id=request.workspace_id,
        results=results,
        total=len(results),
        latency_ms=latency_ms,
    )


@app.post(
    "/inject",
    response_model=InjectResponse,
    summary="Active context injection for AI agents",
    tags=["memory"],
)
async def inject(
    request: InjectRequest,
    x_cortex_roles: str | None = Header(default=None, alias="X-Cortex-Roles"),
) -> InjectResponse:
    """Inject relevant organizational memory into an AI agent's context window.

    Called by the MCP server (mcp/server.ts) on every agent tool invocation.
    Returns the most relevant decisions ranked by importance × trust × recency.

    Phase 3: full implementation with Qdrant semantic search.
    Current (Phase 2): stub returning empty context.
    """
    t0 = time.time()

    log.info(
        "inject.received",
        agent_id=request.agent_id,
        workspace_id=request.workspace_id,
        context_length=len(request.context),
    )

    try:
        injected = await _memory().inject_decisions(
            context=request.context,
            workspace_id=request.workspace_id,
            caller_roles=_caller_roles(x_cortex_roles),
            limit=min(request.max_tokens // 400, 10),
        )
    except Exception as exc:
        log.error("inject.failed", error=str(exc), agent_id=request.agent_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Context injection failed",
        ) from exc

    latency_ms = round((time.time() - t0) * 1000, 2)
    decisions = [DecisionResult(**record) for record in injected]
    summary = "\n".join(
        f"- {item.content}" for item in decisions[:5]
    ) or "No injectable organizational memory matched this context."
    token_estimate = sum(len(item.content.split()) for item in decisions) * 4 // 3

    return InjectResponse(
        agent_id=request.agent_id,
        workspace_id=request.workspace_id,
        injected_decisions=decisions,
        context_summary=summary,
        token_estimate=token_estimate,
        latency_ms=latency_ms,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Exception handlers
# ─────────────────────────────────────────────────────────────────────────────


@app.exception_handler(Exception)
async def unhandled_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    log.error(
        "api.unhandled_exception",
        method=request.method,
        path=request.url.path,
        error=str(exc),
        error_type=type(exc).__name__,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )
