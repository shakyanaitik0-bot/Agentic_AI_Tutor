"""
Student model for Agentic AI Tutor.
Handles student profiles with encrypted API keys and competitive exam preparation data.
"""
import uuid
from datetime import datetime
from typing import Optional, Dict, List
from sqlalchemy import Column, String, DateTime, Text, JSON, Boolean
from sqlalchemy.orm import relationship
from cryptography.fernet import Fernet
import os
import json
import logging

from app.core.database import Base

logger = logging.getLogger(__name__)

class Student(Base):
    """
    Student model representing a learner in the tutoring system.

    Supports competitive exam preparation (JEE, SAT, GRE) with encrypted API key storage
    and comprehensive learning profile tracking.
    """
    __tablename__ = "students"

    # Primary identification
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)

    # Exam preparation context
    exam_type = Column(String(20), nullable=False, index=True)  # JEE, SAT, GRE, etc.

    # Encrypted API keys - users provide their own to avoid rate limits
    api_key_openai_encrypted = Column(Text, nullable=True)
    api_key_gemini_encrypted = Column(Text, nullable=True)

    # Learning preferences and weak areas (JSON storage)
    learning_preferences = Column(JSON, nullable=True, default=dict)
    weak_areas = Column(JSON, nullable=True, default=list)  # List of weak topics
    strong_areas = Column(JSON, nullable=True, default=list)  # List of strong topics

    # Account management
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_active = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships with other models
    sessions = relationship("Session", back_populates="student", cascade="all, delete-orphan")
    progress_records = relationship("Progress", back_populates="student", cascade="all, delete-orphan")

    def __init__(self, **kwargs):
        """Initialize student with default preferences"""
        super().__init__(**kwargs)

        # Set default learning preferences if not provided
        if not self.learning_preferences:
            self.learning_preferences = {
                "preferred_difficulty": "medium",  # easy, medium, hard
                "questions_per_session": 5,
                "explanation_style": "detailed",  # brief, detailed, step_by_step
                "practice_frequency": "daily",  # daily, weekly, intensive
                "topics_to_focus": [],
                "study_schedule": {
                    "morning": False,
                    "afternoon": True,
                    "evening": True
                }
            }

        # Initialize empty weak/strong areas if not provided
        if not self.weak_areas:
            self.weak_areas = []
        if not self.strong_areas:
            self.strong_areas = []

    @property
    def encryption_key(self) -> bytes:
        """
        Generate encryption key for API keys.
        In production, this should be environment-specific and more secure.
        """
        # Use student ID as part of key generation for per-user encryption
        key_material = f"{self.id}_{os.getenv('SECRET_KEY', 'default-key-for-dev')}"
        return Fernet.generate_key() if not hasattr(self, '_key') else self._key

    def set_openai_key(self, api_key: str) -> bool:
        """
        Encrypt and store OpenAI API key.

        Args:
            api_key: Plain text OpenAI API key

        Returns:
            bool: True if successful, False if error
        """
        try:
            if not api_key or not api_key.strip():
                logger.warning(f"Empty OpenAI API key provided for student {self.id}")
                return False

            # Basic validation - OpenAI keys start with 'sk-'
            if not api_key.startswith('sk-'):
                logger.warning(f"Invalid OpenAI API key format for student {self.id}")
                return False

            # Encrypt the API key
            fernet = Fernet(self.encryption_key)
            self.api_key_openai_encrypted = fernet.encrypt(api_key.encode()).decode()
            logger.info(f"OpenAI API key set for student {self.id}")
            return True

        except Exception as e:
            logger.error(f"Failed to encrypt OpenAI API key for student {self.id}: {e}")
            return False

    def get_openai_key(self) -> Optional[str]:
        """
        Decrypt and return OpenAI API key.

        Returns:
            Optional[str]: Decrypted API key or None if not set/error
        """
        try:
            if not self.api_key_openai_encrypted:
                return None

            fernet = Fernet(self.encryption_key)
            decrypted_key = fernet.decrypt(self.api_key_openai_encrypted.encode()).decode()
            return decrypted_key

        except Exception as e:
            logger.error(f"Failed to decrypt OpenAI API key for student {self.id}: {e}")
            return None

    def set_gemini_key(self, api_key: str) -> bool:
        """
        Encrypt and store Gemini API key.

        Args:
            api_key: Plain text Gemini API key

        Returns:
            bool: True if successful, False if error
        """
        try:
            if not api_key or not api_key.strip():
                logger.warning(f"Empty Gemini API key provided for student {self.id}")
                return False

            # Encrypt the API key
            fernet = Fernet(self.encryption_key)
            self.api_key_gemini_encrypted = fernet.encrypt(api_key.encode()).decode()
            logger.info(f"Gemini API key set for student {self.id}")
            return True

        except Exception as e:
            logger.error(f"Failed to encrypt Gemini API key for student {self.id}: {e}")
            return False

    def get_gemini_key(self) -> Optional[str]:
        """
        Decrypt and return Gemini API key.

        Returns:
            Optional[str]: Decrypted API key or None if not set/error
        """
        try:
            if not self.api_key_gemini_encrypted:
                return None

            fernet = Fernet(self.encryption_key)
            decrypted_key = fernet.decrypt(self.api_key_gemini_encrypted.encode()).decode()
            return decrypted_key

        except Exception as e:
            logger.error(f"Failed to decrypt Gemini API key for student {self.id}: {e}")
            return None

    def update_weak_areas(self, topics: List[str]) -> None:
        """
        Update student's weak areas based on performance.

        Args:
            topics: List of topic names where student is struggling
        """
        # Ensure we're working with a unique list
        current_weak = set(self.weak_areas or [])
        new_weak = set(topics)

        # Update weak areas
        self.weak_areas = list(current_weak.union(new_weak))

        # Remove from strong areas if they're now weak
        if self.strong_areas:
            self.strong_areas = [topic for topic in self.strong_areas if topic not in new_weak]

        logger.info(f"Updated weak areas for student {self.id}: {self.weak_areas}")

    def update_strong_areas(self, topics: List[str]) -> None:
        """
        Update student's strong areas based on performance.

        Args:
            topics: List of topic names where student excels
        """
        # Ensure we're working with a unique list
        current_strong = set(self.strong_areas or [])
        new_strong = set(topics)

        # Update strong areas
        self.strong_areas = list(current_strong.union(new_strong))

        # Remove from weak areas if they're now strong
        if self.weak_areas:
            self.weak_areas = [topic for topic in self.weak_areas if topic not in new_strong]

        logger.info(f"Updated strong areas for student {self.id}: {self.strong_areas}")

    def get_profile_summary(self) -> Dict:
        """
        Get comprehensive student profile for agent context.

        Returns:
            Dict: Profile summary for agent decision making
        """
        return {
            "student_id": self.id,
            "name": self.name,
            "exam_type": self.exam_type,
            "weak_areas": self.weak_areas or [],
            "strong_areas": self.strong_areas or [],
            "learning_preferences": self.learning_preferences or {},
            "has_openai_key": bool(self.api_key_openai_encrypted),
            "has_gemini_key": bool(self.api_key_gemini_encrypted),
            "is_active": self.is_active,
            "days_since_created": (datetime.utcnow() - self.created_at).days,
            "last_active": self.last_active.isoformat() if self.last_active else None
        }

    def update_last_active(self) -> None:
        """Update the last active timestamp"""
        self.last_active = datetime.utcnow()

    def __repr__(self):
        return f"<Student(id='{self.id}', name='{self.name}', exam_type='{self.exam_type}')>"

    def __str__(self):
        return f"{self.name} ({self.exam_type} prep) - {len(self.weak_areas or [])} weak areas"