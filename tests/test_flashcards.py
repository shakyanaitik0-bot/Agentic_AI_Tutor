"""Flashcard generation: the agent wiring and the route end to end."""

import asyncio
import json

import pytest

from app.agents import flashcard_agent as fa
from app.services.unified_retrieval_service import Citation, RetrievalResponse, SourceType


class StubLLM:
    async def generate(self, prompt, **kwargs):
        assert "Generate 3 high-quality flashcards" in prompt
        return (
            "Sure!\n```json\n"
            + json.dumps(
                [
                    {
                        "type": "definition",
                        "front": "What is a derivative?",
                        "back": "The instantaneous rate of change.",
                        "hints": ["slope"],
                        "tags": ["calculus"],
                        "difficulty": "medium",
                    },
                    {
                        "type": "cloze",
                        "front": "d/dx of x^2 is ___",
                        "back": "2x",
                        "hints": [],
                        "tags": ["calculus"],
                        "difficulty": "easy",
                    },
                    {
                        "type": "formula",
                        "front": "Power rule",
                        "back": "d/dx x^n = n·x^(n-1)",
                        "hints": [],
                        "tags": ["calculus"],
                        "difficulty": "medium",
                    },
                ]
            )
            + "\n```"
        )


class StubRetrieval:
    def retrieve(self, query, student_id=None, topic=None, include_web=True, max_results=5):
        return RetrievalResponse(
            context="Calculus notes: a derivative measures rate of change.",
            citations=[
                Citation(
                    id=1,
                    source_type=SourceType.DOCUMENT,
                    title="Calc notes.pdf",
                    reference="calc.pdf",
                    snippet="derivatives",
                    relevance_score=0.9,
                )
            ],
            sources_used=[SourceType.DOCUMENT],
            has_documents=True,
            used_web_fallback=False,
            query=query,
            retrieval_time_ms=1.0,
        )


@pytest.fixture(autouse=True)
def stub_services(monkeypatch):
    monkeypatch.setattr(fa, "get_llm_service", lambda: StubLLM())
    monkeypatch.setattr(fa, "get_unified_retrieval_service", lambda: StubRetrieval())
    fa._flashcard_agent = None
    yield
    fa._flashcard_agent = None


def _auth(client):
    r = client.post(
        "/api/students/register",
        json={
            "name": "Naitik",
            "email": "naitik@example.com",
            "password": "Str0ngPassw0rd!",
            "exam_type": "JEE",
        },
    )
    assert r.status_code in (200, 201), r.text
    body = r.json()
    return body["id"], {"Authorization": f"Bearer {body['access_token']}"}


def test_generate_flashcards_end_to_end(client):
    student_id, headers = _auth(client)

    r = client.post(
        f"/api/flashcards/generate/{student_id}",
        json={"topic": "Derivatives", "num_cards": 3, "difficulty": "medium"},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    deck = r.json()
    assert deck["card_count"] == 3
    assert deck["topic"] == "Derivatives"

    decks = client.get(f"/api/flashcards/decks/{student_id}", headers=headers)
    assert decks.status_code == 200
    assert len(decks.json()) == 1

    study = client.get(f"/api/flashcards/study/{deck['id']}", headers=headers)
    assert study.status_code == 200, study.text
    cards = study.json()["cards"]
    assert len(cards) == 3
    assert any(c["front"] == "What is a derivative?" for c in cards)
    assert any(c["type"] == "cloze" for c in cards)
    assert any(c["hints"] == ["slope"] for c in cards)


@pytest.mark.asyncio
async def test_agent_returns_agent_response():
    agent = fa.get_flashcard_agent()
    resp = await agent.process(topic="Derivatives", num_cards=3, student_id="s1")
    assert isinstance(resp, fa.AgentResponse)
    assert resp.success is True
    assert resp.data["card_count"] == 3
    assert resp.metadata["sources_used"][0]["title"] == "Calc notes.pdf"


class FailingLLM:
    """A provider call that fails the way a retired model does."""

    async def generate(self, prompt, **kwargs):
        raise RuntimeError(
            "NotFound: 404 models/gemini-2.5-flash-lite is no longer available to new users."
        )


class MessyLLM:
    """Well-formed cards, dressed the way models actually dress them."""

    async def generate(self, prompt, **kwargs):
        return (
            "Sure, here are your cards:\n"
            "```json\n"
            '[{"type": "Cloze", "front": "Motion is ___ to a frame", "back": "relative",'
            ' "hints": "pick a frame", "tags": null, "difficulty": "easy"},\n'
            ' {"type": "fill in the blank", "front": "Speed is ___ over time",'
            ' "back": "distance", "difficulty": "medium"}]\n'
            "```\n"
            "Tell me if you want more [cards]!"
        )


def test_a_failed_generation_reports_the_provider_error(monkeypatch):
    """It must not answer a dead provider with placeholder cards."""
    monkeypatch.setattr(fa, "get_llm_service", lambda: FailingLLM())
    fa._flashcard_agent = None

    async def run():
        return await fa.get_flashcard_agent().process(topic="Motion", num_cards=3)

    response = asyncio.run(run())

    assert response.success is False
    assert "no longer available" in response.message
    assert response.data is None


def test_model_phrasing_still_yields_real_cards(monkeypatch):
    """A capitalised or invented type used to discard the whole batch."""
    monkeypatch.setattr(fa, "get_llm_service", lambda: MessyLLM())
    fa._flashcard_agent = None

    async def run():
        return await fa.get_flashcard_agent().process(topic="Motion", num_cards=5)

    response = asyncio.run(run())

    assert response.success is True
    cards = response.data["cards"]
    assert len(cards) == 2
    assert [c["type"] for c in cards] == ["cloze", "cloze"]
    assert cards[0]["back"] == "relative"
    assert cards[0]["hints"] == ["pick a frame"]
    assert cards[0]["tags"] == ["motion"]
    assert not any("[Answer about" in c["back"] for c in cards)
