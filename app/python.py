from fastapi import FastAPI
from app.core.config import settings
from app.api.v1.router import api_router
from app.core.database import engine, Base

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url="/api/v1/openapi.json"
)

# Create database tables on startup (use Alembic migrations for production)
@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

app.include_router(api_router, prefix="/api/v1")

@app.get("/")
def root():
    return {"message": "Welcome to the FastAPI project! Visit /docs for Swagger documentation."}