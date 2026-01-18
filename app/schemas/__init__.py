"""
Pydantic schemas for API request/response validation.

These schemas are used by FastAPI for:
- Request validation
- Response serialization
- OpenAPI documentation generation
"""

from app.schemas.quiz import QuizRequest, QuizQuestion, QuizResponse, QuizSubmission, QuizResult
from app.schemas.plan import (
    StudyPlanRequest,
    StudyPlanResponse,
    StudyPlanTopic,
    DailySchedule,
    Milestone,
)
from app.schemas.feedback import (
    FeedbackRequest,
    ProgressReportResponse,
    TopicPerformance,
    OverallStats,
)
from app.schemas.common import (
    StudentCreate,
    StudentResponse,
    SessionCreate,
    SessionResponse,
    MessageResponse,
)

__all__ = [
    # Quiz schemas
    "QuizRequest",
    "QuizQuestion",
    "QuizResponse",
    "QuizSubmission",
    "QuizResult",
    # Plan schemas
    "StudyPlanRequest",
    "StudyPlanResponse",
    "StudyPlanTopic",
    "DailySchedule",
    "Milestone",
    # Feedback schemas
    "FeedbackRequest",
    "ProgressReportResponse",
    "TopicPerformance",
    "OverallStats",
    # Common schemas
    "StudentCreate",
    "StudentResponse",
    "SessionCreate",
    "SessionResponse",
    "MessageResponse",
]
