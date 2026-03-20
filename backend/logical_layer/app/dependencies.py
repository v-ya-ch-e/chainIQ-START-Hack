"""FastAPI dependency injection for shared clients."""

from __future__ import annotations

from fastapi import Request

from app.clients.llm import LLMClient
from app.clients.organisational import OrganisationalClient
from app.pipeline.runner import PipelineRunner


def get_org_client(request: Request) -> OrganisationalClient:
    """Retrieve the shared OrganisationalClient from app state."""
    return request.app.state.org_client


def get_llm_client(request: Request) -> LLMClient | None:
    """Retrieve the shared LLMClient from app state."""
    return getattr(request.app.state, "llm_client", None)


def get_pipeline_runner(request: Request) -> PipelineRunner:
    """Retrieve the shared PipelineRunner from app state."""
    return request.app.state.pipeline_runner
