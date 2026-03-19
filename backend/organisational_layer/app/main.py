from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import (
    analytics,
    awards,
    categories,
    escalations,
    logs,
    parse,
    intake,
    policies,
    requests,
    rule_versions,
    rules,
    suppliers,
)

app = FastAPI(
    title="ChainIQ Organisational Layer API",
    description="Backend microservice for ChainIQ procurement data — CRUD and analytics endpoints for 22 normalised MySQL tables.",
    version="1.0.0",
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
app.include_router(parse.router)
app.include_router(intake.router)


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok"}
