"""
Authentication and authorization tests.

Covers the two holes these tests exist to keep closed:
- data endpoints must reject requests that carry no valid access token
- a valid token for one student must not unlock another student's data
"""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token, create_tokens, verify_token

# ============================================================================
# Token issuing
# ============================================================================


class TestTokenIssuing:
    """Login and registration hand out usable tokens."""

    def test_login_returns_tokens(self, client: TestClient, sample_student):
        response = client.post(
            "/api/students/login",
            json={"email": sample_student.email, "password": "testpassword123"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["token_type"] == "bearer"
        assert data["expires_in"] > 0
        assert data["id"] == sample_student.id

        token_data = verify_token(data["access_token"], token_type="access")
        assert token_data is not None
        assert token_data.student_id == sample_student.id

    def test_register_returns_tokens(self, client: TestClient):
        response = client.post(
            "/api/students/register",
            json={
                "name": "New Student",
                "email": f"new.{uuid.uuid4().hex[:8]}@example.com",
                "password": "securepassword123",
                "exam_type": "JEE",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert verify_token(data["access_token"], token_type="access") is not None
        assert data["name"] == "New Student"

    def test_login_wrong_password_issues_no_token(self, client: TestClient, sample_student):
        response = client.post(
            "/api/students/login",
            json={"email": sample_student.email, "password": "wrongpassword"},
        )

        assert response.status_code == 401
        assert "access_token" not in response.json()

    def test_refresh_returns_new_tokens(self, client: TestClient, sample_student):
        tokens = create_tokens(sample_student.id, sample_student.email)

        response = client.post(
            "/api/students/refresh", json={"refresh_token": tokens.refresh_token}
        )

        assert response.status_code == 200
        data = response.json()
        assert verify_token(data["access_token"], token_type="access") is not None

    def test_refresh_rejects_access_token(self, client: TestClient, sample_student):
        """An access token must not work where a refresh token is expected."""
        tokens = create_tokens(sample_student.id, sample_student.email)

        response = client.post("/api/students/refresh", json={"refresh_token": tokens.access_token})

        assert response.status_code == 401

    def test_refresh_rejects_garbage(self, client: TestClient):
        response = client.post("/api/students/refresh", json={"refresh_token": "not-a-jwt"})

        assert response.status_code == 401


# ============================================================================
# Endpoints reject unauthenticated callers
# ============================================================================


# (method, path) pairs covering every data-access router.
PROTECTED_ENDPOINTS = [
    ("get", "/api/students/{student_id}"),
    ("get", "/api/students/me"),
    ("post", "/api/sessions/start"),
    ("get", "/api/sessions?student_id={student_id}"),
    ("get", "/api/sessions/some-session-id"),
    ("post", "/api/sessions/some-session-id/end"),
    ("get", "/api/sessions/some-session-id/messages"),
    ("post", "/api/chat"),
    ("post", "/api/quiz/generate"),
    ("post", "/api/quiz/submit"),
    ("post", "/api/plan/generate"),
    ("get", "/api/plan/{student_id}"),
    ("get", "/api/feedback/{student_id}"),
    ("post", "/api/feedback/request"),
    ("get", "/api/documents/list/{student_id}"),
    ("post", "/api/flashcards/generate/{student_id}"),
    ("get", "/api/flashcards/decks/{student_id}"),
    ("get", "/api/flashcards/deck/some-deck-id"),
    ("get", "/api/flashcards/study/some-deck-id"),
    ("get", "/api/flashcards/card/some-card-id/reveal"),
    ("post", "/api/flashcards/review"),
    ("delete", "/api/flashcards/deck/some-deck-id"),
    ("get", "/api/flashcards/stats/{student_id}"),
]


class TestUnauthenticatedAccess:
    """No token means no student data, on every endpoint."""

    @pytest.mark.parametrize("method,path", PROTECTED_ENDPOINTS)
    def test_requires_token(self, client: TestClient, sample_student, method, path):
        url = path.format(student_id=sample_student.id)
        response = client.request(method, url, json={})

        assert response.status_code == 401, f"{method.upper()} {url} was reachable without a token"

    @pytest.mark.parametrize("method,path", PROTECTED_ENDPOINTS)
    def test_rejects_invalid_token(self, client: TestClient, sample_student, method, path):
        url = path.format(student_id=sample_student.id)
        response = client.request(
            method, url, json={}, headers={"Authorization": "Bearer not-a-real-token"}
        )

        assert response.status_code == 401, f"{method.upper()} {url} accepted a forged token"

    def test_rejects_token_for_deleted_student(self, client: TestClient):
        """A well-formed token for a student who no longer exists is refused."""
        token = create_access_token({"sub": str(uuid.uuid4()), "email": "ghost@example.com"})

        response = client.get("/api/students/me", headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 401

    def test_rejects_token_for_inactive_student(
        self, client: TestClient, test_db, sample_student, auth_headers
    ):
        sample_student.is_active = False
        test_db.commit()

        response = client.get("/api/students/me", headers=auth_headers)

        assert response.status_code == 401

    def test_health_stays_public(self, client: TestClient):
        assert client.get("/health").status_code == 200


# ============================================================================
# Endpoints reject the wrong student
# ============================================================================


class TestCrossStudentAccess:
    """A valid token unlocks that student's data and nothing else."""

    def test_cannot_read_another_profile(
        self, client: TestClient, sample_student, other_auth_headers
    ):
        response = client.get(f"/api/students/{sample_student.id}", headers=other_auth_headers)

        assert response.status_code == 403

    def test_can_read_own_profile(self, client: TestClient, sample_student, auth_headers):
        response = client.get(f"/api/students/{sample_student.id}", headers=auth_headers)

        assert response.status_code == 200
        assert response.json()["id"] == sample_student.id

    def test_me_returns_the_token_holder(self, client: TestClient, sample_student, auth_headers):
        response = client.get("/api/students/me", headers=auth_headers)

        assert response.status_code == 200
        assert response.json()["id"] == sample_student.id

    def test_cannot_list_another_students_sessions(
        self, client: TestClient, sample_student, other_auth_headers
    ):
        response = client.get(
            f"/api/sessions?student_id={sample_student.id}", headers=other_auth_headers
        )

        assert response.status_code == 403

    def test_cannot_start_a_session_for_another_student(
        self, client: TestClient, sample_student, other_auth_headers
    ):
        response = client.post(
            "/api/sessions/start",
            json={"student_id": sample_student.id},
            headers=other_auth_headers,
        )

        assert response.status_code == 403

    def test_cannot_read_another_students_session(
        self, client: TestClient, sample_session, other_auth_headers
    ):
        """Someone else's session reads as missing, not as forbidden."""
        response = client.get(f"/api/sessions/{sample_session.id}", headers=other_auth_headers)

        assert response.status_code == 404

    def test_cannot_read_another_students_messages(
        self, client: TestClient, sample_session, other_auth_headers
    ):
        response = client.get(
            f"/api/sessions/{sample_session.id}/messages", headers=other_auth_headers
        )

        assert response.status_code == 404

    def test_cannot_end_another_students_session(
        self, client: TestClient, sample_session, other_auth_headers
    ):
        response = client.post(f"/api/sessions/{sample_session.id}/end", headers=other_auth_headers)

        assert response.status_code == 404

    def test_cannot_chat_in_another_students_session(
        self, client: TestClient, sample_session, other_auth_headers
    ):
        response = client.post(
            "/api/chat",
            json={"session_id": sample_session.id, "message": "Hello"},
            headers=other_auth_headers,
        )

        assert response.status_code == 404

    def test_can_read_own_session(self, client: TestClient, sample_session, auth_headers):
        response = client.get(f"/api/sessions/{sample_session.id}", headers=auth_headers)

        assert response.status_code == 200
        assert response.json()["id"] == sample_session.id

    def test_cannot_generate_a_quiz_for_another_student(
        self, client: TestClient, sample_student, other_auth_headers
    ):
        response = client.post(
            "/api/quiz/generate",
            json={"student_id": sample_student.id, "topic": "Calculus", "num_questions": 3},
            headers=other_auth_headers,
        )

        assert response.status_code == 403

    def test_cannot_submit_a_quiz_as_another_student(
        self, client: TestClient, sample_student, other_auth_headers
    ):
        response = client.post(
            "/api/quiz/submit",
            json={"quiz_id": "quiz-1", "student_id": sample_student.id, "answers": [0]},
            headers=other_auth_headers,
        )

        assert response.status_code == 403

    def test_cannot_read_another_students_progress(
        self, client: TestClient, sample_student_with_progress, other_auth_headers
    ):
        response = client.get(
            f"/api/feedback/{sample_student_with_progress.id}", headers=other_auth_headers
        )

        assert response.status_code == 403

    def test_cannot_request_another_students_report(
        self, client: TestClient, sample_student, other_auth_headers
    ):
        response = client.post(
            "/api/feedback/request",
            json={"student_id": sample_student.id, "report_type": "student"},
            headers=other_auth_headers,
        )

        assert response.status_code == 403

    def test_cannot_generate_a_plan_for_another_student(
        self, client: TestClient, sample_student, other_auth_headers
    ):
        response = client.post(
            "/api/plan/generate",
            json={"student_id": sample_student.id, "timeline_days": 30},
            headers=other_auth_headers,
        )

        assert response.status_code == 403

    def test_cannot_read_another_students_plan(
        self, client: TestClient, sample_student, other_auth_headers
    ):
        response = client.get(f"/api/plan/{sample_student.id}", headers=other_auth_headers)

        assert response.status_code == 403

    def test_cannot_list_another_students_documents(
        self, client: TestClient, sample_student, other_auth_headers
    ):
        response = client.get(
            f"/api/documents/list/{sample_student.id}", headers=other_auth_headers
        )

        assert response.status_code == 403

    def test_cannot_list_another_students_decks(
        self, client: TestClient, sample_student, other_auth_headers
    ):
        response = client.get(
            f"/api/flashcards/decks/{sample_student.id}", headers=other_auth_headers
        )

        assert response.status_code == 403

    def test_cannot_read_another_students_flashcard_stats(
        self, client: TestClient, sample_student, other_auth_headers
    ):
        response = client.get(
            f"/api/flashcards/stats/{sample_student.id}", headers=other_auth_headers
        )

        assert response.status_code == 403
