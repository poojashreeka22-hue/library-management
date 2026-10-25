"""
Library Management System - Configuration Settings.

All settings can be overridden via environment variables or a .env file.
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file if present
load_dotenv()

# ---------------------------------------------------------------------------
# Security & JWT
# ---------------------------------------------------------------------------
SECRET_KEY = os.getenv(
    "SECRET_KEY", "library-management-dev-secret-key-change-in-production"
)
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))

# ---------------------------------------------------------------------------
# Development Administrator Bootstrap Credentials
# ---------------------------------------------------------------------------
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@library.com")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
ADMIN_FULL_NAME = os.getenv("ADMIN_FULL_NAME", "System Administrator")

# ---------------------------------------------------------------------------
# Library business rules
# ---------------------------------------------------------------------------
DEFAULT_LOAN_DAYS = int(os.getenv("DEFAULT_LOAN_DAYS", "14"))
MAX_RENEWALS = int(os.getenv("MAX_RENEWALS", "2"))
RENEWAL_DAYS = int(os.getenv("RENEWAL_DAYS", "14"))
FINE_PER_DAY = float(os.getenv("FINE_PER_DAY", "10.0"))
GRACE_PERIOD_DAYS = int(os.getenv("GRACE_PERIOD_DAYS", "1"))
RESERVATION_EXPIRY_DAYS = int(os.getenv("RESERVATION_EXPIRY_DAYS", "3"))
MAX_ACTIVE_RESERVATIONS = int(os.getenv("MAX_ACTIVE_RESERVATIONS", "3"))
MAX_UNPAID_FINE_LIMIT = float(os.getenv("MAX_UNPAID_FINE_LIMIT", "100.0"))
LOST_BOOK_PRICE = float(os.getenv("LOST_BOOK_PRICE", "250.0"))
DAMAGED_BOOK_PRICE = float(os.getenv("DAMAGED_BOOK_PRICE", "100.0"))

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./library.db")
