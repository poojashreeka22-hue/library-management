"""
Library Management System - SQLAlchemy ORM Models.

All 12 entities with proper relationships, foreign keys, indexes, and constraints.
"""

import enum
from datetime import datetime, date, timedelta

from sqlalchemy import (
    Column, Integer, String, Float, Boolean, Text, DateTime, Date,
    ForeignKey, Table, Enum, UniqueConstraint, Index, event
)
from sqlalchemy.orm import relationship

from app.database import Base


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class UserRole(str, enum.Enum):
    admin = "admin"
    librarian = "librarian"
    readonly = "readonly"


class CopyStatus(str, enum.Enum):
    Available = "Available"
    OnLoan = "On Loan"
    Reserved = "Reserved"
    Lost = "Lost"
    Damaged = "Damaged"
    UnderMaintenance = "Under Maintenance"


class MembershipType(str, enum.Enum):
    standard = "standard"
    premium = "premium"


class ReservationStatus(str, enum.Enum):
    Active = "Active"
    Fulfilled = "Fulfilled"
    Cancelled = "Cancelled"
    Expired = "Expired"


class FineStatus(str, enum.Enum):
    Unpaid = "Unpaid"
    Partial = "Partial"
    Paid = "Paid"
    Waived = "Waived"


class FineType(str, enum.Enum):
    Overdue = "Overdue"
    Lost = "Lost"
    Damaged = "Damaged"


class PaymentMethod(str, enum.Enum):
    Cash = "Cash"
    Card = "Card"
    Online = "Online"


# ---------------------------------------------------------------------------
# Association tables (many-to-many)
# ---------------------------------------------------------------------------

book_authors = Table(
    "book_authors",
    Base.metadata,
    Column("book_id", Integer, ForeignKey("books.id", ondelete="CASCADE"), primary_key=True),
    Column("author_id", Integer, ForeignKey("authors.id", ondelete="CASCADE"), primary_key=True),
)

book_categories = Table(
    "book_categories",
    Base.metadata,
    Column("book_id", Integer, ForeignKey("books.id", ondelete="CASCADE"), primary_key=True),
    Column("category_id", Integer, ForeignKey("categories.id", ondelete="CASCADE"), primary_key=True),
)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(120), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.librarian)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    issued_loans = relationship("Loan", foreign_keys="Loan.issued_by", back_populates="issuing_librarian")
    handled_returns = relationship("Loan", foreign_keys="Loan.returned_to", back_populates="returning_librarian")
    received_payments = relationship("Payment", back_populates="receiver")
    audit_logs = relationship("AuditLog", back_populates="user")


class Author(Base):
    __tablename__ = "authors"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False, index=True)
    biography = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    books = relationship("Book", secondary=book_authors, back_populates="authors")


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    books = relationship("Book", secondary=book_categories, back_populates="categories")


class Book(Base):
    __tablename__ = "books"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False, index=True)
    isbn = Column(String(17), unique=True, nullable=True, index=True)
    publisher = Column(String(200), nullable=True)
    published_year = Column(Integer, nullable=True)
    description = Column(Text, nullable=True)
    language = Column(String(50), default="English")
    page_count = Column(Integer, nullable=True)
    cover_image = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    authors = relationship("Author", secondary=book_authors, back_populates="books")
    categories = relationship("Category", secondary=book_categories, back_populates="books")
    copies = relationship("BookCopy", back_populates="book", cascade="all, delete-orphan")
    reservations = relationship("Reservation", back_populates="book")


class BookCopy(Base):
    __tablename__ = "book_copies"

    id = Column(Integer, primary_key=True, index=True)
    book_id = Column(Integer, ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    barcode = Column(String(50), unique=True, nullable=False, index=True)
    status = Column(Enum(CopyStatus), default=CopyStatus.Available, nullable=False, index=True)
    condition_notes = Column(Text, nullable=True)
    acquired_date = Column(Date, default=date.today)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    book = relationship("Book", back_populates="copies")
    loans = relationship("Loan", back_populates="book_copy")


class Member(Base):
    __tablename__ = "members"

    id = Column(Integer, primary_key=True, index=True)
    member_code = Column(String(20), unique=True, nullable=False, index=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(120), unique=True, nullable=False, index=True)
    phone = Column(String(20), nullable=True)
    address = Column(Text, nullable=True)
    membership_type = Column(Enum(MembershipType), default=MembershipType.standard, nullable=False)
    membership_start = Column(Date, default=date.today, nullable=False)
    membership_expiry = Column(Date, nullable=False)
    max_books = Column(Integer, default=5, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    loans = relationship("Loan", back_populates="member")
    reservations = relationship("Reservation", back_populates="member")
    fines = relationship("Fine", back_populates="member")
    payments = relationship("Payment", back_populates="member")


class Loan(Base):
    __tablename__ = "loans"

    id = Column(Integer, primary_key=True, index=True)
    book_copy_id = Column(Integer, ForeignKey("book_copies.id"), nullable=False, index=True)
    member_id = Column(Integer, ForeignKey("members.id"), nullable=False, index=True)
    issued_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    issue_date = Column(Date, default=date.today, nullable=False)
    due_date = Column(Date, nullable=False)
    return_date = Column(Date, nullable=True)
    returned_to = Column(Integer, ForeignKey("users.id"), nullable=True)
    is_returned = Column(Boolean, default=False, nullable=False, index=True)
    renewal_count = Column(Integer, default=0, nullable=False)
    max_renewals = Column(Integer, default=2, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Constraints
    __table_args__ = (
        Index("ix_loans_active", "book_copy_id", "is_returned"),
        Index("ix_loans_member_active", "member_id", "is_returned"),
    )

    # Relationships
    book_copy = relationship("BookCopy", back_populates="loans")
    member = relationship("Member", back_populates="loans")
    issuing_librarian = relationship("User", foreign_keys=[issued_by], back_populates="issued_loans")
    returning_librarian = relationship("User", foreign_keys=[returned_to], back_populates="handled_returns")
    fine = relationship("Fine", back_populates="loan", uselist=False)


class Reservation(Base):
    __tablename__ = "reservations"

    id = Column(Integer, primary_key=True, index=True)
    book_id = Column(Integer, ForeignKey("books.id"), nullable=False, index=True)
    member_id = Column(Integer, ForeignKey("members.id"), nullable=False, index=True)
    reservation_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    expiry_date = Column(DateTime, nullable=False)
    status = Column(Enum(ReservationStatus), default=ReservationStatus.Active, nullable=False, index=True)
    queue_position = Column(Integer, default=1, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Constraints
    __table_args__ = (
        Index("ix_reservations_active", "book_id", "member_id", "status"),
    )

    # Relationships
    book = relationship("Book", back_populates="reservations")
    member = relationship("Member", back_populates="reservations")


class Fine(Base):
    __tablename__ = "fines"

    id = Column(Integer, primary_key=True, index=True)
    loan_id = Column(Integer, ForeignKey("loans.id"), unique=True, nullable=False)
    member_id = Column(Integer, ForeignKey("members.id"), nullable=False, index=True)
    fine_amount = Column(Float, nullable=False)
    paid_amount = Column(Float, default=0.0, nullable=False)
    status = Column(Enum(FineStatus), default=FineStatus.Unpaid, nullable=False, index=True)
    fine_type = Column(Enum(FineType), default=FineType.Overdue, nullable=False)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    loan = relationship("Loan", back_populates="fine")
    member = relationship("Member", back_populates="fines")
    payments = relationship("Payment", back_populates="fine")


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    fine_id = Column(Integer, ForeignKey("fines.id"), nullable=False, index=True)
    member_id = Column(Integer, ForeignKey("members.id"), nullable=False, index=True)
    amount = Column(Float, nullable=False)
    payment_method = Column(Enum(PaymentMethod), default=PaymentMethod.Cash, nullable=False)
    payment_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    received_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    fine = relationship("Fine", back_populates="payments")
    member = relationship("Member", back_populates="payments")
    receiver = relationship("User", back_populates="received_payments")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(100), nullable=False, index=True)
    entity_type = Column(String(50), nullable=False, index=True)
    entity_id = Column(Integer, nullable=True)
    details = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    user = relationship("User", back_populates="audit_logs")
