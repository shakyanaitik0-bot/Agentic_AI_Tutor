"""
Chat API endpoint.

Main conversational interface using the Orchestrator agent.
"""

import logging
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.orm import Session as DBSessionType

from app.api.dependencies import get_current_student, get_db
from app.models.session import Session as DBSession, Message
from app.models.student import Student
from app.agents.orchestrator import create_orchestrator

router = APIRouter()
logger = logging.getLogger(__name__)


class ChatRequest(BaseModel):
    """Request schema for chat endpoint"""

    session_id: str = Field(..., description="Active session ID")
    message: str = Field(..., min_length=1, max_length=2000, description="User message")
    intent: str | None = Field(
        None, description="Optional explicit intent (plan/quiz/feedback/conversation)"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "session_id": "123e4567-e89b-12d3-a456-426614174000",
                "message": "Create a 30-day study plan for JEE",
                "intent": None,
            }
        }
    )


class ChatResponse(BaseModel):
    """Response schema for chat endpoint"""

    session_id: str
    message_id: int
    agent_response: Dict[str, Any]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "session_id": "123e4567-e89b-12d3-a456-426614174000",
                "message_id": 42,
                "agent_response": {"agent": "PlannerAgent", "intent": "plan", "plan": {}},
            }
        }
    )


@router.post("", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    current_student: Student = Depends(get_current_student),
    db: DBSessionType = Depends(get_db),
):
    """
    Send a message and get AI tutor response.

    Routes the message to appropriate agent via Orchestrator.

    Args:
        request: Chat request with session ID and message
        current_student: Student resolved from the access token
        db: Database session

    Returns:
        ChatResponse: Agent response

    Raises:
        HTTPException: 401 if unauthenticated, 404 if the session does not
            belong to the caller, 400 if session inactive
    """
    # Get and verify session. Sessions owned by another student are reported
    # as missing so session IDs cannot be probed.
    session = db.query(DBSession).filter(DBSession.id == request.session_id).first()
    if not session or session.student_id != current_student.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Session {request.session_id} not found"
        )

    if not session.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Session {request.session_id} is not active",
        )

    # Save user message
    user_message = Message(
        session_id=session.id, role="user", content=request.message, message_type="chat"
    )
    db.add(user_message)
    db.commit()

    logger.info(f"Chat message from session {session.id}: '{request.message[:50]}...'")

    try:
        # Create orchestrator and get response
        orchestrator = create_orchestrator(student=session.student, session=session, db=db)

        # Pass explicit intent if provided
        kwargs = {}
        if request.intent:
            kwargs["intent"] = request.intent

        agent_response = orchestrator.execute(request.message, **kwargs)

        # Commit session state changes (agents may have updated agent_state)
        db.commit()
        db.refresh(session)

        # Save assistant response
        assistant_message = Message(
            session_id=session.id,
            role="assistant",
            content=str(agent_response),  # Serialize response
            message_type="chat",
            message_metadata=agent_response,
        )
        db.add(assistant_message)
        db.commit()
        db.refresh(assistant_message)

        logger.info(f"Agent response: {agent_response.get('agent', 'Unknown')}")

        return ChatResponse(
            session_id=session.id, message_id=assistant_message.id, agent_response=agent_response
        )

    except Exception as e:
        logger.error(f"Error processing chat: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing message: {str(e)}",
        )
