import logging

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app.routers import (
    analytics,
    awards,
    categories,
    dynamic_rules,
    escalations,
    logs,
    parse,
    intake,
    pipeline_results,
    policies,
    requests,
    rule_versions,
    rules,
    suppliers,
)

logger = logging.getLogger(__name__)

# Import ORM-managed models so Base.metadata knows about them
import app.models.logs  # noqa: F401
import app.models.evaluations  # noqa: F401
import app.models.pipeline_results  # noqa: F401
import app.models.dynamic_rules  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine, checkfirst=True)
    logger.info("ORM-managed tables verified / created")
    yield


app = FastAPI(
    title="ChainIQ Organisational Layer API",
    description="Backend microservice for ChainIQ procurement data — CRUD and analytics endpoints for 38 normalised MySQL tables.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(categories.router)
app.include_router(suppliers.router)
app.include_router(requests.router)
app.include_router(awards.router)
app.include_router(escalations.router)
app.include_router(policies.router)
app.include_router(rules.router)
app.include_router(rule_versions.router)
app.include_router(analytics.router)
app.include_router(logs.router)
app.include_router(pipeline_results.router)
app.include_router(parse.router)
app.include_router(intake.router)
app.include_router(dynamic_rules.router)


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok"}
