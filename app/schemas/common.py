"""
Common Pydantic schemas shared across the application.
"""
from pydantic import BaseModel, Field, EmailStr, validator, ConfigDict
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum


class ExamType(str, Enum):
    """Supported exam types"""
    JEE = "JEE"
    SAT = "SAT"
    GRE = "GRE"


class DifficultyLevel(str, Enum):
    """Difficulty levels for questions and topics"""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class StudentCreate(BaseModel):
    """Request schema for creating a new student"""
    name: str = Field(..., min_length=2, max_length=100, description="Student's full name")
    email: EmailStr = Field(..., description="Student's email address")
    exam_type: ExamType = Field(..., description="Type of exam preparing for")
    weak_areas: Optional[List[str]] = Field(default=[], description="Known weak topics")
    strong_areas: Optional[List[str]] = Field(default=[], description="Known strong topics")
    learning_preferences: Optional[Dict[str, Any]] = Field(
        default={},
        description="Learning preferences (visual, practice-heavy, etc.)"
    )
    api_key_openai: Optional[str] = Field(None, description="Optional OpenAI API key")
    api_key_gemini: Optional[str] = Field(None, description="Optional Gemini API key")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Rahul Sharma",
                "email": "rahul@example.com",
                "exam_type": "JEE",
                "weak_areas": ["Calculus", "Organic Chemistry"],
                "strong_areas": ["Algebra", "Mechanics"],
                "learning_preferences": {
                    "style": "visual",
                    "practice_intensity": "high"
                }
            }
        }
    )


class StudentResponse(BaseModel):
    """Response schema for student data"""
    id: str = Field(..., description="Unique student ID")
    name: str
    email: str
    exam_type: str
    weak_areas: List[str]
    strong_areas: List[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SessionCreate(BaseModel):
    """Request schema for creating a new session"""
    student_id: str = Field(..., description="Student ID")
    session_type: Optional[str] = Field("general", description="Type of session (quiz, study, feedback)")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "student_id": "123e4567-e89b-12d3-a456-426614174000",
                "session_type": "quiz"
            }
        }
    )


class SessionResponse(BaseModel):
    """Response schema for session data"""
    id: str = Field(..., description="Unique session ID")
    student_id: str
    is_active: bool
    started_at: datetime
    ended_at: Optional[datetime] = None
    session_type: Optional[str] = None
    questions_asked: int = 0
    questions_answered_correctly: int = 0

    model_config = ConfigDict(from_attributes=True)


class MessageResponse(BaseModel):
    """Response schema for chat messages"""
    id: int
    session_id: str
    role: str = Field(..., description="Message role (user/assistant)")
    content: str
    timestamp: datetime
    message_type: Optional[str] = Field(None, description="Type of message (chat, quiz, explanation)")

    model_config = ConfigDict(from_attributes=True)


class ErrorResponse(BaseModel):
    """Standard error response"""
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "error": "ValidationError",
                "message": "Invalid student ID format",
                "details": {"field": "student_id", "provided": "invalid-id"}
            }
        }
    )


class SuccessResponse(BaseModel):
    """Standard success response"""
    success: bool = True
    message: str = Field(..., description="Success message")
    data: Optional[Dict[str, Any]] = Field(None, description="Response data")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Operation completed successfully",
                "data": {"id": "123", "status": "active"}
            }
        }
    )
