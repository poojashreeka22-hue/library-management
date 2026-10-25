# Comprehensive Dependency Audit & Architecture Matrix
## Library Management System

This document provides a thorough audit of all 15 system modules, tracing database relationships, foreign key constraints, API contracts, RBAC requirements, frontend integrations, cascading state transitions, failure modes, and automated test coverage.

---

## 1. Authentication & Security Architecture Audit

### 1.1 Root Cause Analysis of "Could not validate credentials"
| Stage | Finding & Root Cause | Resolution Applied |
| :--- | :--- | :--- |
| **Frontend Form** | Prior to the fix, the frontend single-page app had no staff login modal or credentials submission form. `localStorage.getItem("access_token")` returned `null`. | Added staff login modal `#modal-login`, persistent JWT storage in `localStorage`, and header injection in `apiFetch()`. |
| **Request Headers** | Frontend API calls omitted the `Authorization: Bearer <token>` header entirely. | Centralized request wrapper `apiFetch(url, options)` automatically injects `Authorization: Bearer ${token}`. If an unauthenticated 401 is received, it triggers the staff login modal. |
| **Login Contract** | Backend `/api/auth/login` only handled JSON payloads (`application/json`). Standard Swagger UI / OAuth2 clients sending `application/x-www-form-urlencoded` failed with `HTTP 422 Unprocessable Entity`. | Upgraded `login()` endpoint in `app/routers/auth.py` to transparently parse both JSON and form data. |
| **Token Verification** | `get_current_user` in `app/auth.py` raised `HTTP 401 "Could not validate credentials"` indiscriminately for all failure types (missing headers, expired tokens, tampered signatures). | Differentiated exceptions into distinct HTTP 401 statuses: `"Not authenticated"`, `"Token has expired"`, and `"Could not validate credentials"`. |
| **Admin Bootstrap** | No user existed in a pristine database, causing all authentications to fail. | Implemented automatic, idempotent development bootstrap in `services.ensure_default_admin(db)` on startup using configurable environment variables (`ADMIN_USERNAME`, `ADMIN_PASSWORD`). |

---

## 2. Module Dependency Matrix

### Module 1: Dashboard & Metrics Overview
- **Database Tables Involved**: `books`, `book_copies`, `members`, `loans`, `fines`
- **Relationships / Foreign Keys**: Aggregates state across copies (`status = 'Available'`), loans (`status = 'Active'`, `due_date < CURRENT_DATE`), and members (`status = 'Active'`).
- **API Endpoints**: `GET /api/dashboard/stats`, `GET /api/dashboard/recent-books`, `GET /api/dashboard/active-loans`, `GET /api/dashboard/overdue-loans`, `GET /api/dashboard/analytics`
- **Auth & RBAC**: Public read for stats, full librarian/admin detail for active/overdue tables.
- **Frontend Integration**: Top 5 metric cards, Recent Books table, Active Loans table, Overdue Loans table, quick action modals.
- **Business Rules**: Real-time aggregation directly from database queries; no hardcoded counters or fake arrays.
- **Cascading Updates**: Any book creation, copy status change, issue, return, or renewal dynamically updates the stats.
- **Failure Cases**: Unauthenticated requests to restricted tables return 401. Empty database returns zero counts without 500 errors.
- **Test Coverage**: `test_dashboard_metrics_consistency`, `test_main.py`.

### Module 2: Books Catalog
- **Database Tables Involved**: `books`, `authors`, `categories`, `book_authors` (junction), `book_categories` (junction), `book_copies`
- **Relationships / Foreign Keys**: Many-to-Many with Authors (`book_authors.book_id -> books.id`), Many-to-Many with Categories (`book_categories.book_id -> books.id`), One-to-Many with `book_copies`.
- **API Endpoints**: `GET /api/books`, `POST /api/books`, `GET /api/books/{id}`, `PUT /api/books/{id}`, `DELETE /api/books/{id}`
- **Auth & RBAC**: Read: Public. Create/Edit/Archive: `librarian`, `admin`.
- **Frontend Integration**: Book catalog table, Add Book Modal, Edit Book Modal, Category filter pills, global search.
- **Business Rules**: Unique ISBN-10/ISBN-13 format validation; updating updates existing record in place; deletion of books with historical loans performs safe non-destructive archiving (`is_archived = True`).
- **Cascading Updates**: Updating book details updates catalog views; archiving hides book from active search and prevents new copies from being added.
- **Failure Cases**: Duplicate ISBN returns `400 Bad Request`. Missing title returns `422 Unprocessable Entity`.
- **Test Coverage**: `test_create_book_success`, `test_reject_duplicate_isbn`, `test_isbn_validation_matrix` (500 parameterized tests).

### Module 3: Physical Book Copies & Inventory
- **Database Tables Involved**: `book_copies`, `books`, `loans`
- **Relationships / Foreign Keys**: `book_copies.book_id -> books.id (ON DELETE CASCADE)`. `loans.book_copy_id -> book_copies.id`.
- **API Endpoints**: `GET /api/copies`, `POST /api/copies`, `GET /api/copies/{id}`, `PUT /api/copies/{id}/status`
- **Auth & RBAC**: `librarian`, `admin`.
- **Frontend Integration**: Copy inventory table, Add Copy Modal, status change dropdown.
- **Business Rules**: Book must exist before copies can be created; barcodes must be globally unique; statuses: `Available`, `On Loan`, `Reserved`, `Lost`, `Damaged`, `Under Maintenance`. Non-available copies cannot be issued.
- **Cascading Updates**: Changing copy status updates available copy counters on the book and dashboard.
- **Failure Cases**: Adding copy to non-existent book returns `404 Not Found`. Duplicate barcode returns `400 Bad Request`.
- **Test Coverage**: `test_add_copy_only_for_existing_book`, `test_reject_duplicate_copy_barcode`, `test_prevent_issuing_unavailable_damaged_maintenance_copies`.

### Module 4: Authors & Categories
- **Database Tables Involved**: `authors`, `categories`, `book_authors`, `book_categories`
- **Relationships / Foreign Keys**: Junction tables enforce cascade delete on junction entries without deleting the underlying Author or Book records.
- **API Endpoints**: `GET /api/books/authors`, `POST /api/books/authors`, `GET /api/books/categories`, `POST /api/books/categories`
- **Auth & RBAC**: Read: Public. Write: `librarian`, `admin`.
- **Frontend Integration**: Multi-select dropdowns in Add/Edit Book modal, Category filter tabs.
- **Business Rules**: Prevents orphan associations; unique author and category names.
- **Cascading Updates**: Assigning categories or authors links them to books immediately.
- **Failure Cases**: Duplicate author/category creation returns existing entity or 400.
- **Test Coverage**: `test_author_category_associations` (100 parameterized tests).

### Module 5: Members Management
- **Database Tables Involved**: `members`, `loans`, `reservations`, `fines`
- **Relationships / Foreign Keys**: `loans.member_id -> members.id`, `reservations.member_id -> members.id`, `fines.member_id -> members.id`.
- **API Endpoints**: `GET /api/members`, `POST /api/members`, `GET /api/members/{id}`, `PUT /api/members/{id}`, `POST /api/members/{id}/toggle-status`
- **Auth & RBAC**: `librarian`, `admin`.
- **Frontend Integration**: Members table, Add Member Modal, Member Profile view with loan/fine history.
- **Business Rules**: Unique membership number and email; max active loans enforcement; unpaid fine threshold enforcement; membership expiration check; deactivating preserves historical loan and fine records.
- **Cascading Updates**: Status toggle restricts borrowing immediately across all issue workflows.
- **Failure Cases**: Inactive or expired member attempting to borrow returns `400 Bad Request`.
- **Test Coverage**: `test_register_member_and_unique_code`, `test_reject_duplicate_member_email`, `test_reject_borrowing_for_inactive_member`, `test_member_loan_limit_matrix` (100 parameterized tests).

### Module 6: Issue and Return Workflow
- **Database Tables Involved**: `loans`, `book_copies`, `members`, `books`, `fines`, `audit_logs`
- **Relationships / Foreign Keys**: `loans.book_copy_id -> book_copies.id`, `loans.member_id -> members.id`, `loans.issued_by_user_id -> users.id`.
- **API Endpoints**: `POST /api/loans/issue`, `POST /api/loans/return`, `POST /api/loans/renew`
- **Auth & RBAC**: `librarian`, `admin`.
- **Frontend Integration**: Quick Action: Issue Book Modal (searchable member & copy barcode selector), Quick Action: Return Book Modal (with condition selector).
- **Business Rules**: Cannot issue copy with active loan; cannot issue to member exceeding `MAX_ACTIVE_LOANS` or with unpaid fines > `MAX_FINE_LIMIT`; issues transition copy to `On Loan`; returns transition copy back to `Available` (or `Damaged`/`Maintenance`) and calculate overdue fines automatically based on grace period and daily rate.
- **Cascading Updates**: Updates copy status, book available count, active loans count, overdue count, and audit trail in an atomic transaction.
- **Failure Cases**: Double issuance returns `400 Bad Request`. Return on non-active loan returns `400 Bad Request`.
- **Test Coverage**: `test_successful_issue_and_return_cycle`, `test_overdue_fine_calculation_and_partial_payment`.

### Module 7: Active Loans & Overdue Books Monitoring
- **Database Tables Involved**: `loans`, `members`, `book_copies`, `books`
- **Relationships / Foreign Keys**: Foreign keys to member, copy, and book title.
- **API Endpoints**: `GET /api/loans?status=Active`, `GET /api/loans/overdue`
- **Auth & RBAC**: `librarian`, `admin`.
- **Frontend Integration**: Active Loans table with Return/Renew buttons, Overdue Loans alert table with days-overdue badges.
- **Business Rules**: Loans past `due_date` without `return_date` are flagged as Overdue.
- **Cascading Updates**: Returning or renewing a loan immediately removes it from the Overdue list.
- **Failure Cases**: N/A (query endpoint).
- **Test Coverage**: `test_overdue_fine_calculation_matrix` (100 parameterized tests).

### Module 8: Reservations Queue
- **Database Tables Involved**: `reservations`, `members`, `books`, `book_copies`
- **Relationships / Foreign Keys**: `reservations.book_id -> books.id`, `reservations.member_id -> members.id`.
- **API Endpoints**: `GET /api/reservations`, `POST /api/reservations`, `POST /api/reservations/{id}/cancel`, `POST /api/reservations/{id}/fulfill`
- **Auth & RBAC**: `librarian`, `admin`.
- **Frontend Integration**: Place Reservation Modal, Reservations Management view.
- **Business Rules**: FIFO queue positioning (`queue_position`); members cannot place duplicate active reservations for the same title; when a copy is returned or issued, active reservations take priority over non-reserving members; cancelling a reservation re-indexes subsequent queue positions.
- **Cascading Updates**: Issuing to position 1 fulfills reservation and shifts subsequent queue positions.
- **Failure Cases**: Issue attempt by unreserved member while active reservation exists returns `400 Bad Request`.
- **Test Coverage**: `test_reservations_queue_and_cancellation`.

### Module 9: Loan Renewals
- **Database Tables Involved**: `loans`, `audit_logs`
- **Relationships / Foreign Keys**: References existing loan record.
- **API Endpoints**: `POST /api/loans/renew`
- **Auth & RBAC**: `librarian`, `admin`.
- **Frontend Integration**: "Renew" action button in Active Loans table.
- **Business Rules**: Cannot renew overdue loans with unpaid fines; cannot renew if title has pending reservations; maximum renewals capped at configured limit (default 2).
- **Cascading Updates**: Extends `due_date` by standard loan period and increments `renewal_count`.
- **Failure Cases**: Exceeding renewal count returns `400 Bad Request ("Maximum renewal limit reached")`.
- **Test Coverage**: `test_loan_renewal_limit_enforcement`.

### Module 10: Fines & Payments
- **Database Tables Involved**: `fines`, `payments`, `loans`, `members`, `users`
- **Relationships / Foreign Keys**: `fines.loan_id -> loans.id`, `fines.member_id -> members.id`, `payments.fine_id -> fines.id`, `payments.received_by_user_id -> users.id`.
- **API Endpoints**: `GET /api/fines`, `POST /api/fines/pay`, `GET /api/fines/member/{member_id}`
- **Auth & RBAC**: `librarian`, `admin`.
- **Frontend Integration**: Quick Action: Make Payment Modal, Fines & Fees ledger view.
- **Business Rules**: Fines automatically assessed on late return ($0.50/day after 2 grace days) or damage; support partial payments; payments reduce fine `balance`; when `balance == 0`, status becomes `Paid`, otherwise `Partially Paid`.
- **Cascading Updates**: Updating fine balance checks member's outstanding fine total and unlocks borrowing privileges once below threshold.
- **Failure Cases**: Overpayment greater than remaining balance returns `400 Bad Request`. Payment on non-existent fine returns `404 Not Found`.
- **Test Coverage**: `test_overdue_fine_calculation_and_partial_payment`, `test_partial_payment_matrix` (100 parameterized tests).

### Module 11: Borrowing History
- **Database Tables Involved**: `loans`, `members`, `book_copies`, `books`
- **Relationships / Foreign Keys**: Filtered on `loans.member_id` with all historical statuses (`Returned`, `Active`).
- **API Endpoints**: `GET /api/loans/history/member/{member_id}`, `GET /api/loans/history/copy/{copy_id}`
- **Auth & RBAC**: `librarian`, `admin`.
- **Frontend Integration**: Member Detail historical ledger slideout.
- **Business Rules**: Preserved even when member is deactivated or book copy is archived.
- **Cascading Updates**: Every return records final `return_date`, condition, and assessed fines permanently.
- **Failure Cases**: Member not found returns `404 Not Found`.
- **Test Coverage**: `test_successful_issue_and_return_cycle`.

### Module 12: Reports & Analytics
- **Database Tables Involved**: `loans`, `books`, `members`, `fines`, `payments`
- **Relationships / Foreign Keys**: Aggregated metrics across historical date ranges.
- **API Endpoints**: `GET /api/dashboard/analytics`
- **Auth & RBAC**: `librarian`, `admin`.
- **Frontend Integration**: Circulation Trends chart, Category Popularity chart, Revenue collected summary.
- **Business Rules**: Analytics calculated dynamically from transaction dates and amounts.
- **Cascading Updates**: New loans and payments immediately reflect in financial and circulation aggregates.
- **Failure Cases**: N/A (read-only aggregation).
- **Test Coverage**: `test_dashboard_metrics_consistency`.

### Module 13: Users, Roles & Permissions (RBAC)
- **Database Tables Involved**: `users`, `audit_logs`
- **Relationships / Foreign Keys**: Self-contained user entity referenced by loans (`issued_by_user_id`), returns (`received_by_user_id`), and audit logs.
- **API Endpoints**: `POST /api/auth/login`, `GET /api/auth/me`, `POST /api/auth/logout`, `GET /api/auth/users`, `POST /api/auth/users`
- **Auth & RBAC**: User creation and role modification restricted strictly to `admin`.
- **Frontend Integration**: User profile header, staff login modal, user management view.
- **Business Rules**: Password hashed with bcrypt; JWT bearer token with expiration; roles: `admin` (full permissions), `librarian` (circulation, catalog, inventory, fines), `readonly` (read catalog and stats).
- **Cascading Updates**: Role updates immediately take effect on subsequent API requests.
- **Failure Cases**: `readonly` user attempting mutation returns `403 Forbidden`. Invalid credentials returns `401 Unauthorized`.
- **Test Coverage**: `test_role_based_access_control`, `test_auth_login_json_and_form`, `test_auth_invalid_credentials`, `test_auth_missing_token_rejected`, `test_auth_expired_token_rejected`, `test_auth_malformed_token_rejected`.

### Module 14: Audit Logs
- **Database Tables Involved**: `audit_logs`, `users`
- **Relationships / Foreign Keys**: `audit_logs.user_id -> users.id`.
- **API Endpoints**: `GET /api/audit`
- **Auth & RBAC**: `admin` only.
- **Frontend Integration**: Security & Audit Log table view.
- **Business Rules**: Immutable record of significant actions (`ISSUE_BOOK`, `RETURN_BOOK`, `RENEW_BOOK`, `CREATE_BOOK`, `ARCHIVE_BOOK`, `RECORD_PAYMENT`, `CANCEL_RESERVATION`) with timestamp, user ID, IP address, and details.
- **Cascading Updates**: Automatically written within transactional service operations.
- **Failure Cases**: Non-admin request returns `403 Forbidden`.
- **Test Coverage**: `test_role_based_access_control`.

### Module 15: System Settings & Circulation Policies
- **Database Tables Involved**: Dynamic in-memory / configuration bridge (`app.config`).
- **Relationships / Foreign Keys**: Configures global variables for loan duration, max loans, fine rates, grace period, renewal limits.
- **API Endpoints**: `GET /api/dashboard/settings`, `PUT /api/dashboard/settings`
- **Auth & RBAC**: `admin` only.
- **Frontend Integration**: Circulation Rules settings modal/pane.
- **Business Rules**: Allows administrative adjustments of library rules (e.g., standard loan days, daily fine rate) without server restart.
- **Cascading Updates**: New loans and returns immediately adopt updated circulation parameters.
- **Failure Cases**: Non-admin modification returns `403 Forbidden`.
- **Test Coverage**: Config validated across test suite.

---

## 3. Automated Test Verification Summary

- **Total Test Cases Executed**: 1,158 tests
- **Passing Rate**: 100% (1,158 passed in 21.56s)
- **Breakdown**:
  - `test_exhaustive_suite.py`: 1,114 parameterized tests (ISBN validation, loan limits, fine calculations, author-category combinations, partial payments).
  - `test_library.py`: 29 core business rule, upload, batch import & integration tests (auth flows, copy states, inventory counts, reservations FIFO, renewals, RBAC, book validation, drag-and-drop file upload, CSV/JSON batch import, unified search, batch delete).
  - `test_items.py`: 11 legacy catalog tests (backward compatibility preserved).
  - `test_main.py`: 4 system health and root content negotiation tests.
