"""FastAPI application entry point for the CvSU-Imus Pseudo Student Portal & AI Enrollment Scheduler."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import APP_DIR, SECRET_KEY
from app.routers import adviser, auth, evaluation, portal_pages, scheduler_api
from app.services.snapshot_loader import init_db


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Initialize SQLite schema and seed BSCS curriculum/offerings/demo personas on startup."""
    init_db()
    yield


app = FastAPI(
    title="CvSU-Imus Student Portal & AI-Driven Enrollment Scheduler (BSCS)",
    description=(
        "1:1 Pseudo Student Portal for Cavite State University - Imus Campus integrated with "
        "an AI-Driven Constraint Satisfaction (CP-SAT) Enrollment Scheduler for Irregular BSCS Students."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    session_cookie="cvsu_portal_session",
    same_site="lax",
)

app.mount("/static", StaticFiles(directory=str(APP_DIR / "static")), name="static")

app.include_router(auth.router)
app.include_router(portal_pages.router)
app.include_router(scheduler_api.router)
app.include_router(adviser.router)
app.include_router(evaluation.router)
