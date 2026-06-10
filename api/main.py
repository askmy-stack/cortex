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
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.contradictions import router as contradictions_router
from api.decisions import router as decisions_router
from api.deps import RolesDep, memory, set_memory_service
from api.memory import MemoryService
from api.remember import router as remember_router
from api.schemas import (
    DecisionResult,
    HealthResponse,
    InjectRequest,
    InjectResponse,
    QueryRequest,
    QueryResponse,
)
from api.webhooks import router as webhooks_router

log = structlog.get_logger(__name__)

_start_time = time.time()


# ─────────────────────────────────────────────────────────────────────────────
# Application lifecycle
# ─────────────────────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup and shutdown lifecycle."""
    service = MemoryService()
    set_memory_service(service)
    log.info(
        "cortex.api.starting",
        version=app.version,
        environment=os.environ.get("ENVIRONMENT", "development"),
    )
    yield
    await service.close()
    set_memory_service(None)
    log.info("cortex.api.shutdown")


app = FastAPI(
    title="Cortex API",
    description="Organizational Memory Operating System — Context API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Browsers reject `Access-Control-Allow-Origin: *` together with credentials.
# Only enable credentials when an explicit origin allowlist is configured.
_cors_origins_raw = os.environ.get("CORS_ORIGINS", "").strip()
if _cors_origins_raw:
    _cors_origins = [o.strip() for o in _cors_origins_raw.split(",") if o.strip()]
    _cors_allow_credentials = True
else:
    _cors_origins = ["*"]
    _cors_allow_credentials = False

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_cors_allow_credentials,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(webhooks_router)
app.include_router(contradictions_router)
app.include_router(decisions_router)
app.include_router(remember_router)


# ─────────────────────────────────────────────────────────────────────────────
# Dependency check helpers
# ─────────────────────────────────────────────────────────────────────────────


async def _check_neo4j() -> str:
    """Ping Neo4j via the shared async driver."""
    try:
        return await memory().neo4j_health()
    except HTTPException:
        return "unreachable"
    except Exception:
        return "unreachable"


def _check_redis() -> str:
    """Ping Redis via the shared cached client."""
    try:
        return memory().redis_health()
    except HTTPException:
        return "unreachable"
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
    neo4j_status = await _check_neo4j()
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
    roles: RolesDep,
) -> QueryResponse:
    """Search organizational decisions by natural language query.

    Neo4j full-text search with optional Qdrant semantic merge (see memory.semantic).

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
        records = await memory().query_decisions(
            query=request.query,
            workspace_id=request.workspace_id,
            limit=request.limit,
            min_importance=request.min_importance,
            min_trust=request.min_trust,
            event_types=request.event_types,
            caller_roles=roles,
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
    roles: RolesDep,
) -> InjectResponse:
    """Inject relevant organizational memory into an AI agent's context window.

    Called by the MCP server (mcp/server.ts) on every agent tool invocation.
    Returns the most relevant decisions ranked by importance × trust × recency.

    Ranks injectable decisions by importance × trust (see scoring.trust_scorer).
    """
    t0 = time.time()

    log.info(
        "inject.received",
        agent_id=request.agent_id,
        workspace_id=request.workspace_id,
        context_length=len(request.context),
    )

    try:
        injected = await memory().inject_decisions(
            context=request.context,
            workspace_id=request.workspace_id,
            caller_roles=roles,
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
