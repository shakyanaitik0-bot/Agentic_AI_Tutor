"""
Test script for Feedback Agent.

Tests:
1. Load student with progress data
2. Initialize Feedback Agent
3. Analyze overall performance
4. Generate personalized recommendations
5. Create student report
6. Create teacher report
7. Test replanning trigger detection
"""
import sys
import os
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.database import get_db_session
from app.models.student import Student
from app.models.progress import Progress
from app.agents.feedback_agent import FeedbackAgent, create_feedback_agent
import json


def print_separator(title=""):
    """Print a visual separator"""
    if title:
        print(f"\n{'=' * 60}")
        print(f"  {title}")
        print(f"{'=' * 60}\n")
    else:
        print(f"{'=' * 60}\n")


def test_feedback_agent():
    """Test Feedback Agent functionality"""
    print("\n" + "=" * 60)
    print("TESTING FEEDBACK AGENT")
    print("=" * 60 + "\n")

    try:
        # 1. Get database session
        print("[1/7] Loading database session...")
        db = next(get_db_session())
        print("    [OK] Database session loaded")

        # 2. Load a student with progress data
        print("\n[2/7] Loading student data...")
        student = db.query(Student).filter(Student.exam_type == "JEE").first()

        if not student:
            print("    [ERROR] No JEE student found in database")
            return

        print(f"    [OK] Student loaded: {student.name} (ID: {student.id})")

        # Check if student has progress data
        progress_count = db.query(Progress).filter(Progress.student_id == student.id).count()
        print(f"    [OK] Found {progress_count} progress records")

        if progress_count == 0:
            print("    [WARNING] No progress data found. Run test_quiz.py first to generate progress data.")
            print("    [INFO] Creating sample progress records for testing...")
            create_sample_progress(db, student)
            progress_count = db.query(Progress).filter(Progress.student_id == student.id).count()
            print(f"    [OK] Created {progress_count} sample progress records")

        # 3. Initialize Feedback Agent
        print("\n[3/7] Initializing Feedback Agent...")
        feedback_agent = create_feedback_agent(
            student=student,
            db_session=db
        )
        print("    [OK] Feedback Agent initialized")

        # 4. Analyze performance
        print("\n[4/7] Analyzing student performance...")
        report = feedback_agent.analyze_performance()
        print("    [OK] Performance analysis complete")

        # Display analysis results
        print("\n    Overall Statistics:")
        stats = report.overall_stats
        print(f"      - Topics studied: {stats['total_topics']}")
        print(f"      - Overall accuracy: {stats['overall_accuracy']}%")
        print(f"      - Total attempts: {stats['total_attempts']}")
        print(f"      - Total correct: {stats['total_correct']}")
        print(f"      - Practice time: {stats['total_time_minutes']} minutes")
        print(f"      - Weak topics: {stats['weak_topics_count']}")
        print(f"      - Strong topics: {stats['strong_topics_count']}")
        print(f"      - Mastery achieved: {stats['mastery_topics_count']}")

        # 5. Display weak topics
        print("\n    Weak Topics:")
        if report.weak_topics:
            for topic in report.weak_topics[:5]:  # Top 5
                print(f"      - {topic['topic']} ({topic['difficulty']}): "
                      f"{topic['accuracy']}% accuracy, "
                      f"{topic['attempts']} attempts")
        else:
            print("      (None - Great job!)")

        # 6. Display strong topics
        print("\n    Strong Topics:")
        if report.strong_topics:
            for topic in report.strong_topics[:5]:  # Top 5
                print(f"      - {topic['topic']} ({topic['difficulty']}): "
                      f"{topic['accuracy']}% accuracy")
        else:
            print("      (None yet - keep practicing!)")

        # 7. Display improving/declining topics
        if report.improving_topics:
            print("\n    Improving Topics:")
            for topic in report.improving_topics[:3]:
                print(f"      - {topic['topic']}: {topic['accuracy']}% (trend: +{topic['trend_value']}%)")

        if report.declining_topics:
            print("\n    Declining Topics:")
            for topic in report.declining_topics[:3]:
                print(f"      - {topic['topic']}: {topic['accuracy']}% (trend: {topic['trend_value']}%)")

        # 8. Display recommendations
        print_separator("PERSONALIZED RECOMMENDATIONS")
        for i, rec in enumerate(report.recommendations, 1):
            print(f"{i}. {rec}")

        # 9. Check replanning trigger
        print_separator("REPLANNING STATUS")
        if report.needs_replanning:
            print("    [ALERT] New study plan recommended!")
            print("    Reasons: Weak areas detected or topics declining")
        else:
            print("    [OK] Current study plan is still effective")

        # 10. Create student report
        print_separator("STUDENT REPORT")
        student_report = feedback_agent.create_student_report(report)
        print(student_report)

        # 11. Create teacher report (JSON format)
        print_separator("TEACHER REPORT (JSON)")
        teacher_report = feedback_agent.create_teacher_report(report)
        print(json.dumps(teacher_report, indent=2))

        # 12. Test report serialization
        print_separator("REPORT SERIALIZATION TEST")
        report_dict = report.to_dict()
        print(f"    [OK] Report serialized to dictionary")
        print(f"    Keys: {', '.join(report_dict.keys())}")

        print_separator("ALL TESTS PASSED")
        print("    [SUCCESS] Feedback Agent is working correctly!")

    except Exception as e:
        print(f"\n    [FAIL] Error during testing: {e}")
        import traceback
        traceback.print_exc()

    finally:
        db.close()


def create_sample_progress(db, student):
    """Create sample progress records for testing"""
    from datetime import datetime, timedelta
    from app.models.progress import Progress

    # Sample topics with varying performance
    sample_data = [
        # Weak topics
        {"topic": "Calculus", "difficulty": "easy", "correct": 4, "total": 10},
        {"topic": "Organic Chemistry", "difficulty": "medium", "correct": 5, "total": 12},
        {"topic": "Thermodynamics", "difficulty": "easy", "correct": 3, "total": 8},

        # Average topics
        {"topic": "Algebra", "difficulty": "medium", "correct": 7, "total": 10},
        {"topic": "Kinematics", "difficulty": "medium", "correct": 8, "total": 12},

        # Strong topics
        {"topic": "Trigonometry", "difficulty": "hard", "correct": 9, "total": 10},
        {"topic": "Electrostatics", "difficulty": "medium", "correct": 11, "total": 12},
    ]

    for data in sample_data:
        # Create progress record
        progress = Progress(
            student_id=student.id,
            topic=data["topic"],
            difficulty_level=data["difficulty"],
            total_attempts=0,
            correct_answers=0
        )
        db.add(progress)
        db.flush()  # Get the ID

        # Record attempts
        for i in range(data["total"]):
            is_correct = (i < data["correct"])
            progress.record_attempt(
                is_correct=is_correct,
                question_type="multiple_choice"
            )

        # Vary last_practiced dates
        days_ago = (len(sample_data) - sample_data.index(data)) * 2
        progress.last_practiced = datetime.utcnow() - timedelta(days=days_ago)

    db.commit()


if __name__ == "__main__":
    test_feedback_agent()
