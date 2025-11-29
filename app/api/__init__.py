"""
API router aggregation.

Combines all route modules into a single router for the main app.
"""
from fastapi import APIRouter

# Import route modules (will be created next)
# from app.api.routes import students, sessions, chat, quiz, feedback, plan

# Create main API router
api_router = APIRouter()

# Include all route modules
# Note: Routes will be added as we create them
# api_router.include_router(students.router, prefix="/students", tags=["Students"])
# api_router.include_router(sessions.router, prefix="/sessions", tags=["Sessions"])
# api_router.include_router(chat.router, prefix="/chat", tags=["Chat"])
# api_router.include_router(quiz.router, prefix="/quiz", tags=["Quiz"])
# api_router.include_router(feedback.router, prefix="/feedback", tags=["Feedback"])
# api_router.include_router(plan.router, prefix="/plan", tags=["Study Plans"])
