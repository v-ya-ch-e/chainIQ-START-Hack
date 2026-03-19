from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.clients.organisational import org_client
from app.routers import processing


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await org_client.close()


app = FastAPI(
    title="ChainIQ Logical Layer API",
    description=(
        "Procurement decision engine that receives purchase requests from n8n, "
        "fetches data from the Organisational Layer, applies business logic, "
        "and returns structured, auditable sourcing recommendations."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(processing.router)


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok"}
