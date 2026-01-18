"""
Student management API endpoints.

Handles student registration and profile retrieval.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, get_student_by_id
from app.models.student import Student
from app.schemas.common import StudentCreate, StudentResponse, StudentLogin

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/register", response_model=StudentResponse, status_code=status.HTTP_201_CREATED)
def register_student(student_data: StudentCreate, db: Session = Depends(get_db)):
    """
    Register a new student.

    Args:
        student_data: Student registration data
        db: Database session

    Returns:
        StudentResponse: Created student profile

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

    return student


@router.post("/login", response_model=StudentResponse)
def login_student(login_data: StudentLogin, db: Session = Depends(get_db)):
    """
    Student login with email and password.

    Args:
        login_data: Email and password
        db: Database session

    Returns:
        StudentResponse: Student profile

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

    # Update last active
    student.update_last_active()
    db.commit()

    logger.info(f"Student login successful: {student.name} ({student.id})")
    return student


@router.get("/{student_id}", response_model=StudentResponse)
def get_student(student: Student = Depends(get_student_by_id)):
    """
    Get student profile by ID.

    Args:
        student: Student from dependency

    Returns:
        StudentResponse: Student profile
    """
    logger.debug(f"Retrieved student: {student.id}")
    return student
