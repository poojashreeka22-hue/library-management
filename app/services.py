"""
Library Management System - Service layer with all business logic.

All database operations and validations are centralized here.
"""

import json
from datetime import datetime, date, timedelta
from typing import Optional, List, Tuple

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_, or_

from app import models, config
from app.models import (
    User, Author, Category, Book, BookCopy, Member, Loan,
    Reservation, Fine, Payment, AuditLog,
    UserRole, CopyStatus, MembershipType, ReservationStatus,
    FineStatus, FineType, PaymentMethod,
    book_authors, book_categories,
)
from app.auth import hash_password, verify_password


# ---------------------------------------------------------------------------
# Audit helper
# ---------------------------------------------------------------------------

def create_audit_log(
    db: Session,
    user_id: Optional[int],
    action: str,
    entity_type: str,
    entity_id: Optional[int] = None,
    details: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> AuditLog:
    """Record an audit event."""
    log = AuditLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
        ip_address=ip_address,
    )
    db.add(log)
    return log


# ---------------------------------------------------------------------------
# User / Auth services
# ---------------------------------------------------------------------------

def create_user(db: Session, username: str, email: str, password: str,
                full_name: str, role: str = "librarian") -> User:
    """Create a new user account."""
    existing = db.query(User).filter(
        or_(User.username == username, User.email == email.lower())
    ).first()
    if existing:
        if existing.username == username:
            raise ValueError("Username already exists")
        raise ValueError("Email already exists")

    user = User(
        username=username,
        email=email.lower(),
        hashed_password=hash_password(password),
        full_name=full_name,
        role=UserRole(role),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    """Authenticate a user by username and password."""
    user = db.query(User).filter(User.username == username).first()
    if not user or not user.is_active:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def get_users(db: Session, skip: int = 0, limit: int = 100) -> List[User]:
    """Get all users."""
    return db.query(User).offset(skip).limit(limit).all()


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    """Get a user by ID."""
    return db.query(User).filter(User.id == user_id).first()


def update_user(db: Session, user_id: int, **kwargs) -> Optional[User]:
    """Update a user's details."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return None

    if "password" in kwargs and kwargs["password"]:
        kwargs["hashed_password"] = hash_password(kwargs.pop("password"))
    else:
        kwargs.pop("password", None)

    if "email" in kwargs and kwargs["email"]:
        existing = db.query(User).filter(
            User.email == kwargs["email"].lower(), User.id != user_id
        ).first()
        if existing:
            raise ValueError("Email already in use")
        kwargs["email"] = kwargs["email"].lower()

    if "role" in kwargs and kwargs["role"]:
        kwargs["role"] = UserRole(kwargs["role"])

    for key, value in kwargs.items():
        if value is not None and hasattr(user, key):
            setattr(user, key, value)

    db.commit()
    db.refresh(user)
    return user


def ensure_default_admin(db: Session) -> None:
    """Create a default admin user from environment configuration if none exists."""
    admin = db.query(User).filter(User.role == UserRole.admin).first()
    if not admin:
        create_user(
            db,
            username=config.ADMIN_USERNAME,
            email=config.ADMIN_EMAIL,
            password=config.ADMIN_PASSWORD,
            full_name=config.ADMIN_FULL_NAME,
            role="admin",
        )


# ---------------------------------------------------------------------------
# Author services
# ---------------------------------------------------------------------------

def create_author(db: Session, name: str, biography: Optional[str] = None) -> Author:
    """Create a new author."""
    author = Author(name=name, biography=biography)
    db.add(author)
    db.commit()
    db.refresh(author)
    return author


def get_authors(db: Session, skip: int = 0, limit: int = 100,
                search: Optional[str] = None) -> List[Author]:
    """Get all authors with optional search."""
    query = db.query(Author)
    if search:
        query = query.filter(Author.name.ilike(f"%{search}%"))
    return query.order_by(Author.name).offset(skip).limit(limit).all()


def get_author_by_id(db: Session, author_id: int) -> Optional[Author]:
    return db.query(Author).filter(Author.id == author_id).first()


def update_author(db: Session, author_id: int, **kwargs) -> Optional[Author]:
    author = db.query(Author).filter(Author.id == author_id).first()
    if not author:
        return None
    for key, value in kwargs.items():
        if value is not None and hasattr(author, key):
            setattr(author, key, value)
    db.commit()
    db.refresh(author)
    return author


def delete_author(db: Session, author_id: int) -> bool:
    """Delete an author if it won't break references."""
    author = db.query(Author).filter(Author.id == author_id).first()
    if not author:
        return False
    # Remove from association table - doesn't break books, just unlinks
    db.execute(book_authors.delete().where(book_authors.c.author_id == author_id))
    db.delete(author)
    db.commit()
    return True


# ---------------------------------------------------------------------------
# Category services
# ---------------------------------------------------------------------------

def create_category(db: Session, name: str, description: Optional[str] = None) -> Category:
    """Create a new category."""
    existing = db.query(Category).filter(Category.name == name).first()
    if existing:
        raise ValueError(f"Category '{name}' already exists")
    cat = Category(name=name, description=description)
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


def get_categories(db: Session, skip: int = 0, limit: int = 100,
                   search: Optional[str] = None) -> List[Category]:
    query = db.query(Category)
    if search:
        query = query.filter(Category.name.ilike(f"%{search}%"))
    return query.order_by(Category.name).offset(skip).limit(limit).all()


def get_category_by_id(db: Session, category_id: int) -> Optional[Category]:
    return db.query(Category).filter(Category.id == category_id).first()


def update_category(db: Session, category_id: int, **kwargs) -> Optional[Category]:
    cat = db.query(Category).filter(Category.id == category_id).first()
    if not cat:
        return None
    if "name" in kwargs and kwargs["name"]:
        existing = db.query(Category).filter(
            Category.name == kwargs["name"], Category.id != category_id
        ).first()
        if existing:
            raise ValueError(f"Category '{kwargs['name']}' already exists")
    for key, value in kwargs.items():
        if value is not None and hasattr(cat, key):
            setattr(cat, key, value)
    db.commit()
    db.refresh(cat)
    return cat


def delete_category(db: Session, category_id: int) -> bool:
    cat = db.query(Category).filter(Category.id == category_id).first()
    if not cat:
        return False
    db.execute(book_categories.delete().where(book_categories.c.category_id == category_id))
    db.delete(cat)
    db.commit()
    return True


# ---------------------------------------------------------------------------
# Book services
# ---------------------------------------------------------------------------

def create_book(db: Session, title: str, isbn: Optional[str] = None,
                publisher: Optional[str] = None, published_year: Optional[int] = None,
                description: Optional[str] = None, language: str = "English",
                page_count: Optional[int] = None,
                cover_image: Optional[str] = None,
                author_ids: List[int] = None,
                category_ids: List[int] = None) -> Book:
    """Create a new book."""
    # Validate ISBN uniqueness
    if isbn:
        existing = db.query(Book).filter(Book.isbn == isbn).first()
        if existing:
            raise ValueError(f"A book with ISBN '{isbn}' already exists")

    # Validate author IDs
    authors = []
    if author_ids:
        authors = db.query(Author).filter(Author.id.in_(author_ids)).all()
        if len(authors) != len(author_ids):
            raise ValueError("One or more author IDs are invalid")

    # Validate category IDs
    categories = []
    if category_ids:
        categories = db.query(Category).filter(Category.id.in_(category_ids)).all()
        if len(categories) != len(category_ids):
            raise ValueError("One or more category IDs are invalid")

    book = Book(
        title=title,
        isbn=isbn,
        publisher=publisher,
        published_year=published_year,
        description=description,
        language=language or "English",
        page_count=page_count,
        cover_image=cover_image,
    )
    book.authors = authors
    book.categories = categories
    db.add(book)
    db.commit()
    db.refresh(book)
    return book


def get_books(db: Session, skip: int = 0, limit: int = 100,
              search: Optional[str] = None, active_only: bool = True) -> List[Book]:
    """Get all books with optional search across title, ISBN, publisher, authors, and categories."""
    query = db.query(Book).options(
        joinedload(Book.authors),
        joinedload(Book.categories),
        joinedload(Book.copies),
    )
    if active_only:
        query = query.filter(Book.is_active == True)
    if search:
        term = f"%{search}%"
        query = query.filter(
            or_(
                Book.title.ilike(term),
                Book.isbn.ilike(term),
                Book.publisher.ilike(term),
                Book.authors.any(Author.name.ilike(term)),
                Book.categories.any(Category.name.ilike(term)),
            )
        )
    return query.order_by(Book.created_at.desc()).offset(skip).limit(limit).all()


def get_book_by_id(db: Session, book_id: int) -> Optional[Book]:
    return db.query(Book).options(
        joinedload(Book.authors),
        joinedload(Book.categories),
        joinedload(Book.copies),
    ).filter(Book.id == book_id).first()


def update_book(db: Session, book_id: int, **kwargs) -> Optional[Book]:
    """Update an existing book record - not create a duplicate."""
    book = db.query(Book).options(
        joinedload(Book.authors),
        joinedload(Book.categories),
    ).filter(Book.id == book_id).first()
    if not book:
        return None

    # ISBN uniqueness check
    if "isbn" in kwargs and kwargs["isbn"]:
        existing = db.query(Book).filter(
            Book.isbn == kwargs["isbn"], Book.id != book_id
        ).first()
        if existing:
            raise ValueError(f"A book with ISBN '{kwargs['isbn']}' already exists")

    # Handle author/category updates
    author_ids = kwargs.pop("author_ids", None)
    category_ids = kwargs.pop("category_ids", None)

    if author_ids is not None:
        authors = db.query(Author).filter(Author.id.in_(author_ids)).all()
        if len(authors) != len(author_ids):
            raise ValueError("One or more author IDs are invalid")
        book.authors = authors

    if category_ids is not None:
        categories = db.query(Category).filter(Category.id.in_(category_ids)).all()
        if len(categories) != len(category_ids):
            raise ValueError("One or more category IDs are invalid")
        book.categories = categories

    for key, value in kwargs.items():
        if value is not None and hasattr(book, key):
            setattr(book, key, value)

    db.commit()
    db.refresh(book)
    return book


def delete_book(db: Session, book_id: int) -> dict:
    """Archive a book instead of deleting it if it has historical loans."""
    book = db.query(Book).options(joinedload(Book.copies)).filter(Book.id == book_id).first()
    if not book:
        raise ValueError("Book not found")

    # Check for historical loans
    has_loans = db.query(Loan).join(BookCopy).filter(BookCopy.book_id == book_id).first()
    if has_loans:
        book.is_active = False
        db.commit()
        return {"action": "archived", "message": "Book archived (has historical loans)"}

    # Safe to delete
    db.delete(book)
    db.commit()
    return {"action": "deleted", "message": "Book deleted"}


# ---------------------------------------------------------------------------
# BookCopy services
# ---------------------------------------------------------------------------

def create_book_copy(db: Session, book_id: int, barcode: str,
                     condition_notes: Optional[str] = None,
                     acquired_date: Optional[date] = None) -> BookCopy:
    """Add a physical copy for an existing book."""
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise ValueError("Book does not exist")
    if not book.is_active:
        raise ValueError("Cannot add copies to an archived book")

    existing = db.query(BookCopy).filter(BookCopy.barcode == barcode).first()
    if existing:
        raise ValueError(f"A copy with barcode '{barcode}' already exists")

    copy = BookCopy(
        book_id=book_id,
        barcode=barcode,
        condition_notes=condition_notes,
        acquired_date=acquired_date or date.today(),
        status=CopyStatus.Available,
    )
    db.add(copy)
    db.commit()
    db.refresh(copy)
    return copy


def get_book_copies(db: Session, book_id: Optional[int] = None,
                    status_filter: Optional[str] = None,
                    skip: int = 0, limit: int = 100) -> List[BookCopy]:
    query = db.query(BookCopy).options(joinedload(BookCopy.book))
    if book_id:
        query = query.filter(BookCopy.book_id == book_id)
    if status_filter:
        query = query.filter(BookCopy.status == CopyStatus(status_filter))
    return query.order_by(BookCopy.id).offset(skip).limit(limit).all()


def get_book_copy_by_id(db: Session, copy_id: int) -> Optional[BookCopy]:
    return db.query(BookCopy).options(joinedload(BookCopy.book)).filter(BookCopy.id == copy_id).first()


def get_book_copy_by_barcode(db: Session, barcode: str) -> Optional[BookCopy]:
    return db.query(BookCopy).options(joinedload(BookCopy.book)).filter(BookCopy.barcode == barcode).first()


def update_book_copy(db: Session, copy_id: int, **kwargs) -> Optional[BookCopy]:
    copy = db.query(BookCopy).filter(BookCopy.id == copy_id).first()
    if not copy:
        return None
    if "status" in kwargs and kwargs["status"]:
        kwargs["status"] = CopyStatus(kwargs["status"])
    for key, value in kwargs.items():
        if value is not None and hasattr(copy, key):
            setattr(copy, key, value)
    db.commit()
    db.refresh(copy)
    return copy


def get_available_copies(db: Session, book_id: Optional[int] = None) -> List[BookCopy]:
    """Get copies that are available for loan."""
    query = db.query(BookCopy).options(joinedload(BookCopy.book)).filter(
        BookCopy.status == CopyStatus.Available
    )
    if book_id:
        query = query.filter(BookCopy.book_id == book_id)
    return query.all()


def count_copies(db: Session, book_id: int) -> dict:
    """Count total and available copies for a book."""
    total = db.query(func.count(BookCopy.id)).filter(BookCopy.book_id == book_id).scalar()
    available = db.query(func.count(BookCopy.id)).filter(
        BookCopy.book_id == book_id,
        BookCopy.status == CopyStatus.Available,
    ).scalar()
    return {"total": total or 0, "available": available or 0}


# ---------------------------------------------------------------------------
# Member services
# ---------------------------------------------------------------------------

def _generate_member_code(db: Session) -> str:
    """Generate next member code like MEM-0001."""
    last = db.query(Member).order_by(Member.id.desc()).first()
    next_num = (last.id + 1) if last else 1
    return f"MEM-{next_num:04d}"


def create_member(db: Session, first_name: str, last_name: str, email: str,
                  phone: Optional[str] = None, address: Optional[str] = None,
                  membership_type: str = "standard", max_books: int = 5) -> Member:
    """Register a new member."""
    existing = db.query(Member).filter(Member.email == email.lower()).first()
    if existing:
        raise ValueError("A member with this email already exists")

    member = Member(
        member_code=_generate_member_code(db),
        first_name=first_name,
        last_name=last_name,
        email=email.lower(),
        phone=phone,
        address=address,
        membership_type=MembershipType(membership_type),
        max_books=max_books,
        membership_start=date.today(),
        membership_expiry=date.today() + timedelta(days=365),
        is_active=True,
    )
    db.add(member)
    db.commit()
    db.refresh(member)
    return member


def get_members(db: Session, skip: int = 0, limit: int = 100,
                search: Optional[str] = None, active_only: bool = False) -> List[Member]:
    query = db.query(Member)
    if active_only:
        query = query.filter(Member.is_active == True)
    if search:
        query = query.filter(
            or_(
                Member.first_name.ilike(f"%{search}%"),
                Member.last_name.ilike(f"%{search}%"),
                Member.email.ilike(f"%{search}%"),
                Member.member_code.ilike(f"%{search}%"),
            )
        )
    return query.order_by(Member.created_at.desc()).offset(skip).limit(limit).all()


def get_member_by_id(db: Session, member_id: int) -> Optional[Member]:
    return db.query(Member).filter(Member.id == member_id).first()


def get_member_active_loans(db: Session, member_id: int) -> int:
    """Count active (non-returned) loans for a member."""
    return db.query(func.count(Loan.id)).filter(
        Loan.member_id == member_id,
        Loan.is_returned == False,
    ).scalar() or 0


def get_member_outstanding_fines(db: Session, member_id: int) -> float:
    """Calculate total outstanding fines for a member."""
    result = db.query(func.sum(Fine.fine_amount - Fine.paid_amount)).filter(
        Fine.member_id == member_id,
        Fine.status.in_([FineStatus.Unpaid, FineStatus.Partial]),
    ).scalar()
    return float(result) if result else 0.0


def update_member(db: Session, member_id: int, **kwargs) -> Optional[Member]:
    """Update a member's details - update the same record."""
    member = db.query(Member).filter(Member.id == member_id).first()
    if not member:
        return None

    if "email" in kwargs and kwargs["email"]:
        existing = db.query(Member).filter(
            Member.email == kwargs["email"].lower(), Member.id != member_id
        ).first()
        if existing:
            raise ValueError("Email already in use by another member")
        kwargs["email"] = kwargs["email"].lower()

    if "membership_type" in kwargs and kwargs["membership_type"]:
        kwargs["membership_type"] = MembershipType(kwargs["membership_type"])

    for key, value in kwargs.items():
        if value is not None and hasattr(member, key):
            setattr(member, key, value)

    db.commit()
    db.refresh(member)
    return member


def deactivate_member(db: Session, member_id: int) -> Optional[Member]:
    """Deactivate a member while preserving history."""
    member = db.query(Member).filter(Member.id == member_id).first()
    if not member:
        return None
    member.is_active = False
    db.commit()
    db.refresh(member)
    return member


def check_member_eligibility(db: Session, member_id: int) -> Tuple[bool, str]:
    """Check if a member is eligible to borrow books."""
    member = db.query(Member).filter(Member.id == member_id).first()
    if not member:
        return False, "Member not found"
    if not member.is_active:
        return False, "Member is inactive"
    if member.membership_expiry < date.today():
        return False, "Membership has expired"

    active_loans = get_member_active_loans(db, member_id)
    if active_loans >= member.max_books:
        return False, f"Maximum loan limit ({member.max_books}) reached"

    outstanding = get_member_outstanding_fines(db, member_id)
    if outstanding >= config.MAX_UNPAID_FINE_LIMIT:
        return False, f"Outstanding fines (₹{outstanding:.2f}) exceed the limit (₹{config.MAX_UNPAID_FINE_LIMIT:.2f})"

    return True, "Eligible"


# ---------------------------------------------------------------------------
# Loan / Issue services
# ---------------------------------------------------------------------------

def issue_book(db: Session, book_copy_id: int, member_id: int,
               issued_by: int, due_date: Optional[date] = None) -> Loan:
    """Issue a book copy to a member with full validation."""
    # 1. Validate member
    member = db.query(Member).filter(Member.id == member_id).first()
    if not member:
        raise ValueError("Member not found")

    eligible, reason = check_member_eligibility(db, member_id)
    if not eligible:
        raise ValueError(reason)

    # 2. Validate book copy
    copy = db.query(BookCopy).options(joinedload(BookCopy.book)).filter(
        BookCopy.id == book_copy_id
    ).first()
    if not copy:
        raise ValueError("Book copy not found")

    if copy.status != CopyStatus.Available:
        raise ValueError(f"Copy is not available (current status: {copy.status.value})")

    # 3. Check for conflicting active loan on the same copy
    active_loan = db.query(Loan).filter(
        Loan.book_copy_id == book_copy_id,
        Loan.is_returned == False,
    ).first()
    if active_loan:
        raise ValueError("This copy already has an active loan")

    # 4. Check for reservation conflicts
    active_reservation = db.query(Reservation).filter(
        Reservation.book_id == copy.book_id,
        Reservation.status == ReservationStatus.Active,
    ).order_by(Reservation.queue_position).first()

    if active_reservation and active_reservation.member_id != member_id:
        raise ValueError("This book is reserved for another member")

    # 5. Validate issuing librarian
    issuer = db.query(User).filter(User.id == issued_by).first()
    if not issuer:
        raise ValueError("Issuing librarian not found")
    if issuer.role not in [UserRole.admin, UserRole.librarian]:
        raise ValueError("User does not have permission to issue books")

    # 6. Calculate due date
    if due_date is None:
        due_date = date.today() + timedelta(days=config.DEFAULT_LOAN_DAYS)

    # 7. Create loan within transaction
    try:
        loan = Loan(
            book_copy_id=book_copy_id,
            member_id=member_id,
            issued_by=issued_by,
            issue_date=date.today(),
            due_date=due_date,
            is_returned=False,
            renewal_count=0,
            max_renewals=config.MAX_RENEWALS,
        )
        db.add(loan)

        # Update copy status
        copy.status = CopyStatus.OnLoan

        # Fulfill reservation if applicable
        if active_reservation and active_reservation.member_id == member_id:
            active_reservation.status = ReservationStatus.Fulfilled

        # Audit log
        create_audit_log(
            db, issued_by, "ISSUE_BOOK", "Loan", None,
            json.dumps({
                "member_id": member_id,
                "book_copy_id": book_copy_id,
                "book_title": copy.book.title,
                "due_date": str(due_date),
            }),
        )

        db.commit()
        db.refresh(loan)
        return loan
    except Exception:
        db.rollback()
        raise


def get_active_loans(db: Session, skip: int = 0, limit: int = 100,
                     member_id: Optional[int] = None) -> List[Loan]:
    """Get all active (non-returned) loans."""
    query = db.query(Loan).options(
        joinedload(Loan.book_copy).joinedload(BookCopy.book),
        joinedload(Loan.member),
        joinedload(Loan.issuing_librarian),
    ).filter(Loan.is_returned == False)
    if member_id:
        query = query.filter(Loan.member_id == member_id)
    return query.order_by(Loan.issue_date.desc()).offset(skip).limit(limit).all()


def get_all_loans(db: Session, skip: int = 0, limit: int = 100,
                  member_id: Optional[int] = None) -> List[Loan]:
    """Get all loans (active and returned)."""
    query = db.query(Loan).options(
        joinedload(Loan.book_copy).joinedload(BookCopy.book),
        joinedload(Loan.member),
        joinedload(Loan.issuing_librarian),
    )
    if member_id:
        query = query.filter(Loan.member_id == member_id)
    return query.order_by(Loan.issue_date.desc()).offset(skip).limit(limit).all()


def get_loan_by_id(db: Session, loan_id: int) -> Optional[Loan]:
    return db.query(Loan).options(
        joinedload(Loan.book_copy).joinedload(BookCopy.book),
        joinedload(Loan.member),
        joinedload(Loan.issuing_librarian),
        joinedload(Loan.returning_librarian),
        joinedload(Loan.fine),
    ).filter(Loan.id == loan_id).first()


def get_overdue_loans(db: Session, skip: int = 0, limit: int = 100) -> List[Loan]:
    """Get active loans that are past their due date."""
    return db.query(Loan).options(
        joinedload(Loan.book_copy).joinedload(BookCopy.book),
        joinedload(Loan.member),
    ).filter(
        Loan.is_returned == False,
        Loan.due_date < date.today(),
    ).order_by(Loan.due_date).offset(skip).limit(limit).all()


# ---------------------------------------------------------------------------
# Return services
# ---------------------------------------------------------------------------

def return_book(db: Session, loan_id: int, returned_to: int,
                condition_notes: Optional[str] = None,
                copy_status_str: str = "Available") -> dict:
    """Process a book return with full validation and fine calculation."""
    loan = db.query(Loan).options(
        joinedload(Loan.book_copy).joinedload(BookCopy.book),
        joinedload(Loan.member),
        joinedload(Loan.fine),
    ).filter(Loan.id == loan_id).first()

    if not loan:
        raise ValueError("Loan not found")
    if loan.is_returned:
        raise ValueError("This loan has already been returned")

    # Validate returning librarian
    returner = db.query(User).filter(User.id == returned_to).first()
    if not returner:
        raise ValueError("Returning librarian not found")
    if returner.role not in [UserRole.admin, UserRole.librarian]:
        raise ValueError("User does not have permission to process returns")

    try:
        return_date_val = date.today()
        loan.return_date = return_date_val
        loan.returned_to = returned_to
        loan.is_returned = True

        # Calculate overdue
        overdue_days = max(0, (return_date_val - loan.due_date).days - config.GRACE_PERIOD_DAYS)
        fine_amount = 0.0

        if overdue_days > 0:
            fine_amount = overdue_days * config.FINE_PER_DAY
            # Create fine only if one doesn't exist
            if not loan.fine:
                fine = Fine(
                    loan_id=loan.id,
                    member_id=loan.member_id,
                    fine_amount=fine_amount,
                    fine_type=FineType.Overdue,
                    reason=f"Overdue by {overdue_days} day(s) at ₹{config.FINE_PER_DAY}/day",
                )
                db.add(fine)

        # Set copy status based on condition
        copy_status = CopyStatus(copy_status_str)
        loan.book_copy.status = copy_status

        if condition_notes:
            loan.book_copy.condition_notes = condition_notes

        # Check for waiting reservations if copy is Available
        if copy_status == CopyStatus.Available:
            _notify_next_reservation(db, loan.book_copy.book_id)

        # Audit
        create_audit_log(
            db, returned_to, "RETURN_BOOK", "Loan", loan.id,
            json.dumps({
                "member_id": loan.member_id,
                "book_copy_id": loan.book_copy_id,
                "book_title": loan.book_copy.book.title,
                "overdue_days": overdue_days,
                "fine_amount": fine_amount,
            }),
        )

        db.commit()

        return {
            "loan_id": loan.id,
            "member_name": f"{loan.member.first_name} {loan.member.last_name}",
            "book_title": loan.book_copy.book.title,
            "barcode": loan.book_copy.barcode,
            "issue_date": loan.issue_date,
            "due_date": loan.due_date,
            "return_date": return_date_val,
            "overdue_days": overdue_days,
            "fine_amount": fine_amount,
            "message": f"Book returned successfully" + (f" with fine ₹{fine_amount:.2f}" if fine_amount > 0 else ""),
        }
    except Exception:
        db.rollback()
        raise


def _notify_next_reservation(db: Session, book_id: int):
    """If a copy becomes available, find the next waiting reservation."""
    next_res = db.query(Reservation).filter(
        Reservation.book_id == book_id,
        Reservation.status == ReservationStatus.Active,
    ).order_by(Reservation.queue_position).first()
    # In a real system, you'd send a notification here
    # For now, we just keep the reservation active


# ---------------------------------------------------------------------------
# Renewal services
# ---------------------------------------------------------------------------

def renew_loan(db: Session, loan_id: int, renewed_by: int) -> Loan:
    """Renew an active loan."""
    loan = db.query(Loan).options(
        joinedload(Loan.book_copy).joinedload(BookCopy.book),
        joinedload(Loan.member),
    ).filter(Loan.id == loan_id).first()

    if not loan:
        raise ValueError("Loan not found")
    if loan.is_returned:
        raise ValueError("Cannot renew a returned loan")
    if loan.renewal_count >= loan.max_renewals:
        raise ValueError(f"Maximum renewal limit ({loan.max_renewals}) reached")

    # Check member eligibility
    eligible, reason = check_member_eligibility(db, loan.member_id)
    if not eligible and "loan limit" not in reason.lower():
        raise ValueError(f"Member not eligible for renewal: {reason}")

    # Check for reservations blocking renewal
    active_reservation = db.query(Reservation).filter(
        Reservation.book_id == loan.book_copy.book_id,
        Reservation.status == ReservationStatus.Active,
        Reservation.member_id != loan.member_id,
    ).first()
    if active_reservation:
        raise ValueError("Cannot renew: book has active reservations from other members")

    # Check overdue restriction - must not be excessively overdue
    if loan.due_date < date.today():
        overdue_days = (date.today() - loan.due_date).days
        if overdue_days > config.GRACE_PERIOD_DAYS:
            raise ValueError(f"Cannot renew: loan is overdue by {overdue_days} day(s). Please return first.")

    # Perform renewal - update same loan, don't create new one
    try:
        loan.due_date = date.today() + timedelta(days=config.RENEWAL_DAYS)
        loan.renewal_count += 1

        create_audit_log(
            db, renewed_by, "RENEW_LOAN", "Loan", loan.id,
            json.dumps({
                "member_id": loan.member_id,
                "new_due_date": str(loan.due_date),
                "renewal_count": loan.renewal_count,
            }),
        )

        db.commit()
        db.refresh(loan)
        return loan
    except Exception:
        db.rollback()
        raise


# ---------------------------------------------------------------------------
# Reservation services
# ---------------------------------------------------------------------------

def create_reservation(db: Session, book_id: int, member_id: int) -> Reservation:
    """Create a reservation for a book title."""
    book = db.query(Book).filter(Book.id == book_id, Book.is_active == True).first()
    if not book:
        raise ValueError("Book not found or inactive")

    member = db.query(Member).filter(Member.id == member_id).first()
    if not member:
        raise ValueError("Member not found")
    if not member.is_active:
        raise ValueError("Member is inactive")
    if member.membership_expiry < date.today():
        raise ValueError("Membership has expired")

    # Check duplicate active reservation
    existing = db.query(Reservation).filter(
        Reservation.book_id == book_id,
        Reservation.member_id == member_id,
        Reservation.status == ReservationStatus.Active,
    ).first()
    if existing:
        raise ValueError("Member already has an active reservation for this book")

    # Check reservation limit
    active_count = db.query(func.count(Reservation.id)).filter(
        Reservation.member_id == member_id,
        Reservation.status == ReservationStatus.Active,
    ).scalar()
    if active_count >= config.MAX_ACTIVE_RESERVATIONS:
        raise ValueError(f"Maximum active reservations ({config.MAX_ACTIVE_RESERVATIONS}) reached")

    # Calculate queue position
    last_position = db.query(func.max(Reservation.queue_position)).filter(
        Reservation.book_id == book_id,
        Reservation.status == ReservationStatus.Active,
    ).scalar() or 0

    reservation = Reservation(
        book_id=book_id,
        member_id=member_id,
        reservation_date=datetime.utcnow(),
        expiry_date=datetime.utcnow() + timedelta(days=config.RESERVATION_EXPIRY_DAYS),
        status=ReservationStatus.Active,
        queue_position=last_position + 1,
    )
    db.add(reservation)

    create_audit_log(
        db, None, "CREATE_RESERVATION", "Reservation", None,
        json.dumps({"book_id": book_id, "member_id": member_id}),
    )

    db.commit()
    db.refresh(reservation)
    return reservation


def get_reservations(db: Session, book_id: Optional[int] = None,
                     member_id: Optional[int] = None,
                     status_filter: Optional[str] = None,
                     skip: int = 0, limit: int = 100) -> List[Reservation]:
    query = db.query(Reservation).options(
        joinedload(Reservation.book),
        joinedload(Reservation.member),
    )
    if book_id:
        query = query.filter(Reservation.book_id == book_id)
    if member_id:
        query = query.filter(Reservation.member_id == member_id)
    if status_filter:
        query = query.filter(Reservation.status == ReservationStatus(status_filter))
    return query.order_by(Reservation.queue_position).offset(skip).limit(limit).all()


def cancel_reservation(db: Session, reservation_id: int, cancelled_by: Optional[int] = None) -> Reservation:
    """Cancel an active reservation."""
    res = db.query(Reservation).filter(Reservation.id == reservation_id).first()
    if not res:
        raise ValueError("Reservation not found")
    if res.status != ReservationStatus.Active:
        raise ValueError("Only active reservations can be cancelled")

    res.status = ReservationStatus.Cancelled

    # Reorder queue positions for remaining active reservations
    remaining = db.query(Reservation).filter(
        Reservation.book_id == res.book_id,
        Reservation.status == ReservationStatus.Active,
        Reservation.id != reservation_id,
    ).order_by(Reservation.queue_position).all()
    for idx, r in enumerate(remaining, 1):
        r.queue_position = idx

    create_audit_log(
        db, cancelled_by, "CANCEL_RESERVATION", "Reservation", reservation_id,
        json.dumps({"book_id": res.book_id, "member_id": res.member_id}),
    )

    db.commit()
    db.refresh(res)
    return res


def expire_reservations(db: Session) -> int:
    """Expire reservations that have passed their expiry date."""
    expired = db.query(Reservation).filter(
        Reservation.status == ReservationStatus.Active,
        Reservation.expiry_date < datetime.utcnow(),
    ).all()
    count = 0
    for res in expired:
        res.status = ReservationStatus.Expired
        count += 1
    if count > 0:
        db.commit()
    return count


# ---------------------------------------------------------------------------
# Fine services
# ---------------------------------------------------------------------------

def get_fines(db: Session, member_id: Optional[int] = None,
              status_filter: Optional[str] = None,
              skip: int = 0, limit: int = 100) -> List[Fine]:
    query = db.query(Fine).options(
        joinedload(Fine.loan).joinedload(Loan.book_copy).joinedload(BookCopy.book),
        joinedload(Fine.member),
    )
    if member_id:
        query = query.filter(Fine.member_id == member_id)
    if status_filter:
        query = query.filter(Fine.status == FineStatus(status_filter))
    return query.order_by(Fine.created_at.desc()).offset(skip).limit(limit).all()


def get_fine_by_id(db: Session, fine_id: int) -> Optional[Fine]:
    return db.query(Fine).options(
        joinedload(Fine.loan).joinedload(Loan.book_copy).joinedload(BookCopy.book),
        joinedload(Fine.member),
        joinedload(Fine.payments),
    ).filter(Fine.id == fine_id).first()


def waive_fine(db: Session, fine_id: int, waived_by: int, reason: str) -> Fine:
    """Waive a fine."""
    fine = db.query(Fine).filter(Fine.id == fine_id).first()
    if not fine:
        raise ValueError("Fine not found")
    if fine.status == FineStatus.Paid:
        raise ValueError("Cannot waive a fully paid fine")
    if fine.status == FineStatus.Waived:
        raise ValueError("Fine is already waived")

    fine.status = FineStatus.Waived
    fine.reason = f"Waived: {reason}"

    create_audit_log(
        db, waived_by, "WAIVE_FINE", "Fine", fine_id,
        json.dumps({"member_id": fine.member_id, "amount": fine.fine_amount}),
    )

    db.commit()
    db.refresh(fine)
    return fine


# ---------------------------------------------------------------------------
# Payment services
# ---------------------------------------------------------------------------

def create_payment(db: Session, fine_id: int, amount: float,
                   payment_method: str, received_by: int,
                   notes: Optional[str] = None) -> Payment:
    """Record a payment against a fine."""
    fine = db.query(Fine).filter(Fine.id == fine_id).first()
    if not fine:
        raise ValueError("Fine not found")
    if fine.status in [FineStatus.Paid, FineStatus.Waived]:
        raise ValueError(f"Fine is already {fine.status.value}")

    if amount <= 0:
        raise ValueError("Payment amount must be positive")

    remaining = fine.fine_amount - fine.paid_amount
    if amount > remaining + 0.01:  # small tolerance for floating point
        raise ValueError(f"Payment amount (₹{amount:.2f}) exceeds remaining balance (₹{remaining:.2f})")

    # Validate receiver
    receiver = db.query(User).filter(User.id == received_by).first()
    if not receiver:
        raise ValueError("Receiver not found")
    if receiver.role not in [UserRole.admin, UserRole.librarian]:
        raise ValueError("User does not have permission to receive payments")

    try:
        payment = Payment(
            fine_id=fine_id,
            member_id=fine.member_id,
            amount=amount,
            payment_method=PaymentMethod(payment_method),
            received_by=received_by,
            notes=notes,
        )
        db.add(payment)

        # Update fine
        fine.paid_amount += amount
        if fine.paid_amount >= fine.fine_amount - 0.01:
            fine.status = FineStatus.Paid
            fine.paid_amount = fine.fine_amount  # exact
        else:
            fine.status = FineStatus.Partial

        create_audit_log(
            db, received_by, "RECEIVE_PAYMENT", "Payment", None,
            json.dumps({
                "fine_id": fine_id,
                "member_id": fine.member_id,
                "amount": amount,
                "method": payment_method,
            }),
        )

        db.commit()
        db.refresh(payment)
        return payment
    except Exception:
        db.rollback()
        raise


def get_payments(db: Session, fine_id: Optional[int] = None,
                 member_id: Optional[int] = None,
                 skip: int = 0, limit: int = 100) -> List[Payment]:
    query = db.query(Payment).options(
        joinedload(Payment.fine),
        joinedload(Payment.member),
        joinedload(Payment.receiver),
    )
    if fine_id:
        query = query.filter(Payment.fine_id == fine_id)
    if member_id:
        query = query.filter(Payment.member_id == member_id)
    return query.order_by(Payment.created_at.desc()).offset(skip).limit(limit).all()


# ---------------------------------------------------------------------------
# Audit log services
# ---------------------------------------------------------------------------

def get_audit_logs(db: Session, entity_type: Optional[str] = None,
                   user_id: Optional[int] = None,
                   skip: int = 0, limit: int = 100) -> List[AuditLog]:
    query = db.query(AuditLog).options(joinedload(AuditLog.user))
    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type)
    if user_id:
        query = query.filter(AuditLog.user_id == user_id)
    return query.order_by(AuditLog.created_at.desc()).offset(skip).limit(limit).all()


# ---------------------------------------------------------------------------
# Dashboard / reporting services
# ---------------------------------------------------------------------------

def get_dashboard_stats(db: Session) -> dict:
    """Calculate all dashboard metrics from the database."""
    total_books = db.query(func.count(Book.id)).filter(Book.is_active == True).scalar() or 0
    total_copies = db.query(func.count(BookCopy.id)).scalar() or 0
    available_copies = db.query(func.count(BookCopy.id)).filter(
        BookCopy.status == CopyStatus.Available
    ).scalar() or 0
    active_members = db.query(func.count(Member.id)).filter(
        Member.is_active == True
    ).scalar() or 0
    active_loans = db.query(func.count(Loan.id)).filter(
        Loan.is_returned == False
    ).scalar() or 0
    overdue_loans = db.query(func.count(Loan.id)).filter(
        Loan.is_returned == False,
        Loan.due_date < date.today(),
    ).scalar() or 0

    outstanding_fines = db.query(
        func.sum(Fine.fine_amount - Fine.paid_amount)
    ).filter(
        Fine.status.in_([FineStatus.Unpaid, FineStatus.Partial])
    ).scalar() or 0.0

    total_collected = db.query(func.sum(Payment.amount)).scalar() or 0.0

    return {
        "total_books": total_books,
        "total_copies": total_copies,
        "available_copies": available_copies,
        "active_members": active_members,
        "active_loans": active_loans,
        "overdue_loans": overdue_loans,
        "outstanding_fines": float(outstanding_fines),
        "total_fines_collected": float(total_collected),
    }


def get_recent_books(db: Session, limit: int = 5) -> List[dict]:
    """Get recently added books."""
    books = db.query(Book).options(
        joinedload(Book.authors),
        joinedload(Book.categories),
        joinedload(Book.copies),
    ).filter(Book.is_active == True).order_by(Book.created_at.desc()).limit(limit).all()

    result = []
    for book in books:
        total = len(book.copies)
        available = sum(1 for c in book.copies if c.status == CopyStatus.Available)
        result.append({
            "id": book.id,
            "title": book.title,
            "author": ", ".join(a.name for a in book.authors) if book.authors else "Unknown",
            "category": ", ".join(c.name for c in book.categories) if book.categories else "General",
            "copies": total,
            "status": "Available" if available > 0 else "All Issued",
        })
    return result


def get_active_loan_summaries(db: Session, limit: int = 5) -> List[dict]:
    """Get recent active loan summaries for dashboard."""
    loans = db.query(Loan).options(
        joinedload(Loan.book_copy).joinedload(BookCopy.book),
        joinedload(Loan.member),
    ).filter(Loan.is_returned == False).order_by(Loan.issue_date.desc()).limit(limit).all()

    return [{
        "member_name": f"{l.member.first_name} {l.member.last_name}",
        "book_title": l.book_copy.book.title,
        "issue_date": l.issue_date,
        "due_date": l.due_date,
        "status": "Overdue" if l.due_date < date.today() else "On Loan",
    } for l in loans]


def get_overdue_summaries(db: Session, limit: int = 5) -> List[dict]:
    """Get overdue book summaries for dashboard."""
    loans = get_overdue_loans(db, limit=limit)
    return [{
        "member_name": f"{l.member.first_name} {l.member.last_name}",
        "book_title": l.book_copy.book.title,
        "days_overdue": (date.today() - l.due_date).days,
        "fine_amount": max(0, (date.today() - l.due_date).days - config.GRACE_PERIOD_DAYS) * config.FINE_PER_DAY,
    } for l in loans]


def get_report_data(db: Session) -> dict:
    """Comprehensive report data."""
    stats = get_dashboard_stats(db)

    # Monthly loan activity
    loans_this_month = db.query(func.count(Loan.id)).filter(
        func.strftime('%Y-%m', Loan.issue_date) == date.today().strftime('%Y-%m')
    ).scalar() or 0

    returns_this_month = db.query(func.count(Loan.id)).filter(
        Loan.is_returned == True,
        func.strftime('%Y-%m', Loan.return_date) == date.today().strftime('%Y-%m')
    ).scalar() or 0

    # Category-wise book distribution
    category_dist = db.query(
        Category.name,
        func.count(Book.id),
    ).join(book_categories).join(Book).filter(
        Book.is_active == True
    ).group_by(Category.name).all()

    # Top borrowed books
    top_books = db.query(
        Book.title,
        func.count(Loan.id).label('loan_count'),
    ).join(BookCopy, Book.id == BookCopy.book_id).join(
        Loan, BookCopy.id == Loan.book_copy_id
    ).group_by(Book.title).order_by(func.count(Loan.id).desc()).limit(10).all()

    return {
        **stats,
        "loans_this_month": loans_this_month,
        "returns_this_month": returns_this_month,
        "category_distribution": [{"name": c[0], "count": c[1]} for c in category_dist],
        "top_borrowed_books": [{"title": t[0], "count": t[1]} for t in top_books],
    }


# ---------------------------------------------------------------------------
# Unified Search & Batch Import Operations
# ---------------------------------------------------------------------------

def unified_search(db: Session, query_str: str, limit: int = 10) -> dict:
    """Unified search across books, members, and copies."""
    if not query_str or not query_str.strip():
        return {"query": "", "total_results": 0, "books": [], "members": [], "copies": []}

    term = f"%{query_str.strip()}%"

    # 1. Search Books
    books = db.query(Book).options(
        joinedload(Book.authors),
        joinedload(Book.categories),
        joinedload(Book.copies),
    ).filter(
        Book.is_active == True,
        or_(
            Book.title.ilike(term),
            Book.isbn.ilike(term),
            Book.publisher.ilike(term),
            Book.authors.any(Author.name.ilike(term)),
            Book.categories.any(Category.name.ilike(term)),
        )
    ).limit(limit).all()

    book_items = []
    for b in books:
        avail = sum(1 for c in b.copies if c.status == CopyStatus.Available)
        book_items.append({
            "id": b.id,
            "title": b.title,
            "isbn": b.isbn,
            "authors": ", ".join(a.name for a in b.authors) or "Unknown",
            "categories": ", ".join(c.name for c in b.categories) or "General",
            "available_copies": avail,
            "total_copies": len(b.copies),
            "status": "Available" if avail > 0 else "Unavailable",
        })

    # 2. Search Members
    members = db.query(Member).filter(
        or_(
            Member.first_name.ilike(term),
            Member.last_name.ilike(term),
            Member.email.ilike(term),
            Member.member_code.ilike(term),
            Member.phone.ilike(term),
        )
    ).limit(limit).all()

    member_items = []
    for m in members:
        active_loans_cnt = db.query(func.count(Loan.id)).filter(
            Loan.member_id == m.id, Loan.is_returned == False
        ).scalar() or 0
        member_items.append({
            "id": m.id,
            "member_code": m.member_code,
            "name": f"{m.first_name} {m.last_name}",
            "email": m.email,
            "phone": m.phone,
            "membership_type": m.membership_type.value if hasattr(m.membership_type, 'value') else str(m.membership_type),
            "is_active": m.is_active,
            "active_loans": active_loans_cnt,
        })

    # 3. Search Copies & Active Loans
    copies = db.query(BookCopy).options(joinedload(BookCopy.book)).filter(
        or_(
            BookCopy.barcode.ilike(term),
            BookCopy.condition_notes.ilike(term),
            BookCopy.book.has(Book.title.ilike(term)),
        )
    ).limit(limit).all()

    copy_items = []
    for c in copies:
        copy_items.append({
            "id": c.id,
            "barcode": c.barcode,
            "book_id": c.book_id,
            "book_title": c.book.title if c.book else "Unknown",
            "status": c.status.value if hasattr(c.status, 'value') else str(c.status),
            "condition_notes": c.condition_notes,
        })

    total = len(book_items) + len(member_items) + len(copy_items)
    return {
        "query": query_str.strip(),
        "total_results": total,
        "books": book_items,
        "members": member_items,
        "copies": copy_items,
    }


def batch_import_books(db: Session, books_data: List[dict]) -> dict:
    """Batch import multiple books with authors, categories, and optional copies."""
    imported_books = []
    errors = []

    for idx, item in enumerate(books_data, 1):
        try:
            title = (item.get("title") or "").strip()
            if not title:
                errors.append(f"Row {idx}: Book title is required")
                continue

            isbn = (item.get("isbn") or "").strip() or None
            if isbn:
                cleaned_isbn = isbn.replace("-", "").replace(" ", "")
                if len(cleaned_isbn) not in (10, 13):
                    errors.append(f"Row {idx} ('{title}'): Invalid ISBN '{isbn}'")
                    continue
                # Uniqueness check
                if db.query(Book).filter(Book.isbn == isbn).first():
                    errors.append(f"Row {idx} ('{title}'): ISBN '{isbn}' already exists")
                    continue

            # Authors
            authors = []
            author_names = item.get("authors") or item.get("author_names") or []
            if isinstance(author_names, str):
                author_names = [a.strip() for a in author_names.split(",") if a.strip()]
            for aname in author_names:
                auth = db.query(Author).filter(Author.name == aname).first()
                if not auth:
                    auth = Author(name=aname)
                    db.add(auth)
                    db.flush()
                authors.append(auth)

            # Categories
            categories = []
            cat_names = item.get("categories") or item.get("category_names") or []
            if isinstance(cat_names, str):
                cat_names = [c.strip() for c in cat_names.split(",") if c.strip()]
            for cname in cat_names:
                cat = db.query(Category).filter(Category.name == cname).first()
                if not cat:
                    cat = Category(name=cname)
                    db.add(cat)
                    db.flush()
                categories.append(cat)

            pub_year = item.get("published_year")
            if pub_year:
                try:
                    pub_year = int(pub_year)
                except ValueError:
                    pub_year = None

            book = Book(
                title=title,
                isbn=isbn,
                publisher=(item.get("publisher") or "").strip() or None,
                published_year=pub_year,
                description=(item.get("description") or "").strip() or None,
                language=(item.get("language") or "English").strip(),
                cover_image=(item.get("cover_image") or "").strip() or None,
            )
            book.authors = authors
            book.categories = categories
            db.add(book)
            db.flush()

            # Add copies if requested
            initial_copies = item.get("initial_copies") or item.get("copies") or 1
            try:
                initial_copies = max(0, min(int(initial_copies), 50))
            except ValueError:
                initial_copies = 1

            for c_idx in range(1, initial_copies + 1):
                clean_title = "".join(ch for ch in title if ch.isalnum())[:4].upper()
                barcode = f"BC-{clean_title}-{book.id:03d}-{c_idx:02d}"
                while db.query(BookCopy).filter(BookCopy.barcode == barcode).first():
                    barcode += "-X"
                copy = BookCopy(
                    book_id=book.id,
                    barcode=barcode,
                    status=CopyStatus.Available,
                    condition_notes="Imported via batch catalog",
                )
                db.add(copy)

            db.commit()
            db.refresh(book)
            imported_books.append(book)
        except Exception as e:
            db.rollback()
            errors.append(f"Row {idx}: {str(e)}")

    return {
        "success": len(imported_books) > 0 or len(errors) == 0,
        "imported_count": len(imported_books),
        "failed_count": len(errors),
        "errors": errors,
        "books": imported_books,
    }

