# Library Management System

A production-grade, medium-level Library Management System built with Python 3, FastAPI, SQLite, SQLAlchemy, Pydantic v2, HTML5, CSS3, JavaScript (ES6), and Pytest.

The user interface is designed directly in reference to the modern Library Management Dashboard design with interactive views for catalog management, physical inventory, member registration, circulation (book issue & return), reservations, renewals, overdue fines, fee collection, reports, and system audit logs.

---

## Architecture & Technology Stack

- **Backend Framework**: [FastAPI](https://fastapi.tiangolo.com/) (RESTful APIs with dependency injection, auto-generated OpenAPI & Swagger UI)
- **Database ORM**: [SQLAlchemy 2.0](https://www.sqlalchemy.org/) with SQLite database (`library.db`)
- **Data Validation**: [Pydantic v2](https://docs.pydantic.dev/) schemas with custom validators
- **Security & Authentication**: [PyJWT](https://pyjwt.readthedocs.io/) (JWT tokens), [bcrypt](https://pypi.org/project/bcrypt/) password hashing, Role-Based Access Control (`admin`, `librarian`, `readonly`)
- **Frontend Architecture**: Single Page Application (SPA) using vanilla HTML5, CSS3, and JavaScript, consuming backend JSON APIs
- **Automated Test Suite**: [Pytest](https://docs.pytest.org/) with SQLite in-memory test database, testing both successful and rejected business rule workflows

---

## Project Structure

```
fastapi-project/
├── app/
│   ├── __init__.py
│   ├── config.py             # Business rule constants & configuration
│   ├── database.py           # Engine, SessionLocal, Base, get_db dependency
│   ├── models.py             # 12 SQLAlchemy ORM models & relationships
│   ├── schemas.py            # Pydantic v2 request & response schemas
│   ├── auth.py               # Password hashing, JWT verification, RBAC
│   ├── services.py           # Core business logic, validations & transactions
│   ├── seed.py               # Initial baseline seed data matching UI
│   ├── main.py               # FastAPI entrypoint, middleware, routers & UI mounting
│   ├── crud.py               # In-memory repository (preserved for backward compatibility)
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── auth.py           # Login, staff accounts, profiles (/api/auth)
│   │   ├── books.py          # Books, authors, categories (/api/books, /api/authors, /api/categories)
│   │   ├── copies.py         # Physical inventory & barcodes (/api/copies)
│   │   ├── members.py        # Member registration & eligibility (/api/members)
│   │   ├── loans.py          # Book issue, return, renewals, active, overdue (/api/loans)
│   │   ├── reservations.py   # Title reservations & waiting queues (/api/reservations)
│   │   ├── fines.py          # Overdue fines, payments, waivers (/api/fines, /api/payments)
│   │   ├── dashboard.py      # Real-time metrics & reports (/api/dashboard)
│   │   ├── audit.py          # System audit trail logs (/api/audit)
│   │   └── items.py          # Legacy item catalog endpoints (/items)
│   └── static/
│       ├── index.html        # Interactive Single Page Application (SPA)
│       ├── css/
│       │   └── style.css     # Clean styles matching reference dashboard
│       └── js/
│           └── app.js        # Dynamic UI state, API clients, form handlers
├── tests/
│   ├── __init__.py
│   ├── conftest.py           # Pytest fixtures and TestClient configuration
│   ├── test_library.py       # Comprehensive tests for all 12 modules & business rules
│   ├── test_main.py          # General health & root endpoint tests
│   └── test_items.py         # Legacy items CRUD tests
├── requirements.txt          # Project dependencies
├── run_tests.py              # Automated test runner with PASS summary
├── pytest.ini                # Pytest configuration
└── README.md                 # Project documentation & dependency matrix
```

---

## Getting Started

### 1. Prerequisites & Environment
Ensure you are using Python 3.10+ (or Python 3.14). Activate the virtual environment:

```powershell
cd "C:\Users\pooja\.gemini\antigravity\scratch\fastapi-project"
.\.venv\Scripts\Activate.ps1
```

### 2. Install Dependencies
```powershell
pip install -r requirements.txt
```

### 3. Run the Development Server
```powershell
uvicorn app.main:app --reload --port 8000
```

- **Interactive Dashboard UI**: [http://127.0.0.1:8000/](http://127.0.0.1:8000/) or [http://127.0.0.1:8000/app](http://127.0.0.1:8000/app)
- **Interactive Swagger Documentation**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc Documentation**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
- **Health Check**: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

### 4. Default Credentials
- **Username**: `admin`
- **Password**: `admin123`
- **Role**: `admin`

---

## Running the Automated Test Suite

To run all **1,158 automated test cases** across the entire project:

```powershell
python run_tests.py
```

Or directly via pytest:
```powershell
pytest -v
```

### Automated Test Coverage Breakdown (1,158 Tests Total):
- **150 ISBN Format Validation Tests**: Valid ISBN-10, valid ISBN-13 with hyphens and spaces, boundary checks, and format rejections.
- **150 Email Format Validation Tests**: RFC-compliant formats, subdomains, plus-addressing, and malformed email rejections.
- **150 Overdue Fine Calculation Tests**: 0 to 149 days overdue testing daily accrual rates and grace period threshold boundaries.
- **150 Payment Amount Tests**: Exact payments, partial payments, micro-cents, negative rejection, and overpayment bounds.
- **120 Physical Copy Status Transition Tests**: Issuance availability across all 6 copy states (`Available`, `On Loan`, `Reserved`, `Lost`, `Damaged`, `Under Maintenance`).
- **100 Member Loan Quota Tests**: Member active loan limits (1 to 10 books) and borrowing caps.
- **100 Loan Renewal Tests**: Renewal limit caps (0, 1, 2, 3+) and grace period validation.
- **100 Reservation Queue Tests**: Multi-member FIFO queue indexing and re-ordering upon cancellations.
- **100 Category & Author Linkage Tests**: Association pairs and metadata integrity.
- **26 End-to-End Business Rule, Upload & Search Tests**: Full database lifecycle (issue, return, fines, waivers, rollbacks, dashboard metrics, JSON vs Form OAuth2 login, expired/malformed tokens, RBAC, Book validation & cover upload, drag-and-drop multi-file upload, batch CSV/JSON import, unified search, batch book deletion).
- **13 Legacy Catalog Tests**: Item catalog endpoints preserving backward compatibility.

---

## Dependency Matrix

| Source Record | Required Related Record | Business / Validation Rule | Expected Behavior When Rule Fails | Automated Test Covering Rule |
| :--- | :--- | :--- | :--- | :--- |
| **Book** | None | Title is mandatory; ISBN format must be valid (10 or 13 digits) and unique. | HTTP 400 Bad Request with descriptive message ("already exists"). | `test_reject_duplicate_isbn` |
| **Book Copy** | `Book` | A copy cannot be added unless parent Book title exists; barcode must be unique. | HTTP 400 Bad Request ("Book does not exist" or "already exists"). | `test_add_copy_only_for_existing_book`, `test_reject_duplicate_copy_barcode` |
| **Member** | None | Unique email and auto-generated `MEM-XXXX` code; max book limits. | HTTP 400 Bad Request ("already exists"). | `test_register_member_and_unique_code`, `test_reject_duplicate_member_email` |
| **Loan (Issue)** | `Member`, `BookCopy`, `User` | Member must be active, non-expired, under loan limit, under fine limit; copy must be in `Available` status; no conflicting active loan. | HTTP 400 Bad Request rejecting issue without creating partial data. | `test_reject_borrowing_for_inactive_member`, `test_enforce_member_borrowing_limit`, `test_prevent_issuing_unavailable_damaged_maintenance_copies` |
| **Loan (Return)** | `Loan` | Active loan must exist; cannot return an already returned loan; copy status updated; overdue fines calculated. | HTTP 400 Bad Request ("already been returned"). | `test_successful_issue_and_return_cycle` |
| **Loan (Renewal)** | `Loan`, `Member` | Loan must be active; renewal count < max renewals (2); no pending reservation on title. | HTTP 400 Bad Request ("limit reached" or "reserved"). | `test_loan_renewal_limit_enforcement` |
| **Reservation** | `Member`, `Book` | Member must be active; cannot create duplicate active reservation for same book; maintains queue position. | HTTP 400 Bad Request ("already has an active reservation"). | `test_reservations_queue_and_cancellation` |
| **Fine** | `Loan`, `Member` | Automatically created on overdue return based on days past due date minus grace period. | Prevents duplicate fine records for same event; records balance. | `test_overdue_fine_calculation_and_partial_payment` |
| **Payment** | `Fine`, `Member`, `User` | Payment amount must be > 0 and cannot exceed remaining balance. | HTTP 400 Bad Request rejecting overpayments or invalid amounts. | `test_overdue_fine_calculation_and_partial_payment` |
| **Security / RBAC** | `User` | Only authenticated staff with required roles can issue, return, or manage inventory. | HTTP 403 Forbidden or 401 Unauthorized. | `test_role_based_access_control` |
