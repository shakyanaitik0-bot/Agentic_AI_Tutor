"""
Student management API endpoints.

Handles student registration and profile retrieval.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_student, get_db, verify_student_access
from app.core.security import create_tokens, refresh_access_token
from app.models.student import Student
from app.schemas.common import (
    LoginResponse,
    RefreshRequest,
    StudentCreate,
    StudentLogin,
    StudentResponse,
    TokenPair,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/register", response_model=LoginResponse, status_code=status.HTTP_201_CREATED)
def register_student(student_data: StudentCreate, db: Session = Depends(get_db)):
    """
    Register a new student.

    Args:
        student_data: Student registration data
        db: Database session

    Returns:
        LoginResponse: The new student profile plus access and refresh tokens

    Raises:
        HTTPException: 400 if email already exists
    """
    # Check if email already exists
    existing = db.query(Student).filter(Student.email == student_data.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Student with email {student_data.email} already exists",
        )

    # Create new student
    student = Student(
        name=student_data.name,
        email=student_data.email,
        exam_type=student_data.exam_type.value,
        weak_areas=student_data.weak_areas or [],
        strong_areas=student_data.strong_areas or [],
        learning_preferences=student_data.learning_preferences or {},
    )

    # Set password (hashed)
    student.set_password(student_data.password)

    # Set API keys if provided (will be encrypted automatically)
    if student_data.api_key_openai:
        student.set_api_key("openai", student_data.api_key_openai)
    if student_data.api_key_gemini:
        student.set_api_key("gemini", student_data.api_key_gemini)

    db.add(student)
    db.commit()
    db.refresh(student)

    logger.info(f"Registered new student: {student.name} ({student.id})")

    tokens = create_tokens(student.id, student.email)

    return LoginResponse(
        **StudentResponse.model_validate(student).model_dump(),
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        token_type=tokens.token_type,
        expires_in=tokens.expires_in,
    )


@router.post("/login", response_model=LoginResponse)
def login_student(login_data: StudentLogin, db: Session = Depends(get_db)):
    """
    Student login with email and password.

    Args:
        login_data: Email and password
        db: Database session

    Returns:
        LoginResponse: The student profile plus access and refresh tokens

    Raises:
        HTTPException: 401 if credentials invalid
    """
    # Find student by email
    student = db.query(Student).filter(Student.email == login_data.email).first()

    if not student:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
        )

    # Verify password
    if not student.verify_password(login_data.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
        )

    if not student.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Student account is inactive"
        )

    # Update last active
    student.update_last_active()
    db.commit()

    # Issue JWT credentials so the client can authenticate later requests
    tokens = create_tokens(student.id, student.email)

    logger.info(f"Student login successful: {student.name} ({student.id})")

    tokens = create_tokens(student.id, student.email)

    return LoginResponse(
        **StudentResponse.model_validate(student).model_dump(),
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        token_type=tokens.token_type,
        expires_in=tokens.expires_in,
    )


@router.post("/refresh", response_model=TokenPair)
def refresh_tokens(refresh_data: RefreshRequest):
    """
    Exchange a refresh token for a fresh pair of tokens.

    Args:
        refresh_data: Refresh token issued at login

    Returns:
        TokenPair: New access and refresh tokens

    Raises:
        HTTPException: 401 if the refresh token is invalid or expired
    """
    tokens = refresh_access_token(refresh_data.refresh_token)

    if tokens is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return tokens


@router.get("/me", response_model=StudentResponse)
def get_current_profile(student: Student = Depends(get_current_student)):
    """
    Get the profile of the authenticated student.

    Args:
        student: Student resolved from the access token

    Returns:
        StudentResponse: Student profile
    """
    return student


@router.get("/{student_id}", response_model=StudentResponse)
def get_student(student_id: str, current_student: Student = Depends(get_current_student)):
    """
    Get a student profile by ID.

    Students may only read their own profile.

    Args:
        student_id: Student ID from the path
        current_student: Student resolved from the access token

    Returns:
        StudentResponse: Student profile

    Raises:
        HTTPException: 401 if unauthenticated, 403 if the ID is not the caller's
    """
    verify_student_access(student_id, current_student)

    logger.debug(f"Retrieved student: {current_student.id}")
    return current_student
