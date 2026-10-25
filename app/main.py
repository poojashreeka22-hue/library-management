"""
Library Management System - FastAPI Application Entrypoint.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from app.database import init_db, SessionLocal
from app.seed import seed_library_data
from app.schemas import HealthResponse

# Routers
from app.routers.auth import router as auth_router
from app.routers.books import router as books_router
from app.routers.copies import router as copies_router
from app.routers.members import router as members_router
from app.routers.loans import router as loans_router
from app.routers.reservations import router as reservations_router
from app.routers.fines import router as fines_router
from app.routers.dashboard import router as dashboard_router
from app.routers.audit import router as audit_router
from app.routers.items import router as items_router
from app.routers.search import router as search_router


# Initialize tables on import to guarantee all models and tables exist
init_db()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: initialize database and seed baseline catalog data."""
    init_db()
    db = SessionLocal()
    try:
        seed_library_data(db)
    finally:
        db.close()
    yield


app = FastAPI(
    title="Library Management System API",
    description="Full-featured Library Management System with REST API, business rules, and interactive dashboard.",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static Files
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Sub-routers
app.include_router(auth_router)
app.include_router(books_router)
app.include_router(copies_router)
app.include_router(members_router)
app.include_router(loans_router)
app.include_router(reservations_router)
app.include_router(fines_router)
app.include_router(dashboard_router)
app.include_router(audit_router)
app.include_router(items_router)
app.include_router(search_router)


@app.get("/", tags=["UI"])
def read_root(request: Request):
    """Serve the interactive library dashboard for browsers, or JSON welcome for API clients."""
    accept = request.headers.get("accept", "")
    index_file = os.path.join(static_dir, "index.html")
    # If a browser requests the page (sends text/html in Accept header), return the HTML dashboard
    if "text/html" in accept and os.path.exists(index_file):
        return FileResponse(index_file)
    # Default JSON root response preserving existing test compatibility
    return {
        "message": "Welcome to the FastAPI Service!",
        "status": "online",
        "docs_url": "/docs",
    }


@app.get("/app", tags=["UI"])
def app_ui():
    """Direct route to interactive dashboard UI."""
    index_file = os.path.join(static_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "UI not found"}


@app.get("/health", response_model=HealthResponse, tags=["General"])
def health_check():
    """Health check endpoint for monitoring."""
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        service="Item Catalog Service",
    )
