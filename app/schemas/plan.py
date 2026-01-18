"""
Pydantic schemas for Study Plan-related API endpoints.
"""

from pydantic import BaseModel, Field, validator, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import datetime


class StudyPlanRequest(BaseModel):
    """Request schema for generating a study plan"""

    student_id: str = Field(..., description="Student ID")
    timeline_days: int = Field(..., ge=7, le=365, description="Plan duration in days (7-365)")
    focus_topics: Optional[List[str]] = Field(None, description="Specific topics to focus on")
    hours_per_day: Optional[float] = Field(None, ge=1, le=12, description="Study hours per day")

    @validator("timeline_days")
    def validate_timeline(cls, v):
        """Ensure reasonable timeline"""
        if v < 7:
            raise ValueError("Timeline must be at least 7 days")
        if v > 365:
            raise ValueError("Timeline cannot exceed 365 days")
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "student_id": "123e4567-e89b-12d3-a456-426614174000",
                "timeline_days": 30,
                "focus_topics": ["Calculus", "Organic Chemistry"],
                "hours_per_day": 4.5,
            }
        }
    )


class StudyPlanTopic(BaseModel):
    """Schema for a topic in the study plan"""

    topic: str = Field(..., description="Topic name")
    priority: int = Field(..., ge=1, le=5, description="Priority level (1=highest, 5=lowest)")
    urgency: str = Field(..., description="Urgency level (high/medium/low)")
    reason: str = Field(..., description="Why this topic is included")
    estimated_hours: float = Field(..., ge=0, description="Estimated study hours needed")
    difficulty_level: str = Field(..., description="Current difficulty to start with")
    subtopics: Optional[List[str]] = Field(default=[], description="Subtopics to cover")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "topic": "Calculus - Derivatives",
                "priority": 1,
                "urgency": "high",
                "reason": "Low accuracy (45%) indicates fundamental gaps",
                "estimated_hours": 8.0,
                "difficulty_level": "easy",
                "subtopics": ["Power rule", "Chain rule", "Product rule"],
            }
        }
    )


class DailySchedule(BaseModel):
    """Schema for daily study schedule"""

    day: int = Field(..., ge=1, description="Day number in the plan")
    date: Optional[str] = Field(None, description="Actual date (YYYY-MM-DD)")
    topics: List[str] = Field(..., min_items=1, description="Topics to study this day")
    hours_allocated: float = Field(..., ge=0, description="Total hours for the day")
    focus_areas: List[str] = Field(default=[], description="Specific focus areas")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "day": 1,
                "date": "2024-01-15",
                "topics": ["Calculus - Derivatives", "Algebra - Quadratics"],
                "hours_allocated": 4.0,
                "focus_areas": ["Power rule problems", "Solving quadratic equations"],
            }
        }
    )


class Milestone(BaseModel):
    """Schema for plan milestones"""

    day: int = Field(..., description="Day when milestone should be achieved")
    percentage: int = Field(..., ge=0, le=100, description="Percentage of plan completed")
    description: str = Field(..., description="Milestone description")
    topics_covered: List[str] = Field(
        default=[], description="Topics that should be covered by this point"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "day": 7,
                "percentage": 25,
                "description": "Week 1 Complete - Foundation Topics",
                "topics_covered": ["Calculus basics", "Algebra fundamentals"],
            }
        }
    )


class StudyPlanResponse(BaseModel):
    """Response schema for generated study plan"""

    plan_id: str = Field(..., description="Unique plan identifier")
    student_id: str
    exam_type: str
    timeline_days: int
    total_topics: int
    topics: List[StudyPlanTopic] = Field(..., description="Ordered list of topics to study")
    daily_schedule: List[DailySchedule] = Field(..., description="Day-by-day schedule")
    milestones: List[Milestone] = Field(..., description="Progress milestones")
    explanation: str = Field(..., description="Overall plan explanation and strategy")
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    total_estimated_hours: float = Field(..., description="Total study hours estimated")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "plan_id": "plan_1234",
                "student_id": "123e4567-e89b-12d3-a456-426614174000",
                "exam_type": "JEE",
                "timeline_days": 30,
                "total_topics": 8,
                "topics": [],
                "daily_schedule": [],
                "milestones": [],
                "explanation": "This 30-day plan focuses on your weak areas...",
                "generated_at": "2024-01-15T10:00:00Z",
                "total_estimated_hours": 120.0,
            }
        }
    )


class PlanUpdateRequest(BaseModel):
    """Request schema for updating an existing plan"""

    plan_id: str = Field(..., description="Plan ID to update")
    student_id: str = Field(..., description="Student ID")
    adjustments: Dict[str, Any] = Field(..., description="Requested adjustments")
    reason: str = Field(..., description="Reason for update")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "plan_id": "plan_1234",
                "student_id": "123e4567-e89b-12d3-a456-426614174000",
                "adjustments": {"add_topics": ["Thermodynamics"], "extend_days": 10},
                "reason": "Need more time for Physics topics",
            }
        }
    )
