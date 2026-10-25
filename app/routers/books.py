"""
Router for Books, Authors, and Categories management.
"""

from typing import List, Optional
import os
import uuid
import csv
import io
import json
from fastapi import APIRouter, Depends, HTTPException, Query, status, UploadFile, File
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, UserRole, CopyStatus
from app.schemas import (
    BookCreate, BookUpdate, BookResponse, BookListResponse,
    AuthorCreate, AuthorUpdate, AuthorResponse,
    CategoryCreate, CategoryUpdate, CategoryResponse,
    MessageResponse, FileUploadResponse, UploadedFileInfo, BatchImportResponse
)
from app.auth import get_current_user, require_role
from app import services

router = APIRouter(prefix="/api", tags=["Books, Authors & Categories"])


# ---------------------------------------------------------------------------
# Authors Endpoints
# ---------------------------------------------------------------------------

@router.get("/authors", response_model=List[AuthorResponse])
def list_authors(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Retrieve all authors."""
    return services.get_authors(db, skip=skip, limit=limit, search=search)


@router.post("/authors", response_model=AuthorResponse, status_code=status.HTTP_201_CREATED)
def create_author(
    payload: AuthorCreate,
    current_user: User = Depends(require_role(UserRole.admin, UserRole.librarian)),
    db: Session = Depends(get_db)
):
    """Create a new author."""
    author = services.create_author(db, name=payload.name, biography=payload.biography)
    services.create_audit_log(
        db, current_user.id, "CREATE_AUTHOR", "Author", author.id, f"Created author {author.name}"
    )
    return author


@router.put("/authors/{author_id}", response_model=AuthorResponse)
def update_author(
    author_id: int,
    payload: AuthorUpdate,
    current_user: User = Depends(require_role(UserRole.admin, UserRole.librarian)),
    db: Session = Depends(get_db)
):
    """Update author information."""
    author = services.update_author(db, author_id, **payload.model_dump(exclude_unset=True))
    if not author:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Author not found")
    return author


@router.delete("/authors/{author_id}", response_model=MessageResponse)
def delete_author(
    author_id: int,
    current_user: User = Depends(require_role(UserRole.admin)),
    db: Session = Depends(get_db)
):
    """Delete an author."""
    success = services.delete_author(db, author_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Author not found")
    return MessageResponse(message="Author deleted successfully")


# ---------------------------------------------------------------------------
# Categories Endpoints
# ---------------------------------------------------------------------------

@router.get("/categories", response_model=List[CategoryResponse])
def list_categories(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Retrieve all categories."""
    return services.get_categories(db, skip=skip, limit=limit, search=search)


@router.post("/categories", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
def create_category(
    payload: CategoryCreate,
    current_user: User = Depends(require_role(UserRole.admin, UserRole.librarian)),
    db: Session = Depends(get_db)
):
    """Create a new category."""
    try:
        cat = services.create_category(db, name=payload.name, description=payload.description)
        services.create_audit_log(
            db, current_user.id, "CREATE_CATEGORY", "Category", cat.id, f"Created category {cat.name}"
        )
        return cat
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/categories/{category_id}", response_model=CategoryResponse)
def update_category(
    category_id: int,
    payload: CategoryUpdate,
    current_user: User = Depends(require_role(UserRole.admin, UserRole.librarian)),
    db: Session = Depends(get_db)
):
    """Update category details."""
    try:
        cat = services.update_category(db, category_id, **payload.model_dump(exclude_unset=True))
        if not cat:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
        return cat
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/categories/{category_id}", response_model=MessageResponse)
def delete_category(
    category_id: int,
    current_user: User = Depends(require_role(UserRole.admin)),
    db: Session = Depends(get_db)
):
    """Delete category."""
    success = services.delete_category(db, category_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    return MessageResponse(message="Category deleted successfully")


# ---------------------------------------------------------------------------
# Books Endpoints
# ---------------------------------------------------------------------------

@router.get("/books", response_model=List[BookResponse])
def list_books(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    search: Optional[str] = Query(None),
    active_only: bool = Query(True),
    db: Session = Depends(get_db)
):
    """Retrieve book catalog with author, category, and copy counts."""
    books = services.get_books(db, skip=skip, limit=limit, search=search, active_only=active_only)
    result = []
    for book in books:
        total_copies = len(book.copies)
        available_copies = sum(1 for c in book.copies if c.status == CopyStatus.Available)
        b_dict = {
            "id": book.id,
            "title": book.title,
            "isbn": book.isbn,
            "publisher": book.publisher,
            "published_year": book.published_year,
            "description": book.description,
            "language": book.language,
            "page_count": book.page_count,
            "cover_image": book.cover_image,
            "is_active": book.is_active,
            "created_at": book.created_at,
            "updated_at": book.updated_at,
            "authors": [AuthorResponse.model_validate(a) for a in book.authors],
            "categories": [CategoryResponse.model_validate(c) for c in book.categories],
            "total_copies": total_copies,
            "available_copies": available_copies,
        }
        result.append(BookResponse(**b_dict))
    return result


@router.get("/books/{book_id}", response_model=BookResponse)
def get_book_details(book_id: int, db: Session = Depends(get_db)):
    """Fetch details of a single book title."""
    book = services.get_book_by_id(db, book_id)
    if not book:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")
    total_copies = len(book.copies)
    available_copies = sum(1 for c in book.copies if c.status == CopyStatus.Available)
    b_dict = {
        "id": book.id,
        "title": book.title,
        "isbn": book.isbn,
        "publisher": book.publisher,
        "published_year": book.published_year,
        "description": book.description,
        "language": book.language,
        "page_count": book.page_count,
        "cover_image": book.cover_image,
        "is_active": book.is_active,
        "created_at": book.created_at,
        "updated_at": book.updated_at,
        "authors": [AuthorResponse.model_validate(a) for a in book.authors],
        "categories": [CategoryResponse.model_validate(c) for c in book.categories],
        "total_copies": total_copies,
        "available_copies": available_copies,
    }
    return BookResponse(**b_dict)


@router.post("/books", response_model=BookResponse, status_code=status.HTTP_201_CREATED)
def create_book(
    payload: BookCreate,
    current_user: User = Depends(require_role(UserRole.admin, UserRole.librarian)),
    db: Session = Depends(get_db)
):
    """Add a new book title to the catalog."""
    try:
        book = services.create_book(
            db=db,
            title=payload.title,
            isbn=payload.isbn,
            publisher=payload.publisher,
            published_year=payload.published_year,
            description=payload.description,
            language=payload.language or "English",
            page_count=payload.page_count,
            cover_image=payload.cover_image,
            author_ids=payload.author_ids,
            category_ids=payload.category_ids,
            initial_copies=payload.initial_copies if payload.initial_copies is not None else 0,
            barcode_prefix=payload.barcode_prefix,
        )
        services.create_audit_log(
            db, current_user.id, "CREATE_BOOK", "Book", book.id, f"Created book '{book.title}' (ISBN: {book.isbn})"
        )
        return get_book_details(book.id, db)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/books/upload", response_model=FileUploadResponse)
async def upload_book_files(
    files: List[UploadFile] = File(...),
    current_user: User = Depends(require_role(UserRole.admin, UserRole.librarian)),
):
    """Upload one or multiple book covers or document files via drag-and-drop or file selector."""
    uploads_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "uploads")
    os.makedirs(uploads_dir, exist_ok=True)

    uploaded_items = []
    for f in files:
        # Generate safe unique filename
        ext = os.path.splitext(f.filename)[1].lower() if f.filename else ".bin"
        unique_id = uuid.uuid4().hex[:12]
        clean_name = f"{unique_id}{ext}"
        filepath = os.path.join(uploads_dir, clean_name)

        content = await f.read()
        with open(filepath, "wb") as out_file:
            out_file.write(content)

        uploaded_items.append(UploadedFileInfo(
            original_name=f.filename or "unknown",
            filename=clean_name,
            url=f"/static/uploads/{clean_name}",
            size=len(content),
            content_type=f.content_type or "application/octet-stream",
        ))

    return FileUploadResponse(uploaded=uploaded_items)


@router.post("/books/batch-import")
async def batch_import_books_endpoint(
    file: Optional[UploadFile] = File(None),
    current_user: User = Depends(require_role(UserRole.admin, UserRole.librarian)),
    db: Session = Depends(get_db)
):
    """Batch import multiple books from a CSV or JSON file uploaded via drag-and-drop."""
    if not file:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No file was provided for batch import")

    content = await file.read()
    filename = (file.filename or "").lower()
    books_data = []

    if filename.endswith(".json"):
        try:
            books_data = json.loads(content.decode("utf-8"))
            if not isinstance(books_data, list):
                if isinstance(books_data, dict) and "books" in books_data:
                    books_data = books_data["books"]
                else:
                    raise ValueError("JSON must contain an array of book objects")
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid JSON format: {str(e)}")
    elif filename.endswith(".csv") or filename.endswith(".txt"):
        try:
            text_stream = io.StringIO(content.decode("utf-8-sig", errors="ignore"))
            reader = csv.DictReader(text_stream)
            for row in reader:
                # normalize keys
                row_clean = {k.strip().lower().replace(" ", "_"): v.strip() for k, v in row.items() if k}
                books_data.append({
                    "title": row_clean.get("title") or row_clean.get("book_title"),
                    "isbn": row_clean.get("isbn"),
                    "publisher": row_clean.get("publisher"),
                    "published_year": row_clean.get("published_year") or row_clean.get("year"),
                    "authors": row_clean.get("authors") or row_clean.get("author"),
                    "categories": row_clean.get("categories") or row_clean.get("category"),
                    "initial_copies": row_clean.get("copies") or 1,
                })
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid CSV format: {str(e)}")
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Supported file formats: .csv or .json")

    result = services.batch_import_books(db, books_data)
    services.create_audit_log(
        db, current_user.id, "BATCH_IMPORT_BOOKS", "Book", None,
        f"Batch imported {result['imported_count']} books ({result['failed_count']} errors)"
    )

    # Format return
    response_books = []
    for b in result["books"]:
        response_books.append(get_book_details(b.id, db))

    return {
        "success": result["success"],
        "imported_count": result["imported_count"],
        "failed_count": result["failed_count"],
        "errors": result["errors"],
        "books": response_books,
    }


@router.post("/books/batch-delete", response_model=MessageResponse)
def batch_delete_books(
    payload: dict,
    current_user: User = Depends(require_role(UserRole.admin)),
    db: Session = Depends(get_db)
):
    """Batch delete or archive multiple books by ID."""
    book_ids = payload.get("book_ids", [])
    if not book_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No book IDs provided")

    processed = 0
    for bid in book_ids:
        try:
            services.delete_book(db, int(bid))
            processed += 1
        except Exception:
            continue

    services.create_audit_log(
        db, current_user.id, "BATCH_DELETE_BOOKS", "Book", None,
        f"Processed batch archive/delete for {processed} books"
    )
    return MessageResponse(message=f"Successfully processed {processed} books")


@router.put("/books/{book_id}", response_model=BookResponse)
def update_book(
    book_id: int,
    payload: BookUpdate,
    current_user: User = Depends(require_role(UserRole.admin, UserRole.librarian)),
    db: Session = Depends(get_db)
):
    """Update existing book record."""
    try:
        book = services.update_book(db, book_id, **payload.model_dump(exclude_unset=True))
        if not book:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")
        services.create_audit_log(
            db, current_user.id, "UPDATE_BOOK", "Book", book_id, f"Updated book #{book_id}"
        )
        return get_book_details(book_id, db)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/books/{book_id}")
def delete_or_archive_book(
    book_id: int,
    current_user: User = Depends(require_role(UserRole.admin)),
    db: Session = Depends(get_db)
):
    """Safely archive book if loans exist, or delete if safe."""
    try:
        result = services.delete_book(db, book_id)
        services.create_audit_log(
            db, current_user.id, result["action"].upper() + "_BOOK", "Book", book_id, result["message"]
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
