"""
Test script for all API endpoints.

Tests endpoints in logical order:
1. Health check
2. Student registration
3. Session management
4. Chat/Orchestrator
5. Quiz generation and submission
6. Feedback/Progress report
7. Study plan generation
"""
import requests
import json
from typing import Dict, Any
from datetime import datetime

BASE_URL = "http://127.0.0.1:8000"
API_URL = f"{BASE_URL}/api"

# Test data storage
test_data = {
    "student_id": None,
    "session_id": None,
    "quiz_id": None,
    "plan_id": None
}


def print_section(title: str):
    """Print a formatted section header"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def print_result(endpoint: str, status_code: int, response: Dict[Any, Any], expected: int = 200):
    """Print test result"""
    success = "✓" if status_code == expected else "✗"
    print(f"{success} {endpoint}")
    print(f"   Status: {status_code} (expected {expected})")
    if status_code != expected:
        print(f"   Response: {json.dumps(response, indent=2)}")
    print()


def test_health_check():
    """Test health check endpoint"""
    print_section("1. Health Check")

    response = requests.get(f"{BASE_URL}/health")
    data = response.json()

    print_result("GET /health", response.status_code, data)
    print(f"Service: {data.get('service')}")
    print(f"Version: {data.get('version')}")
    print(f"LLM Provider: {data.get('llm_provider', 'Not configured')}")
    print(f"Embedding Provider: {data.get('embedding_provider')}")

    return response.status_code == 200


def test_student_registration():
    """Test student registration"""
    print_section("2. Student Registration")

    student_data = {
        "name": "Test Student",
        "email": f"test_{datetime.now().timestamp()}@example.com",
        "exam_type": "JEE",
        "weak_areas": ["Calculus", "Organic Chemistry"],
        "strong_areas": ["Algebra", "Mechanics"],
        "learning_preferences": {
            "style": "visual",
            "practice_intensity": "high"
        }
    }

    response = requests.post(f"{API_URL}/students/register", json=student_data)
    data = response.json()

    print_result("POST /api/students/register", response.status_code, data, expected=201)

    if response.status_code == 201:
        test_data["student_id"] = data["id"]
        print(f"Created Student ID: {data['id']}")
        print(f"Name: {data['name']}")
        print(f"Email: {data['email']}")
        print(f"Exam Type: {data['exam_type']}")
        return True
    else:
        print(f"ERROR: {json.dumps(data, indent=2)}")
        return False


def test_get_student():
    """Test getting student details"""
    print_section("3. Get Student Details")

    student_id = test_data["student_id"]
    response = requests.get(f"{API_URL}/students/{student_id}")
    data = response.json()

    print_result(f"GET /api/students/{student_id}", response.status_code, data)

    if response.status_code == 200:
        print(f"Student: {data['name']} ({data['email']})")
        print(f"Weak Areas: {', '.join(data['weak_areas'])}")
        print(f"Strong Areas: {', '.join(data['strong_areas'])}")
        return True
    else:
        print(f"ERROR: {json.dumps(data, indent=2)}")
        return False


def test_create_session():
    """Test session creation"""
    print_section("4. Create Session")

    session_data = {
        "student_id": test_data["student_id"],
        "session_type": "quiz"
    }

    response = requests.post(f"{API_URL}/sessions/start", json=session_data)
    data = response.json()

    print_result("POST /api/sessions/start", response.status_code, data, expected=201)

    if response.status_code == 201:
        test_data["session_id"] = data["id"]
        print(f"Created Session ID: {data['id']}")
        print(f"Active: {data['is_active']}")
        print(f"Type: {data.get('session_type')}")
        return True
    else:
        print(f"ERROR: {json.dumps(data, indent=2)}")
        return False


def test_get_session():
    """Test getting session details"""
    print_section("5. Get Session Details")

    session_id = test_data["session_id"]
    response = requests.get(f"{API_URL}/sessions/{session_id}")
    data = response.json()

    print_result(f"GET /api/sessions/{session_id}", response.status_code, data)

    if response.status_code == 200:
        print(f"Session: {data['id']}")
        print(f"Active: {data['is_active']}")
        print(f"Questions Asked: {data['questions_asked']}")
        return True
    else:
        print(f"ERROR: {json.dumps(data, indent=2)}")
        return False


def test_chat_endpoint():
    """Test chat/orchestrator endpoint"""
    print_section("6. Chat/Orchestrator")

    chat_data = {
        "session_id": test_data["session_id"],
        "message": "Hello! Can you help me with Calculus?",
        "intent": None
    }

    print("⚠️  Note: This will invoke the orchestrator agent")
    print(f"Message: {chat_data['message']}")

    response = requests.post(f"{API_URL}/chat", json=chat_data)
    data = response.json()

    print_result("POST /api/chat", response.status_code, data)

    if response.status_code == 200:
        print(f"Response received from agent")
        print(f"Agent Response Keys: {list(data.get('agent_response', {}).keys())}")
        return True
    else:
        print(f"ERROR: {json.dumps(data, indent=2)}")
        return False


def test_quiz_generation():
    """Test quiz generation"""
    print_section("7. Quiz Generation")

    quiz_request = {
        "topic": "Calculus",
        "difficulty": "easy",
        "num_questions": 3,
        "student_id": test_data["student_id"]
    }

    print(f"Generating quiz: {quiz_request['topic']} ({quiz_request['difficulty']})")
    print(f"Questions: {quiz_request['num_questions']}")

    response = requests.post(f"{API_URL}/quiz/generate", json=quiz_request)
    data = response.json()

    print_result("POST /api/quiz/generate", response.status_code, data)

    if response.status_code == 200:
        test_data["quiz_id"] = data["quiz_id"]
        print(f"Quiz ID: {data['quiz_id']}")
        print(f"Topic: {data['topic']}")
        print(f"Difficulty: {data['difficulty']}")
        print(f"Questions Generated: {len(data['questions'])}")
        return True
    else:
        print(f"ERROR: {json.dumps(data, indent=2)}")
        return False


def test_quiz_submission():
    """Test quiz submission"""
    print_section("8. Quiz Submission")

    # Submit answers (selecting first option for all questions)
    submission_data = {
        "quiz_id": test_data["quiz_id"],
        "student_id": test_data["student_id"],
        "answers": [0, 1, 2]  # Sample answers
    }

    print(f"Submitting answers: {submission_data['answers']}")

    response = requests.post(f"{API_URL}/quiz/submit", json=submission_data)
    data = response.json()

    print_result("POST /api/quiz/submit", response.status_code, data)

    if response.status_code == 200:
        print(f"Total Questions: {data['total_questions']}")
        print(f"Correct Answers: {data['correct_answers']}")
        print(f"Accuracy: {data['accuracy']}%")
        print(f"Passed: {data['passed']}")
        return True
    else:
        print(f"ERROR: {json.dumps(data, indent=2)}")
        return False


def test_feedback_report():
    """Test feedback/progress report"""
    print_section("9. Feedback/Progress Report")

    student_id = test_data["student_id"]

    print(f"Requesting progress report for student {student_id}")

    response = requests.get(f"{API_URL}/feedback/{student_id}")
    data = response.json()

    print_result(f"GET /api/feedback/{student_id}", response.status_code, data)

    if response.status_code == 200:
        stats = data.get('overall_stats', {})
        print(f"Overall Accuracy: {stats.get('overall_accuracy', 0)}%")
        print(f"Total Topics: {stats.get('total_topics', 0)}")
        print(f"Total Attempts: {stats.get('total_attempts', 0)}")
        print(f"Weak Topics: {len(data.get('weak_topics', []))}")
        print(f"Strong Topics: {len(data.get('strong_topics', []))}")
        return True
    else:
        print(f"ERROR: {json.dumps(data, indent=2)}")
        return False


def test_plan_generation():
    """Test study plan generation"""
    print_section("10. Study Plan Generation")

    plan_request = {
        "student_id": test_data["student_id"],
        "timeline_days": 30,
        "focus_topics": ["Calculus", "Organic Chemistry"],
        "hours_per_day": 4.0
    }

    print(f"Generating {plan_request['timeline_days']}-day study plan")
    print(f"Focus Topics: {', '.join(plan_request['focus_topics'])}")
    print(f"Hours/Day: {plan_request['hours_per_day']}")

    response = requests.post(f"{API_URL}/plan/generate", json=plan_request)
    data = response.json()

    print_result("POST /api/plan/generate", response.status_code, data)

    if response.status_code == 200:
        test_data["plan_id"] = data["plan_id"]
        print(f"Plan ID: {data['plan_id']}")
        print(f"Timeline: {data['timeline_days']} days")
        print(f"Total Topics: {data['total_topics']}")
        print(f"Total Hours: {data['total_estimated_hours']}")
        print(f"Daily Schedules: {len(data['daily_schedule'])}")
        return True
    else:
        print(f"ERROR: {json.dumps(data, indent=2)}")
        return False


def test_get_plan():
    """Test getting study plan"""
    print_section("11. Get Study Plan")

    student_id = test_data["student_id"]

    response = requests.get(f"{API_URL}/plan/{student_id}")
    data = response.json()

    print_result(f"GET /api/plan/{student_id}", response.status_code, data)

    if response.status_code == 200:
        print(f"Plan ID: {data['plan_id']}")
        print(f"Timeline: {data['timeline_days']} days")
        print(f"Topics: {data['total_topics']}")
        return True
    else:
        print(f"ERROR: {json.dumps(data, indent=2)}")
        return False


def test_end_session():
    """Test ending a session"""
    print_section("12. End Session")

    session_id = test_data["session_id"]

    response = requests.post(f"{API_URL}/sessions/{session_id}/end")
    data = response.json()

    print_result(f"POST /api/sessions/{session_id}/end", response.status_code, data)

    if response.status_code == 200:
        print(f"Session ended successfully")
        print(f"Duration: {data.get('duration_seconds', 0)} seconds")
        return True
    else:
        print(f"ERROR: {json.dumps(data, indent=2)}")
        return False


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("  AGENTIC AI TUTOR - API ENDPOINT TESTS")
    print("="*60)
    print(f"\nBase URL: {BASE_URL}")
    print(f"API URL: {API_URL}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    results = []

    # Run tests in sequence
    try:
        results.append(("Health Check", test_health_check()))
        results.append(("Student Registration", test_student_registration()))

        if test_data["student_id"]:
            results.append(("Get Student", test_get_student()))
            results.append(("Create Session", test_create_session()))

            if test_data["session_id"]:
                results.append(("Get Session", test_get_session()))
                results.append(("Chat/Orchestrator", test_chat_endpoint()))
                results.append(("Quiz Generation", test_quiz_generation()))

                if test_data["quiz_id"]:
                    results.append(("Quiz Submission", test_quiz_submission()))

                results.append(("Feedback Report", test_feedback_report()))
                results.append(("Plan Generation", test_plan_generation()))

                if test_data["plan_id"]:
                    results.append(("Get Plan", test_get_plan()))

                results.append(("End Session", test_end_session()))

    except requests.exceptions.ConnectionError:
        print("\n❌ ERROR: Could not connect to API server")
        print("   Make sure the server is running: uvicorn app.main:app --reload")
        return
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        return

    # Print summary
    print_section("TEST SUMMARY")

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status:10} {test_name}")

    print(f"\n{'='*60}")
    print(f"Total: {passed}/{total} tests passed ({100*passed//total if total > 0 else 0}%)")
    print(f"{'='*60}\n")

    # Print test data for reference
    if test_data["student_id"]:
        print("\nTest Data Created:")
        print(f"  Student ID: {test_data['student_id']}")
        print(f"  Session ID: {test_data['session_id']}")
        print(f"  Quiz ID: {test_data['quiz_id']}")
        print(f"  Plan ID: {test_data['plan_id']}")
        print()


if __name__ == "__main__":
    main()
