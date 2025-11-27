#!/usr/bin/env python3
"""
Database initialization script for Agentic AI Tutor.

This script creates all database tables and optionally seeds with sample data
for development and testing purposes.

Usage:
    python scripts/init_db.py                    # Create tables only
    python scripts/init_db.py --seed             # Create tables + sample data
    python scripts/init_db.py --reset            # Drop + recreate tables
    python scripts/init_db.py --reset --seed     # Full reset with sample data
"""
import sys
import os
import argparse
import logging
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from datetime import datetime, timedelta
from sqlalchemy.exc import IntegrityError
from app.core.database import engine, Base, get_db_session, init_database, check_db_connection
from app.models.student import Student
from app.models.session import Session, Message
from app.models.progress import Progress, DifficultyLevel, StrengthLevel

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_tables(drop_existing: bool = False):
    """
    Create all database tables.

    Args:
        drop_existing: If True, drop existing tables first
    """
    try:
        logger.info("Initializing database...")

        if drop_existing:
            logger.warning("Dropping all existing tables...")
            Base.metadata.drop_all(bind=engine)
            logger.info("All tables dropped successfully")

        # Create all tables
        init_database()
        logger.info("All tables created successfully")

        # Verify connection
        if check_db_connection():
            logger.info("Database connection verified")
        else:
            logger.error("Database connection failed")
            return False

        return True

    except Exception as e:
        logger.error(f"Failed to create tables: {e}")
        return False

def seed_sample_data():
    """
    Seed database with sample data for development and testing.
    Creates sample students, sessions, and progress records.
    """
    logger.info("Seeding sample data...")

    db = get_db_session()
    try:
        # Sample students for different exam types
        students_data = [
            {
                "name": "Arjun Sharma",
                "email": "arjun.sharma@example.com",
                "exam_type": "JEE",
                "weak_areas": ["Probability", "Calculus"],
                "strong_areas": ["Algebra", "Geometry"]
            },
            {
                "name": "Emma Johnson",
                "email": "emma.johnson@example.com",
                "exam_type": "SAT",
                "weak_areas": ["Advanced Math", "Reading Comprehension"],
                "strong_areas": ["Basic Math", "Grammar"]
            },
            {
                "name": "Raj Patel",
                "email": "raj.patel@example.com",
                "exam_type": "GRE",
                "weak_areas": ["Quantitative Reasoning"],
                "strong_areas": ["Verbal Reasoning", "Analytical Writing"]
            }
        ]

        created_students = []

        # Create students
        for student_data in students_data:
            try:
                student = Student(
                    name=student_data["name"],
                    email=student_data["email"],
                    exam_type=student_data["exam_type"],
                    weak_areas=student_data["weak_areas"],
                    strong_areas=student_data["strong_areas"]
                )

                # Set sample API keys (for development only)
                student.set_openai_key("sk-sample_key_for_development_only")

                db.add(student)
                db.flush()  # Get student ID
                created_students.append(student)

                logger.info(f"Created student: {student.name} ({student.exam_type})")

            except IntegrityError as e:
                logger.warning(f"Student {student_data['email']} already exists, skipping...")
                db.rollback()
                # Fetch existing student
                existing = db.query(Student).filter_by(email=student_data["email"]).first()
                if existing:
                    created_students.append(existing)

        # Create sample sessions and progress for each student
        for student in created_students:
            create_sample_session_data(db, student)
            create_sample_progress_data(db, student)

        db.commit()
        logger.info(f"Successfully seeded data for {len(created_students)} students")

        # Print summary
        print_database_summary(db)

    except Exception as e:
        logger.error(f"Failed to seed sample data: {e}")
        db.rollback()
        raise
    finally:
        db.close()

def create_sample_session_data(db, student: Student):
    """Create sample session and message data for a student"""

    # Create a recent active session
    session = Session(
        student_id=student.id,
        session_type="general",
        current_topic="Probability" if "Probability" in student.weak_areas else "Algebra",
        is_active=True,
        started_at=datetime.utcnow() - timedelta(minutes=30)
    )

    db.add(session)
    db.flush()

    # Add sample conversation messages
    messages_data = [
        ("user", "Hi! I need help with probability problems", "chat"),
        ("assistant", "I'd be happy to help you with probability! Let me start by explaining conditional probability and then give you some practice questions.", "response"),
        ("user", "What is conditional probability?", "question"),
        ("assistant", "Conditional probability is the probability of event A happening given that event B has already occurred. It's written as P(A|B) and calculated as P(A∩B)/P(B).", "explanation")
    ]

    for role, content, msg_type in messages_data:
        message = Message.create_user_message(session.id, content, msg_type) if role == "user" else \
                 Message.create_assistant_message(session.id, content, msg_type, topic=session.current_topic)

        db.add(message)

    # Update session stats
    session.questions_asked = 2
    session.questions_answered_correctly = 1
    session.add_topic_covered(session.current_topic)

    logger.debug(f"Created sample session for {student.name}")

def create_sample_progress_data(db, student: Student):
    """Create sample progress data for a student"""

    # Define topics based on exam type
    topics_by_exam = {
        "JEE": ["Algebra", "Calculus", "Probability", "Geometry", "Physics", "Chemistry"],
        "SAT": ["Basic Math", "Advanced Math", "Reading Comprehension", "Grammar", "Essay Writing"],
        "GRE": ["Quantitative Reasoning", "Verbal Reasoning", "Analytical Writing", "Data Analysis"]
    }

    topics = topics_by_exam.get(student.exam_type, ["Mathematics", "Science", "English"])

    for topic in topics:
        for difficulty in [DifficultyLevel.EASY, DifficultyLevel.MEDIUM, DifficultyLevel.HARD]:

            # Create realistic performance based on student's weak/strong areas
            if topic in (student.weak_areas or []):
                # Weak area - lower performance
                attempts = 15
                correct = 6 if difficulty == DifficultyLevel.EASY.value else \
                         4 if difficulty == DifficultyLevel.MEDIUM.value else 2
            elif topic in (student.strong_areas or []):
                # Strong area - higher performance
                attempts = 20
                correct = 18 if difficulty == DifficultyLevel.EASY.value else \
                         16 if difficulty == DifficultyLevel.MEDIUM.value else 12
            else:
                # Average performance
                attempts = 12
                correct = 8 if difficulty == DifficultyLevel.EASY.value else \
                         6 if difficulty == DifficultyLevel.MEDIUM.value else 4

            progress = Progress(
                student_id=student.id,
                topic=topic,
                difficulty_level=difficulty.value,
                total_attempts=attempts,
                correct_answers=correct,
                total_time_spent_minutes=attempts * 2.5,  # ~2.5 min per question
                first_attempted=datetime.utcnow() - timedelta(days=10),
                last_practiced=datetime.utcnow() - timedelta(days=1),
                consecutive_correct=2 if correct > attempts * 0.6 else 0,
                max_streak=5
            )

            # Update derived fields
            progress._update_strength_level()
            progress._update_mastery_status()
            progress._update_review_status()

            db.add(progress)

    logger.debug(f"Created sample progress data for {student.name}")

def print_database_summary(db):
    """Print summary of database contents"""

    student_count = db.query(Student).count()
    session_count = db.query(Session).count()
    message_count = db.query(Message).count()
    progress_count = db.query(Progress).count()

    print("\n" + "="*60)
    print("DATABASE INITIALIZATION COMPLETE")
    print("="*60)
    print(f"STATS: Students:        {student_count}")
    print(f" Sessions:        {session_count}")
    print(f" Messages:        {message_count}")
    print(f" Progress Records: {progress_count}")

    # Show student details
    students = db.query(Student).all()
    print(f"\n STUDENTS:")
    for student in students:
        print(f"   • {student.name} ({student.exam_type}) - {student.email}")
        weak_count = len(student.weak_areas or [])
        strong_count = len(student.strong_areas or [])
        print(f"     Weak areas: {weak_count}, Strong areas: {strong_count}")

    print(f"\n Database file: {os.getenv('DATABASE_URL', 'sqlite:///./data/tutor_app.db')}")
    print("="*60)

def main():
    """Main function with command line argument parsing"""

    parser = argparse.ArgumentParser(
        description="Initialize Agentic AI Tutor database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/init_db.py                    # Create tables only
    python scripts/init_db.py --seed             # Create tables + sample data
    python scripts/init_db.py --reset            # Drop + recreate tables
    python scripts/init_db.py --reset --seed     # Full reset with sample data
        """
    )

    parser.add_argument(
        "--reset",
        action="store_true",
        help="Drop existing tables before creating new ones"
    )

    parser.add_argument(
        "--seed",
        action="store_true",
        help="Seed database with sample data after table creation"
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        print("Initializing Agentic AI Tutor Database...")
        print("=" * 50)

        if args.reset:
            print("WARNING:  WARNING: This will delete all existing data!")
            response = input("Continue? (yes/no): ").lower().strip()
            if response not in ['yes', 'y']:
                print("Aborted.")
                return

        # Create tables
        if not create_tables(drop_existing=args.reset):
            print("ERROR: Database initialization failed!")
            sys.exit(1)

        # Seed sample data if requested
        if args.seed:
            seed_sample_data()
        else:
            print("\nSUCCESS: Database tables created successfully!")
            print("TIP: Use --seed flag to add sample data for development")

        print("\nREADY: Database is ready for the Agentic AI Tutor!")

    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        print(f"\nERROR: Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()