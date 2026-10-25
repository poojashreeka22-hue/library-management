"""
Router for Book Loans: Issue, Return, Renewal, Active Loans, Overdue Books, and History.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, UserRole, Loan, BookCopy
from app.schemas import (
    LoanCreate, LoanResponse, LoanRenewRequest,
    ReturnCreate, ReturnResponse, MessageResponse
)
from app.auth import get_current_user, require_role
from app import services

router = APIRouter(prefix="/api/loans", tags=["Loans: Issue, Return & Renewals"])


def _to_loan_response(l: Loan) -> LoanResponse:
    member_name = f"{l.member.first_name} {l.member.last_name}" if l.member else "Unknown"
    book_title = l.book_copy.book.title if (l.book_copy and l.book_copy.book) else "Unknown"
    barcode = l.book_copy.barcode if l.book_copy else "Unknown"
    issuer_name = l.issuing_librarian.full_name if l.issuing_librarian else "Staff"
    return LoanResponse(
        id=l.id,
        book_copy_id=l.book_copy_id,
        member_id=l.member_id,
        issued_by=l.issued_by,
        issue_date=l.issue_date,
        due_date=l.due_date,
        return_date=l.return_date,
        is_returned=l.is_returned,
        renewal_count=l.renewal_count,
        max_renewals=l.max_renewals,
        created_at=l.created_at,
        member_name=member_name,
        book_title=book_title,
        barcode=barcode,
        issuer_name=issuer_name,
    )


@router.get("/active", response_model=List[LoanResponse])
def list_active_loans(
    member_id: Optional[int] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """Retrieve all currently active loans."""
    loans = services.get_active_loans(db, skip=skip, limit=limit, member_id=member_id)
    return [_to_loan_response(l) for l in loans]


@router.get("/overdue", response_model=List[LoanResponse])
def list_overdue_loans(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """Retrieve all active loans past their due date."""
    loans = services.get_overdue_loans(db, skip=skip, limit=limit)
    return [_to_loan_response(l) for l in loans]


@router.get("/history", response_model=List[LoanResponse])
def list_borrowing_history(
    member_id: Optional[int] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """Retrieve full borrowing transaction history."""
    loans = services.get_all_loans(db, skip=skip, limit=limit, member_id=member_id)
    return [_to_loan_response(l) for l in loans]


@router.get("/{loan_id}", response_model=LoanResponse)
def get_loan_details(loan_id: int, db: Session = Depends(get_db)):
    """Fetch loan details by ID."""
    loan = services.get_loan_by_id(db, loan_id)
    if not loan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loan not found")
    return _to_loan_response(loan)


@router.post("/issue", response_model=LoanResponse, status_code=status.HTTP_201_CREATED)
def issue_book_copy(
    payload: LoanCreate,
    current_user: User = Depends(require_role(UserRole.admin, UserRole.librarian)),
    db: Session = Depends(get_db)
):
    """Issue an available physical book copy to an eligible member."""
    try:
        loan = services.issue_book(
            db=db,
            book_copy_id=payload.book_copy_id,
            member_id=payload.member_id,
            issued_by=current_user.id,
            due_date=payload.due_date,
        )
        return _to_loan_response(loan)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/return", response_model=ReturnResponse)
def return_borrowed_book(
    payload: ReturnCreate,
    current_user: User = Depends(require_role(UserRole.admin, UserRole.librarian)),
    db: Session = Depends(get_db)
):
    """Process book return, calculate overdue fines, and update physical copy condition."""
    try:
        res = services.return_book(
            db=db,
            loan_id=payload.loan_id,
            returned_to=current_user.id,
            condition_notes=payload.condition_notes,
            copy_status_str=payload.copy_status.value if hasattr(payload.copy_status, 'value') else payload.copy_status,
        )
        return ReturnResponse(**res)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/renew", response_model=LoanResponse)
def renew_borrowed_book(
    payload: LoanRenewRequest,
    current_user: User = Depends(require_role(UserRole.admin, UserRole.librarian)),
    db: Session = Depends(get_db)
):
    """Renew an active loan extending its due date within allowed limits."""
    try:
        loan = services.renew_loan(db=db, loan_id=payload.loan_id, renewed_by=current_user.id)
        return _to_loan_response(loan)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
