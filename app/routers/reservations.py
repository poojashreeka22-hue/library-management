"""
Router for Book Title Reservations and Queue Management.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, UserRole, Reservation
from app.schemas import ReservationCreate, ReservationResponse, MessageResponse
from app.auth import get_current_user, require_role
from app import services

router = APIRouter(prefix="/api/reservations", tags=["Reservations"])


def _to_reservation_response(r: Reservation) -> ReservationResponse:
    book_title = r.book.title if r.book else "Unknown"
    member_name = f"{r.member.first_name} {r.member.last_name}" if r.member else "Unknown"
    return ReservationResponse(
        id=r.id,
        book_id=r.book_id,
        member_id=r.member_id,
        reservation_date=r.reservation_date,
        expiry_date=r.expiry_date,
        status=r.status.value,
        queue_position=r.queue_position,
        created_at=r.created_at,
        book_title=book_title,
        member_name=member_name,
    )


@router.get("", response_model=List[ReservationResponse])
def list_reservations(
    book_id: Optional[int] = Query(None),
    member_id: Optional[int] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """Retrieve reservations with filtering by book, member, or status."""
    reservations = services.get_reservations(
        db, book_id=book_id, member_id=member_id, status_filter=status_filter,
        skip=skip, limit=limit
    )
    return [_to_reservation_response(r) for r in reservations]


@router.post("", response_model=ReservationResponse, status_code=status.HTTP_201_CREATED)
def place_reservation(
    payload: ReservationCreate,
    current_user: User = Depends(require_role(UserRole.admin, UserRole.librarian)),
    db: Session = Depends(get_db)
):
    """Place a new reservation for an active member on a book title."""
    try:
        res = services.create_reservation(db=db, book_id=payload.book_id, member_id=payload.member_id)
        return _to_reservation_response(res)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{reservation_id}/cancel", response_model=ReservationResponse)
def cancel_active_reservation(
    reservation_id: int,
    current_user: User = Depends(require_role(UserRole.admin, UserRole.librarian)),
    db: Session = Depends(get_db)
):
    """Cancel an active reservation and adjust waiting queue positions."""
    try:
        res = services.cancel_reservation(db=db, reservation_id=reservation_id, cancelled_by=current_user.id)
        return _to_reservation_response(res)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
