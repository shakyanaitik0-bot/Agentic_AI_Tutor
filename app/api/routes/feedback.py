"""
Feedback and progress API endpoints.

Handles progress reports and performance analysis.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session as DBSessionType

from app.api.dependencies import get_db, get_student_by_id
from app.models.student import Student
from app.models.session import Session as DBSession
from app.agents.feedback_agent import create_feedback_agent
from app.schemas.feedback import (
    FeedbackRequest,
    ProgressReportResponse,
    ReportType
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/{student_id}", response_model=ProgressReportResponse)
def get_progress_report(
    student_id: str,
    report_type: ReportType = Query(ReportType.STUDENT, description="Type of report"),
    db: DBSessionType = Depends(get_db)
):
    """
    Get progress report for a student.

    Args:
        student_id: Student ID
        report_type: Type of report (student/teacher/data)
        db: Database session

    Returns:
        ProgressReportResponse: Detailed progress report

    Raises:
        HTTPException: 404 if student not found
    """
    # Get student
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student {student_id} not found"
        )

    # Get or create session for feedback
    active_session = db.query(DBSession).filter(
        DBSession.student_id == student.id,
        DBSession.is_active == True
    ).first()

    if not active_session:
        # Create temporary session for feedback
        active_session = DBSession(
            student_id=student.id,
            is_active=True,
            session_type="feedback"
        )
        db.add(active_session)
        db.commit()
        db.refresh(active_session)

    logger.info(f"Generating {report_type.value} progress report for {student.name}")

    try:
        # Create feedback agent
        feedback_agent = create_feedback_agent(
            student=student,
            session=active_session,
            db=db
        )

        # Generate report
        result = feedback_agent.execute(
            f"Show progress report",
            report_type=report_type.value
        )

        # Extract report data based on format
        if result.get("format") == "json" and "data" in result:
            data = result["data"]

            # Convert to ProgressReportResponse
            response = ProgressReportResponse(
                student_id=student_id,
                overall_stats=data.get("overall_stats", {}),
                weak_topics=data.get("weak_topics", []),
                strong_topics=data.get("strong_topics", []),
                improving_topics=data.get("improving_topics", []),
                declining_topics=data.get("declining_topics", []),
                recommendations=data.get("recommendations", []),
                needs_replanning=data.get("needs_replanning", False),
                report_summary=data.get("summary")
            )

            logger.info(f"Generated report: {response.overall_stats.get('total_topics', 0)} topics analyzed")

            return response
        else:
            # Fallback: create minimal response
            logger.warning("Report format unexpected, returning minimal response")
            return ProgressReportResponse(
                student_id=student_id,
                overall_stats={
                    "total_topics": 0,
                    "total_attempts": 0,
                    "total_correct": 0,
                    "overall_accuracy": 0.0,
                    "total_time_minutes": 0.0,
                    "weak_topics_count": 0,
                    "strong_topics_count": 0,
                    "mastery_topics_count": 0,
                    "recently_practiced_count": 0
                },
                weak_topics=[],
                strong_topics=[],
                improving_topics=[],
                declining_topics=[],
                recommendations=["Complete some quizzes to see your progress"],
                needs_replanning=False
            )

    except Exception as e:
        logger.error(f"Error generating progress report: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating progress report: {str(e)}"
        )


@router.post("/request", response_model=ProgressReportResponse)
def request_feedback(
    request: FeedbackRequest,
    db: DBSessionType = Depends(get_db)
):
    """
    Request a customized feedback report.

    Args:
        request: Feedback request parameters
        db: Database session

    Returns:
        ProgressReportResponse: Generated report

    Raises:
        HTTPException: 404 if student not found
    """
    return get_progress_report(
        student_id=request.student_id,
        report_type=request.report_type,
        db=db
    )
