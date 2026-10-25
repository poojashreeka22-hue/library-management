/**
 * Library Management System - Frontend SPA Application
 * Connects all APIs, validates forms, and renders views matching reference UI.
 */

// Global State
const state = {
  currentView: "dashboard",
  user: null,
  books: [],
  copies: [],
  members: [],
  activeLoans: [],
  overdueLoans: [],
  fines: [],
  categories: [],
  authors: [],
};

// ==========================================================================
// Centralized API Client with Token Interceptor
// ==========================================================================

async function apiFetch(url, options = {}) {
  options.headers = options.headers || {};

  // Inject Authorization Bearer token from localStorage if available
  const token = localStorage.getItem("access_token");
  if (token) {
    options.headers["Authorization"] = `Bearer ${token}`;
  }

  // Same-origin cookie support
  options.credentials = "same-origin";

  const res = await fetch(url, options);

  // Intercept 401 Unauthorized for expired or missing tokens
  if (res.status === 401) {
    const clone = res.clone();
    try {
      const data = await clone.json();
      if (data.detail === "Token has expired") {
        showToast("Session expired. Please sign in again.", "error");
        localStorage.removeItem("access_token");
        updateAuthUI(null);
        openModal("modal-login");
      } else if (data.detail === "Not authenticated" || data.detail === "Could not validate credentials") {
        // Trigger login modal if user attempted a protected mutation
        if (options.method && options.method !== "GET") {
          showToast("Authentication required. Please sign in.", "error");
          openModal("modal-login");
        }
      }
    } catch (_) {}
  }

  return res;
}

// Utilities
function showToast(message, type = "success") {
  const container = document.getElementById("toast-container");
  if (!container) return;
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.innerHTML = `<span>${message}</span>`;
  container.appendChild(toast);
  setTimeout(() => {
    toast.remove();
  }, 4000);
}

function formatDate(dateStr) {
  if (!dateStr) return "-";
  const d = new Date(dateStr);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

function updateDateTime() {
  const badge = document.getElementById("current-date-time");
  if (badge) {
    const now = new Date();
    const formatted = now.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }) +
      " " + now.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" });
    badge.innerText = formatted;
  }
}

// Modal management
function openModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) {
    modal.classList.add("show");
  }
}

function closeModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) {
    modal.classList.remove("show");
  }
}

// ==========================================================================
// Authentication & User Session Management
// ==========================================================================

async function checkAuthStatus() {
  const token = localStorage.getItem("access_token");
  if (!token) {
    // Attempt developer bootstrap auto-login for immediate out-of-the-box operation
    try {
      const loginRes = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: "admin", password: "admin123" }),
      });
      if (loginRes.ok) {
        const loginData = await loginRes.json();
        localStorage.setItem("access_token", loginData.access_token);
        return checkAuthStatus();
      }
    } catch (_) {}

    updateAuthUI(null);
    return;
  }

  try {
    const res = await apiFetch("/api/auth/me");
    if (res.ok) {
      const user = await res.json();
      state.user = user;
      updateAuthUI(user);
    } else {
      localStorage.removeItem("access_token");
      updateAuthUI(null);
    }
  } catch (err) {
    console.error("Auth check failed:", err);
    updateAuthUI(null);
  }
}

function updateAuthUI(user) {
  const avatarEl = document.getElementById("user-avatar");
  const nameEl = document.getElementById("user-display-name");
  const roleEl = document.getElementById("user-display-role");
  const authActionText = document.getElementById("auth-action-text");

  if (user) {
    if (avatarEl) avatarEl.innerText = user.full_name ? user.full_name.charAt(0).toUpperCase() : "A";
    if (nameEl) nameEl.innerText = user.full_name || user.username;
    if (roleEl) roleEl.innerText = user.role.charAt(0).toUpperCase() + user.role.slice(1);
    if (authActionText) authActionText.innerText = "Logout";
  } else {
    if (avatarEl) avatarEl.innerText = "?";
    if (nameEl) nameEl.innerText = "Sign In";
    if (roleEl) roleEl.innerText = "Staff Login";
    if (authActionText) authActionText.innerText = "Sign In";
  }
}

function openLoginOrProfileModal() {
  if (state.user) {
    showToast(`Signed in as ${state.user.full_name} (${state.user.role})`);
  } else {
    openModal("modal-login");
  }
}

async function handleAuthAction() {
  const token = localStorage.getItem("access_token");
  if (token) {
    // Perform Logout
    try {
      await apiFetch("/api/auth/logout", { method: "POST" });
    } catch (_) {}
    localStorage.removeItem("access_token");
    state.user = null;
    updateAuthUI(null);
    showToast("Signed out successfully");
    switchView("dashboard");
  } else {
    openModal("modal-login");
  }
}

async function handleLoginSubmit(e) {
  e.preventDefault();
  const form = e.target;
  const username = form.username.value.trim();
  const password = form.password.value;

  try {
    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "Authentication failed");
    }

    localStorage.setItem("access_token", data.access_token);
    closeModal("modal-login");
    form.reset();

    // Fetch user profile
    await checkAuthStatus();
    showToast(`Welcome back, ${state.user?.full_name || username}!`);

    // Refresh current view & dropdowns
    await fetchDashboard();
    await loadDropdowns();
    if (state.currentView !== "dashboard") {
      switchView(state.currentView);
    }
  } catch (err) {
    showToast(err.message, "error");
  }
}

// ==========================================================================
// API Calls & Data Fetching
// ==========================================================================

async function fetchDashboard() {
  try {
    const res = await apiFetch("/api/dashboard");
    if (!res.ok) throw new Error("Failed to load dashboard data");
    const data = await res.json();
    renderDashboard(data);
  } catch (err) {
    console.error("Dashboard error:", err);
  }
}

function renderDashboard(data) {
  // Stat cards
  document.getElementById("stat-total-books").innerText = data.stats.total_books;
  document.getElementById("stat-total-copies").innerText = data.stats.total_copies;
  document.getElementById("stat-active-members").innerText = data.stats.active_members;
  document.getElementById("stat-current-loans").innerText = data.stats.active_loans;
  document.getElementById("stat-overdue-books").innerText = data.stats.overdue_loans;

  // Recent Books Table
  const recentTbody = document.getElementById("recent-books-tbody");
  if (recentTbody) {
    if (data.recent_books.length === 0) {
      recentTbody.innerHTML = `<tr><td colspan="5" style="text-align:center;color:#94a3b8;padding:24px;">No books in catalog</td></tr>`;
    } else {
      recentTbody.innerHTML = data.recent_books.map(b => `
        <tr>
          <td>
            <div class="book-title-cell">
              <div class="book-thumb">${b.title.substring(0, 2).toUpperCase()}</div>
              <span>${b.title}</span>
            </div>
          </td>
          <td>${b.author}</td>
          <td>${b.category}</td>
          <td>${b.copies}</td>
          <td><span class="badge ${b.status === 'Available' ? 'green' : 'orange'}">${b.status}</span></td>
        </tr>
      `).join("");
    }
  }

  // Active Loans Table
  const activeTbody = document.getElementById("active-loans-tbody");
  if (activeTbody) {
    if (data.active_loans.length === 0) {
      activeTbody.innerHTML = `<tr><td colspan="5" style="text-align:center;color:#94a3b8;padding:24px;">No current active loans</td></tr>`;
    } else {
      activeTbody.innerHTML = data.active_loans.map(l => `
        <tr>
          <td><strong>${l.member_name}</strong></td>
          <td>${l.book_title}</td>
          <td>${formatDate(l.issue_date)}</td>
          <td>${formatDate(l.due_date)}</td>
          <td><span class="badge ${l.status === 'Overdue' ? 'red' : 'green'}">${l.status}</span></td>
        </tr>
      `).join("");
    }
  }

  // Overdue Books Table
  const overdueTbody = document.getElementById("overdue-books-tbody");
  if (overdueTbody) {
    if (data.overdue_books.length === 0) {
      overdueTbody.innerHTML = `<tr><td colspan="5" style="text-align:center;color:#94a3b8;padding:24px;">No overdue books!</td></tr>`;
    } else {
      overdueTbody.innerHTML = data.overdue_books.map(o => `
        <tr>
          <td><strong>${o.member_name}</strong></td>
          <td>${o.book_title}</td>
          <td class="text-danger">${o.days_overdue} days</td>
          <td>₹${o.fine_amount.toFixed(2)}</td>
          <td><span class="badge red">Overdue</span></td>
        </tr>
      `).join("");
    }
  }
}

// Load dropdowns for modals and forms
async function loadDropdowns() {
  try {
    // 1. Eligible members for Issue Book
    const memRes = await apiFetch("/api/members/eligible");
    if (memRes.ok) {
      const eligibleMembers = await memRes.json();
      const issueMemSelect = document.getElementById("issue-member-select");
      const resMemSelect = document.getElementById("reserve-member-select");
      const options = `<option value="">-- Select Eligible Member --</option>` +
        eligibleMembers.map(m => `<option value="${m.id}">${m.member_code} - ${m.first_name} ${m.last_name} (${m.active_loans}/${m.max_books} books)</option>`).join("");
      if (issueMemSelect) issueMemSelect.innerHTML = options;
      if (resMemSelect) resMemSelect.innerHTML = options;
    }

    // 2. Available physical copies for Issue Book
    const copiesRes = await apiFetch("/api/copies/available");
    if (copiesRes.ok) {
      const availCopies = await copiesRes.json();
      const issueCopySelect = document.getElementById("issue-copy-select");
      if (issueCopySelect) {
        issueCopySelect.innerHTML = `<option value="">-- Select Available Physical Copy --</option>` +
          availCopies.map(c => `<option value="${c.id}">${c.barcode} | ${c.book_title}</option>`).join("");
      }
    }

    // 3. Books for Add Copy and Reservations
    const booksRes = await apiFetch("/api/books");
    if (booksRes.ok) {
      const books = await booksRes.json();
      state.books = books;
      const copyBookSelect = document.getElementById("copy-book-select");
      const resBookSelect = document.getElementById("reserve-book-select");
      const options = `<option value="">-- Select Book Title --</option>` +
        books.map(b => `<option value="${b.id}">${b.title} (Available: ${b.available_copies}/${b.total_copies})</option>`).join("");
      if (copyBookSelect) copyBookSelect.innerHTML = options;
      if (resBookSelect) resBookSelect.innerHTML = options;
    }

    // 4. Active loans for Return Book
    const loansRes = await apiFetch("/api/loans/active");
    if (loansRes.ok) {
      const activeLoans = await loansRes.json();
      const returnLoanSelect = document.getElementById("return-loan-select");
      if (returnLoanSelect) {
        returnLoanSelect.innerHTML = `<option value="">-- Select Active Loan to Return --</option>` +
          activeLoans.map(l => `<option value="${l.id}">${l.barcode} - ${l.book_title} (Borrowed by: ${l.member_name}, Due: ${formatDate(l.due_date)})</option>`).join("");
      }
    }

    // 5. Unpaid fines for Make Payment
    const finesRes = await apiFetch("/api/fines?status=Unpaid");
    if (finesRes.ok) {
      const unpaidFines = await finesRes.json();
      const paymentFineSelect = document.getElementById("payment-fine-select");
      if (paymentFineSelect) {
        paymentFineSelect.innerHTML = `<option value="">-- Select Fine to Settle --</option>` +
          unpaidFines.map(f => `<option value="${f.id}" data-remaining="${f.remaining}">Fine #${f.id} - ${f.member_name} (${f.book_title}) - Due: ₹${f.remaining.toFixed(2)}</option>`).join("");
      }
    }

    // 6. Authors and Categories for Add Book form
    const [authRes, catRes] = await Promise.all([
      apiFetch("/api/authors"),
      apiFetch("/api/categories")
    ]);
    if (authRes.ok && catRes.ok) {
      const authors = await authRes.json();
      const categories = await catRes.json();
      state.authors = authors;
      state.categories = categories;

      renderAuthorMultiSelect();
      renderCategoryMultiSelect();
    }
  } catch (err) {
    console.error("Dropdown loading error:", err);
  }
}

// ==========================================================================
// Views Switching Logic
// ==========================================================================

function switchView(viewName) {
  state.currentView = viewName;

  // Update sidebar active classes
  document.querySelectorAll(".nav-item").forEach(item => {
    item.classList.remove("active");
    if (item.getAttribute("data-view") === viewName) {
      item.classList.add("active");
    }
  });

  const dashboardView = document.getElementById("view-dashboard");
  const dynamicView = document.getElementById("view-dynamic");

  if (viewName === "dashboard") {
    dashboardView.style.display = "block";
    dynamicView.style.display = "none";
    fetchDashboard();
  } else {
    dashboardView.style.display = "none";
    dynamicView.style.display = "block";
    renderDynamicView(viewName);
  }
}

async function renderDynamicView(viewName) {
  const container = document.getElementById("dynamic-content");
  container.innerHTML = `<div style="text-align:center;padding:40px;color:#94a3b8;">Loading ${viewName.replace('-', ' ')}...</div>`;

  try {
    switch (viewName) {
      case "book-catalog":
        await renderBookCatalog(container);
        break;
      case "book-copies":
        await renderBookCopies(container);
        break;
      case "categories-authors":
        await renderCategoriesAuthors(container);
        break;
      case "members":
        await renderMembers(container);
        break;
      case "issue-return":
        await renderIssueReturn(container);
        break;
      case "reservations":
        await renderReservations(container);
        break;
      case "active-loans":
        await renderActiveLoans(container);
        break;
      case "overdue-books":
        await renderOverdueBooks(container);
        break;
      case "fine-payments":
        await renderFinePayments(container);
        break;
      case "borrowing-history":
        await renderBorrowingHistory(container);
        break;
      case "renewals":
        await renderRenewals(container);
        break;
      case "users-accounts":
        await renderUserAccounts(container);
        break;
      case "roles-permissions":
        renderRolesPermissions(container);
        break;
      case "reports-analytics":
        await renderReportsAnalytics(container);
        break;
      case "audit-logs":
        await renderAuditLogs(container);
        break;
      case "system-settings":
        await renderSystemSettings(container);
        break;
      default:
        container.innerHTML = `<div style="padding:20px;">View: ${viewName}</div>`;
    }
  } catch (err) {
    container.innerHTML = `<div style="padding:20px;color:red;">Error loading view: ${err.message}</div>`;
  }
}

// 1. Book Catalog View
async function renderBookCatalog(container) {
  const res = await apiFetch("/api/books");
  const books = await res.json();
  state.books = books;

  container.innerHTML = `
    <div class="page-banner">
      <div>
        <h2 class="page-title">Book Catalog</h2>
        <p class="page-subtitle">Manage library titles, metadata, multi-item selections, and copy distributions.</p>
      </div>
      <div style="display:flex;gap:10px;">
        <button class="btn btn-secondary" onclick="openModal('modal-batch-import')">📁 Batch Import (CSV/JSON)</button>
        <button class="btn btn-primary" onclick="openModal('modal-add-book')">+ Add New Book</button>
      </div>
    </div>
    <div class="grid-card">
      <div class="table-wrapper">
        <table class="data-table" id="book-catalog-table">
          <thead>
            <tr>
              <th style="width:40px;"><input type="checkbox" id="select-all-books" onchange="toggleSelectAllBooks(this)" title="Select all items"></th>
              <th>Cover / Title</th>
              <th>ISBN</th>
              <th>Authors</th>
              <th>Categories</th>
              <th>Total Copies</th>
              <th>Available</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            ${books.map(b => `
              <tr data-book-id="${b.id}">
                <td><input type="checkbox" class="book-row-checkbox" value="${b.id}" onchange="updateSelectedBooksCount()"></td>
                <td>
                  <div class="book-title-cell">
                    ${b.cover_image ? `<img src="${b.cover_image}" style="width:28px;height:28px;object-fit:cover;border-radius:4px;" alt="cover">` : `<div class="book-thumb">${b.title.substring(0, 2).toUpperCase()}</div>`}
                    <strong>${b.title}</strong>
                  </div>
                </td>
                <td>${b.isbn || '-'}</td>
                <td>${b.authors.map(a => a.name).join(', ') || 'Unknown'}</td>
                <td>${b.categories.map(c => c.name).join(', ') || 'General'}</td>
                <td>${b.total_copies}</td>
                <td><strong style="color:${b.available_copies > 0 ? '#166534' : '#991b1b'}">${b.available_copies}</strong></td>
                <td><span class="badge ${b.is_active ? 'green' : 'red'}">${b.is_active ? 'Active' : 'Archived'}</span></td>
                <td>
                  <button class="btn btn-secondary btn-sm" onclick="archiveBook(${b.id})">Archive / Delete</button>
                </td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    </div>
    <div id="catalog-bulk-bar" class="bulk-actions-bar" style="display:none;">
      <span id="bulk-selected-count">0 items selected</span>
      <button class="btn btn-danger btn-sm" onclick="batchArchiveSelectedBooks()">Archive Selected</button>
      <button class="btn btn-secondary btn-sm" onclick="clearSelectedBooks()">Deselect All</button>
    </div>
  `;
}

function toggleSelectAllBooks(masterCheckbox) {
  const checkboxes = document.querySelectorAll(".book-row-checkbox");
  checkboxes.forEach(cb => cb.checked = masterCheckbox.checked);
  updateSelectedBooksCount();
}

function updateSelectedBooksCount() {
  const checkboxes = document.querySelectorAll(".book-row-checkbox:checked");
  const count = checkboxes.length;
  const bar = document.getElementById("catalog-bulk-bar");
  const countLabel = document.getElementById("bulk-selected-count");
  const master = document.getElementById("select-all-books");

  if (master) {
    const total = document.querySelectorAll(".book-row-checkbox").length;
    master.checked = total > 0 && count === total;
  }

  if (bar && countLabel) {
    if (count > 0) {
      countLabel.innerText = `${count} book${count > 1 ? 's' : ''} selected`;
      bar.style.display = "flex";
    } else {
      bar.style.display = "none";
    }
  }
}

function clearSelectedBooks() {
  document.querySelectorAll(".book-row-checkbox").forEach(cb => cb.checked = false);
  const master = document.getElementById("select-all-books");
  if (master) master.checked = false;
  updateSelectedBooksCount();
}

async function batchArchiveSelectedBooks() {
  const checked = document.querySelectorAll(".book-row-checkbox:checked");
  const bookIds = Array.from(checked).map(cb => parseInt(cb.value));
  if (bookIds.length === 0) return;

  if (!confirm(`Are you sure you want to archive/delete the ${bookIds.length} selected books?`)) return;

  try {
    const res = await apiFetch("/api/books/batch-delete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ book_ids: bookIds }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Batch delete failed");

    showToast(data.message || `Successfully processed ${bookIds.length} books`);
    clearSelectedBooks();
    await fetchDashboard();
    await loadDropdowns();
    if (state.currentView !== "dashboard") switchView(state.currentView);
  } catch (err) {
    showToast(err.message, "error");
  }
}

// 2. Book Copies View
async function renderBookCopies(container) {
  const res = await apiFetch("/api/copies");
  const copies = await res.json();
  container.innerHTML = `
    <div class="page-banner">
      <div>
        <h2 class="page-title">Book Copies & Inventory</h2>
        <p class="page-subtitle">Track individual physical barcodes and copy conditions.</p>
      </div>
      <button class="btn btn-primary" onclick="openModal('modal-add-copy')">+ Add Physical Copy</button>
    </div>
    <div class="grid-card">
      <div class="table-wrapper">
        <table class="data-table">
          <thead>
            <tr>
              <th>Barcode</th>
              <th>Book Title</th>
              <th>Status</th>
              <th>Condition</th>
              <th>Acquired Date</th>
            </tr>
          </thead>
          <tbody>
            ${copies.map(c => `
              <tr>
                <td><code>${c.barcode}</code></td>
                <td><strong>${c.book_title}</strong></td>
                <td><span class="badge ${c.status === 'Available' ? 'green' : (c.status === 'On Loan' ? 'blue' : 'red')}">${c.status}</span></td>
                <td>${c.condition_notes || 'Good'}</td>
                <td>${formatDate(c.acquired_date)}</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

// 3. Categories & Authors View
async function renderCategoriesAuthors(container) {
  const [catRes, autRes] = await Promise.all([apiFetch("/api/categories"), apiFetch("/api/authors")]);
  const categories = await catRes.json();
  const authors = await autRes.json();

  container.innerHTML = `
    <div class="page-banner">
      <div>
        <h2 class="page-title">Categories & Authors</h2>
        <p class="page-subtitle">Maintain classifications and author directories.</p>
      </div>
    </div>
    <div class="dashboard-grid">
      <div class="grid-card">
        <div class="card-header-row">
          <h3 class="card-title">Categories (${categories.length})</h3>
        </div>
        <div class="table-wrapper">
          <table class="data-table">
            <thead><tr><th>Name</th><th>Description</th></tr></thead>
            <tbody>
              ${categories.map(c => `<tr><td><strong>${c.name}</strong></td><td>${c.description || '-'}</td></tr>`).join('')}
            </tbody>
          </table>
        </div>
      </div>
      <div class="grid-card">
        <div class="card-header-row">
          <h3 class="card-title">Authors (${authors.length})</h3>
        </div>
        <div class="table-wrapper">
          <table class="data-table">
            <thead><tr><th>Author Name</th><th>Biography</th></tr></thead>
            <tbody>
              ${authors.map(a => `<tr><td><strong>${a.name}</strong></td><td>${a.biography || '-'}</td></tr>`).join('')}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  `;
}

// 4. Members View
async function renderMembers(container) {
  const res = await apiFetch("/api/members");
  const members = await res.json();
  container.innerHTML = `
    <div class="page-banner">
      <div>
        <h2 class="page-title">Registered Members</h2>
        <p class="page-subtitle">Member eligibility, loan limits, and status tracking.</p>
      </div>
      <button class="btn btn-primary" onclick="openModal('modal-add-member')">+ Register New Member</button>
    </div>
    <div class="grid-card">
      <div class="table-wrapper">
        <table class="data-table">
          <thead>
            <tr>
              <th>Member Code</th>
              <th>Name</th>
              <th>Email</th>
              <th>Active Loans</th>
              <th>Max Limit</th>
              <th>Unpaid Fines</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            ${members.map(m => `
              <tr>
                <td><code>${m.member_code}</code></td>
                <td><strong>${m.first_name} ${m.last_name}</strong></td>
                <td>${m.email}</td>
                <td>${m.active_loans}</td>
                <td>${m.max_books}</td>
                <td style="color:${m.outstanding_fines > 0 ? '#b91c1c' : '#15803d'}">₹${m.outstanding_fines.toFixed(2)}</td>
                <td><span class="badge ${m.is_active ? 'green' : 'red'}">${m.is_active ? 'Active' : 'Inactive'}</span></td>
                <td>
                  ${m.is_active ? `<button class="btn btn-secondary btn-sm" onclick="deactivateMember(${m.id})">Deactivate</button>` : `<span style="color:#94a3b8;font-size:0.8rem;">Archived</span>`}
                </td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

// 5. Issue & Return View
async function renderIssueReturn(container) {
  container.innerHTML = `
    <div class="page-banner">
      <div>
        <h2 class="page-title">Book Issue & Return Station</h2>
        <p class="page-subtitle">Circulation desk for issuing and receiving library items.</p>
      </div>
    </div>
    <div class="dashboard-grid">
      <div class="grid-card">
        <h3 class="card-title" style="margin-bottom:16px;">Quick Issue Book</h3>
        <form id="view-issue-form" onsubmit="handleIssueSubmit(event, 'view-issue-form')">
          <div class="form-group">
            <label class="form-label">Eligible Member <span class="req">*</span></label>
            <select class="form-control" name="member_id" id="station-issue-member" required></select>
          </div>
          <div class="form-group">
            <label class="form-label">Available Physical Copy <span class="req">*</span></label>
            <select class="form-control" name="book_copy_id" id="station-issue-copy" required></select>
          </div>
          <button type="submit" class="btn btn-primary" style="width:100%;">Confirm Issue</button>
        </form>
      </div>
      <div class="grid-card">
        <h3 class="card-title" style="margin-bottom:16px;">Process Book Return</h3>
        <form id="view-return-form" onsubmit="handleReturnSubmit(event, 'view-return-form')">
          <div class="form-group">
            <label class="form-label">Active Loan Record <span class="req">*</span></label>
            <select class="form-control" name="loan_id" id="station-return-loan" required></select>
          </div>
          <div class="form-group">
            <label class="form-label">Condition Status</label>
            <select class="form-control" name="copy_status">
              <option value="Available">Available (Good)</option>
              <option value="Damaged">Damaged</option>
              <option value="Under Maintenance">Under Maintenance</option>
              <option value="Lost">Lost</option>
            </select>
          </div>
          <button type="submit" class="btn btn-primary" style="width:100%;">Process Return</button>
        </form>
      </div>
    </div>
  `;
  await loadDropdowns();
  // Sync station dropdowns with loaded selects
  document.getElementById("station-issue-member").innerHTML = document.getElementById("issue-member-select").innerHTML;
  document.getElementById("station-issue-copy").innerHTML = document.getElementById("issue-copy-select").innerHTML;
  document.getElementById("station-return-loan").innerHTML = document.getElementById("return-loan-select").innerHTML;
}

// 6. Active Loans View
async function renderActiveLoans(container) {
  const res = await apiFetch("/api/loans/active");
  const loans = await res.json();
  container.innerHTML = `
    <div class="page-banner">
      <div>
        <h2 class="page-title">Active Loans</h2>
        <p class="page-subtitle">Current open borrow records.</p>
      </div>
      <button class="btn btn-primary" onclick="openModal('modal-issue-book')">+ Issue New Book</button>
    </div>
    <div class="grid-card">
      <div class="table-wrapper">
        <table class="data-table">
          <thead>
            <tr>
              <th>Member</th>
              <th>Book Title</th>
              <th>Barcode</th>
              <th>Issue Date</th>
              <th>Due Date</th>
              <th>Renewals</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            ${loans.map(l => `
              <tr>
                <td><strong>${l.member_name}</strong></td>
                <td>${l.book_title}</td>
                <td><code>${l.barcode}</code></td>
                <td>${formatDate(l.issue_date)}</td>
                <td>${formatDate(l.due_date)}</td>
                <td>${l.renewal_count} / ${l.max_renewals}</td>
                <td>
                  <button class="btn btn-secondary btn-sm" onclick="renewLoan(${l.id})">Renew</button>
                  <button class="btn btn-primary btn-sm" onclick="quickReturn(${l.id})">Return</button>
                </td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

// 7. Overdue Books View
async function renderOverdueBooks(container) {
  const res = await apiFetch("/api/loans/overdue");
  const loans = await res.json();
  container.innerHTML = `
    <div class="page-banner">
      <div>
        <h2 class="page-title">Overdue Books</h2>
        <p class="page-subtitle">Books exceeding due date requiring urgent return.</p>
      </div>
    </div>
    <div class="grid-card">
      <div class="table-wrapper">
        <table class="data-table">
          <thead>
            <tr>
              <th>Member Name</th>
              <th>Book Title</th>
              <th>Barcode</th>
              <th>Due Date</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            ${loans.length === 0 ? `<tr><td colspan="6" style="text-align:center;padding:24px;color:#64748b;">No overdue books!</td></tr>` :
              loans.map(l => `
                <tr>
                  <td><strong>${l.member_name}</strong></td>
                  <td>${l.book_title}</td>
                  <td><code>${l.barcode}</code></td>
                  <td class="text-danger">${formatDate(l.due_date)}</td>
                  <td><span class="badge red">Overdue</span></td>
                  <td>
                    <button class="btn btn-primary btn-sm" onclick="quickReturn(${l.id})">Process Return</button>
                  </td>
                </tr>
              `).join('')}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

// 8. Fines & Payments View
async function renderFinePayments(container) {
  const [finesRes, payRes] = await Promise.all([apiFetch("/api/fines"), apiFetch("/api/payments")]);
  const fines = await finesRes.json();
  const payments = await payRes.json();

  container.innerHTML = `
    <div class="page-banner">
      <div>
        <h2 class="page-title">Fines & Payments</h2>
        <p class="page-subtitle">Manage overdue penalties, fee collection, and waivers.</p>
      </div>
      <button class="btn btn-primary" onclick="openModal('modal-make-payment')">Record Payment</button>
    </div>
    <div class="dashboard-grid">
      <div class="grid-card">
        <h3 class="card-title" style="margin-bottom:14px;">Outstanding Fines</h3>
        <div class="table-wrapper">
          <table class="data-table">
            <thead>
              <tr>
                <th>Member</th>
                <th>Amount</th>
                <th>Paid</th>
                <th>Remaining</th>
                <th>Status</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              ${fines.map(f => `
                <tr>
                  <td><strong>${f.member_name}</strong></td>
                  <td>₹${f.fine_amount.toFixed(2)}</td>
                  <td>₹${f.paid_amount.toFixed(2)}</td>
                  <td style="color:${f.remaining > 0 ? '#b91c1c' : '#15803d'}">₹${f.remaining.toFixed(2)}</td>
                  <td><span class="badge ${f.status === 'Paid' ? 'green' : (f.status === 'Waived' ? 'blue' : 'red')}">${f.status}</span></td>
                  <td>
                    ${f.status !== 'Paid' && f.status !== 'Waived' ? `<button class="btn btn-secondary btn-sm" onclick="waiveFine(${f.id})">Waive</button>` : '-'}
                  </td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      </div>
      <div class="grid-card">
        <h3 class="card-title" style="margin-bottom:14px;">Recent Payments</h3>
        <div class="table-wrapper">
          <table class="data-table">
            <thead>
              <tr>
                <th>Member</th>
                <th>Amount</th>
                <th>Method</th>
                <th>Date</th>
                <th>Receiver</th>
              </tr>
            </thead>
            <tbody>
              ${payments.map(p => `
                <tr>
                  <td><strong>Member #${p.member_id}</strong></td>
                  <td style="color:#15803d;font-weight:700;">+₹${p.amount.toFixed(2)}</td>
                  <td>${p.payment_method}</td>
                  <td>${formatDate(p.payment_date)}</td>
                  <td>${p.receiver_name}</td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  `;
}

// 9. Reservations View
async function renderReservations(container) {
  const res = await apiFetch("/api/reservations");
  const reservations = await res.json();
  container.innerHTML = `
    <div class="page-banner">
      <div>
        <h2 class="page-title">Book Reservations</h2>
        <p class="page-subtitle">Waiting queue and book reservations.</p>
      </div>
      <button class="btn btn-primary" onclick="openModal('modal-add-reservation')">+ Place Reservation</button>
    </div>
    <div class="grid-card">
      <div class="table-wrapper">
        <table class="data-table">
          <thead>
            <tr>
              <th>Queue #</th>
              <th>Book Title</th>
              <th>Member Name</th>
              <th>Reserved On</th>
              <th>Expires On</th>
              <th>Status</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            ${reservations.length === 0 ? `<tr><td colspan="7" style="text-align:center;padding:24px;color:#64748b;">No active reservations</td></tr>` :
              reservations.map(r => `
                <tr>
                  <td><strong>#${r.queue_position}</strong></td>
                  <td>${r.book_title}</td>
                  <td>${r.member_name}</td>
                  <td>${formatDate(r.reservation_date)}</td>
                  <td>${formatDate(r.expiry_date)}</td>
                  <td><span class="badge ${r.status === 'Active' ? 'blue' : (r.status === 'Fulfilled' ? 'green' : 'red')}">${r.status}</span></td>
                  <td>
                    ${r.status === 'Active' ? `<button class="btn btn-secondary btn-sm" onclick="cancelReservation(${r.id})">Cancel</button>` : '-'}
                  </td>
                </tr>
              `).join('')}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

// 10. Borrowing History View
async function renderBorrowingHistory(container) {
  const res = await apiFetch("/api/loans/history");
  const history = await res.json();
  container.innerHTML = `
    <div class="page-banner">
      <div>
        <h2 class="page-title">Borrowing History</h2>
        <p class="page-subtitle">Complete historical archive of all issues and returns.</p>
      </div>
    </div>
    <div class="grid-card">
      <div class="table-wrapper">
        <table class="data-table">
          <thead>
            <tr>
              <th>Loan #</th>
              <th>Member</th>
              <th>Book Title</th>
              <th>Issued On</th>
              <th>Due Date</th>
              <th>Returned On</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            ${history.map(h => `
              <tr>
                <td><code>#${h.id}</code></td>
                <td><strong>${h.member_name}</strong></td>
                <td>${h.book_title}</td>
                <td>${formatDate(h.issue_date)}</td>
                <td>${formatDate(h.due_date)}</td>
                <td>${formatDate(h.return_date)}</td>
                <td><span class="badge ${h.is_returned ? 'green' : 'blue'}">${h.is_returned ? 'Returned' : 'Active'}</span></td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

// 11. Renewals View
async function renderRenewals(container) {
  const res = await apiFetch("/api/loans/active");
  const loans = await res.json();
  container.innerHTML = `
    <div class="page-banner">
      <div>
        <h2 class="page-title">Loan Renewals</h2>
        <p class="page-subtitle">Manage extension requests and renewal quotas.</p>
      </div>
    </div>
    <div class="grid-card">
      <div class="table-wrapper">
        <table class="data-table">
          <thead>
            <tr>
              <th>Member</th>
              <th>Book Title</th>
              <th>Current Due Date</th>
              <th>Renewals Used</th>
              <th>Remaining Quota</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            ${loans.map(l => `
              <tr>
                <td><strong>${l.member_name}</strong></td>
                <td>${l.book_title}</td>
                <td>${formatDate(l.due_date)}</td>
                <td>${l.renewal_count}</td>
                <td>${Math.max(0, l.max_renewals - l.renewal_count)}</td>
                <td>
                  <button class="btn btn-secondary btn-sm" ${l.renewal_count >= l.max_renewals ? 'disabled' : ''} onclick="renewLoan(${l.id})">
                    ${l.renewal_count >= l.max_renewals ? 'Max Renewals Reached' : 'Renew Loan'}
                  </button>
                </td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

// 12. User Accounts View
async function renderUserAccounts(container) {
  const res = await apiFetch("/api/auth/users");
  if (!res.ok) {
    container.innerHTML = `<div style="padding:24px;color:#b91c1c;">Admin credentials required to view staff accounts.</div>`;
    return;
  }
  const users = await res.json();
  container.innerHTML = `
    <div class="page-banner">
      <div>
        <h2 class="page-title">Librarians & User Accounts</h2>
        <p class="page-subtitle">Manage librarian access, roles, and administrative users.</p>
      </div>
    </div>
    <div class="grid-card">
      <div class="table-wrapper">
        <table class="data-table">
          <thead>
            <tr>
              <th>Username</th>
              <th>Full Name</th>
              <th>Email</th>
              <th>Role</th>
              <th>Status</th>
              <th>Joined Date</th>
            </tr>
          </thead>
          <tbody>
            ${users.map(u => `
              <tr>
                <td><code>${u.username}</code></td>
                <td><strong>${u.full_name}</strong></td>
                <td>${u.email}</td>
                <td><span class="badge blue">${u.role}</span></td>
                <td><span class="badge ${u.is_active ? 'green' : 'red'}">${u.is_active ? 'Active' : 'Inactive'}</span></td>
                <td>${formatDate(u.created_at)}</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

// 13. Roles & Permissions View
function renderRolesPermissions(container) {
  container.innerHTML = `
    <div class="page-banner">
      <div>
        <h2 class="page-title">Roles & Permissions Matrix</h2>
        <p class="page-subtitle">Security access levels and system operation privileges.</p>
      </div>
    </div>
    <div class="grid-card">
      <div class="table-wrapper">
        <table class="data-table">
          <thead>
            <tr>
              <th>Permission / Capability</th>
              <th>Administrator</th>
              <th>Librarian</th>
              <th>Read-Only</th>
            </tr>
          </thead>
          <tbody>
            <tr><td>View Catalog, Loans & Inventory</td><td><span class="badge green">Allowed</span></td><td><span class="badge green">Allowed</span></td><td><span class="badge green">Allowed</span></td></tr>
            <tr><td>Create / Edit Books & Physical Copies</td><td><span class="badge green">Allowed</span></td><td><span class="badge green">Allowed</span></td><td><span class="badge red">Denied</span></td></tr>
            <tr><td>Register & Deactivate Members</td><td><span class="badge green">Allowed</span></td><td><span class="badge green">Allowed</span></td><td><span class="badge red">Denied</span></td></tr>
            <tr><td>Issue, Return & Renew Loans</td><td><span class="badge green">Allowed</span></td><td><span class="badge green">Allowed</span></td><td><span class="badge red">Denied</span></td></tr>
            <tr><td>Record Fine Payments</td><td><span class="badge green">Allowed</span></td><td><span class="badge green">Allowed</span></td><td><span class="badge red">Denied</span></td></tr>
            <tr><td>Waive Late Fines</td><td><span class="badge green">Allowed</span></td><td><span class="badge red">Denied</span></td><td><span class="badge red">Denied</span></td></tr>
            <tr><td>Manage Staff User Accounts</td><td><span class="badge green">Allowed</span></td><td><span class="badge red">Denied</span></td><td><span class="badge red">Denied</span></td></tr>
            <tr><td>Inspect System Audit Logs</td><td><span class="badge green">Allowed</span></td><td><span class="badge red">Denied</span></td><td><span class="badge red">Denied</span></td></tr>
            <tr><td>Modify System Settings</td><td><span class="badge green">Allowed</span></td><td><span class="badge red">Denied</span></td><td><span class="badge red">Denied</span></td></tr>
          </tbody>
        </table>
      </div>
    </div>
  `;
}

// 14. Reports & Analytics View
async function renderReportsAnalytics(container) {
  const res = await apiFetch("/api/dashboard/reports");
  const rep = await res.json();
  container.innerHTML = `
    <div class="page-banner">
      <div>
        <h2 class="page-title">Reports & Analytics</h2>
        <p class="page-subtitle">Real-time statistics and borrowing metrics.</p>
      </div>
    </div>
    <div class="dashboard-grid">
      <div class="grid-card">
        <h3 class="card-title">Circulation Summary</h3>
        <p style="margin-top:14px;color:#64748b;">Loans Issued This Month: <strong>${rep.loans_this_month}</strong></p>
        <p style="margin-top:8px;color:#64748b;">Returns Processed: <strong>${rep.returns_this_month}</strong></p>
        <p style="margin-top:8px;color:#64748b;">Total Fines Collected: <strong>₹${rep.total_fines_collected.toFixed(2)}</strong></p>
        <p style="margin-top:8px;color:#64748b;">Outstanding Fine Balance: <strong>₹${rep.outstanding_fines.toFixed(2)}</strong></p>
      </div>
      <div class="grid-card">
        <h3 class="card-title">Category Distribution</h3>
        <ul style="margin-top:14px;list-style:none;padding:0;">
          ${rep.category_distribution.map(c => `
            <li style="display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #f1f5f9;">
              <span>${c.name}</span>
              <strong>${c.count} titles</strong>
            </li>
          `).join('')}
        </ul>
      </div>
    </div>
  `;
}

// 15. Audit Logs View
async function renderAuditLogs(container) {
  const res = await apiFetch("/api/audit");
  if (!res.ok) {
    container.innerHTML = `<div style="padding:24px;color:#b91c1c;">Admin privileges required to view audit logs.</div>`;
    return;
  }
  const logs = await res.json();
  container.innerHTML = `
    <div class="page-banner">
      <div>
        <h2 class="page-title">System Audit Logs</h2>
        <p class="page-subtitle">Immutable log of security and circulation events.</p>
      </div>
    </div>
    <div class="grid-card">
      <div class="table-wrapper">
        <table class="data-table">
          <thead>
            <tr>
              <th>Timestamp</th>
              <th>Action</th>
              <th>Entity</th>
              <th>User</th>
              <th>Details</th>
            </tr>
          </thead>
          <tbody>
            ${logs.map(l => `
              <tr>
                <td>${new Date(l.created_at).toLocaleString()}</td>
                <td><span class="badge blue">${l.action}</span></td>
                <td>${l.entity_type} #${l.entity_id || '-'}</td>
                <td><strong>${l.user_name || 'System'}</strong></td>
                <td><code>${l.details || '-'}</code></td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

// 16. System Settings View
async function renderSystemSettings(container) {
  const res = await apiFetch("/api/dashboard/settings");
  const settings = await res.json();
  container.innerHTML = `
    <div class="page-banner">
      <div>
        <h2 class="page-title">System Settings</h2>
        <p class="page-subtitle">Circulation rules, fine parameters, and loan durations.</p>
      </div>
    </div>
    <div class="grid-card" style="max-width:680px;">
      <form onsubmit="handleUpdateSettings(event)">
        <div class="form-row">
          <div class="form-group">
            <label class="form-label">Default Loan Duration (Days)</label>
            <input type="number" name="default_loan_days" class="form-control" value="${settings.default_loan_days}" required>
          </div>
          <div class="form-group">
            <label class="form-label">Daily Overdue Fine (₹/Day)</label>
            <input type="number" step="0.5" name="fine_per_day" class="form-control" value="${settings.fine_per_day}" required>
          </div>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label class="form-label">Grace Period (Days)</label>
            <input type="number" name="grace_period_days" class="form-control" value="${settings.grace_period_days}" required>
          </div>
          <div class="form-group">
            <label class="form-label">Max Renewals Allowed</label>
            <input type="number" name="max_renewals" class="form-control" value="${settings.max_renewals}" required>
          </div>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label class="form-label">Reservation Expiry (Days)</label>
            <input type="number" name="reservation_expiry_days" class="form-control" value="${settings.reservation_expiry_days}" required>
          </div>
          <div class="form-group">
            <label class="form-label">Max Unpaid Fine Limit (₹)</label>
            <input type="number" step="10" name="max_unpaid_fine_limit" class="form-control" value="${settings.max_unpaid_fine_limit}" required>
          </div>
        </div>
        <button type="submit" class="btn btn-primary" style="margin-top:12px;">Save Settings</button>
      </form>
    </div>
  `;
}

async function handleUpdateSettings(e) {
  e.preventDefault();
  const form = e.target;
  const payload = {
    default_loan_days: parseInt(form.default_loan_days.value),
    fine_per_day: parseFloat(form.fine_per_day.value),
    grace_period_days: parseInt(form.grace_period_days.value),
    max_renewals: parseInt(form.max_renewals.value),
    reservation_expiry_days: parseInt(form.reservation_expiry_days.value),
    max_unpaid_fine_limit: parseFloat(form.max_unpaid_fine_limit.value),
  };

  try {
    const res = await apiFetch("/api/dashboard/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Failed to update settings");
    }
    showToast("Settings updated successfully!");
  } catch (err) {
    showToast(err.message, "error");
  }
}

// ==========================================================================
// Form Actions & Workflow Handlers (Create Book, Multi-Item, Drag & Drop)
// ==========================================================================

const bookFormState = {
  selectedAuthorIds: new Set(),
  selectedCategoryIds: new Set(),
  uploadedFiles: [], // [{original_name, filename, url, size}]
  batchFile: null,
};

function formatApiError(data) {
  if (!data) return "An unexpected error occurred.";
  if (typeof data.detail === "string") return data.detail;
  if (Array.isArray(data.detail)) {
    return data.detail.map(d => {
      const field = d.loc && d.loc.length > 0 ? d.loc[d.loc.length - 1] : "";
      const fieldName = field ? field.charAt(0).toUpperCase() + field.slice(1).replace(/_/g, " ") + ": " : "";
      return fieldName + d.msg;
    }).join("; ");
  }
  return data.message || "Failed to process request.";
}

// --------------------------------------------------------------------------
// Multi-Item Tag Selectors for Authors and Categories
// --------------------------------------------------------------------------

function renderAuthorMultiSelect() {
  const chipsContainer = document.getElementById("selected-authors-chips");
  const cloudContainer = document.getElementById("author-pill-cloud");
  if (!chipsContainer || !cloudContainer) return;

  // 1. Render Selected Chips
  if (bookFormState.selectedAuthorIds.size === 0) {
    chipsContainer.innerHTML = `<span class="placeholder-chip">Click authors below to select...</span>`;
  } else {
    chipsContainer.innerHTML = Array.from(bookFormState.selectedAuthorIds).map(id => {
      const author = state.authors.find(a => a.id === id);
      const name = author ? author.name : `Author #${id}`;
      return `
        <span class="chip-item">
          <span>${name}</span>
          <span class="chip-remove" onclick="removeAuthor(${id})" title="Remove author">&times;</span>
        </span>
      `;
    }).join("");
  }

  // 2. Render Available Cloud Pills
  cloudContainer.innerHTML = state.authors.map(a => {
    const isSelected = bookFormState.selectedAuthorIds.has(a.id);
    return `
      <span class="cloud-pill ${isSelected ? 'selected' : ''}" onclick="toggleAuthorSelect(${a.id})">
        ${isSelected ? '✓ ' : '+ '}${a.name}
      </span>
    `;
  }).join("");
}

function toggleAuthorSelect(authorId) {
  if (bookFormState.selectedAuthorIds.has(authorId)) {
    bookFormState.selectedAuthorIds.delete(authorId);
  } else {
    bookFormState.selectedAuthorIds.add(authorId);
  }
  document.getElementById("author-error").innerText = "";
  renderAuthorMultiSelect();
}

function removeAuthor(authorId) {
  bookFormState.selectedAuthorIds.delete(authorId);
  renderAuthorMultiSelect();
}

function toggleQuickAddAuthor() {
  const panel = document.getElementById("quick-add-author-panel");
  if (!panel) return;
  panel.style.display = panel.style.display === "none" ? "flex" : "none";
  if (panel.style.display === "flex") {
    document.getElementById("quick-author-name").focus();
  }
}

async function saveQuickAuthor() {
  const input = document.getElementById("quick-author-name");
  const name = input ? input.value.trim() : "";
  if (!name) return;

  try {
    const res = await apiFetch("/api/authors", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    const newAuthor = await res.json();
    if (!res.ok) throw new Error(formatApiError(newAuthor));

    state.authors.push(newAuthor);
    bookFormState.selectedAuthorIds.add(newAuthor.id);
    input.value = "";
    document.getElementById("quick-add-author-panel").style.display = "none";
    renderAuthorMultiSelect();
    showToast(`Author '${newAuthor.name}' added and selected!`);
  } catch (err) {
    showToast(err.message, "error");
  }
}

function renderCategoryMultiSelect() {
  const chipsContainer = document.getElementById("selected-categories-chips");
  const cloudContainer = document.getElementById("category-pill-cloud");
  if (!chipsContainer || !cloudContainer) return;

  // 1. Render Selected Chips
  if (bookFormState.selectedCategoryIds.size === 0) {
    chipsContainer.innerHTML = `<span class="placeholder-chip">Click categories below to select...</span>`;
  } else {
    chipsContainer.innerHTML = Array.from(bookFormState.selectedCategoryIds).map(id => {
      const cat = state.categories.find(c => c.id === id);
      const name = cat ? cat.name : `Category #${id}`;
      return `
        <span class="chip-item">
          <span>${name}</span>
          <span class="chip-remove" onclick="removeCategory(${id})" title="Remove category">&times;</span>
        </span>
      `;
    }).join("");
  }

  // 2. Render Available Cloud Pills
  cloudContainer.innerHTML = state.categories.map(c => {
    const isSelected = bookFormState.selectedCategoryIds.has(c.id);
    return `
      <span class="cloud-pill ${isSelected ? 'selected' : ''}" onclick="toggleCategorySelect(${c.id})">
        ${isSelected ? '✓ ' : '+ '}${c.name}
      </span>
    `;
  }).join("");
}

function toggleCategorySelect(catId) {
  if (bookFormState.selectedCategoryIds.has(catId)) {
    bookFormState.selectedCategoryIds.delete(catId);
  } else {
    bookFormState.selectedCategoryIds.add(catId);
  }
  document.getElementById("category-error").innerText = "";
  renderCategoryMultiSelect();
}

function removeCategory(catId) {
  bookFormState.selectedCategoryIds.delete(catId);
  renderCategoryMultiSelect();
}

function toggleQuickAddCategory() {
  const panel = document.getElementById("quick-add-category-panel");
  if (!panel) return;
  panel.style.display = panel.style.display === "none" ? "flex" : "none";
  if (panel.style.display === "flex") {
    document.getElementById("quick-category-name").focus();
  }
}

async function saveQuickCategory() {
  const input = document.getElementById("quick-category-name");
  const name = input ? input.value.trim() : "";
  if (!name) return;

  try {
    const res = await apiFetch("/api/categories", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    const newCat = await res.json();
    if (!res.ok) throw new Error(formatApiError(newCat));

    state.categories.push(newCat);
    bookFormState.selectedCategoryIds.add(newCat.id);
    input.value = "";
    document.getElementById("quick-add-category-panel").style.display = "none";
    renderCategoryMultiSelect();
    showToast(`Category '${newCat.name}' added and selected!`);
  } catch (err) {
    showToast(err.message, "error");
  }
}

// --------------------------------------------------------------------------
// Drag and Drop File Upload
// --------------------------------------------------------------------------

function setupBookDropzone() {
  const dropzone = document.getElementById("book-dropzone");
  if (!dropzone) return;

  ["dragenter", "dragover"].forEach(eventName => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.add("drag-over");
    });
  });

  ["dragleave", "drop"].forEach(eventName => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.remove("drag-over");
    });
  });

  dropzone.addEventListener("drop", async (e) => {
    const files = e.dataTransfer.files;
    if (files && files.length > 0) {
      await uploadBookFiles(Array.from(files));
    }
  });
}

async function handleFileSelect(e) {
  const files = e.target.files;
  if (files && files.length > 0) {
    await uploadBookFiles(Array.from(files));
  }
}

async function uploadBookFiles(files) {
  if (!files || files.length === 0) return;
  const formData = new FormData();
  files.forEach(f => formData.append("files", f));

  showToast(`Uploading ${files.length} file(s)...`);

  try {
    const res = await apiFetch("/api/books/upload", {
      method: "POST",
      body: formData,
    });
    const data = await res.json();
    if (!res.ok) throw new Error(formatApiError(data));

    data.uploaded.forEach(item => {
      bookFormState.uploadedFiles.push(item);
    });

    renderUploadedFilesList();
    showToast(`Successfully uploaded ${data.uploaded.length} file(s)!`);
  } catch (err) {
    showToast(err.message, "error");
  }
}

function renderUploadedFilesList() {
  const container = document.getElementById("book-uploaded-files-list");
  if (!container) return;

  if (bookFormState.uploadedFiles.length === 0) {
    container.innerHTML = "";
    return;
  }

  container.innerHTML = bookFormState.uploadedFiles.map((file, idx) => {
    const isImg = file.url.match(/\.(jpeg|jpg|gif|png|webp)$/i);
    const sizeKB = (file.size / 1024).toFixed(1);
    return `
      <div class="uploaded-file-item">
        <div class="file-item-left">
          ${isImg ? `<img src="${file.url}" class="file-thumb-preview" alt="Preview">` : `
            <svg style="width:24px;height:24px;color:#3b82f6;" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"/>
            </svg>
          `}
          <div>
            <div style="font-weight:600;color:#1e293b;">${file.original_name}</div>
            <div style="font-size:0.72rem;color:#64748b;">${sizeKB} KB ${idx === 0 && isImg ? '· (Primary Cover)' : ''}</div>
          </div>
        </div>
        <span class="file-item-remove" onclick="removeUploadedFile(${idx})" title="Remove file">&times;</span>
      </div>
    `;
  }).join("");
}

function removeUploadedFile(index) {
  bookFormState.uploadedFiles.splice(index, 1);
  renderUploadedFilesList();
}

// --------------------------------------------------------------------------
// Batch Import Drag & Drop Handling
// --------------------------------------------------------------------------

function setupBatchImportDropzone() {
  const dropzone = document.getElementById("batch-import-dropzone");
  if (!dropzone) return;

  ["dragenter", "dragover"].forEach(eventName => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.add("drag-over");
    });
  });

  ["dragleave", "drop"].forEach(eventName => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.remove("drag-over");
    });
  });

  dropzone.addEventListener("drop", (e) => {
    const files = e.dataTransfer.files;
    if (files && files.length > 0) {
      setBatchImportFile(files[0]);
    }
  });
}

function handleBatchFileSelect(e) {
  if (e.target.files && e.target.files.length > 0) {
    setBatchImportFile(e.target.files[0]);
  }
}

function setBatchImportFile(file) {
  bookFormState.batchFile = file;
  const infoEl = document.getElementById("batch-file-info");
  const btn = document.getElementById("btn-run-batch-import");
  if (infoEl) {
    infoEl.innerHTML = `
      <div class="uploaded-file-item">
        <div style="font-weight:600;">Selected: ${file.name} (${(file.size / 1024).toFixed(1)} KB)</div>
        <span class="file-item-remove" onclick="clearBatchImportFile()">&times;</span>
      </div>
    `;
  }
  if (btn) btn.disabled = false;
}

function clearBatchImportFile() {
  bookFormState.batchFile = null;
  const infoEl = document.getElementById("batch-file-info");
  const btn = document.getElementById("btn-run-batch-import");
  if (infoEl) infoEl.innerHTML = "";
  if (btn) btn.disabled = true;
}

async function submitBatchImport() {
  if (!bookFormState.batchFile) return;
  const alertEl = document.getElementById("batch-import-alert");
  const btn = document.getElementById("btn-run-batch-import");

  const formData = new FormData();
  formData.append("file", bookFormState.batchFile);

  btn.disabled = true;
  btn.innerText = "Importing...";
  if (alertEl) alertEl.style.display = "none";

  try {
    const res = await apiFetch("/api/books/batch-import", {
      method: "POST",
      body: formData,
    });
    const data = await res.json();
    if (!res.ok) throw new Error(formatApiError(data));

    if (alertEl) {
      alertEl.className = "form-alert success";
      alertEl.innerText = `Successfully imported ${data.imported_count} book(s)! (${data.failed_count} errors)`;
      alertEl.style.display = "flex";
    }

    showToast(`Batch import complete: ${data.imported_count} books imported.`);
    setTimeout(() => {
      closeModal("modal-batch-import");
      clearBatchImportFile();
    }, 1500);

    await fetchDashboard();
    await loadDropdowns();
    if (state.currentView !== "dashboard") switchView(state.currentView);
  } catch (err) {
    if (alertEl) {
      alertEl.className = "form-alert error";
      alertEl.innerText = err.message;
      alertEl.style.display = "flex";
    }
    showToast(err.message, "error");
  } finally {
    btn.disabled = false;
    btn.innerText = "Start Import";
  }
}

// --------------------------------------------------------------------------
// Create New Book Entry Form Handler
// --------------------------------------------------------------------------

async function handleAddBook(e) {
  e.preventDefault();
  const form = e.target;
  const alertBox = document.getElementById("add-book-alert");
  const saveBtn = document.getElementById("btn-save-book");

  // 1. Clear previous validation states
  alertBox.style.display = "none";
  alertBox.className = "form-alert";
  alertBox.innerText = "";
  document.querySelectorAll("#modal-add-book .field-error").forEach(el => el.innerText = "");
  document.querySelectorAll("#modal-add-book .form-control").forEach(el => el.classList.remove("is-invalid"));

  const titleInput = document.getElementById("add-book-title");
  const isbnInput = document.getElementById("add-book-isbn");
  const yearInput = document.getElementById("add-book-year");

  const title = titleInput.value.trim();
  const rawIsbn = isbnInput.value.trim();
  const rawYear = yearInput.value.trim();
  let hasErrors = false;

  // 2. Validate Book Title
  if (!title) {
    titleInput.classList.add("is-invalid");
    document.getElementById("title-error").innerText = "Book title is required.";
    hasErrors = true;
  }

  // 3. Validate ISBN
  let cleanIsbn = null;
  if (rawIsbn) {
    cleanIsbn = rawIsbn.replace(/[- ]/g, "");
    if (cleanIsbn.length === 10) {
      if (!/^\d{9}[\dXx]$/.test(cleanIsbn)) {
        isbnInput.classList.add("is-invalid");
        document.getElementById("isbn-error").innerText = "Invalid ISBN-10: Must be 9 digits followed by a digit or 'X'.";
        hasErrors = true;
      }
    } else if (cleanIsbn.length === 13) {
      if (!/^\d{13}$/.test(cleanIsbn)) {
        isbnInput.classList.add("is-invalid");
        document.getElementById("isbn-error").innerText = "Invalid ISBN-13: Must contain exactly 13 numeric digits.";
        hasErrors = true;
      }
    } else {
      isbnInput.classList.add("is-invalid");
      document.getElementById("isbn-error").innerText = "ISBN must be either 10 or 13 digits (excluding hyphens).";
      hasErrors = true;
    }
  }

  // 4. Validate Published Year
  let publishedYear = null;
  if (rawYear) {
    publishedYear = parseInt(rawYear);
    if (isNaN(publishedYear) || publishedYear < 1000 || publishedYear > 2100) {
      yearInput.classList.add("is-invalid");
      document.getElementById("year-error").innerText = "Published year must be between 1000 and 2100.";
      hasErrors = true;
    }
  }

  // 5. Validate Authors Selection
  const authorIds = Array.from(bookFormState.selectedAuthorIds);
  if (authorIds.length === 0) {
    document.getElementById("author-error").innerText = "Please select or add at least one author.";
    hasErrors = true;
  }

  // 6. Validate Categories Selection
  const categoryIds = Array.from(bookFormState.selectedCategoryIds);
  if (categoryIds.length === 0) {
    document.getElementById("category-error").innerText = "Please select or add at least one category.";
    hasErrors = true;
  }

  if (hasErrors) {
    alertBox.className = "form-alert error";
    alertBox.innerText = "Please correct the highlighted fields before submitting.";
    alertBox.style.display = "flex";
    return;
  }

  // Find primary cover image if uploaded
  const primaryCover = bookFormState.uploadedFiles.find(f => f.url.match(/\.(jpeg|jpg|gif|png|webp)$/i));

  const payload = {
    title: title,
    isbn: cleanIsbn || null,
    publisher: form.publisher.value.trim() || null,
    published_year: publishedYear,
    language: form.language.value.trim() || "English",
    cover_image: primaryCover ? primaryCover.url : null,
    author_ids: authorIds,
    category_ids: categoryIds,
  };

  // 7. Submit to Backend
  saveBtn.disabled = true;
  saveBtn.innerText = "Saving Book...";

  try {
    const res = await apiFetch("/api/books", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(formatApiError(data));
    }

    // Success response
    alertBox.className = "form-alert success";
    alertBox.innerText = `Book '${data.title}' has been successfully added to the catalog!`;
    alertBox.style.display = "flex";
    showToast(`Book '${data.title}' added successfully!`);

    // Reset form & state
    setTimeout(() => {
      closeModal("modal-add-book");
      form.reset();
      bookFormState.selectedAuthorIds.clear();
      bookFormState.selectedCategoryIds.clear();
      bookFormState.uploadedFiles = [];
      renderAuthorMultiSelect();
      renderCategoryMultiSelect();
      renderUploadedFilesList();
      alertBox.style.display = "none";
    }, 800);

    await fetchDashboard();
    await loadDropdowns();
    if (state.currentView !== "dashboard") switchView(state.currentView);
  } catch (err) {
    alertBox.className = "form-alert error";
    alertBox.innerText = err.message;
    alertBox.style.display = "flex";
    showToast(err.message, "error");
  } finally {
    saveBtn.disabled = false;
    saveBtn.innerText = "Save Book Entry";
  }
}

async function handleAddMember(e) {
  e.preventDefault();
  const form = e.target;
  const payload = {
    first_name: form.first_name.value.trim(),
    last_name: form.last_name.value.trim(),
    email: form.email.value.trim(),
    phone: form.phone.value.trim() || null,
    membership_type: form.membership_type.value,
  };

  try {
    const res = await apiFetch("/api/members", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Failed to register member");

    showToast(`Member registered: ${data.member_code} (${data.first_name})`);
    closeModal("modal-add-member");
    form.reset();
    await fetchDashboard();
    await loadDropdowns();
    if (state.currentView !== "dashboard") switchView(state.currentView);
  } catch (err) {
    showToast(err.message, "error");
  }
}

async function handleAddCopy(e) {
  e.preventDefault();
  const form = e.target;
  const payload = {
    book_id: parseInt(form.book_id.value),
    barcode: form.barcode.value.trim(),
    condition_notes: form.condition_notes.value.trim() || null,
  };

  try {
    const res = await apiFetch("/api/copies", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Failed to add copy");

    showToast(`Copy added with barcode: ${data.barcode}`);
    closeModal("modal-add-copy");
    form.reset();
    await fetchDashboard();
    await loadDropdowns();
    if (state.currentView !== "dashboard") switchView(state.currentView);
  } catch (err) {
    showToast(err.message, "error");
  }
}

async function handleIssueSubmit(e, formId = "form-issue-book") {
  if (e) e.preventDefault();
  const form = document.getElementById(formId);
  const payload = {
    member_id: parseInt(form.member_id.value),
    book_copy_id: parseInt(form.book_copy_id.value),
  };

  try {
    const res = await apiFetch("/api/loans/issue", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Failed to issue book");

    showToast(`Book issued! Due date: ${formatDate(data.due_date)}`);
    closeModal("modal-issue-book");
    form.reset();
    await fetchDashboard();
    await loadDropdowns();
    if (state.currentView !== "dashboard") switchView(state.currentView);
  } catch (err) {
    showToast(err.message, "error");
  }
}

async function handleReturnSubmit(e, formId = "form-return-book") {
  if (e) e.preventDefault();
  const form = document.getElementById(formId);
  const payload = {
    loan_id: parseInt(form.loan_id.value),
    copy_status: form.copy_status.value,
  };

  try {
    const res = await apiFetch("/api/loans/return", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Failed to return book");

    showToast(data.message || "Book returned successfully!");
    closeModal("modal-return-book");
    form.reset();
    await fetchDashboard();
    await loadDropdowns();
    if (state.currentView !== "dashboard") switchView(state.currentView);
  } catch (err) {
    showToast(err.message, "error");
  }
}

async function handleMakePayment(e) {
  e.preventDefault();
  const form = e.target;
  const payload = {
    fine_id: parseInt(form.fine_id.value),
    amount: parseFloat(form.amount.value),
    payment_method: form.payment_method.value,
  };

  try {
    const res = await apiFetch("/api/payments", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Payment failed");

    showToast(`Payment of ₹${data.amount.toFixed(2)} recorded!`);
    closeModal("modal-make-payment");
    form.reset();
    await fetchDashboard();
    await loadDropdowns();
    if (state.currentView !== "dashboard") switchView(state.currentView);
  } catch (err) {
    showToast(err.message, "error");
  }
}

async function handleAddReservation(e) {
  e.preventDefault();
  const form = e.target;
  const payload = {
    book_id: parseInt(form.book_id.value),
    member_id: parseInt(form.member_id.value),
  };

  try {
    const res = await apiFetch("/api/reservations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Reservation failed");

    showToast(`Reserved! Queue position: #${data.queue_position}`);
    closeModal("modal-add-reservation");
    form.reset();
    await fetchDashboard();
    await loadDropdowns();
    if (state.currentView !== "dashboard") switchView(state.currentView);
  } catch (err) {
    showToast(err.message, "error");
  }
}

async function renewLoan(loanId) {
  try {
    const res = await apiFetch("/api/loans/renew", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ loan_id: loanId }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Failed to renew loan");

    showToast(`Loan renewed! New due date: ${formatDate(data.due_date)}`);
    await fetchDashboard();
    await loadDropdowns();
    if (state.currentView !== "dashboard") switchView(state.currentView);
  } catch (err) {
    showToast(err.message, "error");
  }
}

async function quickReturn(loanId) {
  try {
    const res = await apiFetch("/api/loans/return", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ loan_id: loanId, copy_status: "Available" }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Return failed");

    showToast(data.message || "Book returned successfully!");
    await fetchDashboard();
    await loadDropdowns();
    if (state.currentView !== "dashboard") switchView(state.currentView);
  } catch (err) {
    showToast(err.message, "error");
  }
}

async function waiveFine(fineId) {
  const reason = prompt("Enter waiver reason (e.g. Director approval):");
  if (!reason) return;

  try {
    const res = await apiFetch(`/api/fines/${fineId}/waive`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reason }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Waive failed");

    showToast(`Fine #${fineId} waived`);
    await fetchDashboard();
    await loadDropdowns();
    if (state.currentView !== "dashboard") switchView(state.currentView);
  } catch (err) {
    showToast(err.message, "error");
  }
}

async function deactivateMember(memberId) {
  if (!confirm("Are you sure you want to deactivate this member? Their borrowing history will be preserved.")) return;
  try {
    const res = await apiFetch(`/api/members/${memberId}/deactivate`, { method: "POST" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Failed to deactivate member");

    showToast(`Member deactivated`);
    await fetchDashboard();
    await loadDropdowns();
    if (state.currentView !== "dashboard") switchView(state.currentView);
  } catch (err) {
    showToast(err.message, "error");
  }
}

async function archiveBook(bookId) {
  if (!confirm("Archive/delete this book? If it has historical loans, it will be safely archived.")) return;
  try {
    const res = await apiFetch(`/api/books/${bookId}`, { method: "DELETE" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Failed to delete book");

    showToast(data.message || "Book processed");
    await fetchDashboard();
    await loadDropdowns();
    if (state.currentView !== "dashboard") switchView(state.currentView);
  } catch (err) {
    showToast(err.message, "error");
  }
}

async function cancelReservation(reservationId) {
  try {
    const res = await apiFetch(`/api/reservations/${reservationId}/cancel`, { method: "POST" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Cancel failed");

    showToast("Reservation cancelled");
    if (state.currentView !== "dashboard") switchView(state.currentView);
  } catch (err) {
    showToast(err.message, "error");
  }
}

// ==========================================================================
// Search & Filter Integration
// ==========================================================================

// ==========================================================================
// Search & Filter Integration (Instant Dropdown & View Filtering)
// ==========================================================================

let searchDebounceTimer = null;
let currentHighlightedSearchIndex = -1;

function setupGlobalSearch() {
  const searchInput = document.getElementById("global-search");
  const clearBtn = document.getElementById("search-clear-btn");
  const dropdown = document.getElementById("global-search-dropdown");
  if (!searchInput) return;

  // Real-time input listener with debounced backend query + in-page filtering
  searchInput.addEventListener("input", (e) => {
    const query = e.target.value.trim();

    if (clearBtn) {
      clearBtn.style.display = query.length > 0 ? "flex" : "none";
    }

    // 1. In-page active table filtering immediately for instant responsiveness
    filterActiveTableRows(query.toLowerCase());

    // 2. Debounced API search for global dropdown results across books, members, copies
    clearTimeout(searchDebounceTimer);
    if (!query) {
      if (dropdown) dropdown.style.display = "none";
      return;
    }

    searchDebounceTimer = setTimeout(async () => {
      await executeGlobalSearch(query);
    }, 180);
  });

  // Keyboard navigation & submission
  searchInput.addEventListener("keydown", (e) => {
    const items = document.querySelectorAll(".search-item");

    if (e.key === "ArrowDown") {
      e.preventDefault();
      if (items.length === 0) return;
      currentHighlightedSearchIndex = (currentHighlightedSearchIndex + 1) % items.length;
      updateSearchHighlight(items);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      if (items.length === 0) return;
      currentHighlightedSearchIndex = (currentHighlightedSearchIndex - 1 + items.length) % items.length;
      updateSearchHighlight(items);
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (currentHighlightedSearchIndex >= 0 && items[currentHighlightedSearchIndex]) {
        items[currentHighlightedSearchIndex].click();
      } else {
        // If query entered, filter or navigate to catalog
        const query = searchInput.value.trim();
        if (query) {
          if (dropdown) dropdown.style.display = "none";
          if (state.currentView === "dashboard") {
            switchView("book-catalog");
            setTimeout(() => filterActiveTableRows(query.toLowerCase()), 200);
          }
        }
      }
    } else if (e.key === "Escape") {
      if (dropdown) dropdown.style.display = "none";
      searchInput.blur();
    }
  });

  // Close dropdown on click outside
  document.addEventListener("click", (e) => {
    if (!e.target.closest(".search-box-wrapper")) {
      if (dropdown) dropdown.style.display = "none";
    }
  });
}

function updateSearchHighlight(items) {
  items.forEach((item, idx) => {
    if (idx === currentHighlightedSearchIndex) {
      item.classList.add("active");
      item.scrollIntoView({ block: "nearest" });
    } else {
      item.classList.remove("active");
    }
  });
}

async function executeGlobalSearch(query) {
  const dropdown = document.getElementById("global-search-dropdown");
  if (!dropdown) return;

  try {
    const res = await apiFetch(`/api/search?q=${encodeURIComponent(query)}`);
    if (!res.ok) throw new Error("Search query failed");
    const data = await res.json();

    currentHighlightedSearchIndex = -1;

    if (data.total_results === 0) {
      dropdown.innerHTML = `
        <div class="search-empty-state">
          No matching books, members, or barcodes found for "<strong>${escapeHtml(query)}</strong>"
        </div>
      `;
      dropdown.style.display = "block";
      return;
    }

    let html = "";

    // 1. Books section
    if (data.books && data.books.length > 0) {
      html += `<div class="search-category-header">📚 Books (${data.books.length})</div>`;
      data.books.forEach(b => {
        html += `
          <div class="search-item" onclick="selectSearchResult('book', ${b.id}, '${escapeHtml(b.title)}')">
            <div class="search-item-info">
              <div class="search-item-title">${highlightMatch(b.title, query)}</div>
              <div class="search-item-sub">By ${highlightMatch(b.authors, query)} · ISBN: ${b.isbn ? highlightMatch(b.isbn, query) : 'N/A'}</div>
            </div>
            <span class="search-item-badge badge ${b.available_copies > 0 ? 'green' : 'red'}">
              ${b.available_copies}/${b.total_copies} Avail
            </span>
          </div>
        `;
      });
    }

    // 2. Members section
    if (data.members && data.members.length > 0) {
      html += `<div class="search-category-header">👥 Members (${data.members.length})</div>`;
      data.members.forEach(m => {
        html += `
          <div class="search-item" onclick="selectSearchResult('member', ${m.id}, '${escapeHtml(m.name)}')">
            <div class="search-item-info">
              <div class="search-item-title">${highlightMatch(m.name, query)} (${highlightMatch(m.member_code, query)})</div>
              <div class="search-item-sub">${highlightMatch(m.email, query)} · ${m.phone ? highlightMatch(m.phone, query) : ''}</div>
            </div>
            <span class="search-item-badge badge ${m.is_active ? 'blue' : 'gray'}">
              ${m.membership_type} · ${m.active_loans} loans
            </span>
          </div>
        `;
      });
    }

    // 3. Copies & Loans section
    if (data.copies && data.copies.length > 0) {
      html += `<div class="search-category-header">🏷️ Copies & Barcodes (${data.copies.length})</div>`;
      data.copies.forEach(c => {
        html += `
          <div class="search-item" onclick="selectSearchResult('copy', ${c.id}, '${escapeHtml(c.barcode)}')">
            <div class="search-item-info">
              <div class="search-item-title">${highlightMatch(c.barcode, query)}</div>
              <div class="search-item-sub">${highlightMatch(c.book_title, query)}</div>
            </div>
            <span class="search-item-badge badge ${c.status === 'Available' ? 'green' : 'orange'}">
              ${c.status}
            </span>
          </div>
        `;
      });
    }

    dropdown.innerHTML = html;
    dropdown.style.display = "block";
  } catch (err) {
    console.error("Search execution error:", err);
  }
}

function selectSearchResult(type, id, label) {
  const dropdown = document.getElementById("global-search-dropdown");
  if (dropdown) dropdown.style.display = "none";

  if (type === "book") {
    switchView("book-catalog");
    setTimeout(() => filterActiveTableRows(label.toLowerCase()), 200);
  } else if (type === "member") {
    switchView("members");
    setTimeout(() => filterActiveTableRows(label.toLowerCase()), 200);
  } else if (type === "copy") {
    switchView("book-copies");
    setTimeout(() => filterActiveTableRows(label.toLowerCase()), 200);
  }
}

function clearGlobalSearch() {
  const searchInput = document.getElementById("global-search");
  const clearBtn = document.getElementById("search-clear-btn");
  const dropdown = document.getElementById("global-search-dropdown");

  if (searchInput) searchInput.value = "";
  if (clearBtn) clearBtn.style.display = "none";
  if (dropdown) dropdown.style.display = "none";

  filterActiveTableRows("");
}

function filterActiveTableRows(query) {
  // Select all tables currently visible on the page
  const tables = document.querySelectorAll("table.data-table, #recent-books-table, #active-loans-table, #overdue-books-table");

  tables.forEach(table => {
    const tbody = table.querySelector("tbody");
    if (!tbody) return;

    // Remove any previously injected empty-state row
    const existingEmpty = tbody.querySelector(".search-empty-row");
    if (existingEmpty) existingEmpty.remove();

    const rows = Array.from(tbody.querySelectorAll("tr:not(.search-empty-row)"));
    if (rows.length === 0) return;

    let visibleCount = 0;
    rows.forEach(r => {
      const text = r.innerText.toLowerCase();
      if (!query || text.includes(query)) {
        r.style.display = "";
        visibleCount++;
      } else {
        r.style.display = "none";
      }
    });

    if (query && visibleCount === 0) {
      const colCount = table.querySelectorAll("thead th").length || 5;
      const emptyTr = document.createElement("tr");
      emptyTr.className = "search-empty-row";
      emptyTr.innerHTML = `
        <td colspan="${colCount}" style="text-align:center;padding:24px;color:#94a3b8;">
          No matching records found for "<strong>${escapeHtml(query)}</strong>"
        </td>
      `;
      tbody.appendChild(emptyTr);
    }
  });
}

function highlightMatch(text, query) {
  if (!text) return "";
  if (!query) return escapeHtml(text);
  const escapedQuery = query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const regex = new RegExp(`(${escapedQuery})`, "gi");
  return escapeHtml(text).replace(regex, `<mark style="background:#fef08a;padding:0 2px;border-radius:2px;">$1</mark>`);
}

function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

// Initializer
document.addEventListener("DOMContentLoaded", async () => {
  updateDateTime();
  setInterval(updateDateTime, 30000);

  // Set up navigation clicks
  document.querySelectorAll(".nav-item").forEach(item => {
    item.addEventListener("click", () => {
      const view = item.getAttribute("data-view");
      if (view) switchView(view);
    });
  });

  // Setup interactive modules
  setupGlobalSearch();
  setupBookDropzone();
  setupBatchImportDropzone();

  // Check auth session
  await checkAuthStatus();

  // Load dashboard and dropdowns
  await fetchDashboard();
  await loadDropdowns();
});
