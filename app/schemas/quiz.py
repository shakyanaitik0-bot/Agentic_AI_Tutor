"""
Pydantic schemas for Quiz-related API endpoints.
"""

from pydantic import BaseModel, Field, validator, ConfigDict
from typing import List, Optional
from datetime import datetime

from app.schemas.common import DifficultyLevel


class QuizRequest(BaseModel):
    """Request schema for generating a quiz"""

    topic: str = Field(..., min_length=2, max_length=100, description="Topic for the quiz")
    difficulty: Optional[DifficultyLevel] = Field(
        None, description="Difficulty level (auto-selected if not provided)"
    )
    num_questions: int = Field(3, ge=1, le=10, description="Number of questions (1-10)")
    student_id: str = Field(..., description="Student ID for adaptive difficulty")

    @validator("num_questions")
    def validate_num_questions(cls, v):
        """Ensure reasonable number of questions"""
        if v < 1 or v > 10:
            raise ValueError("Number of questions must be between 1 and 10")
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "topic": "Calculus",
                "difficulty": "medium",
                "num_questions": 5,
                "student_id": "123e4567-e89b-12d3-a456-426614174000",
            }
        }
    )


class QuizQuestion(BaseModel):
    """Schema for a single quiz question"""

    question_id: str = Field(..., description="Unique question identifier")
    question_text: str = Field(..., description="The question text")
    options: List[str] = Field(..., min_items=4, max_items=4, description="Four answer options")
    correct_answer_index: int = Field(..., ge=0, le=3, description="Index of correct answer (0-3)")
    explanation: str = Field(..., description="Explanation of the correct answer")
    topic: str = Field(..., description="Topic of the question")
    difficulty: str = Field(..., description="Difficulty level")

    @validator("options")
    def validate_options(cls, v):
        """Ensure exactly 4 unique options"""
        if len(v) != 4:
            raise ValueError("Must have exactly 4 options")
        if len(set(v)) != 4:
            raise ValueError("All options must be unique")
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "question_id": "q_1234",
                "question_text": "What is the derivative of x^2?",
                "options": ["x", "2x", "x^2", "2"],
                "correct_answer_index": 1,
                "explanation": "Using the power rule, d/dx(x^n) = nx^(n-1), so d/dx(x^2) = 2x",
                "topic": "Calculus",
                "difficulty": "easy",
            }
        }
    )


class QuizResponse(BaseModel):
    """Response schema for generated quiz"""

    quiz_id: str = Field(..., description="Unique quiz identifier")
    topic: str
    difficulty: str
    num_questions: int
    questions: List[QuizQuestion]
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    student_id: str

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "quiz_id": "quiz_5678",
                "topic": "Calculus",
                "difficulty": "medium",
                "num_questions": 3,
                "questions": [],  # List of QuizQuestion objects
                "generated_at": "2024-01-15T10:30:00Z",
                "student_id": "123e4567-e89b-12d3-a456-426614174000",
            }
        }
    )


class QuizSubmission(BaseModel):
    """Request schema for submitting quiz answers"""

    quiz_id: str = Field(..., description="Quiz ID being submitted")
    student_id: str = Field(..., description="Student ID")
    answers: List[int] = Field(..., description="List of selected answer indices (0-3)")

    @validator("answers")
    def validate_answers(cls, v):
        """Ensure all answers are valid indices"""
        for answer in v:
            if answer < 0 or answer > 3:
                raise ValueError("Answer indices must be between 0 and 3")
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "quiz_id": "quiz_5678",
                "student_id": "123e4567-e89b-12d3-a456-426614174000",
                "answers": [1, 2, 0],
            }
        }
    )


class QuestionResult(BaseModel):
    """Result for a single question"""

    question_id: str
    selected_answer: int
    correct_answer: int
    is_correct: bool
    explanation: str


class QuizResult(BaseModel):
    """Response schema for quiz grading results"""

    quiz_id: str
    student_id: str
    total_questions: int
    correct_answers: int
    accuracy: float = Field(..., ge=0, le=100, description="Accuracy percentage")
    passed: bool = Field(..., description="Whether student passed (>= 60%)")
    results: List[QuestionResult] = Field(..., description="Per-question results")
    graded_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "quiz_id": "quiz_5678",
                "student_id": "123e4567-e89b-12d3-a456-426614174000",
                "total_questions": 3,
                "correct_answers": 2,
                "accuracy": 66.7,
                "passed": True,
                "results": [],  # List of QuestionResult objects
                "graded_at": "2024-01-15T10:35:00Z",
            }
        }
    )
