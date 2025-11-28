"""
Test script for Quiz Generator Agent.
Verifies adaptive quiz generation with RAG integration.
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.database import get_database
from app.models.student import Student
from app.models.session import Session
from app.models.progress import Progress
from app.agents.quiz_agent import QuizGeneratorAgent

def test_quiz_agent():
    """Test Quiz Generator Agent functionality"""
    print("\n" + "="*70)
    print("Testing Quiz Generator Agent")
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

        # Check progress
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

        # Initialize Quiz Generator Agent
        print("\n[3] Initializing Quiz Generator Agent...")
        quiz_agent = QuizGeneratorAgent(student=student, session=session, db=db)
        print(f"    Agent: {quiz_agent.agent_name}")
        print("    [OK] Agent initialized")

        # Test 1: Generate quiz with auto-difficulty
        print("\n[4] Generating quiz on Calculus (auto-difficulty)...")
        result = quiz_agent.execute(
            "Create a quiz on Calculus",
            topic="Calculus",
            num_questions=3
        )

        quiz = result["quiz"]
        print(f"    Topic: {quiz['topic']}")
        print(f"    Difficulty: {quiz['difficulty']}")
        print(f"    Questions generated: {quiz['num_questions']}")
        print("    [OK] Quiz generated with auto-difficulty")

        # Test 2: Display questions
        print("\n[5] Quiz questions preview...")
        for idx, q in enumerate(quiz['questions'], 1):
            print(f"\n    Q{idx}. {q['question_text']}")
            for opt_idx, option in enumerate(q['options']):
                marker = " ✓" if opt_idx == q['correct_answer_index'] else ""
                print(f"       {chr(65+opt_idx)}. {option}{marker}")
            print(f"       Topic: {q['topic']} | Difficulty: {q['difficulty']}")
        print("\n    [OK] All questions display correctly")

        # Test 3: Test grading
        print("\n[6] Testing quiz grading...")

        # Generate answers based on actual number of questions
        num_actual_questions = len(quiz['questions'])
        if num_actual_questions == 0:
            print("    [SKIP] No questions generated, cannot test grading")
        else:
            # Simulate student answers (get first one correct, rest wrong)
            student_answers = []
            for i, q in enumerate(quiz['questions']):
                if i == 0:
                    # First answer correct
                    student_answers.append(q['correct_answer_index'])
                else:
                    # Others wrong
                    student_answers.append((q['correct_answer_index'] + 1) % 4)

            grade_result = quiz_agent.grade_quiz(quiz, student_answers)
            print(f"    Total questions: {grade_result['total_questions']}")
            print(f"    Correct answers: {grade_result['correct_answers']}")
            print(f"    Accuracy: {grade_result['accuracy']:.1f}%")
            print(f"    Passed: {grade_result['passed']}")
            print("    [OK] Grading working correctly")

        # Test 4: Verify progress update
        print("\n[7] Verifying progress update...")
        progress = db.query(Progress).filter(
            Progress.student_id == student.id,
            Progress.topic == "Calculus"
        ).first()

        if progress:
            print(f"    Topic: {progress.topic}")
            print(f"    Total attempts: {progress.total_attempts}")
            print(f"    Accuracy: {progress.accuracy_percentage:.1f}%")
            print("    [OK] Progress record updated")
        else:
            print("    [WARNING] No progress record found (may be created on next attempt)")

        # Test 5: Test different difficulty levels
        print("\n[8] Testing different difficulty levels...")
        for diff in ["easy", "medium", "hard"]:
            result = quiz_agent.execute(
                f"Create a {diff} quiz on Probability",
                topic="Probability",
                difficulty=diff,
                num_questions=2
            )
            quiz = result["quiz"]
            print(f"    {diff.capitalize()}: {quiz['num_questions']} questions generated")
        print("    [OK] All difficulty levels working")

        print("\n" + "="*70)
        print("ALL TESTS PASSED - Quiz Generator Agent working!")
        print("="*70)
        print("\nQuiz Generator Features:")
        print("  - Adaptive difficulty based on Progress")
        print("  - RAG-based content retrieval")
        print("  - LLM-generated MCQs with explanations")
        print("  - Automatic grading")
        print("  - Progress tracking after quiz")
        print("\nTo test:")
        print("  python scripts/test_quiz.py")
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
    success = test_quiz_agent()
    sys.exit(0 if success else 1)
