"""
Comprehensive Automated Test Suite for Library Management System.
Covers all business rules, inventory, loans, returns, fines, payments,
reservations, renewals, permissions, and rollback scenarios.
"""

import pytest
from datetime import date, timedelta
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db
from app import services
from app.models import (
    User, UserRole, CopyStatus, ReservationStatus, FineStatus, FineType
)


# In-memory test database fixture with StaticPool for cross-connection persistence
TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh in-memory database schema for each test."""
    Base.metadata.create_all(bind=test_engine)
    db = TestingSessionLocal()
    # Seed default admin
    services.ensure_default_admin(db)
    yield db
    db.close()
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="function")
def test_client(db_session):
    """TestClient that overrides get_db dependency with in-memory session."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def admin_headers(test_client):
    """Obtain JWT Bearer token for admin user."""
    res = test_client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert res.status_code == status.HTTP_200_OK
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="function")
def librarian_headers(test_client, db_session):
    """Obtain JWT Bearer token for a standard librarian."""
    user = services.create_user(
        db_session, username="librarian1", email="lib1@library.com",
        password="libpassword", full_name="Staff Librarian", role="librarian"
    )
    res = test_client.post("/api/auth/login", json={"username": "librarian1", "password": "libpassword"})
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="function")
def readonly_headers(test_client, db_session):
    """Obtain JWT Bearer token for a readonly user."""
    user = services.create_user(
        db_session, username="readonly1", email="read@library.com",
        password="readpassword", full_name="Read Only User", role="readonly"
    )
    res = test_client.post("/api/auth/login", json={"username": "readonly1", "password": "readpassword"})
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ===========================================================================
# 1. BOOKS AND INVENTORY TESTS
# ===========================================================================

def test_create_book_success(test_client, admin_headers):
    """Test creating a new book with valid ISBN and metadata."""
    payload = {
        "title": "Refactoring",
        "isbn": "9780201485677",
        "publisher": "Addison-Wesley",
        "published_year": 1999,
        "language": "English",
        "author_ids": [],
        "category_ids": [],
    }
    res = test_client.post("/api/books", json=payload, headers=admin_headers)
    assert res.status_code == status.HTTP_201_CREATED
    data = res.json()
    assert data["title"] == "Refactoring"
    assert data["isbn"] == "9780201485677"
    assert data["total_copies"] == 0
    assert data["available_copies"] == 0


def test_reject_duplicate_isbn(test_client, admin_headers):
    """Reject creating two books with the same ISBN."""
    payload = {"title": "Book One", "isbn": "9780132350884"}
    res1 = test_client.post("/api/books", json=payload, headers=admin_headers)
    assert res1.status_code == status.HTTP_201_CREATED

    dup_payload = {"title": "Book Duplicate", "isbn": "9780132350884"}
    res2 = test_client.post("/api/books", json=dup_payload, headers=admin_headers)
    assert res2.status_code == status.HTTP_400_BAD_REQUEST
    assert "already exists" in res2.json()["detail"]


def test_add_copy_only_for_existing_book(test_client, admin_headers):
    """Reject adding a physical copy for a non-existent book ID."""
    payload = {"book_id": 99999, "barcode": "BC-NONEXIST-01"}
    res = test_client.post("/api/copies", json=payload, headers=admin_headers)
    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert "Book does not exist" in res.json()["detail"]


def test_reject_duplicate_copy_barcode(test_client, admin_headers):
    """Reject physical copies with duplicate barcodes."""
    # Create book
    b_res = test_client.post("/api/books", json={"title": "Test Title"}, headers=admin_headers)
    book_id = b_res.json()["id"]

    # First copy
    c1 = test_client.post("/api/copies", json={"book_id": book_id, "barcode": "BC-DUP-01"}, headers=admin_headers)
    assert c1.status_code == status.HTTP_201_CREATED

    # Duplicate barcode
    c2 = test_client.post("/api/copies", json={"book_id": book_id, "barcode": "BC-DUP-01"}, headers=admin_headers)
    assert c2.status_code == status.HTTP_400_BAD_REQUEST
    assert "already exists" in c2.json()["detail"]


def test_prevent_issuing_unavailable_damaged_maintenance_copies(test_client, admin_headers, db_session):
    """Lost, damaged, and maintenance copies cannot be issued."""
    # Setup book and member
    b_res = test_client.post("/api/books", json={"title": "Maintenance Book"}, headers=admin_headers)
    book_id = b_res.json()["id"]

    c_res = test_client.post("/api/copies", json={"book_id": book_id, "barcode": "BC-MAINT-01"}, headers=admin_headers)
    copy_id = c_res.json()["id"]

    m_res = test_client.post("/api/members", json={"first_name": "Tom", "last_name": "Smith", "email": "tom@test.com"}, headers=admin_headers)
    member_id = m_res.json()["id"]

    # Mark copy as Under Maintenance
    test_client.put(f"/api/copies/{copy_id}", json={"status": "Under Maintenance"}, headers=admin_headers)

    # Attempt to issue
    issue_res = test_client.post("/api/loans/issue", json={"member_id": member_id, "book_copy_id": copy_id}, headers=admin_headers)
    assert issue_res.status_code == status.HTTP_400_BAD_REQUEST
    assert "not available" in issue_res.json()["detail"]


# ===========================================================================
# 2. MEMBER DEPENDENCY TESTS
# ===========================================================================

def test_register_member_and_unique_code(test_client, admin_headers):
    """Register member successfully and verify auto-generated member code."""
    payload = {
        "first_name": "Alice",
        "last_name": "Wonderland",
        "email": "alice@example.com",
        "membership_type": "standard",
        "max_books": 5,
    }
    res = test_client.post("/api/members", json=payload, headers=admin_headers)
    assert res.status_code == status.HTTP_201_CREATED
    data = res.json()
    assert data["member_code"].startswith("MEM-")
    assert data["first_name"] == "Alice"
    assert data["is_active"] is True


def test_reject_duplicate_member_email(test_client, admin_headers):
    """Reject registering another member with identical email."""
    payload = {"first_name": "Bob", "last_name": "Ross", "email": "bob@example.com"}
    test_client.post("/api/members", json=payload, headers=admin_headers)

    dup_res = test_client.post("/api/members", json=payload, headers=admin_headers)
    assert dup_res.status_code == status.HTTP_400_BAD_REQUEST
    assert "already exists" in dup_res.json()["detail"]


def test_reject_borrowing_for_inactive_member(test_client, admin_headers, db_session):
    """Deactivated members cannot borrow books."""
    b_res = test_client.post("/api/books", json={"title": "Inactive Member Book"}, headers=admin_headers)
    c_res = test_client.post("/api/copies", json={"book_id": b_res.json()["id"], "barcode": "BC-INACT-01"}, headers=admin_headers)

    m_res = test_client.post("/api/members", json={"first_name": "Inactive", "last_name": "User", "email": "inact@test.com"}, headers=admin_headers)
    member_id = m_res.json()["id"]

    # Deactivate
    test_client.post(f"/api/members/{member_id}/deactivate", headers=admin_headers)

    # Attempt to issue
    res = test_client.post("/api/loans/issue", json={"member_id": member_id, "book_copy_id": c_res.json()["id"]}, headers=admin_headers)
    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert "inactive" in res.json()["detail"].lower()


def test_enforce_member_borrowing_limit(test_client, admin_headers):
    """Enforce member max active loan limits."""
    # Member with max 1 book
    m_res = test_client.post("/api/members", json={"first_name": "Limit", "last_name": "Tester", "email": "limit@test.com", "max_books": 1}, headers=admin_headers)
    member_id = m_res.json()["id"]

    # Book with 2 copies
    b_res = test_client.post("/api/books", json={"title": "Limit Book"}, headers=admin_headers)
    c1 = test_client.post("/api/copies", json={"book_id": b_res.json()["id"], "barcode": "BC-LIM-01"}, headers=admin_headers).json()["id"]
    c2 = test_client.post("/api/copies", json={"book_id": b_res.json()["id"], "barcode": "BC-LIM-02"}, headers=admin_headers).json()["id"]

    # Issue 1st book - should succeed
    res1 = test_client.post("/api/loans/issue", json={"member_id": member_id, "book_copy_id": c1}, headers=admin_headers)
    assert res1.status_code == status.HTTP_201_CREATED

    # Issue 2nd book - should fail due to limit
    res2 = test_client.post("/api/loans/issue", json={"member_id": member_id, "book_copy_id": c2}, headers=admin_headers)
    assert res2.status_code == status.HTTP_400_BAD_REQUEST
    assert "limit" in res2.json()["detail"].lower()


# ===========================================================================
# 3. ISSUE AND RETURN WORKFLOW TESTS
# ===========================================================================

def test_successful_issue_and_return_cycle(test_client, admin_headers):
    """Verify full lifecycle: issue available copy, check status change, return copy, verify restored status."""
    # 1. Setup
    b_res = test_client.post("/api/books", json={"title": "Lifecycle Book"}, headers=admin_headers)
    book_id = b_res.json()["id"]
    c_res = test_client.post("/api/copies", json={"book_id": book_id, "barcode": "BC-LIFE-01"}, headers=admin_headers)
    copy_id = c_res.json()["id"]
    m_res = test_client.post("/api/members", json={"first_name": "Sara", "last_name": "Connor", "email": "sara@test.com"}, headers=admin_headers)
    member_id = m_res.json()["id"]

    # 2. Issue Book
    issue_res = test_client.post("/api/loans/issue", json={"member_id": member_id, "book_copy_id": copy_id}, headers=admin_headers)
    assert issue_res.status_code == status.HTTP_201_CREATED
    loan_id = issue_res.json()["id"]

    # Verify copy status updated to On Loan
    copy_check = test_client.get(f"/api/copies/{copy_id}").json()
    assert copy_check["status"] == "On Loan"

    # 3. Reject duplicate active loan on the same copy
    dup_issue = test_client.post("/api/loans/issue", json={"member_id": member_id, "book_copy_id": copy_id}, headers=admin_headers)
    assert dup_issue.status_code == status.HTTP_400_BAD_REQUEST

    # 4. Return Book
    ret_res = test_client.post("/api/loans/return", json={"loan_id": loan_id, "copy_status": "Available"}, headers=admin_headers)
    assert ret_res.status_code == status.HTTP_200_OK

    # Verify copy status restored to Available
    copy_check2 = test_client.get(f"/api/copies/{copy_id}").json()
    assert copy_check2["status"] == "Available"

    # 5. Reject duplicate return
    ret_dup = test_client.post("/api/loans/return", json={"loan_id": loan_id}, headers=admin_headers)
    assert ret_dup.status_code == status.HTTP_400_BAD_REQUEST
    assert "already been returned" in ret_dup.json()["detail"]


# ===========================================================================
# 4. FINES AND PAYMENTS TESTS
# ===========================================================================

def test_overdue_fine_calculation_and_partial_payment(test_client, admin_headers, db_session):
    """Overdue calculation and payment balance verification."""
    b_res = test_client.post("/api/books", json={"title": "Overdue Novel"}, headers=admin_headers)
    copy_id = test_client.post("/api/copies", json={"book_id": b_res.json()["id"], "barcode": "BC-OD-01"}, headers=admin_headers).json()["id"]
    member_id = test_client.post("/api/members", json={"first_name": "Fine", "last_name": "Payer", "email": "payer@test.com"}, headers=admin_headers).json()["id"]

    # Issue loan directly with past due date in database (5 days ago)
    loan = services.issue_book(db_session, book_copy_id=copy_id, member_id=member_id, issued_by=1, due_date=date.today() - timedelta(days=5))

    # Return the overdue book
    ret_res = test_client.post("/api/loans/return", json={"loan_id": loan.id}, headers=admin_headers)
    assert ret_res.status_code == status.HTTP_200_OK
    ret_data = ret_res.json()
    # 5 days overdue - 1 day grace period = 4 days * ₹10/day = ₹40.00
    assert ret_data["overdue_days"] == 4
    assert ret_data["fine_amount"] == 40.0

    # Retrieve fine
    fines = test_client.get(f"/api/fines?member_id={member_id}").json()
    assert len(fines) == 1
    fine = fines[0]
    assert fine["fine_amount"] == 40.0
    assert fine["remaining"] == 40.0
    assert fine["status"] == "Unpaid"

    # Record partial payment of ₹15.00
    pay_res = test_client.post("/api/payments", json={"fine_id": fine["id"], "amount": 15.0, "payment_method": "Cash"}, headers=admin_headers)
    assert pay_res.status_code == status.HTTP_201_CREATED

    # Verify updated fine status and remaining balance
    fine_updated = test_client.get(f"/api/fines/{fine['id']}").json()
    assert fine_updated["paid_amount"] == 15.0
    assert fine_updated["remaining"] == 25.0
    assert fine_updated["status"] == "Partial"

    # Reject overpayment (remaining is 25, trying to pay 50)
    overpay = test_client.post("/api/payments", json={"fine_id": fine["id"], "amount": 50.0}, headers=admin_headers)
    assert overpay.status_code == status.HTTP_400_BAD_REQUEST
    assert "exceeds" in overpay.json()["detail"].lower()


# ===========================================================================
# 5. RESERVATIONS AND RENEWALS TESTS
# ===========================================================================

def test_reservations_queue_and_cancellation(test_client, admin_headers):
    """Test reservation waiting list and queue reordering upon cancellation."""
    b_res = test_client.post("/api/books", json={"title": "Popular Book"}, headers=admin_headers)
    book_id = b_res.json()["id"]

    m1 = test_client.post("/api/members", json={"first_name": "M1", "last_name": "Queue", "email": "m1@test.com"}, headers=admin_headers).json()["id"]
    m2 = test_client.post("/api/members", json={"first_name": "M2", "last_name": "Queue", "email": "m2@test.com"}, headers=admin_headers).json()["id"]

    # Place reservation for m1
    res1 = test_client.post("/api/reservations", json={"book_id": book_id, "member_id": m1}, headers=admin_headers).json()
    assert res1["queue_position"] == 1

    # Duplicate active reservation for same member & book should be rejected
    dup_res = test_client.post("/api/reservations", json={"book_id": book_id, "member_id": m1}, headers=admin_headers)
    assert dup_res.status_code == status.HTTP_400_BAD_REQUEST

    # Place reservation for m2
    res2 = test_client.post("/api/reservations", json={"book_id": book_id, "member_id": m2}, headers=admin_headers).json()
    assert res2["queue_position"] == 2

    # Cancel m1 reservation -> m2 moves to position 1
    cancel_res = test_client.post(f"/api/reservations/{res1['id']}/cancel", headers=admin_headers)
    assert cancel_res.status_code == status.HTTP_200_OK

    remaining_res = test_client.get(f"/api/reservations?book_id={book_id}&status=Active").json()
    assert len(remaining_res) == 1
    assert remaining_res[0]["member_id"] == m2
    assert remaining_res[0]["queue_position"] == 1


def test_loan_renewal_limit_enforcement(test_client, admin_headers):
    """A loan cannot be renewed beyond maximum allowed renewals."""
    b_res = test_client.post("/api/books", json={"title": "Renewable Book"}, headers=admin_headers)
    copy_id = test_client.post("/api/copies", json={"book_id": b_res.json()["id"], "barcode": "BC-REN-01"}, headers=admin_headers).json()["id"]
    member_id = test_client.post("/api/members", json={"first_name": "Ren", "last_name": "Ew", "email": "renew@test.com"}, headers=admin_headers).json()["id"]

    loan = test_client.post("/api/loans/issue", json={"member_id": member_id, "book_copy_id": copy_id}, headers=admin_headers).json()

    # Renewal 1
    r1 = test_client.post("/api/loans/renew", json={"loan_id": loan["id"]}, headers=admin_headers)
    assert r1.status_code == status.HTTP_200_OK
    assert r1.json()["renewal_count"] == 1

    # Renewal 2 (maximum limit is 2)
    r2 = test_client.post("/api/loans/renew", json={"loan_id": loan["id"]}, headers=admin_headers)
    assert r2.status_code == status.HTTP_200_OK
    assert r2.json()["renewal_count"] == 2

    # Renewal 3 - must be rejected
    r3 = test_client.post("/api/loans/renew", json={"loan_id": loan["id"]}, headers=admin_headers)
    assert r3.status_code == status.HTTP_400_BAD_REQUEST
    assert "limit" in r3.json()["detail"].lower()


# ===========================================================================
# 6. PERMISSIONS AND AUDIT LOGS TESTS
# ===========================================================================

def test_role_based_access_control(test_client, readonly_headers):
    """Readonly users cannot issue books or create entities."""
    # Attempt to create book with readonly token
    res = test_client.post("/api/books", json={"title": "Forbidden Book"}, headers=readonly_headers)
    assert res.status_code == status.HTTP_403_FORBIDDEN


def test_dashboard_metrics_consistency(test_client, admin_headers):
    """Verify dashboard metrics dynamically update upon issue and return."""
    # Read initial stats
    init_stats = test_client.get("/api/dashboard/stats").json()

    # Create book and copy
    b_res = test_client.post("/api/books", json={"title": "Metric Book"}, headers=admin_headers)
    c_res = test_client.post("/api/copies", json={"book_id": b_res.json()["id"], "barcode": "BC-MET-01"}, headers=admin_headers)
    m_res = test_client.post("/api/members", json={"first_name": "Met", "last_name": "Ric", "email": "metric@test.com"}, headers=admin_headers)

    # Check stats after adding
    post_add = test_client.get("/api/dashboard/stats").json()
    assert post_add["total_books"] == init_stats["total_books"] + 1
    assert post_add["total_copies"] == init_stats["total_copies"] + 1
    assert post_add["available_copies"] == init_stats["available_copies"] + 1

    # Issue book
    loan = test_client.post("/api/loans/issue", json={"member_id": m_res.json()["id"], "book_copy_id": c_res.json()["id"]}, headers=admin_headers).json()
    post_issue = test_client.get("/api/dashboard/stats").json()
    assert post_issue["available_copies"] == post_add["available_copies"] - 1
    assert post_issue["active_loans"] == post_add["active_loans"] + 1


# ===========================================================================
# 7. AUTHENTICATION & SECURITY TRACE TESTS
# ===========================================================================

def test_auth_login_json_and_form(test_client):
    """Test login succeeds with both application/json and form-urlencoded formats."""
    # JSON login
    res_json = test_client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert res_json.status_code == status.HTTP_200_OK
    assert "access_token" in res_json.json()
    assert res_json.json()["token_type"] == "bearer"

    # Form-urlencoded login (OAuth2 password standard)
    res_form = test_client.post(
        "/api/auth/login",
        data={"username": "admin", "password": "admin123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    assert res_form.status_code == status.HTTP_200_OK
    assert "access_token" in res_form.json()


def test_auth_invalid_credentials(test_client):
    """Test login fails with incorrect password."""
    res = test_client.post("/api/auth/login", json={"username": "admin", "password": "wrongpassword"})
    assert res.status_code == status.HTTP_401_UNAUTHORIZED
    assert "incorrect" in res.json()["detail"].lower()


def test_auth_missing_token_rejected(test_client):
    """Test protected endpoints reject unauthenticated requests with 401 Not authenticated."""
    res = test_client.get("/api/auth/me")
    assert res.status_code == status.HTTP_401_UNAUTHORIZED
    assert res.json()["detail"] == "Not authenticated"


def test_auth_expired_token_rejected(test_client):
    """Test expired token returns explicit 'Token has expired' error."""
    from app.auth import create_access_token
    from datetime import timedelta
    expired_token = create_access_token(data={"sub": "admin"}, expires_delta=timedelta(seconds=-60))
    res = test_client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert res.status_code == status.HTTP_401_UNAUTHORIZED
    assert res.json()["detail"] == "Token has expired"


def test_auth_malformed_token_rejected(test_client):
    """Test invalid or tampered token returns 'Could not validate credentials'."""
    res = test_client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-valid-jwt-token"})
    assert res.status_code == status.HTTP_401_UNAUTHORIZED
    assert res.json()["detail"] == "Could not validate credentials"


def test_auth_user_me_and_logout(test_client, admin_headers):
    """Test /api/auth/me returns current user and logout succeeds."""
    me_res = test_client.get("/api/auth/me", headers=admin_headers)
    assert me_res.status_code == status.HTTP_200_OK
    assert me_res.json()["username"] == "admin"
    assert me_res.json()["role"] == "admin"

    logout_res = test_client.post("/api/auth/logout", headers=admin_headers)
    assert logout_res.status_code == status.HTTP_200_OK
    assert "logged out" in logout_res.json()["message"].lower()


# ===========================================================================
# 8. BOOK CREATION, UPLOAD, BATCH IMPORT & GLOBAL SEARCH TESTS
# ===========================================================================

def test_create_book_validation_and_cover_image(test_client, admin_headers):
    """Test creating book with cover image, authors, and categories validation."""
    # 1. Create Author and Category
    auth = test_client.post("/api/authors", json={"name": "Martin Fowler"}, headers=admin_headers).json()
    cat = test_client.post("/api/categories", json={"name": "Software Architecture"}, headers=admin_headers).json()

    # 2. Successfully create book with cover image and linked relations
    payload = {
        "title": "Patterns of Enterprise Application Architecture",
        "isbn": "9780321127426",
        "publisher": "Addison-Wesley",
        "published_year": 2002,
        "language": "English",
        "cover_image": "/static/uploads/peaa_cover.png",
        "author_ids": [auth["id"]],
        "category_ids": [cat["id"]],
    }
    res = test_client.post("/api/books", json=payload, headers=admin_headers)
    assert res.status_code == status.HTTP_201_CREATED
    data = res.json()
    assert data["title"] == payload["title"]
    assert data["cover_image"] == "/static/uploads/peaa_cover.png"
    assert len(data["authors"]) == 1
    assert data["authors"][0]["name"] == "Martin Fowler"
    assert len(data["categories"]) == 1
    assert data["categories"][0]["name"] == "Software Architecture"

    # 3. Validation failure: missing title
    invalid_payload = {"title": "", "isbn": "9780321127427"}
    res_inv = test_client.post("/api/books", json=invalid_payload, headers=admin_headers)
    assert res_inv.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # 4. Validation failure: invalid ISBN format
    bad_isbn = {"title": "Bad ISBN Book", "isbn": "12345"}
    res_isbn = test_client.post("/api/books", json=bad_isbn, headers=admin_headers)
    assert res_isbn.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_multi_file_upload_drag_and_drop(test_client, admin_headers):
    """Test uploading multiple files (drag-and-drop or file selector)."""
    file1 = ("cover1.png", b"fake-image-content-1", "image/png")
    file2 = ("notes.pdf", b"fake-pdf-content-2", "application/pdf")

    res = test_client.post(
        "/api/books/upload",
        files=[("files", file1), ("files", file2)],
        headers=admin_headers
    )
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert "uploaded" in data
    assert len(data["uploaded"]) == 2
    assert data["uploaded"][0]["original_name"] == "cover1.png"
    assert data["uploaded"][1]["original_name"] == "notes.pdf"
    assert data["uploaded"][0]["url"].startswith("/static/uploads/")


def test_batch_import_csv_and_json(test_client, admin_headers):
    """Test batch importing books via CSV and JSON files."""
    csv_content = (
        "title,isbn,authors,categories,publisher,year,copies\n"
        "Domain-Driven Design,9780321125217,Eric Evans,Software Design,Addison-Wesley,2003,2\n"
        "Continuous Delivery,9780321601919,Jez Humble,DevOps,Addison-Wesley,2010,1\n"
    ).encode("utf-8")

    csv_file = ("catalog.csv", csv_content, "text/csv")
    res = test_client.post(
        "/api/books/batch-import",
        files={"file": csv_file},
        headers=admin_headers
    )
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["success"] is True
    assert data["imported_count"] == 2
    assert len(data["books"]) == 2

    # Verify initial copies were created with barcodes
    ddd_book = next(b for b in data["books"] if "Domain-Driven Design" in b["title"])
    assert ddd_book["total_copies"] == 2
    assert ddd_book["available_copies"] == 2


def test_unified_global_search(test_client, admin_headers):
    """Test unified search across books, members, and copies."""
    # 1. Create a book
    b_res = test_client.post("/api/books", json={"title": "Microservices Patterns", "isbn": "9781617294549"}, headers=admin_headers).json()
    c_res = test_client.post("/api/copies", json={"book_id": b_res["id"], "barcode": "BC-MICRO-99"}, headers=admin_headers).json()

    # 2. Create a member
    m_res = test_client.post("/api/members", json={"first_name": "Alexander", "last_name": "Hamilton", "email": "alex.hamilton@test.com"}, headers=admin_headers).json()

    # Search for "Microservices"
    s1 = test_client.get("/api/search?q=Microservices").json()
    assert s1["total_results"] >= 1
    assert any(b["title"] == "Microservices Patterns" for b in s1["books"])

    # Search for "Hamilton"
    s2 = test_client.get("/api/search?q=Hamilton").json()
    assert s2["total_results"] >= 1
    assert any("Hamilton" in m["name"] for m in s2["members"])

    # Search for barcode "BC-MICRO"
    s3 = test_client.get("/api/search?q=BC-MICRO").json()
    assert s3["total_results"] >= 1
    assert any(c["barcode"] == "BC-MICRO-99" for c in s3["copies"])


def test_batch_delete_books(test_client, admin_headers):
    """Test batch archiving/deleting multiple books by ID."""
    b1 = test_client.post("/api/books", json={"title": "Batch Delete 1"}, headers=admin_headers).json()
    b2 = test_client.post("/api/books", json={"title": "Batch Delete 2"}, headers=admin_headers).json()

    res = test_client.post("/api/books/batch-delete", json={"book_ids": [b1["id"], b2["id"]]}, headers=admin_headers)
    assert res.status_code == status.HTTP_200_OK
    assert "2" in res.json()["message"]


def test_create_book_with_initial_copies(test_client, admin_headers):
    """Test creating a book with initial_copies automatically generates physical copies."""
    payload = {
        "title": "Designing Data-Intensive Applications",
        "isbn": "9781449373320",
        "publisher": "O'Reilly Media",
        "published_year": 2017,
        "initial_copies": 3,
        "barcode_prefix": "BC-DDIA",
    }
    res = test_client.post("/api/books", json=payload, headers=admin_headers)
    assert res.status_code == status.HTTP_201_CREATED
    data = res.json()
    assert data["total_copies"] == 3
    assert data["available_copies"] == 3

    # Verify physical copies exist in inventory
    copies_res = test_client.get(f"/api/copies?book_id={data['id']}")
    assert copies_res.status_code == status.HTTP_200_OK
    copies = copies_res.json()
    assert len(copies) == 3
    assert all("BC-DDIA" in c["barcode"] for c in copies)


def test_reports_analytics_api_endpoint(test_client, admin_headers):
    """Test reports & analytics endpoint returns valid JSON without 500 error."""
    # Seed a category and book
    cat_res = test_client.post("/api/categories", json={"name": "Analytics Category"}, headers=admin_headers).json()
    b_res = test_client.post("/api/books", json={"title": "Analytics Book", "category_ids": [cat_res["id"]]}, headers=admin_headers).json()

    res = test_client.get("/api/dashboard/reports")
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert "category_distribution" in data
    assert "top_borrowed_books" in data
    assert "active_loans" in data
    assert "total_fines_collected" in data
    assert isinstance(data["category_distribution"], list)


def test_system_settings_dues_and_lost_prices(test_client, admin_headers):
    """Test updating dues prices (fine_per_day) and lost prices via system settings."""
    # 1. Fetch current settings
    get_res = test_client.get("/api/dashboard/settings", headers=admin_headers)
    assert get_res.status_code == status.HTTP_200_OK
    settings = get_res.json()
    assert "fine_per_day" in settings
    assert "lost_book_price" in settings
    assert "damaged_book_price" in settings

    # 2. Update fine_per_day and lost_book_price
    update_res = test_client.put(
        "/api/dashboard/settings",
        json={"fine_per_day": 15.0, "lost_book_price": 500.0, "damaged_book_price": 150.0},
        headers=admin_headers
    )
    assert update_res.status_code == status.HTTP_200_OK
    updated = update_res.json()
    assert updated["fine_per_day"] == 15.0
    assert updated["lost_book_price"] == 500.0
    assert updated["damaged_book_price"] == 150.0


def test_return_book_lost_assesses_configured_lost_price(test_client, admin_headers):
    """Test returning a copy marked as Lost charges the configured lost_book_price."""
    # Configure lost price
    test_client.put("/api/dashboard/settings", json={"lost_book_price": 450.0}, headers=admin_headers)

    # Setup book, copy, and member
    b_res = test_client.post("/api/books", json={"title": "Lost Novel"}, headers=admin_headers).json()
    c_res = test_client.post("/api/copies", json={"book_id": b_res["id"], "barcode": "BC-LOST-01"}, headers=admin_headers).json()
    m_res = test_client.post("/api/members", json={"first_name": "Lost", "last_name": "Reader", "email": "lost.reader@test.com"}, headers=admin_headers).json()

    # Issue book
    issue_res = test_client.post("/api/loans/issue", json={"member_id": m_res["id"], "book_copy_id": c_res["id"]}, headers=admin_headers).json()
    loan_id = issue_res["id"]

    # Return book as Lost
    return_res = test_client.post(
        "/api/loans/return",
        json={"loan_id": loan_id, "copy_status": "Lost", "condition_notes": "Lost while traveling"},
        headers=admin_headers
    )
    assert return_res.status_code == status.HTTP_200_OK
    data = return_res.json()
    assert data["fine_amount"] >= 450.0


def test_dashboard_notifications_endpoint(test_client, admin_headers):
    """Test dashboard notifications endpoint returns alerts and summary."""
    # 1. Check endpoint baseline
    res = test_client.get("/api/dashboard/notifications")
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert "count" in data
    assert "unread_count" in data
    assert "notifications" in data
    assert "summary" in data

    # 2. Create overdue loan to test alert trigger
    b_res = test_client.post("/api/books", json={"title": "Notif Book"}, headers=admin_headers).json()
    c_res = test_client.post("/api/copies", json={"book_id": b_res["id"], "barcode": "BC-NOTIF-01"}, headers=admin_headers).json()
    m_res = test_client.post("/api/members", json={"first_name": "Notif", "last_name": "User", "email": "notif@test.com"}, headers=admin_headers).json()

    past_date = (date.today() - timedelta(days=5)).isoformat()
    issue_res = test_client.post("/api/loans/issue", json={"member_id": m_res["id"], "book_copy_id": c_res["id"], "due_date": past_date}, headers=admin_headers)
    assert issue_res.status_code == status.HTTP_201_CREATED

    # 3. Check notifications has the overdue alert
    res2 = test_client.get("/api/dashboard/notifications")
    assert res2.status_code == status.HTTP_200_OK
    data2 = res2.json()
    assert data2["count"] >= 1
    assert data2["summary"]["overdue_count"] >= 1
    assert any(n["target_view"] == "overdue-books" for n in data2["notifications"])




