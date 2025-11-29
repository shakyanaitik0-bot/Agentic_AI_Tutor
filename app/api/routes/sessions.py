"""
Session management API endpoints.

Handles learning session creation, retrieval, and termination.
"""
import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as DBSessionType

from app.api.dependencies import get_db, get_student_by_id, get_session_by_id
from app.models.student import Student
from app.models.session import Session as DBSession
from app.schemas.common import SessionCreate, SessionResponse

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/start", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
def start_session(
    session_data: SessionCreate,
    db: DBSessionType = Depends(get_db)
):
    """
    Start a new learning session for a student.

    Args:
        session_data: Session creation data
        db: Database session

    Returns:
        SessionResponse: Created session

    Raises:
        HTTPException: 404 if student not found
    """
    # Verify student exists
    student = db.query(Student).filter(Student.id == session_data.student_id).first()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student {session_data.student_id} not found"
        )

    # Create new session
    new_session = DBSession(
        student_id=session_data.student_id,
        is_active=True,
        session_type=session_data.session_type
    )

    db.add(new_session)
    db.commit()
    db.refresh(new_session)

    logger.info(f"Started session {new_session.id} for student {student.name}")

    return new_session


@router.get("/{session_id}", response_model=SessionResponse)
def get_session(session: DBSession = Depends(get_session_by_id)):
    """
    Get session details by ID.

    Args:
        session: Session from dependency

    Returns:
        SessionResponse: Session details
    """
    logger.debug(f"Retrieved session: {session.id}")
    return session


@router.post("/{session_id}/end", response_model=SessionResponse)
def end_session(
    session: DBSession = Depends(get_session_by_id),
    db: DBSessionType = Depends(get_db)
):
    """
    End an active session.

    Args:
        session: Session from dependency
        db: Database session

    Returns:
        SessionResponse: Updated session

    Raises:
        HTTPException: 400 if session already ended
    """
    if not session.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Session {session.id} is already ended"
        )

    # End the session
    session.is_active = False
    session.ended_at = datetime.utcnow()

    db.commit()
    db.refresh(session)

    logger.info(f"Ended session {session.id}")

    return session
