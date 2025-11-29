"""
Shared dependencies for API routes.

Provides common functionality like database sessions and student lookups.
"""
from typing import Generator
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_database
from app.models.student import Student
from app.models.session import Session as DBSession


def get_db() -> Generator[Session, None, None]:
    """
    Dependency to get database session.

    Yields:
        Session: SQLAlchemy database session

    Example:
        @app.get("/students")
        def get_students(db: Session = Depends(get_db)):
            return db.query(Student).all()
    """
    db = next(get_database())
    try:
        yield db
    finally:
        db.close()


def get_student_by_id(student_id: str, db: Session = Depends(get_db)) -> Student:
    """
    Dependency to get student by ID.

    Args:
        student_id: Student UUID
        db: Database session

    Returns:
        Student: Student model instance

    Raises:
        HTTPException: 404 if student not found

    Example:
        @app.get("/students/{student_id}")
        def get_student(student: Student = Depends(get_student_by_id)):
            return student
    """
    student = db.query(Student).filter(Student.id == student_id).first()

    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student with ID {student_id} not found"
        )

    return student


def get_session_by_id(session_id: str, db: Session = Depends(get_db)) -> DBSession:
    """
    Dependency to get session by ID.

    Args:
        session_id: Session UUID
        db: Database session

    Returns:
        DBSession: Session model instance

    Raises:
        HTTPException: 404 if session not found

    Example:
        @app.get("/sessions/{session_id}")
        def get_session(session: DBSession = Depends(get_session_by_id)):
            return session
    """
    session = db.query(DBSession).filter(DBSession.id == session_id).first()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session with ID {session_id} not found"
        )

    return session


def verify_active_session(session: DBSession = Depends(get_session_by_id)) -> DBSession:
    """
    Dependency to verify session is active.

    Args:
        session: Session from get_session_by_id

    Returns:
        DBSession: Active session

    Raises:
        HTTPException: 400 if session is not active

    Example:
        @app.post("/chat")
        def chat(
            message: str,
            session: DBSession = Depends(verify_active_session)
        ):
            # Session is guaranteed to be active
            pass
    """
    if not session.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Session {session.id} is not active"
        )

    return session
