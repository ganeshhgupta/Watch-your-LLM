import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()  # Load .env before anything else (important for local dev)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import init_db
from routes.stats import router as stats_router
from routes.traces import router as traces_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="LLM Observability API",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — allow dashboard origin(s).  Comma-separated list in env var.
_raw_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173")
allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(traces_router)
app.include_router(stats_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
