"""Orchestrator intent routing and error reporting."""

import pytest

from app.agents.orchestrator import IntentType, OrchestratorAgent
from app.core.security import get_password_hash
from app.models.session import Session as DBSession
from app.models.student import Student


class StubLLM:
    """Stands in for LLMService; the orchestrator only ever asks it for text."""

    def __init__(self, reply="CONVERSATION", error=None):
        self.reply = reply
        self.error = error

    def chat_completion(self, messages, **kwargs):
        if self.error:
            raise self.error
        return self.reply


class StubRAG:
    def get_context(self, query, top_k=None, metadata_filter=None):
        return "", []


@pytest.fixture
def orchestrator(test_db):
    student = Student(
        name="Naitik",
        email="naitik@example.com",
        password_hash=get_password_hash("Str0ngPassw0rd!"),
        exam_type="JEE",
    )
    test_db.add(student)
    test_db.commit()
    test_db.refresh(student)

    session = DBSession(student_id=student.id, session_type="chat")
    test_db.add(session)
    test_db.commit()
    test_db.refresh(session)

    def _make(llm=None):
        return OrchestratorAgent(
            student=student,
            session=session,
            db=test_db,
            llm_service=llm or StubLLM(),
            rag_service=StubRAG(),
        )

    return _make


@pytest.mark.parametrize(
    "message",
    [
        "Build me a 30-day plan",
        "Create a 30-day study plan for JEE",
        "make me a study plan",
        "draw up a plan for next month",
        "give me a revision roadmap",
    ],
)
def test_plan_requests_route_to_planner(orchestrator, message):
    """Plan requests must match a pattern, not fall through to the LLM classifier."""
    assert orchestrator()._classify_intent(message) == IntentType.PLAN


@pytest.mark.parametrize(
    "message,expected",
    [
        ("quiz me on kinematics", IntentType.QUIZ),
        ("how am I doing so far", IntentType.FEEDBACK),
        ("explain Newton's second law", IntentType.CONVERSATION),
    ],
)
def test_other_intents_still_classify(orchestrator, message, expected):
    assert orchestrator()._classify_intent(message) == expected


def test_failure_reports_the_cause(orchestrator):
    """A swallowed exception must still tell the user what actually went wrong."""
    orch = orchestrator(llm=StubLLM(error=RuntimeError("provider rejected the key")))

    response = orch.execute("explain Newton's second law")

    assert response["agent"] == "Orchestrator"
    assert "RuntimeError: provider rejected the key" == response["error"]
    assert "provider rejected the key" in response["message"]
