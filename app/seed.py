"""
Seed initial library data matching reference UI design.
"""

from datetime import date, timedelta
from sqlalchemy.orm import Session

from app import models, services, config
from app.models import (
    User, UserRole, Author, Category, Book, BookCopy, Member, Loan, Fine,
    CopyStatus, MembershipType, FineStatus, FineType
)


def seed_library_data(db: Session):
    """Seed initial records if database is empty."""
    # 1. Admin user from environment configuration
    admin = db.query(User).filter(User.username == config.ADMIN_USERNAME).first()
    if not admin:
        admin = services.create_user(
            db,
            username=config.ADMIN_USERNAME,
            email=config.ADMIN_EMAIL,
            password=config.ADMIN_PASSWORD,
            full_name=config.ADMIN_FULL_NAME,
            role="admin",
        )

    # If books already exist, do not re-seed
    if db.query(Book).count() > 0:
        return

    # 2. Categories
    cat_names = ["Programming", "Self Help", "History", "Science Fiction", "Fiction", "Mystery", "Fantasy"]
    categories = {}
    for name in cat_names:
        cat = Category(name=name, description=f"Books related to {name}")
        db.add(cat)
        categories[name] = cat
    db.commit()

    # 3. Authors
    author_names = [
        "Robert C. Martin", "James Clear", "Yuval Noah Harari", "Frank Herbert",
        "Paulo Coelho", "George Orwell", "Dan Brown", "Gillian Flynn", "J.R.R. Tolkien"
    ]
    authors = {}
    for name in author_names:
        aut = Author(name=name, biography=f"Renowned author {name}")
        db.add(aut)
        authors[name] = aut
    db.commit()

    # 4. Books
    books_data = [
        ("Clean Code", "9780132350884", "Robert C. Martin", "Programming", 5),
        ("Atomic Habits", "9780735211292", "James Clear", "Self Help", 8),
        ("Sapiens", "9780062316097", "Yuval Noah Harari", "History", 6),
        ("Dune", "9780441172719", "Frank Herbert", "Science Fiction", 4),
        ("The Alchemist", "9780062315007", "Paulo Coelho", "Fiction", 7),
        ("1984", "9780451524935", "George Orwell", "Fiction", 4),
        ("The Da Vinci Code", "9780307474278", "Dan Brown", "Mystery", 5),
        ("Gone Girl", "9780307588371", "Gillian Flynn", "Mystery", 3),
        ("The Hobbit", "9780547928227", "J.R.R. Tolkien", "Fantasy", 6),
    ]

    books = {}
    copies = {}
    for title, isbn, author_name, cat_name, copy_count in books_data:
        b = Book(
            title=title,
            isbn=isbn,
            publisher="Standard Press",
            published_year=2020,
            description=f"A great read: {title}",
            language="English",
            page_count=350,
        )
        b.authors = [authors[author_name]]
        b.categories = [categories[cat_name]]
        db.add(b)
        db.commit()
        db.refresh(b)
        books[title] = b

        # Add physical copies
        copies[title] = []
        for i in range(1, copy_count + 1):
            short_code = "".join([w[0] for w in title.split() if w])[:3].upper()
            barcode = f"BC-{short_code}-{b.id:03d}-{i:02d}"
            c = BookCopy(
                book_id=b.id,
                barcode=barcode,
                status=CopyStatus.Available,
                acquired_date=date.today() - timedelta(days=60),
            )
            db.add(c)
            copies[title].append(c)
    db.commit()

    # 5. Members
    members_data = [
        ("Priya", "Patel", "priya.patel@example.com", "9876543210"),
        ("Rohit", "Verma", "rohit.verma@example.com", "9876543211"),
        ("Sneha", "Iyer", "sneha.iyer@example.com", "9876543212"),
        ("Amit", "Kumar", "amit.kumar@example.com", "9876543213"),
        ("Neha", "Singh", "neha.singh@example.com", "9876543214"),
        ("Rahul", "Sharma", "rahul.sharma@example.com", "9876543215"),
        ("Vikram", "Singh", "vikram.singh@example.com", "9876543216"),
        ("Anjali", "Mehta", "anjali.mehta@example.com", "9876543217"),
    ]

    members = {}
    for first, last, email, phone in members_data:
        m = services.create_member(
            db, first_name=first, last_name=last, email=email, phone=phone
        )
        members[f"{first} {last}"] = m

    # 6. Active Loans matching reference UI
    # Priya Patel - Clean Code (Issue: 5 days ago, Due: in 25 days)
    # Rohit Verma - Atomic Habits
    # Sneha Iyer - Sapiens
    # Amit Kumar - Dune
    # Neha Singh - The Alchemist
    active_loan_configs = [
        ("Priya Patel", "Clean Code", 5, 25),
        ("Rohit Verma", "Atomic Habits", 7, 23),
        ("Sneha Iyer", "Sapiens", 10, 20),
        ("Amit Kumar", "Dune", 13, 17),
        ("Neha Singh", "The Alchemist", 15, 15),
    ]

    for member_name, book_title, days_ago, days_ahead in active_loan_configs:
        m = members[member_name]
        copy = copies[book_title][0]
        copy.status = CopyStatus.OnLoan
        loan = Loan(
            book_copy_id=copy.id,
            member_id=m.id,
            issued_by=admin.id,
            issue_date=date.today() - timedelta(days=days_ago),
            due_date=date.today() + timedelta(days=days_ahead),
            is_returned=False,
        )
        db.add(loan)
    db.commit()

    # 7. Overdue Loans matching reference UI
    # Rahul Sharma - 1984 (3 days overdue, Fine ₹30.00)
    # Sneha Iyer - The Da Vinci Code (5 days overdue, Fine ₹50.00)
    # Vikram Singh - Gone Girl (7 days overdue, Fine ₹70.00)
    # Anjali Mehta - The Hobbit (2 days overdue, Fine ₹20.00)
    overdue_configs = [
        ("Rahul Sharma", "1984", 3, 30.0),
        ("Sneha Iyer", "The Da Vinci Code", 5, 50.0),
        ("Vikram Singh", "Gone Girl", 7, 70.0),
        ("Anjali Mehta", "The Hobbit", 2, 20.0),
    ]

    for member_name, book_title, overdue_days, fine_val in overdue_configs:
        m = members[member_name]
        copy = copies[book_title][1]
        copy.status = CopyStatus.OnLoan
        loan = Loan(
            book_copy_id=copy.id,
            member_id=m.id,
            issued_by=admin.id,
            issue_date=date.today() - timedelta(days=14 + overdue_days),
            due_date=date.today() - timedelta(days=overdue_days),
            is_returned=False,
        )
        db.add(loan)
        db.commit()
        db.refresh(loan)

        # Create fine
        fine = Fine(
            loan_id=loan.id,
            member_id=m.id,
            fine_amount=fine_val,
            paid_amount=0.0,
            status=FineStatus.Unpaid,
            fine_type=FineType.Overdue,
            reason=f"Overdue by {overdue_days} days",
        )
        db.add(fine)
    db.commit()
