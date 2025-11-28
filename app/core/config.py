"""
Configuration management for Agentic AI Tutor.
Handles environment variables and application settings using Pydantic.
"""
import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, validator
import logging

logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    Uses Pydantic Settings for type validation and environment variable loading.
    Supports both system-wide admin keys and per-student API keys.
    """

    # Application Settings
    app_name: str = Field(default="Agentic AI Tutor", description="Application name")
    app_version: str = Field(default="0.1.0", description="Application version")
    debug: bool = Field(default=False, description="Debug mode flag")
    log_level: str = Field(default="INFO", description="Logging level")

    # Database Configuration
    database_url: str = Field(
        default="sqlite:///./data/tutor_app.db",
        description="SQLite database connection URL"
    )
    db_echo: bool = Field(default=False, description="Echo SQL queries for debugging")

    # API Keys - Admin/Default (Optional - users can provide their own)
    default_openai_api_key: Optional[str] = Field(
        default=None,
        description="Default OpenAI API key (optional, for testing)"
    )
    default_gemini_api_key: Optional[str] = Field(
        default=None,
        description="Default Gemini API key (optional, for testing)"
    )

    # Pinecone Configuration
    pinecone_api_key: str = Field(
        ...,
        description="Pinecone API key for vector database (required)"
    )
    pinecone_environment: str = Field(
        default="us-east-1",
        description="Pinecone environment/region"
    )
    pinecone_index_name: str = Field(
        default="tutor-knowledge-base",
        description="Pinecone index name for knowledge base"
    )
    pinecone_dimension: int = Field(
        default=1536,
        description="Vector dimension (1536 for text-embedding-3-small)"
    )
    pinecone_metric: str = Field(
        default="cosine",
        description="Distance metric for vector similarity"
    )

    # LLM Configuration
    default_llm_provider: str = Field(
        default="openai",
        description="Default LLM provider (openai or gemini)"
    )
    llm_temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="LLM temperature for response generation"
    )
    llm_max_tokens: int = Field(
        default=2000,
        gt=0,
        description="Maximum tokens for LLM responses"
    )
    llm_timeout: int = Field(
        default=30,
        gt=0,
        description="LLM API timeout in seconds"
    )

    # Embedding Configuration
    embedding_model: str = Field(
        default="text-embedding-3-small",
        description="OpenAI embedding model"
    )
    embedding_batch_size: int = Field(
        default=100,
        gt=0,
        description="Batch size for embedding generation"
    )

    # RAG Configuration
    rag_chunk_size: int = Field(
        default=500,
        gt=0,
        description="Document chunk size in tokens"
    )
    rag_chunk_overlap: int = Field(
        default=50,
        ge=0,
        description="Overlap between chunks in tokens"
    )
    rag_top_k: int = Field(
        default=5,
        gt=0,
        description="Number of top results to retrieve from RAG"
    )
    rag_similarity_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Minimum similarity score for RAG results"
    )
    rag_max_context_tokens: int = Field(
        default=3000,
        gt=0,
        description="Maximum context tokens for RAG"
    )

    # Session Configuration
    session_timeout_minutes: int = Field(
        default=60,
        gt=0,
        description="Session inactivity timeout in minutes"
    )
    max_conversation_history: int = Field(
        default=20,
        gt=0,
        description="Maximum conversation messages to keep in context"
    )

    # Quiz Configuration
    quiz_easy_accuracy_threshold: float = Field(
        default=50.0,
        description="Accuracy below this (%) triggers easy difficulty"
    )
    quiz_hard_accuracy_threshold: float = Field(
        default=80.0,
        description="Accuracy above this (%) triggers hard difficulty"
    )
    default_questions_per_quiz: int = Field(
        default=5,
        gt=0,
        description="Default number of questions per quiz"
    )

    # Progress Tracking
    weak_area_threshold: float = Field(
        default=60.0,
        description="Accuracy below this (%) marks topic as weak"
    )
    mastery_threshold: float = Field(
        default=85.0,
        description="Accuracy above this (%) indicates mastery"
    )
    stale_days_threshold: int = Field(
        default=7,
        gt=0,
        description="Days without practice to mark topic as stale"
    )

    # API Configuration
    api_prefix: str = Field(default="/api", description="API route prefix")
    cors_origins: list[str] = Field(
        default=["*"],
        description="Allowed CORS origins"
    )

    # Security
    secret_key: str = Field(
        default="your-secret-key-change-in-production",
        description="Secret key for encryption (change in production!)"
    )

    # Model configuration
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    @validator("log_level")
    def validate_log_level(cls, v):
        """Validate that log level is one of the standard Python logging levels"""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"log_level must be one of {valid_levels}")
        return v.upper()

    @validator("default_llm_provider")
    def validate_llm_provider(cls, v):
        """Validate that LLM provider is supported"""
        valid_providers = ["openai", "gemini"]
        if v.lower() not in valid_providers:
            raise ValueError(f"default_llm_provider must be one of {valid_providers}")
        return v.lower()

    @validator("pinecone_metric")
    def validate_pinecone_metric(cls, v):
        """Validate Pinecone distance metric"""
        valid_metrics = ["cosine", "euclidean", "dotproduct"]
        if v.lower() not in valid_metrics:
            raise ValueError(f"pinecone_metric must be one of {valid_metrics}")
        return v.lower()

    def get_llm_api_key(self, provider: str, student_key: Optional[str] = None) -> Optional[str]:
        """
        Get LLM API key with fallback logic.

        Priority: Student's key > Default admin key > None

        Args:
            provider: LLM provider name ("openai" or "gemini")
            student_key: Optional student-provided API key

        Returns:
            Optional[str]: API key to use, or None if not available
        """
        # Use student's key if provided
        if student_key:
            return student_key

        # Fall back to default admin key
        if provider.lower() == "openai":
            return self.default_openai_api_key
        elif provider.lower() == "gemini":
            return self.default_gemini_api_key

        return None

    def is_llm_available(self, provider: str, student_key: Optional[str] = None) -> bool:
        """
        Check if LLM provider is available (has valid API key).

        Args:
            provider: LLM provider name ("openai" or "gemini")
            student_key: Optional student-provided API key

        Returns:
            bool: True if API key is available for the provider
        """
        api_key = self.get_llm_api_key(provider, student_key)
        return api_key is not None and len(api_key.strip()) > 0

    def get_database_path(self) -> str:
        """
        Get the filesystem path to the SQLite database.

        Returns:
            str: Absolute path to database file
        """
        # Extract path from database URL
        db_path = self.database_url.replace("sqlite:///", "")
        return os.path.abspath(db_path)

    def setup_logging(self) -> None:
        """
        Configure application-wide logging based on settings.
        """
        logging.basicConfig(
            level=getattr(logging, self.log_level),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler('logs/app.log', mode='a')
            ]
        )
        logger.info(f"Logging configured at {self.log_level} level")

    def __repr__(self) -> str:
        """String representation hiding sensitive data"""
        return (
            f"Settings(app_name='{self.app_name}', "
            f"llm_provider='{self.default_llm_provider}', "
            f"pinecone_index='{self.pinecone_index_name}')"
        )


# Global settings instance
# Import this in other modules: from app.core.config import settings
settings = Settings()

# Ensure logs directory exists
os.makedirs("logs", exist_ok=True)

# Setup logging on module import
if not logging.getLogger().handlers:
    settings.setup_logging()

logger.info(f"Configuration loaded: {settings.app_name} v{settings.app_version}")
logger.debug(f"Database: {settings.get_database_path()}")
logger.debug(f"Pinecone Index: {settings.pinecone_index_name}")