"""FastAPI application entry point with lifespan management."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.clients.llm import LLMClient
from app.clients.organisational import OrganisationalClient
from app.config import settings
from app.pipeline.runner import PipelineRunner
from app.routers import pipeline, status, steps

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create shared clients at startup, close them at shutdown."""

    logger.info(
        "Starting Logical Layer — Org Layer: %s, Model: %s",
        settings.ORGANISATIONAL_LAYER_URL,
        settings.ANTHROPIC_MODEL,
    )

    # LLM client (optional — pipeline works without it via fallbacks)
    llm_client: LLMClient | None = None
    if settings.ANTHROPIC_API_KEY:
        llm_client = LLMClient(
            api_key=settings.ANTHROPIC_API_KEY,
            model=settings.ANTHROPIC_MODEL,
        )
        logger.info("LLM client configured (model: %s)", settings.ANTHROPIC_MODEL)
    else:
        logger.warning("No ANTHROPIC_API_KEY — LLM calls will use deterministic fallbacks")

    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as http_client:
        org_client = OrganisationalClient(
            client=http_client,
            base_url=settings.ORGANISATIONAL_LAYER_URL,
        )

        app.state.org_client = org_client
        app.state.llm_client = llm_client
        app.state.pipeline_runner = PipelineRunner(org_client, llm_client)

        logger.info("Logical Layer ready")
        yield

    logger.info("Logical Layer shutting down")


app = FastAPI(
    title="ChainIQ Logical Layer",
    description="Procurement decision engine — 9-step pipeline with audit trail",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(pipeline.router)
app.include_router(status.router)
app.include_router(steps.router)


@app.get("/health", tags=["Health"])
async def health_check():
    """Service health check with Org Layer connectivity status."""
    org_status = "unknown"
    try:
        org_client: OrganisationalClient = app.state.org_client
        reachable = await org_client.health_check()
        org_status = "reachable" if reachable else "unreachable"
    except Exception:
        org_status = "unreachable"

    llm_status = "configured" if app.state.llm_client else "not_configured"
    llm_detail = (
        f"Configured for Anthropic model {settings.ANTHROPIC_MODEL}."
        if app.state.llm_client
        else (
            "ANTHROPIC_API_KEY is not set. LLM-assisted steps run in deterministic "
            "fallback mode."
        )
    )

    return {
        "status": "ok",
        "org_layer": org_status,
        "llm": llm_status,
        "llm_detail": llm_detail,
        "version": "2.0.0",
    }
