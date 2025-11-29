"""
Pydantic schemas for Feedback/Progress-related API endpoints.
"""
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class ReportType(str, Enum):
    """Types of feedback reports"""
    STUDENT = "student"
    TEACHER = "teacher"
    DATA = "data"


class FeedbackRequest(BaseModel):
    """Request schema for getting feedback/progress report"""
    student_id: str = Field(..., description="Student ID")
    report_type: ReportType = Field(ReportType.STUDENT, description="Type of report to generate")
    format: str = Field("text", description="Output format (text/json)")
    include_recommendations: bool = Field(True, description="Include personalized recommendations")

    class Config:
        schema_extra = {
            "example": {
                "student_id": "123e4567-e89b-12d3-a456-426614174000",
                "report_type": "student",
                "format": "json",
                "include_recommendations": True
            }
        }


class OverallStats(BaseModel):
    """Overall performance statistics"""
    total_topics: int = Field(..., ge=0, description="Total topics studied")
    total_attempts: int = Field(..., ge=0, description="Total quiz attempts")
    total_correct: int = Field(..., ge=0, description="Total correct answers")
    overall_accuracy: float = Field(..., ge=0, le=100, description="Overall accuracy percentage")
    total_time_minutes: float = Field(..., ge=0, description="Total study time in minutes")
    weak_topics_count: int = Field(..., ge=0, description="Number of weak topics")
    strong_topics_count: int = Field(..., ge=0, description="Number of strong topics")
    mastery_topics_count: int = Field(..., ge=0, description="Number of mastered topics")
    recently_practiced_count: int = Field(..., ge=0, description="Topics practiced in last 7 days")

    class Config:
        schema_extra = {
            "example": {
                "total_topics": 10,
                "total_attempts": 87,
                "total_correct": 61,
                "overall_accuracy": 70.1,
                "total_time_minutes": 245.5,
                "weak_topics_count": 3,
                "strong_topics_count": 4,
                "mastery_topics_count": 2,
                "recently_practiced_count": 6
            }
        }


class TopicPerformance(BaseModel):
    """Performance data for a single topic"""
    topic: str = Field(..., description="Topic name")
    difficulty: str = Field(..., description="Current difficulty level")
    accuracy: float = Field(..., ge=0, le=100, description="Accuracy percentage")
    attempts: int = Field(..., ge=0, description="Number of attempts")
    correct: int = Field(..., ge=0, description="Correct answers")
    time_spent_minutes: float = Field(..., ge=0, description="Time spent on topic")
    last_practiced: datetime = Field(..., description="Last practice timestamp")
    days_since_practice: int = Field(..., ge=0, description="Days since last practice")
    consecutive_correct: int = Field(..., ge=0, description="Current correct streak")
    max_streak: int = Field(..., ge=0, description="Best streak achieved")
    mastery_achieved: bool = Field(..., description="Whether mastery level reached")
    needs_review: bool = Field(..., description="Whether review is recommended")
    trend: str = Field(..., description="Performance trend (improving/stable/declining)")
    trend_value: float = Field(..., description="Trend value (positive=improving)")
    common_mistakes: List[str] = Field(default=[], description="Common mistake patterns")

    class Config:
        schema_extra = {
            "example": {
                "topic": "Calculus",
                "difficulty": "medium",
                "accuracy": 67.5,
                "attempts": 20,
                "correct": 13,
                "time_spent_minutes": 45.0,
                "last_practiced": "2024-01-14T15:30:00Z",
                "days_since_practice": 1,
                "consecutive_correct": 3,
                "max_streak": 5,
                "mastery_achieved": False,
                "needs_review": False,
                "trend": "improving",
                "trend_value": 12.5,
                "common_mistakes": ["Sign errors in chain rule"]
            }
        }


class ProgressReportResponse(BaseModel):
    """Response schema for progress/feedback report"""
    student_id: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    overall_stats: OverallStats
    weak_topics: List[TopicPerformance] = Field(..., description="Topics needing attention")
    strong_topics: List[TopicPerformance] = Field(..., description="Strong performance topics")
    improving_topics: List[TopicPerformance] = Field(..., description="Topics showing improvement")
    declining_topics: List[TopicPerformance] = Field(..., description="Topics with declining performance")
    recommendations: List[str] = Field(..., description="Personalized recommendations")
    needs_replanning: bool = Field(..., description="Whether new study plan is recommended")
    report_summary: Optional[str] = Field(None, description="Human-readable summary")

    class Config:
        schema_extra = {
            "example": {
                "student_id": "123e4567-e89b-12d3-a456-426614174000",
                "generated_at": "2024-01-15T10:00:00Z",
                "overall_stats": {},  # OverallStats object
                "weak_topics": [],  # List of TopicPerformance objects
                "strong_topics": [],
                "improving_topics": [],
                "declining_topics": [],
                "recommendations": [
                    "Focus on Calculus - your weakest area",
                    "Practice Organic Chemistry regularly to prevent decline"
                ],
                "needs_replanning": True,
                "report_summary": "Overall performance is 70.1%. Focus on 3 weak areas..."
            }
        }


class TopicProgressUpdate(BaseModel):
    """Request schema for manually updating topic progress"""
    student_id: str = Field(..., description="Student ID")
    topic: str = Field(..., description="Topic name")
    difficulty: str = Field(..., description="Difficulty level")
    is_correct: bool = Field(..., description="Whether attempt was correct")
    time_spent_minutes: float = Field(0, ge=0, description="Time spent")
    mistake_pattern: Optional[str] = Field(None, description="Mistake pattern if incorrect")

    class Config:
        schema_extra = {
            "example": {
                "student_id": "123e4567-e89b-12d3-a456-426614174000",
                "topic": "Calculus",
                "difficulty": "medium",
                "is_correct": True,
                "time_spent_minutes": 5.5,
                "mistake_pattern": None
            }
        }


class ProgressStatsResponse(BaseModel):
    """Quick progress statistics response"""
    student_id: str
    overall_accuracy: float = Field(..., ge=0, le=100)
    total_attempts: int = Field(..., ge=0)
    weak_count: int = Field(..., ge=0)
    strong_count: int = Field(..., ge=0)
    last_activity: Optional[datetime] = None

    class Config:
        schema_extra = {
            "example": {
                "student_id": "123e4567-e89b-12d3-a456-426614174000",
                "overall_accuracy": 70.1,
                "total_attempts": 87,
                "weak_count": 3,
                "strong_count": 4,
                "last_activity": "2024-01-14T15:30:00Z"
            }
        }
