"""
Router for System Audit Logs.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, UserRole, AuditLog
from app.schemas import AuditLogResponse
from app.auth import require_role
from app import services

router = APIRouter(prefix="/api/audit", tags=["Audit Logs"])


@router.get("", response_model=List[AuditLogResponse])
def list_audit_logs(
    entity_type: Optional[str] = Query(None),
    user_id: Optional[int] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(require_role(UserRole.admin)),
    db: Session = Depends(get_db)
):
    """Admin-only: inspect security and operational audit logs."""
    logs = services.get_audit_logs(db, entity_type=entity_type, user_id=user_id, skip=skip, limit=limit)
    result = []
    for log in logs:
        user_name = log.user.full_name if log.user else (log.user.username if log.user else "System")
        result.append(AuditLogResponse(
            id=log.id,
            user_id=log.user_id,
            action=log.action,
            entity_type=log.entity_type,
            entity_id=log.entity_id,
            details=log.details,
            ip_address=log.ip_address,
            created_at=log.created_at,
            user_name=user_name,
        ))
    return result
