"""
API router aggregation.

Combines all route modules into a single router for the main app.
"""

from fastapi import APIRouter, Depends

from app.api.dependencies import require_auth

# Import all route modules
from app.api.routes import students, sessions, chat, quiz, feedback, plan, documents, flashcards

# Create main API router
api_router = APIRouter()

# Every router below carries student data, so a valid access token is required
# at the router level as well as inside each endpoint. The router-level check
# means a new endpoint cannot be added without authentication by accident.
authenticated = [Depends(require_auth)]

# The students router is mounted without a router-level guard because
# /register, /login and /refresh are how a client obtains a token in the first
# place; its other endpoints depend on get_current_student individually.
api_router.include_router(students.router, prefix="/students", tags=["Students"])
api_router.include_router(
    sessions.router, prefix="/sessions", tags=["Sessions"], dependencies=authenticated
)
api_router.include_router(chat.router, prefix="/chat", tags=["Chat"], dependencies=authenticated)
api_router.include_router(quiz.router, prefix="/quiz", tags=["Quiz"], dependencies=authenticated)
api_router.include_router(
    feedback.router, prefix="/feedback", tags=["Feedback"], dependencies=authenticated
)
api_router.include_router(
    plan.router, prefix="/plan", tags=["Study Plans"], dependencies=authenticated
)
api_router.include_router(
    documents.router, prefix="/documents", tags=["Documents"], dependencies=authenticated
)
api_router.include_router(flashcards.router, tags=["Flashcards"], dependencies=authenticated)
