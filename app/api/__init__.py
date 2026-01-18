"""
API router aggregation.

Combines all route modules into a single router for the main app.
"""

from fastapi import APIRouter

# Import all route modules
from app.api.routes import students, sessions, chat, quiz, feedback, plan, documents, flashcards

# Create main API router
api_router = APIRouter()

# Include all route modules with prefixes and tags
api_router.include_router(students.router, prefix="/students", tags=["Students"])
api_router.include_router(sessions.router, prefix="/sessions", tags=["Sessions"])
api_router.include_router(chat.router, prefix="/chat", tags=["Chat"])
api_router.include_router(quiz.router, prefix="/quiz", tags=["Quiz"])
api_router.include_router(feedback.router, prefix="/feedback", tags=["Feedback"])
api_router.include_router(plan.router, prefix="/plan", tags=["Study Plans"])
api_router.include_router(documents.router, prefix="/documents", tags=["Documents"])
api_router.include_router(flashcards.router, tags=["Flashcards"])
