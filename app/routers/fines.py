"""
Router for Fines and Payments management.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, UserRole, Fine, Payment
from app.schemas import (
    FineResponse, FineWaiveRequest, PaymentCreate, PaymentResponse, MessageResponse
)
from app.auth import get_current_user, require_role
from app import services

router = APIRouter(prefix="/api", tags=["Fines & Payments"])


def _to_fine_response(f: Fine) -> FineResponse:
    member_name = f"{f.member.first_name} {f.member.last_name}" if f.member else "Unknown"
    book_title = f.loan.book_copy.book.title if (f.loan and f.loan.book_copy and f.loan.book_copy.book) else "General"
    remaining = max(0.0, f.fine_amount - f.paid_amount)
    return FineResponse(
        id=f.id,
        loan_id=f.loan_id,
        member_id=f.member_id,
        fine_amount=f.fine_amount,
        paid_amount=f.paid_amount,
        status=f.status.value,
        fine_type=f.fine_type.value,
        reason=f.reason,
        created_at=f.created_at,
        updated_at=f.updated_at,
        member_name=member_name,
        book_title=book_title,
        remaining=remaining,
    )


@router.get("/fines", response_model=List[FineResponse])
def list_fines(
    member_id: Optional[int] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """Retrieve all fines with optional filter by member and payment status."""
    fines = services.get_fines(db, member_id=member_id, status_filter=status_filter, skip=skip, limit=limit)
    return [_to_fine_response(f) for f in fines]


@router.get("/fines/{fine_id}", response_model=FineResponse)
def get_fine_details(fine_id: int, db: Session = Depends(get_db)):
    """Fetch details of a single fine record."""
    fine = services.get_fine_by_id(db, fine_id)
    if not fine:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fine not found")
    return _to_fine_response(fine)


@router.post("/fines/{fine_id}/waive", response_model=FineResponse)
def waive_fine_record(
    fine_id: int,
    payload: FineWaiveRequest,
    current_user: User = Depends(require_role(UserRole.admin)),
    db: Session = Depends(get_db)
):
    """Admin-only: waive an unpaid or partially paid fine."""
    try:
        fine = services.waive_fine(db=db, fine_id=fine_id, waived_by=current_user.id, reason=payload.reason)
        return _to_fine_response(fine)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/payments", response_model=List[PaymentResponse])
def list_payments(
    fine_id: Optional[int] = Query(None),
    member_id: Optional[int] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """Retrieve list of payments recorded."""
    payments = services.get_payments(db, fine_id=fine_id, member_id=member_id, skip=skip, limit=limit)
    result = []
    for p in payments:
        receiver_name = p.receiver.full_name if p.receiver else "Staff"
        result.append(PaymentResponse(
            id=p.id,
            fine_id=p.fine_id,
            member_id=p.member_id,
            amount=p.amount,
            payment_method=p.payment_method.value,
            payment_date=p.payment_date,
            received_by=p.received_by,
            notes=p.notes,
            created_at=p.created_at,
            receiver_name=receiver_name,
        ))
    return result


@router.post("/payments", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
def record_payment(
    payload: PaymentCreate,
    current_user: User = Depends(require_role(UserRole.admin, UserRole.librarian)),
    db: Session = Depends(get_db)
):
    """Record payment against an outstanding fine balance."""
    try:
        payment = services.create_payment(
            db=db,
            fine_id=payload.fine_id,
            amount=payload.amount,
            payment_method=payload.payment_method.value,
            received_by=current_user.id,
            notes=payload.notes,
        )
        return PaymentResponse(
            id=payment.id,
            fine_id=payment.fine_id,
            member_id=payment.member_id,
            amount=payment.amount,
            payment_method=payment.payment_method.value,
            payment_date=payment.payment_date,
            received_by=payment.received_by,
            notes=payment.notes,
            created_at=payment.created_at,
            receiver_name=current_user.full_name,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
