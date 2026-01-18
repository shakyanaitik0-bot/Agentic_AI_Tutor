"""
Shared dependencies for API routes.

Provides common functionality like:
- Database sessions
- JWT authentication
- Student lookups
- Rate limiting
"""

import logging
from typing import Generator, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.database import get_database
from app.core.security import verify_token, TokenData
from app.models.student import Student
from app.models.session import Session as DBSession

logger = logging.getLogger(__name__)

# JWT Bearer scheme
security = HTTPBearer(auto_error=False)


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
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Student with ID {student_id} not found"
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
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Session with ID {session_id} not found"
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
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Session {session.id} is not active"
        )

    return session


# ============================================================================
# JWT Authentication Dependencies
# ============================================================================


async def get_token_data(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[TokenData]:
    """
    Extract and verify JWT token from Authorization header.

    Args:
        credentials: Bearer token from Authorization header

    Returns:
        TokenData if valid token, None if no token provided

    Raises:
        HTTPException: 401 if token is invalid
    """
    if credentials is None:
        return None

    token = credentials.credentials
    token_data = verify_token(token, token_type="access")

    if token_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return token_data


async def require_auth(token_data: Optional[TokenData] = Depends(get_token_data)) -> TokenData:
    """
    Require valid JWT authentication.

    Args:
        token_data: Token data from get_token_data

    Returns:
        TokenData: Verified token data

    Raises:
        HTTPException: 401 if not authenticated
    """
    if token_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return token_data


async def get_current_student(
    token_data: TokenData = Depends(require_auth), db: Session = Depends(get_db)
) -> Student:
    """
    Get the currently authenticated student.

    Args:
        token_data: Verified token data
        db: Database session

    Returns:
        Student: Current student model

    Raises:
        HTTPException: 401 if student not found
    """
    student = db.query(Student).filter(Student.id == token_data.student_id).first()

    if student is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Student not found")

    if not student.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Student account is inactive"
        )

    return student


async def get_optional_current_student(
    token_data: Optional[TokenData] = Depends(get_token_data), db: Session = Depends(get_db)
) -> Optional[Student]:
    """
    Get current student if authenticated, None otherwise.

    Useful for endpoints that work with or without authentication.

    Args:
        token_data: Optional token data
        db: Database session

    Returns:
        Student or None
    """
    if token_data is None:
        return None

    return db.query(Student).filter(Student.id == token_data.student_id).first()
