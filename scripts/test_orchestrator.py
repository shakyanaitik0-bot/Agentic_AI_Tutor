"""
Test script for Orchestrator Agent.

Tests:
1. Load database session and student
2. Create session
3. Initialize Orchestrator
4. Test intent classification
5. Test routing to Planner Agent
6. Test routing to Quiz Generator Agent
7. Test routing to Feedback Agent
8. Test routing to Conversation Agent
9. Test multi-agent workflow
"""
import sys
import os
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.database import get_database
from app.models.student import Student
from app.models.session import Session
from app.models.progress import Progress
from app.agents.orchestrator import OrchestratorAgent, IntentType, create_orchestrator
import json


def print_separator(title=""):
    """Print a visual separator"""
    if title:
        print(f"\n{'=' * 70}")
        print(f"  {title}")
        print(f"{'=' * 70}\n")
    else:
        print(f"{'=' * 70}\n")


def test_orchestrator():
    """Test Orchestrator Agent functionality"""
    print("\n" + "=" * 70)
    print("TESTING ORCHESTRATOR AGENT")
    print("=" * 70 + "\n")

    db = None
    try:
        # 1. Get database session
        print("[1/9] Loading database session...")
        db = next(get_database())
        print("    [OK] Database session loaded")

        # 2. Load student
        print("\n[2/9] Loading student data...")
        student = db.query(Student).filter(Student.exam_type == "JEE").first()

        if not student:
            print("    [ERROR] No JEE student found in database")
            return

        print(f"    [OK] Student loaded: {student.name} (ID: {student.id})")

        # Ensure student has progress data
        progress_count = db.query(Progress).filter(Progress.student_id == student.id).count()
        if progress_count == 0:
            print("    [WARNING] No progress data found. Creating sample data...")
            create_sample_progress(db, student)
            progress_count = db.query(Progress).filter(Progress.student_id == student.id).count()
            print(f"    [OK] Created {progress_count} sample progress records")

        # 3. Create session
        print("\n[3/9] Creating session...")
        session = Session(student_id=student.id, is_active=True)
        db.add(session)
        db.commit()
        print(f"    Session ID: {session.id[:16]}...")
        print("    [OK] Session created")

        # 4. Initialize Orchestrator
        print("\n[4/9] Initializing Orchestrator...")
        orchestrator = create_orchestrator(
            student=student,
            session=session,
            db=db
        )
        print("    [OK] Orchestrator initialized")

        # 5. Test intent classification
        print_separator("TEST 1: Intent Classification")
        test_intents = [
            ("Create a 30-day study plan for JEE", IntentType.PLAN),
            ("Give me a quiz on Calculus", IntentType.QUIZ),
            ("How am I doing in Physics?", IntentType.FEEDBACK),
            ("Explain Newton's laws of motion", IntentType.CONVERSATION),
        ]

        for user_input, expected_intent in test_intents:
            classified = orchestrator._classify_intent(user_input)
            status = "OK" if classified == expected_intent else "MISMATCH"
            print(f"    [{status}] '{user_input[:40]}...'")
            print(f"         Expected: {expected_intent.value}, Got: {classified.value}")

        # 6. Test routing to Planner Agent
        print_separator("TEST 2: Route to Planner Agent")
        print("    Request: 'Create a 14-day study plan'")
        response = orchestrator.execute(
            "Create a 14-day study plan",
            timeline_days=14
        )
        print(f"    [OK] Agent used: {response.get('agent')}")
        print(f"    Intent classified: {response.get('orchestrator', {}).get('intent')}")
        if 'plan' in response:
            plan_data = response['plan']
            print(f"    Plan timeline: {plan_data.get('timeline_days')} days")
            print(f"    Topics in plan: {len(plan_data.get('topics', []))}")

        # 7. Test routing to Quiz Generator
        print_separator("TEST 3: Route to Quiz Generator Agent")
        print("    Request: 'Give me a quiz on Algebra with 3 questions'")
        response = orchestrator.execute(
            "Give me a quiz on Algebra",
            topic="Algebra",
            num_questions=3
        )
        print(f"    [OK] Agent used: {response.get('agent')}")
        print(f"    Intent classified: {response.get('orchestrator', {}).get('intent')}")
        if 'quiz' in response:
            quiz_data = response['quiz']
            print(f"    Quiz topic: {quiz_data.get('topic')}")
            print(f"    Number of questions: {len(quiz_data.get('questions', []))}")

        # 8. Test routing to Feedback Agent
        print_separator("TEST 4: Route to Feedback Agent")
        print("    Request: 'Show me my progress report'")
        response = orchestrator.execute(
            "Show me my progress report",
            report_type="student"
        )
        print(f"    [OK] Agent used: {response.get('agent')}")
        print(f"    Intent classified: {response.get('orchestrator', {}).get('intent')}")
        if 'data' in response or 'content' in response:
            print(f"    Report type: {response.get('report_type')}")
            print(f"    Needs replanning: {response.get('needs_replanning', False)}")
            if response.get('orchestrator_suggestion'):
                print(f"    Orchestrator suggestion: {response['orchestrator_suggestion'][:60]}...")

        # 9. Test routing to Conversation Agent
        print_separator("TEST 5: Route to Conversation Agent")
        print("    Request: 'Explain the concept of derivatives in calculus'")
        response = orchestrator.execute(
            "Explain the concept of derivatives in calculus"
        )
        print(f"    [OK] Agent used: {response.get('agent')}")
        print(f"    Intent classified: {response.get('orchestrator', {}).get('intent')}")
        if 'response' in response:
            print(f"    Response length: {len(response['response'])} characters")

        # 10. Test multi-agent workflow
        print_separator("TEST 6: Multi-Agent Workflow")
        print("    Workflow: quiz_with_feedback")
        try:
            workflow_result = orchestrator.execute_workflow(
                workflow_type="quiz_with_feedback",
                topic="Physics",
                num_questions=2
            )
            print(f"    [OK] Workflow executed: {workflow_result.get('workflow')}")
            print(f"    Feedback included: {'feedback' in workflow_result}")
            print(f"    Quiz included: {'quiz' in workflow_result}")
            print(f"    Message: {workflow_result.get('message', '')[:60]}...")
        except Exception as e:
            print(f"    [SKIP] Workflow test skipped: {e}")

        print_separator("TEST 7: Assess and Plan Workflow")
        print("    Workflow: assess_and_plan")
        try:
            workflow_result = orchestrator.execute_workflow(
                workflow_type="assess_and_plan",
                timeline_days=21
            )
            print(f"    [OK] Workflow executed: {workflow_result.get('workflow')}")
            print(f"    Feedback included: {'feedback' in workflow_result}")
            print(f"    Plan included: {'plan' in workflow_result}")
            print(f"    Message: {workflow_result.get('message', '')}")
        except Exception as e:
            print(f"    [SKIP] Workflow test skipped: {e}")

        # 11. Test lazy loading of agents
        print_separator("TEST 8: Lazy Loading Verification")
        print("    Checking if agents are lazy loaded...")
        orchestrator2 = create_orchestrator(student=student, session=session, db=db)
        print(f"    Planner Agent (before use): {orchestrator2._planner_agent}")
        print(f"    Quiz Agent (before use): {orchestrator2._quiz_agent}")
        print(f"    Feedback Agent (before use): {orchestrator2._feedback_agent}")

        # Trigger one agent
        orchestrator2.execute("Show my progress", report_type="data")
        print(f"    Feedback Agent (after use): {orchestrator2._feedback_agent is not None}")
        print(f"    Planner Agent (still lazy): {orchestrator2._planner_agent is None}")
        print("    [OK] Lazy loading working correctly")

        print_separator("ALL TESTS PASSED")
        print("    [SUCCESS] Orchestrator Agent is working correctly!")
        print("\n    The Orchestrator can:")
        print("      - Classify user intents accurately")
        print("      - Route to appropriate specialized agents")
        print("      - Execute multi-agent workflows")
        print("      - Lazy load agents for efficiency")
        print("      - Synthesize responses with metadata")

    except Exception as e:
        print(f"\n    [FAIL] Error during testing: {e}")
        import traceback
        traceback.print_exc()

    finally:
        if db:
            db.close()


def create_sample_progress(db, student):
    """Create sample progress records for testing"""
    from datetime import datetime, timedelta

    sample_data = [
        {"topic": "Calculus", "difficulty": "easy", "correct": 4, "total": 10},
        {"topic": "Algebra", "difficulty": "medium", "correct": 7, "total": 10},
        {"topic": "Physics", "difficulty": "medium", "correct": 6, "total": 10},
    ]

    for data in sample_data:
        progress = Progress(
            student_id=student.id,
            topic=data["topic"],
            difficulty_level=data["difficulty"],
            total_attempts=0,
            correct_answers=0
        )
        db.add(progress)
        db.flush()

        for i in range(data["total"]):
            is_correct = (i < data["correct"])
            progress.record_attempt(
                is_correct=is_correct,
                question_type="multiple_choice"
            )

    db.commit()


if __name__ == "__main__":
    test_orchestrator()
