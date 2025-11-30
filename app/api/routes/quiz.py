"""
Quiz API endpoints.

Handles quiz generation and submission.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as DBSessionType

from app.api.dependencies import get_db, get_student_by_id
from app.models.student import Student
from app.models.session import Session as DBSession
from app.agents.quiz_agent import QuizGeneratorAgent
from app.schemas.quiz import QuizRequest, QuizResponse, QuizSubmission, QuizResult

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/generate", response_model=QuizResponse)
def generate_quiz(
    request: QuizRequest,
    db: DBSessionType = Depends(get_db)
):
    """
    Generate an adaptive quiz for a student.

    Args:
        request: Quiz generation request
        db: Database session

    Returns:
        QuizResponse: Generated quiz

    Raises:
        HTTPException: 404 if student not found
    """
    # Get student
    student = db.query(Student).filter(Student.id == request.student_id).first()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student {request.student_id} not found"
        )

    # Get or create active session for quiz
    active_session = db.query(DBSession).filter(
        DBSession.student_id == student.id,
        DBSession.is_active == True
    ).first()

    if not active_session:
        # Create new session
        active_session = DBSession(
            student_id=student.id,
            is_active=True,
            session_type="quiz"
        )
        db.add(active_session)
        db.commit()
        db.refresh(active_session)

    logger.info(f"Generating quiz for {student.name} on {request.topic}")

    try:
        # Create quiz agent
        quiz_agent = QuizGeneratorAgent(
            student=student,
            session=active_session,
            db=db
        )

        # Generate quiz
        user_message = f"Generate a quiz on {request.topic}"
        kwargs = {
            "topic": request.topic,
            "num_questions": request.num_questions
        }

        if request.difficulty:
            kwargs["difficulty"] = request.difficulty.value

        result = quiz_agent.execute(user_message, **kwargs)

        # Extract quiz data from result
        quiz_data = result.get("quiz", {})

        # Convert to QuizResponse format
        response = QuizResponse(
            quiz_id=quiz_data.get("quiz_id", "unknown"),
            topic=quiz_data.get("topic", request.topic),
            difficulty=quiz_data.get("difficulty", "medium"),
            num_questions=len(quiz_data.get("questions", [])),
            questions=quiz_data.get("questions", []),
            student_id=request.student_id
        )

        logger.info(f"Generated quiz {response.quiz_id} with {response.num_questions} questions")

        return response

    except Exception as e:
        logger.error(f"Error generating quiz: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating quiz: {str(e)}"
        )


@router.post("/submit", response_model=QuizResult)
def submit_quiz(
    submission: QuizSubmission,
    db: DBSessionType = Depends(get_db)
):
    """
    Submit quiz answers for grading.

    Args:
        submission: Quiz submission with answers
        db: Database session

    Returns:
        QuizResult: Grading results

    Raises:
        HTTPException: 404 if student not found
    """
    # Get student
    student = db.query(Student).filter(Student.id == submission.student_id).first()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student {submission.student_id} not found"
        )

    # Get active session
    active_session = db.query(DBSession).filter(
        DBSession.student_id == student.id,
        DBSession.is_active == True
    ).first()

    if not active_session:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active session found. Start a session first."
        )

    logger.info(f"Grading quiz {submission.quiz_id} for {student.name}")

    try:
        # Create quiz agent
        quiz_agent = QuizGeneratorAgent(
            student=student,
            session=active_session,
            db=db
        )

        # Retrieve quiz data from session state
        session_state = active_session.agent_state or {}
        stored_quiz = session_state.get("last_quiz")

        if not stored_quiz or stored_quiz.get("quiz_id") != submission.quiz_id:
            logger.warning(f"Quiz {submission.quiz_id} not found in session state")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Quiz not found. Please generate a new quiz."
            )

        # Grade the quiz (this will update Progress records)
        result = quiz_agent.grade_quiz(stored_quiz, submission.answers)

        # Convert to QuizResult format
        response = QuizResult(
            quiz_id=submission.quiz_id,
            student_id=submission.student_id,
            total_questions=result.get("total_questions", 0),
            correct_answers=result.get("correct_answers", 0),
            accuracy=result.get("accuracy", 0.0),
            passed=result.get("passed", False),
            results=result.get("results", [])
        )

        logger.info(f"Quiz graded: {response.accuracy:.1f}% ({response.correct_answers}/{response.total_questions})")

        return response

    except Exception as e:
        logger.error(f"Error grading quiz: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error grading quiz: {str(e)}"
        )
