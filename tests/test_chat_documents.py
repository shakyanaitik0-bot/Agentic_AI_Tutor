"""The tutor must use documents the student already uploaded to the Library."""

import pytest

from app.agents.base_agent import SimpleConversationAgent, refers_to_uploaded_material
from app.core.security import get_password_hash
from app.models.session import Session as DBSession
from app.models.student import Student

DOC_TEXT = "Assignment 1: derive the work-energy theorem for a variable force."


class StubRAG:
    """
    Stands in for RAGService, reproducing the behaviour that hid the upload:
    a student's own documents only come back when the search is scoped to
    them. An exam_type-only search is held to the stricter similarity
    threshold and returns nothing.
    """

    def __init__(self):
        self.filters_seen = []

    def get_context(self, query, top_k=None, metadata_filter=None):
        self.filters_seen.append(metadata_filter)
        if metadata_filter and "student_id" in metadata_filter:
            return DOC_TEXT, [{"id": "chunk-1", "score": 0.42}]
        return "", []

    def get_student_chunks(self, student_id, limit=5):
        return [{"content": DOC_TEXT, "filename": "ASSISMENT 1.docx", "metadata": {}}]

    def list_student_documents(self, student_id):
        return [{"filename": "ASSISMENT 1.docx", "num_chunks": 1}]


class CapturingLLM:
    """Records the prompt so the test can see what the tutor was told."""

    def __init__(self):
        self.prompts = []

    def chat_completion(self, messages, **kwargs):
        self.prompts.append(messages[-1]["content"])
        return "Here is what your assignment covers..."


@pytest.fixture
def agent(test_db):
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

    rag, llm = StubRAG(), CapturingLLM()
    conversation = SimpleConversationAgent(
        student=student, session=session, llm_service=llm, rag_service=rag
    )
    return conversation, rag, llm


def test_retrieval_is_scoped_to_the_students_own_uploads(agent):
    """Filtering on exam_type alone skipped the student's own documents."""
    conversation, rag, _ = agent

    context = conversation.retrieve_knowledge("work energy theorem", top_k=3)

    assert any(
        "student_id" in (f or {}) for f in rag.filters_seen
    ), "no search was scoped to the student, so their uploads can never match"
    assert DOC_TEXT in context


def test_asking_about_the_upload_reaches_the_document(agent):
    """The reported bug: the tutor claimed no file had been uploaded."""
    conversation, _, llm = agent

    conversation.execute("analyse the file that i uploaded")

    prompt = llm.prompts[-1]
    assert DOC_TEXT in prompt, "the document never reached the tutor"
    assert "ASSISMENT 1.docx" in prompt, "the tutor was not told the file exists"


def test_an_ordinary_question_does_not_read_the_library(agent):
    """Only a message about the upload should pull the whole document in."""
    conversation, _, llm = agent

    conversation.execute("what is Newton's second law")

    assert "ASSISMENT 1.docx" not in llm.prompts[-1]


@pytest.mark.parametrize(
    "message,expected",
    [
        ("analyse the file that i uploaded", True),
        ("summarise my notes", True),
        ("what's in the document?", True),
        ("explain Newton's second law", False),
        ("quiz me on kinematics", False),
    ],
)
def test_upload_references(message, expected):
    assert refers_to_uploaded_material(message) is expected
