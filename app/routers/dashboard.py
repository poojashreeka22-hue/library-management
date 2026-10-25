"""
Router for Library Dashboard Metrics and Analytics Reports.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, UserRole
from app.schemas import DashboardResponse, DashboardStats, RecentBookSummary, ActiveLoanSummary, OverdueBookSummary
from app.auth import get_optional_user, require_role
from app import services, config

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard & Analytics"])


@router.get("", response_model=DashboardResponse)
def get_dashboard_summary(db: Session = Depends(get_db)):
    """Retrieve full dashboard data matching the reference UI design."""
    stats = services.get_dashboard_stats(db)
    recent_books = services.get_recent_books(db, limit=5)
    active_loans = services.get_active_loan_summaries(db, limit=5)
    overdue_books = services.get_overdue_summaries(db, limit=5)

    return DashboardResponse(
        stats=DashboardStats(**stats),
        recent_books=[RecentBookSummary(**b) for b in recent_books],
        active_loans=[ActiveLoanSummary(**l) for l in active_loans],
        overdue_books=[OverdueBookSummary(**o) for o in overdue_books],
    )


@router.get("/stats", response_model=DashboardStats)
def get_stats_only(db: Session = Depends(get_db)):
    """Retrieve top metric cards statistics."""
    stats = services.get_dashboard_stats(db)
    return DashboardStats(**stats)


@router.get("/notifications")
def get_dashboard_notifications(db: Session = Depends(get_db)):
    """Retrieve real-time actionable notifications and system alerts."""
    return services.get_notifications(db)


@router.get("/reports")
def get_full_reports(
    current_user: User = Depends(require_role(UserRole.admin, UserRole.librarian)),
    db: Session = Depends(get_db)
):
    """Retrieve comprehensive analytics and distribution reports."""
    return services.get_report_data(db)


@router.get("/settings")
def get_system_settings(db: Session = Depends(get_db)):
    """Retrieve runtime library configuration settings."""
    return {
        "default_loan_days": config.DEFAULT_LOAN_DAYS,
        "max_renewals": config.MAX_RENEWALS,
        "renewal_days": config.RENEWAL_DAYS,
        "fine_per_day": config.FINE_PER_DAY,
        "grace_period_days": config.GRACE_PERIOD_DAYS,
        "reservation_expiry_days": config.RESERVATION_EXPIRY_DAYS,
        "max_active_reservations": config.MAX_ACTIVE_RESERVATIONS,
        "max_unpaid_fine_limit": config.MAX_UNPAID_FINE_LIMIT,
        "lost_book_price": config.LOST_BOOK_PRICE,
        "damaged_book_price": config.DAMAGED_BOOK_PRICE,
    }


@router.put("/settings")
def update_system_settings(
    payload: dict,
    current_user: User = Depends(require_role(UserRole.admin, UserRole.librarian)),
    db: Session = Depends(get_db),
):
    """Staff: update runtime system settings including dues prices and lost book prices."""
    if "default_loan_days" in payload:
        config.DEFAULT_LOAN_DAYS = int(payload["default_loan_days"])
    if "max_renewals" in payload:
        config.MAX_RENEWALS = int(payload["max_renewals"])
    if "renewal_days" in payload:
        config.RENEWAL_DAYS = int(payload["renewal_days"])
    if "fine_per_day" in payload:
        config.FINE_PER_DAY = float(payload["fine_per_day"])
    if "grace_period_days" in payload:
        config.GRACE_PERIOD_DAYS = int(payload["grace_period_days"])
    if "reservation_expiry_days" in payload:
        config.RESERVATION_EXPIRY_DAYS = int(payload["reservation_expiry_days"])
    if "max_active_reservations" in payload:
        config.MAX_ACTIVE_RESERVATIONS = int(payload["max_active_reservations"])
    if "max_unpaid_fine_limit" in payload:
        config.MAX_UNPAID_FINE_LIMIT = float(payload["max_unpaid_fine_limit"])
    if "lost_book_price" in payload:
        config.LOST_BOOK_PRICE = float(payload["lost_book_price"])
    if "damaged_book_price" in payload:
        config.DAMAGED_BOOK_PRICE = float(payload["damaged_book_price"])

    services.create_audit_log(
        db, current_user.id, "UPDATE_SETTINGS", "System", None,
        f"Updated system settings: dues rate ₹{config.FINE_PER_DAY}/day, lost price ₹{config.LOST_BOOK_PRICE}"
    )
    db.commit()
    return get_system_settings(db)
