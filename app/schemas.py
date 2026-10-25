"""
Library Management System - Pydantic v2 Schemas.

Complete request/response models for all entities with validation.
"""

import re
from datetime import datetime, date
from typing import Optional, List, Any
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, computed_field


# ---------------------------------------------------------------------------
# Enums (mirror SQLAlchemy enums for API)
# ---------------------------------------------------------------------------

class UserRoleEnum(str, Enum):
    admin = "admin"
    librarian = "librarian"
    readonly = "readonly"


class CopyStatusEnum(str, Enum):
    Available = "Available"
    OnLoan = "On Loan"
    Reserved = "Reserved"
    Lost = "Lost"
    Damaged = "Damaged"
    UnderMaintenance = "Under Maintenance"


class MembershipTypeEnum(str, Enum):
    standard = "standard"
    premium = "premium"


class ReservationStatusEnum(str, Enum):
    Active = "Active"
    Fulfilled = "Fulfilled"
    Cancelled = "Cancelled"
    Expired = "Expired"


class FineStatusEnum(str, Enum):
    Unpaid = "Unpaid"
    Partial = "Partial"
    Paid = "Paid"
    Waived = "Waived"


class FineTypeEnum(str, Enum):
    Overdue = "Overdue"
    Lost = "Lost"
    Damaged = "Damaged"


class PaymentMethodEnum(str, Enum):
    Cash = "Cash"
    Card = "Card"
    Online = "Online"


# ---------------------------------------------------------------------------
# Utility schemas
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str
    version: str
    service: str


# Legacy Item schemas preserved for backward compatibility
class ItemBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=100, description="The title of the item")
    description: Optional[str] = Field(None, max_length=300, description="Detailed description")
    price: float = Field(..., gt=0, description="The price must be greater than zero")
    in_stock: bool = Field(default=True, description="Whether the item is currently in stock")


class ItemCreate(ItemBase):
    pass


class ItemUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=300)
    price: Optional[float] = Field(None, gt=0)
    in_stock: Optional[bool] = None


class ItemResponse(ItemBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class MessageResponse(BaseModel):
    message: str
    detail: Optional[str] = None


class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    page: int
    per_page: int
    pages: int


# ---------------------------------------------------------------------------
# Auth schemas
# ---------------------------------------------------------------------------

class TokenData(BaseModel):
    username: str
    role: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1)


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., max_length=120)
    password: str = Field(..., min_length=6)
    full_name: str = Field(..., min_length=1, max_length=100)
    role: UserRoleEnum = UserRoleEnum.librarian

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(pattern, v):
            raise ValueError("Invalid email format")
        return v.lower()


class UserUpdate(BaseModel):
    email: Optional[str] = Field(None, max_length=120)
    full_name: Optional[str] = Field(None, min_length=1, max_length=100)
    role: Optional[UserRoleEnum] = None
    is_active: Optional[bool] = None
    password: Optional[str] = Field(None, min_length=6)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(pattern, v):
            raise ValueError("Invalid email format")
        return v.lower()


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    full_name: str
    role: UserRoleEnum
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Author schemas
# ---------------------------------------------------------------------------

class AuthorCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    biography: Optional[str] = None


class AuthorUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=150)
    biography: Optional[str] = None


class AuthorResponse(BaseModel):
    id: int
    name: str
    biography: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Category schemas
# ---------------------------------------------------------------------------

class CategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None


class CategoryUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None


class CategoryResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Book schemas
# ---------------------------------------------------------------------------

class BookCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    isbn: Optional[str] = Field(None, max_length=17)
    publisher: Optional[str] = Field(None, max_length=200)
    published_year: Optional[int] = Field(None, ge=1000, le=2100)
    description: Optional[str] = None
    language: Optional[str] = Field("English", max_length=50)
    page_count: Optional[int] = Field(None, ge=1)
    cover_image: Optional[str] = Field(None, max_length=500)
    author_ids: List[int] = Field(default_factory=list)
    category_ids: List[int] = Field(default_factory=list)

    @field_validator("isbn")
    @classmethod
    def validate_isbn(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        cleaned = v.replace("-", "").replace(" ", "")
        if len(cleaned) == 10:
            if not re.match(r"^\d{9}[\dXx]$", cleaned):
                raise ValueError("Invalid ISBN-10 format")
        elif len(cleaned) == 13:
            if not re.match(r"^\d{13}$", cleaned):
                raise ValueError("Invalid ISBN-13 format")
        else:
            raise ValueError("ISBN must be 10 or 13 digits")
        return v


class BookUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    isbn: Optional[str] = Field(None, max_length=17)
    publisher: Optional[str] = Field(None, max_length=200)
    published_year: Optional[int] = Field(None, ge=1000, le=2100)
    description: Optional[str] = None
    language: Optional[str] = Field(None, max_length=50)
    page_count: Optional[int] = Field(None, ge=1)
    cover_image: Optional[str] = Field(None, max_length=500)
    is_active: Optional[bool] = None
    author_ids: Optional[List[int]] = None
    category_ids: Optional[List[int]] = None

    @field_validator("isbn")
    @classmethod
    def validate_isbn(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        cleaned = v.replace("-", "").replace(" ", "")
        if len(cleaned) == 10:
            if not re.match(r"^\d{9}[\dXx]$", cleaned):
                raise ValueError("Invalid ISBN-10 format")
        elif len(cleaned) == 13:
            if not re.match(r"^\d{13}$", cleaned):
                raise ValueError("Invalid ISBN-13 format")
        else:
            raise ValueError("ISBN must be 10 or 13 digits")
        return v


class BookResponse(BaseModel):
    id: int
    title: str
    isbn: Optional[str]
    publisher: Optional[str]
    published_year: Optional[int]
    description: Optional[str]
    language: Optional[str]
    page_count: Optional[int]
    cover_image: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]
    authors: List[AuthorResponse] = []
    categories: List[CategoryResponse] = []
    total_copies: int = 0
    available_copies: int = 0

    model_config = ConfigDict(from_attributes=True)


class BatchBookItem(BaseModel):
    title: str = Field(..., min_length=1)
    isbn: Optional[str] = None
    publisher: Optional[str] = None
    published_year: Optional[int] = None
    language: Optional[str] = "English"
    author_names: Optional[List[str]] = Field(default_factory=list)
    category_names: Optional[List[str]] = Field(default_factory=list)
    initial_copies: Optional[int] = 1


class BatchImportResponse(BaseModel):
    success: bool
    imported_count: int
    failed_count: int
    errors: List[str] = []
    books: List[BookResponse] = []


class UploadedFileInfo(BaseModel):
    original_name: str
    filename: str
    url: str
    size: int
    content_type: str


class FileUploadResponse(BaseModel):
    uploaded: List[UploadedFileInfo]


class BookListResponse(BaseModel):
    id: int
    title: str
    isbn: Optional[str]
    publisher: Optional[str]
    is_active: bool
    author_names: str = ""
    category_names: str = ""
    total_copies: int = 0
    available_copies: int = 0

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# BookCopy schemas
# ---------------------------------------------------------------------------

class BookCopyCreate(BaseModel):
    book_id: int
    barcode: str = Field(..., min_length=1, max_length=50)
    condition_notes: Optional[str] = None
    acquired_date: Optional[date] = None


class BookCopyUpdate(BaseModel):
    status: Optional[CopyStatusEnum] = None
    condition_notes: Optional[str] = None


class BookCopyResponse(BaseModel):
    id: int
    book_id: int
    barcode: str
    status: CopyStatusEnum
    condition_notes: Optional[str]
    acquired_date: Optional[date]
    created_at: datetime
    book_title: str = ""

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Member schemas
# ---------------------------------------------------------------------------

class MemberCreate(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    email: str = Field(..., max_length=120)
    phone: Optional[str] = Field(None, max_length=20)
    address: Optional[str] = None
    membership_type: MembershipTypeEnum = MembershipTypeEnum.standard
    max_books: int = Field(5, ge=1, le=50)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(pattern, v):
            raise ValueError("Invalid email format")
        return v.lower()


class MemberUpdate(BaseModel):
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    email: Optional[str] = Field(None, max_length=120)
    phone: Optional[str] = Field(None, max_length=20)
    address: Optional[str] = None
    membership_type: Optional[MembershipTypeEnum] = None
    max_books: Optional[int] = Field(None, ge=1, le=50)
    is_active: Optional[bool] = None
    membership_expiry: Optional[date] = None

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(pattern, v):
            raise ValueError("Invalid email format")
        return v.lower()


class MemberResponse(BaseModel):
    id: int
    member_code: str
    first_name: str
    last_name: str
    email: str
    phone: Optional[str]
    address: Optional[str]
    membership_type: MembershipTypeEnum
    membership_start: date
    membership_expiry: date
    max_books: int
    is_active: bool
    active_loans: int = 0
    outstanding_fines: float = 0.0
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Loan schemas
# ---------------------------------------------------------------------------

class LoanCreate(BaseModel):
    book_copy_id: int
    member_id: int
    due_date: Optional[date] = None


class LoanResponse(BaseModel):
    id: int
    book_copy_id: int
    member_id: int
    issued_by: int
    issue_date: date
    due_date: date
    return_date: Optional[date]
    is_returned: bool
    renewal_count: int
    max_renewals: int
    created_at: datetime
    member_name: str = ""
    book_title: str = ""
    barcode: str = ""
    issuer_name: str = ""

    model_config = ConfigDict(from_attributes=True)


class LoanRenewRequest(BaseModel):
    loan_id: int


# ---------------------------------------------------------------------------
# Return schemas
# ---------------------------------------------------------------------------

class ReturnCreate(BaseModel):
    loan_id: int
    condition_notes: Optional[str] = None
    copy_status: CopyStatusEnum = CopyStatusEnum.Available


class ReturnResponse(BaseModel):
    loan_id: int
    member_name: str
    book_title: str
    barcode: str
    issue_date: date
    due_date: date
    return_date: date
    overdue_days: int = 0
    fine_amount: float = 0.0
    message: str = ""

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Reservation schemas
# ---------------------------------------------------------------------------

class ReservationCreate(BaseModel):
    book_id: int
    member_id: int


class ReservationResponse(BaseModel):
    id: int
    book_id: int
    member_id: int
    reservation_date: datetime
    expiry_date: datetime
    status: ReservationStatusEnum
    queue_position: int
    created_at: datetime
    book_title: str = ""
    member_name: str = ""

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Fine schemas
# ---------------------------------------------------------------------------

class FineResponse(BaseModel):
    id: int
    loan_id: int
    member_id: int
    fine_amount: float
    paid_amount: float
    status: FineStatusEnum
    fine_type: FineTypeEnum
    reason: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]
    member_name: str = ""
    book_title: str = ""
    remaining: float = 0.0

    model_config = ConfigDict(from_attributes=True)


class FineWaiveRequest(BaseModel):
    reason: str = Field(..., min_length=1)


# ---------------------------------------------------------------------------
# Payment schemas
# ---------------------------------------------------------------------------

class PaymentCreate(BaseModel):
    fine_id: int
    amount: float = Field(..., gt=0)
    payment_method: PaymentMethodEnum = PaymentMethodEnum.Cash
    notes: Optional[str] = None


class PaymentResponse(BaseModel):
    id: int
    fine_id: int
    member_id: int
    amount: float
    payment_method: PaymentMethodEnum
    payment_date: datetime
    received_by: int
    notes: Optional[str]
    created_at: datetime
    receiver_name: str = ""

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# AuditLog schemas
# ---------------------------------------------------------------------------

class AuditLogResponse(BaseModel):
    id: int
    user_id: Optional[int]
    action: str
    entity_type: str
    entity_id: Optional[int]
    details: Optional[str]
    ip_address: Optional[str]
    created_at: datetime
    user_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Dashboard schemas
# ---------------------------------------------------------------------------

class DashboardStats(BaseModel):
    total_books: int = 0
    total_copies: int = 0
    available_copies: int = 0
    active_members: int = 0
    active_loans: int = 0
    overdue_loans: int = 0
    outstanding_fines: float = 0.0
    total_fines_collected: float = 0.0


class RecentBookSummary(BaseModel):
    id: int
    title: str
    author: str
    category: str
    copies: int
    status: str


class ActiveLoanSummary(BaseModel):
    member_name: str
    book_title: str
    issue_date: date
    due_date: date
    status: str


class OverdueBookSummary(BaseModel):
    member_name: str
    book_title: str
    days_overdue: int
    fine_amount: float


class DashboardResponse(BaseModel):
    stats: DashboardStats
    recent_books: List[RecentBookSummary] = []
    active_loans: List[ActiveLoanSummary] = []
    overdue_books: List[OverdueBookSummary] = []


# ---------------------------------------------------------------------------
# Unified Search schemas
# ---------------------------------------------------------------------------

class SearchBookItem(BaseModel):
    id: int
    title: str
    isbn: Optional[str] = None
    authors: str = ""
    categories: str = ""
    available_copies: int = 0
    total_copies: int = 0
    status: str = "Available"


class SearchMemberItem(BaseModel):
    id: int
    member_code: str
    name: str
    email: str
    phone: Optional[str] = None
    membership_type: str = "standard"
    is_active: bool = True
    active_loans: int = 0


class SearchCopyItem(BaseModel):
    id: int
    barcode: str
    book_id: int
    book_title: str
    status: str
    condition_notes: Optional[str] = None


class UnifiedSearchResponse(BaseModel):
    query: str
    total_results: int
    books: List[SearchBookItem] = []
    members: List[SearchMemberItem] = []
    copies: List[SearchCopyItem] = []

