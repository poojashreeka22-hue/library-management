"""
Unified Search API for Books, Members, Copies, and Loans.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import UnifiedSearchResponse
from app import services

router = APIRouter(prefix="/api/search", tags=["Global Search"])


@router.get("", response_model=UnifiedSearchResponse)
def global_search(
    q: str = Query(..., min_length=1, description="Search query string"),
    limit: int = Query(10, ge=1, le=50, description="Max results per category"),
    db: Session = Depends(get_db)
):
    """Execute unified search across Books, Members, and Copies/Loans."""
    return services.unified_search(db=db, query_str=q, limit=limit)
