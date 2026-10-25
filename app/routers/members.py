"""
Router for Members management, registration, and eligibility checking.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, UserRole
from app.schemas import (
    MemberCreate, MemberUpdate, MemberResponse, MessageResponse
)
from app.auth import get_current_user, require_role
from app import services

router = APIRouter(prefix="/api/members", tags=["Members"])


def _to_member_response(m, db: Session) -> MemberResponse:
    active_loans = services.get_member_active_loans(db, m.id)
    fines = services.get_member_outstanding_fines(db, m.id)
    return MemberResponse(
        id=m.id,
        member_code=m.member_code,
        first_name=m.first_name,
        last_name=m.last_name,
        email=m.email,
        phone=m.phone,
        address=m.address,
        membership_type=m.membership_type.value,
        membership_start=m.membership_start,
        membership_expiry=m.membership_expiry,
        max_books=m.max_books,
        is_active=m.is_active,
        active_loans=active_loans,
        outstanding_fines=fines,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


@router.get("", response_model=List[MemberResponse])
def list_members(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    search: Optional[str] = Query(None),
    active_only: bool = Query(False),
    db: Session = Depends(get_db)
):
    """Retrieve all library members with loan and fine statistics."""
    members = services.get_members(db, skip=skip, limit=limit, search=search, active_only=active_only)
    return [_to_member_response(m, db) for m in members]


@router.get("/eligible", response_model=List[MemberResponse])
def list_eligible_members(db: Session = Depends(get_db)):
    """Retrieve members who are currently eligible to borrow books."""
    members = services.get_members(db, active_only=True)
    eligible = []
    for m in members:
        is_ok, _ = services.check_member_eligibility(db, m.id)
        if is_ok:
            eligible.append(_to_member_response(m, db))
    return eligible


@router.get("/{member_id}", response_model=MemberResponse)
def get_member_profile(member_id: int, db: Session = Depends(get_db)):
    """Get detailed profile of a member."""
    m = services.get_member_by_id(db, member_id)
    if not m:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    return _to_member_response(m, db)


@router.get("/{member_id}/eligibility")
def check_borrowing_eligibility(member_id: int, db: Session = Depends(get_db)):
    """Check if member can borrow with descriptive status and reasons."""
    eligible, reason = services.check_member_eligibility(db, member_id)
    active_loans = services.get_member_active_loans(db, member_id)
    outstanding_fines = services.get_member_outstanding_fines(db, member_id)
    return {
        "member_id": member_id,
        "eligible": eligible,
        "reason": reason,
        "active_loans": active_loans,
        "outstanding_fines": outstanding_fines,
    }


@router.post("", response_model=MemberResponse, status_code=status.HTTP_201_CREATED)
def register_member(
    payload: MemberCreate,
    current_user: User = Depends(require_role(UserRole.admin, UserRole.librarian)),
    db: Session = Depends(get_db)
):
    """Register a new library member."""
    try:
        member = services.create_member(
            db=db,
            first_name=payload.first_name,
            last_name=payload.last_name,
            email=payload.email,
            phone=payload.phone,
            address=payload.address,
            membership_type=payload.membership_type.value,
            max_books=payload.max_books,
        )
        services.create_audit_log(
            db, current_user.id, "REGISTER_MEMBER", "Member", member.id,
            f"Registered member {member.member_code} ({member.first_name} {member.last_name})"
        )
        return _to_member_response(member, db)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/{member_id}", response_model=MemberResponse)
def update_member_details(
    member_id: int,
    payload: MemberUpdate,
    current_user: User = Depends(require_role(UserRole.admin, UserRole.librarian)),
    db: Session = Depends(get_db)
):
    """Update existing member information."""
    try:
        member = services.update_member(db, member_id, **payload.model_dump(exclude_unset=True))
        if not member:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
        services.create_audit_log(
            db, current_user.id, "UPDATE_MEMBER", "Member", member_id, f"Updated member #{member_id}"
        )
        return _to_member_response(member, db)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{member_id}/deactivate", response_model=MemberResponse)
def deactivate_member(
    member_id: int,
    current_user: User = Depends(require_role(UserRole.admin, UserRole.librarian)),
    db: Session = Depends(get_db)
):
    """Deactivate member without deleting history."""
    member = services.deactivate_member(db, member_id)
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    services.create_audit_log(
        db, current_user.id, "DEACTIVATE_MEMBER", "Member", member_id, f"Deactivated member #{member_id}"
    )
    return _to_member_response(member, db)
