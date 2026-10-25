"""
Router for Physical Book Copies and Inventory management.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, UserRole, CopyStatus
from app.schemas import BookCopyCreate, BookCopyUpdate, BookCopyResponse, MessageResponse
from app.auth import get_current_user, require_role
from app import services

router = APIRouter(prefix="/api/copies", tags=["Physical Inventory & Copies"])


@router.get("", response_model=List[BookCopyResponse])
def list_copies(
    book_id: Optional[int] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """List physical copies with optional filters for book and status."""
    copies = services.get_book_copies(
        db, book_id=book_id, status_filter=status_filter, skip=skip, limit=limit
    )
    result = []
    for c in copies:
        result.append(BookCopyResponse(
            id=c.id,
            book_id=c.book_id,
            barcode=c.barcode,
            status=c.status.value,
            condition_notes=c.condition_notes,
            acquired_date=c.acquired_date,
            created_at=c.created_at,
            book_title=c.book.title if c.book else "Unknown",
        ))
    return result


@router.get("/available", response_model=List[BookCopyResponse])
def list_available_copies(
    book_id: Optional[int] = Query(None),
    db: Session = Depends(get_db)
):
    """Retrieve only copies with status 'Available' that can be issued."""
    copies = services.get_available_copies(db, book_id=book_id)
    return [
        BookCopyResponse(
            id=c.id,
            book_id=c.book_id,
            barcode=c.barcode,
            status=c.status.value,
            condition_notes=c.condition_notes,
            acquired_date=c.acquired_date,
            created_at=c.created_at,
            book_title=c.book.title if c.book else "Unknown",
        )
        for c in copies
    ]


@router.get("/{copy_id}", response_model=BookCopyResponse)
def get_copy_by_id(copy_id: int, db: Session = Depends(get_db)):
    """Fetch physical copy details by ID."""
    copy = services.get_book_copy_by_id(db, copy_id)
    if not copy:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book copy not found")
    return BookCopyResponse(
        id=copy.id,
        book_id=copy.book_id,
        barcode=copy.barcode,
        status=copy.status.value,
        condition_notes=copy.condition_notes,
        acquired_date=copy.acquired_date,
        created_at=copy.created_at,
        book_title=copy.book.title if copy.book else "Unknown",
    )


@router.get("/barcode/{barcode}", response_model=BookCopyResponse)
def get_copy_by_barcode(barcode: str, db: Session = Depends(get_db)):
    """Fetch physical copy details by barcode."""
    copy = services.get_book_copy_by_barcode(db, barcode)
    if not copy:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book copy not found")
    return BookCopyResponse(
        id=copy.id,
        book_id=copy.book_id,
        barcode=copy.barcode,
        status=copy.status.value,
        condition_notes=copy.condition_notes,
        acquired_date=copy.acquired_date,
        created_at=copy.created_at,
        book_title=copy.book.title if copy.book else "Unknown",
    )


@router.post("", response_model=BookCopyResponse, status_code=status.HTTP_201_CREATED)
def add_physical_copy(
    payload: BookCopyCreate,
    current_user: User = Depends(require_role(UserRole.admin, UserRole.librarian)),
    db: Session = Depends(get_db)
):
    """Add a new physical copy for an existing book title."""
    try:
        copy = services.create_book_copy(
            db=db,
            book_id=payload.book_id,
            barcode=payload.barcode,
            condition_notes=payload.condition_notes,
            acquired_date=payload.acquired_date,
        )
        services.create_audit_log(
            db, current_user.id, "ADD_COPY", "BookCopy", copy.id,
            f"Added copy barcode '{copy.barcode}' for book #{copy.book_id}"
        )
        return BookCopyResponse(
            id=copy.id,
            book_id=copy.book_id,
            barcode=copy.barcode,
            status=copy.status.value,
            condition_notes=copy.condition_notes,
            acquired_date=copy.acquired_date,
            created_at=copy.created_at,
            book_title=copy.book.title if copy.book else "Unknown",
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/{copy_id}", response_model=BookCopyResponse)
def update_physical_copy(
    copy_id: int,
    payload: BookCopyUpdate,
    current_user: User = Depends(require_role(UserRole.admin, UserRole.librarian)),
    db: Session = Depends(get_db)
):
    """Update copy condition notes or status (e.g. Lost, Damaged, Under Maintenance)."""
    copy = services.update_book_copy(db, copy_id, **payload.model_dump(exclude_unset=True))
    if not copy:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book copy not found")
    services.create_audit_log(
        db, current_user.id, "UPDATE_COPY", "BookCopy", copy.id,
        f"Updated copy #{copy.id} status to {copy.status.value}"
    )
    return BookCopyResponse(
        id=copy.id,
        book_id=copy.book_id,
        barcode=copy.barcode,
        status=copy.status.value,
        condition_notes=copy.condition_notes,
        acquired_date=copy.acquired_date,
        created_at=copy.created_at,
        book_title=copy.book.title if copy.book else "Unknown",
    )
