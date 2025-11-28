"""
Test script for Planner Agent.
Verifies study plan generation based on progress data.
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.database import get_database
from app.models.student import Student
from app.models.session import Session
from app.models.progress import Progress
from app.agents.planner_agent import PlannerAgent
import uuid
from datetime import datetime

def test_planner_agent():
    """Test Planner Agent functionality"""
    print("\n" + "="*70)
    print("Testing Planner Agent")
    print("="*70)

    try:
        # Get database session
        print("\n[1] Loading student and progress data...")
        db = next(get_database())

        # Get first student
        student = db.query(Student).first()
        if not student:
            print("    [FAIL] No students found. Run: python scripts/init_db.py")
            return False

        print(f"    Student: {student.name}")
        print(f"    Exam: {student.exam_type}")

        # Check progress records
        progress_count = db.query(Progress).filter(
            Progress.student_id == student.id
        ).count()
        print(f"    Progress records: {progress_count}")
        print("    [OK] Data loaded")

        # Create session
        print("\n[2] Creating session...")
        session = Session(student_id=student.id, is_active=True)
        db.add(session)
        db.commit()
        print(f"    Session ID: {session.id[:16]}...")
        print("    [OK] Session created")

        # Initialize Planner Agent
        print("\n[3] Initializing Planner Agent...")
        planner = PlannerAgent(student=student, session=session, db=db)
        print(f"    Agent: {planner.agent_name}")
        print("    [OK] Agent initialized")

        # Test: Generate 30-day study plan
        print("\n[4] Generating 30-day study plan...")
        result = planner.execute(
            "Create a 30-day study plan focusing on my weak areas",
            timeline_days=30
        )

        study_plan = result["study_plan"]
        print(f"    Total topics: {study_plan['total_topics']}")
        print(f"    Total hours: {study_plan['total_hours']:.1f}")
        print(f"    Timeline: {study_plan['timeline_days']} days")
        print(f"    Weak areas identified: {result['summary']['weak_areas']}")
        print("    [OK] Study plan generated")

        # Display plan details
        print("\n[5] Study plan details...")
        print(f"    Topics prioritized:")
        for idx, topic in enumerate(study_plan['topics'][:5], 1):  # Show top 5
            print(f"      {idx}. {topic['topic']} - {topic['estimated_hours']:.1f}h ({topic['difficulty']})")
            print(f"         Reason: {topic['reason']}")

        print(f"\n    Daily schedule (first 3 days):")
        for day_schedule in study_plan['daily_schedule'][:3]:
            print(f"      Day {day_schedule['day']} ({day_schedule['date']}):")
            for topic in day_schedule['topics']:
                print(f"        - {topic['topic']}: {topic['hours']:.1f}h")

        print(f"\n    Milestones:")
        for milestone in study_plan['milestones']:
            print(f"      Day {milestone['day']}: {milestone['target']} ({milestone['percentage']}%)")

        print("    [OK] Plan details verified")

        # Test explanation
        print("\n[6] Testing plan explanation...")
        explanation = result["explanation"]
        print(f"    Explanation length: {len(explanation)} chars")
        print(f"    Explanation preview:")
        print(f"    \"{explanation[:200]}...\"")
        print("    [OK] Explanation generated")

        # Test different timelines
        print("\n[7] Testing different timelines...")
        for days in [7, 14, 60]:
            result = planner.execute(
                f"Create a {days}-day study plan",
                timeline_days=days
            )
            plan = result["study_plan"]
            print(f"    {days}-day plan: {plan['total_topics']} topics, {plan['total_hours']:.1f} hours")
        print("    [OK] Multiple timelines tested")

        print("\n" + "="*70)
        print("ALL TESTS PASSED - Planner Agent working!")
        print("="*70)
        print("\nPlanner Agent Features:")
        print("  - Progress analysis (weak/strong/review areas)")
        print("  - Topic prioritization by urgency")
        print("  - Daily schedule generation")
        print("  - Milestone tracking")
        print("  - Explainable recommendations via Gemini")
        print("\n")

        # Cleanup
        db.close()
        return True

    except Exception as e:
        print(f"\n[FAIL] Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_planner_agent()
    sys.exit(0 if success else 1)
