"""
Auth router for login, profile, user management.
"""

from datetime import timedelta
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, UserRole
from app.schemas import (
    LoginRequest, Token, UserResponse, UserCreate, UserUpdate, MessageResponse
)
from app.auth import (
    hash_password, verify_password, create_access_token,
    get_current_user, require_role
)
from app import services, config

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/login", response_model=Token)
async def login(request: Request, response: Response, db: Session = Depends(get_db)):
    """Authenticate user and return JWT token. Supports both JSON and Form submissions."""
    username = None
    password = None

    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            body = await request.json()
            username = body.get("username")
            password = body.get("password")
        except Exception:
            pass
    elif "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
        try:
            form = await request.form()
            username = form.get("username")
            password = form.get("password")
        except Exception:
            pass
    else:
        # Fallback: try JSON then form
        try:
            body = await request.json()
            username = body.get("username")
            password = body.get("password")
        except Exception:
            try:
                form = await request.form()
                username = form.get("username")
                password = form.get("password")
            except Exception:
                pass

    if not username or not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username and password are required"
        )

    user = services.authenticate_user(db, str(username).strip(), str(password))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )
    access_token = create_access_token(
        data={"sub": user.username, "role": user.role.value, "id": user.id}
    )
    # Also set cookie for frontend convenience
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        max_age=config.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax",
    )
    return Token(access_token=access_token, token_type="bearer")


@router.post("/logout", response_model=MessageResponse)
def logout(response: Response):
    """Log out current user by clearing auth cookie."""
    response.delete_cookie(key="access_token")
    return MessageResponse(message="Successfully logged out")


@router.get("/me", response_model=UserResponse)
def get_current_user_profile(current_user: User = Depends(get_current_user)):
    """Get profile of authenticated user."""
    return current_user


@router.get("/users", response_model=List[UserResponse])
def list_users(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(require_role(UserRole.admin)),
    db: Session = Depends(get_db)
):
    """Admin-only: list all librarians and admin accounts."""
    return services.get_users(db, skip=skip, limit=limit)


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_new_user(
    payload: UserCreate,
    current_user: User = Depends(require_role(UserRole.admin)),
    db: Session = Depends(get_db)
):
    """Admin-only: create a new staff account."""
    try:
        user = services.create_user(
            db=db,
            username=payload.username,
            email=payload.email,
            password=payload.password,
            full_name=payload.full_name,
            role=payload.role.value,
        )
        services.create_audit_log(
            db, current_user.id, "CREATE_USER", "User", user.id,
            f"Created user {user.username} with role {user.role.value}"
        )
        return user
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/users/{user_id}", response_model=UserResponse)
def update_user_account(
    user_id: int,
    payload: UserUpdate,
    current_user: User = Depends(require_role(UserRole.admin)),
    db: Session = Depends(get_db)
):
    """Admin-only: update user details."""
    try:
        user = services.update_user(db, user_id, **payload.model_dump(exclude_unset=True))
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return user
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
