"""
Study plan API endpoints.

Handles study plan generation and retrieval.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as DBSessionType

from app.api.dependencies import get_current_student, get_db, verify_student_access
from app.models.student import Student
from app.models.session import Session as DBSession
from app.agents.planner_agent import PlannerAgent
from app.schemas.plan import StudyPlanRequest, StudyPlanResponse

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/generate", response_model=StudyPlanResponse)
def generate_study_plan(
    request: StudyPlanRequest,
    current_student: Student = Depends(get_current_student),
    db: DBSessionType = Depends(get_db),
):
    """
    Generate a personalized study plan for the authenticated student.

    Args:
        request: Study plan request parameters
        current_student: Student resolved from the access token
        db: Database session

    Returns:
        StudyPlanResponse: Generated study plan

    Raises:
        HTTPException: 401 if unauthenticated, 403 if planning for another
            student
    """
    verify_student_access(request.student_id, current_student)
    student = current_student

    # Get or create session
    active_session = (
        db.query(DBSession)
        .filter(DBSession.student_id == student.id, DBSession.is_active == True)
        .first()
    )

    if not active_session:
        active_session = DBSession(student_id=student.id, is_active=True, session_type="planning")
        db.add(active_session)
        db.commit()
        db.refresh(active_session)

    logger.info(f"Generating {request.timeline_days}-day study plan for {student.name}")

    try:
        # Create planner agent
        planner = PlannerAgent(student=student, session=active_session, db=db)

        # Generate plan
        user_message = f"Create a {request.timeline_days}-day study plan"
        kwargs = {"timeline_days": request.timeline_days}

        if request.focus_topics:
            kwargs["focus_topics"] = request.focus_topics

        result = planner.execute(user_message, **kwargs)

        # Commit session state changes (planner may have updated agent_state)
        db.commit()
        db.refresh(active_session)

        # Extract plan data (PlannerAgent returns "study_plan" key)
        plan_data = result.get("study_plan", {})
        explanation = result.get("explanation", "Study plan generated successfully")

        # Convert to StudyPlanResponse
        response = StudyPlanResponse(
            plan_id=plan_data.get("plan_id", "unknown"),
            student_id=request.student_id,
            exam_type=student.exam_type,
            timeline_days=plan_data.get("timeline_days", request.timeline_days),
            total_topics=plan_data.get("total_topics", 0),
            topics=plan_data.get("topics", []),
            daily_schedule=plan_data.get("daily_schedule", []),
            milestones=plan_data.get("milestones", []),
            explanation=explanation,
            total_estimated_hours=plan_data.get("total_hours", 0.0),
        )

        logger.info(f"Generated plan {response.plan_id} with {response.total_topics} topics")

        return response

    except Exception as e:
        logger.error(f"Error generating study plan: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating study plan: {str(e)}",
        )


@router.get("/{student_id}", response_model=StudyPlanResponse)
def get_latest_plan(
    student_id: str,
    current_student: Student = Depends(get_current_student),
    db: DBSessionType = Depends(get_db),
):
    """
    Get the latest study plan for the authenticated student.

    Note: Currently generates a new plan on request.
    In production, this should retrieve stored plans from database.

    Args:
        student_id: Student ID (must be the caller's own)
        current_student: Student resolved from the access token
        db: Database session

    Returns:
        StudyPlanResponse: Latest study plan

    Raises:
        HTTPException: 401 if unauthenticated, 403 if requesting another
            student's plan
    """
    verify_student_access(student_id, current_student)

    # For now, generate a default 30-day plan
    # In production, retrieve from database
    request = StudyPlanRequest(student_id=student_id, timeline_days=30)

    return generate_study_plan(request, current_student, db)
