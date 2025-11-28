"""
Configuration management for Agentic AI Tutor.
Loads settings from config.yaml and environment variables.
"""
import os
import yaml
import logging
from pathlib import Path
from typing import Any, Optional, Dict
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Configure basic logging for this module
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """
    Application settings combining YAML config and environment variables.

    YAML file (config.yaml) contains all non-sensitive settings.
    Environment variables (.env) contain API keys and secrets.

    Priority: Environment variables > YAML config > Defaults
    """

    # Sensitive data from environment variables only
    pinecone_api_key: str = Field(
        ...,
        description="Pinecone API key (from .env)"
    )
    default_openai_api_key: Optional[str] = Field(
        default=None,
        description="Default OpenAI API key (from .env, optional)",
        validation_alias="OPENAI_API_KEY"
    )
    default_gemini_api_key: Optional[str] = Field(
        default=None,
        description="Default Gemini API key (from .env, optional)",
        validation_alias="GEMINI_API_KEY"
    )
    secret_key: str = Field(
        default="your-secret-key-change-in-production",
        description="Secret key for encryption (from .env)"
    )

    # Environment selection
    environment: str = Field(
        default="development",
        description="Active environment (development/production)"
    )

    # YAML configuration will be loaded into this
    _yaml_config: Dict[str, Any] = {}

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    def __init__(self, **kwargs):
        """Initialize settings by loading YAML config first, then env vars"""
        # Load YAML configuration
        yaml_config = self._load_yaml_config()

        # Merge with kwargs
        merged_config = {**kwargs}
        super().__init__(**merged_config)

        # Store YAML config
        self._yaml_config = yaml_config

        # Apply environment-specific overrides
        self._apply_environment_overrides()

        # Setup logging
        self.setup_logging()

    @staticmethod
    def _load_yaml_config() -> Dict[str, Any]:
        """
        Load configuration from config.yaml file.

        Returns:
            Dict: Configuration dictionary from YAML
        """
        config_path = Path("config.yaml")

        if not config_path.exists():
            logger.warning(f"Config file not found: {config_path}. Using defaults.")
            return {}

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
                logger.info(f"Loaded configuration from {config_path}")
                return config or {}
        except Exception as e:
            logger.error(f"Failed to load config.yaml: {e}")
            return {}

    def _apply_environment_overrides(self) -> None:
        """Apply environment-specific configuration overrides"""
        if "environments" not in self._yaml_config:
            return

        env_name = self.get("active_environment", self.environment)
        env_config = self._yaml_config.get("environments", {}).get(env_name, {})

        if env_config:
            logger.info(f"Applying {env_name} environment overrides")
            self._deep_merge(self._yaml_config, env_config)

    @staticmethod
    def _deep_merge(base: Dict, override: Dict) -> None:
        """Deep merge override dict into base dict"""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                Settings._deep_merge(base[key], value)
            else:
                base[key] = value

    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get configuration value using dot notation.

        Examples:
            settings.get("llm.temperature")  # Returns 0.7
            settings.get("quiz.difficulty_thresholds.easy_below")  # Returns 50.0

        Args:
            key_path: Dot-separated path to config value (e.g., "llm.temperature")
            default: Default value if key not found

        Returns:
            Any: Configuration value or default
        """
        keys = key_path.split(".")
        value = self._yaml_config

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default

        return value

    # Convenience methods for commonly used settings

    @property
    def app_name(self) -> str:
        """Get application name"""
        return self.get("app.name", "Agentic AI Tutor")

    @property
    def app_version(self) -> str:
        """Get application version"""
        return self.get("app.version", "0.1.0")

    @property
    def debug(self) -> bool:
        """Get debug mode flag"""
        return self.get("app.debug", False)

    @property
    def log_level(self) -> str:
        """Get logging level"""
        return self.get("app.log_level", "INFO")

    @property
    def database_url(self) -> str:
        """Get database URL"""
        return self.get("database.url", "sqlite:///./data/tutor_app.db")

    @property
    def default_llm_provider(self) -> str:
        """Get default LLM provider"""
        return self.get("llm.default_provider", "openai")

    @property
    def llm_temperature(self) -> float:
        """Get LLM temperature"""
        return self.get("llm.temperature", 0.7)

    @property
    def llm_max_tokens(self) -> int:
        """Get LLM max tokens"""
        return self.get("llm.max_tokens", 2000)

    @property
    def llm_timeout(self) -> int:
        """Get LLM timeout in seconds"""
        return self.get("llm.timeout", 30)

    @property
    def embedding_model(self) -> str:
        """Get embedding model name"""
        return self.get("embeddings.model", "text-embedding-3-small")

    @property
    def pinecone_index_name(self) -> str:
        """Get Pinecone index name"""
        return self.get("pinecone.index_name", "tutor-knowledge-base")

    @property
    def pinecone_dimension(self) -> int:
        """Get Pinecone vector dimension"""
        return self.get("pinecone.dimension", 1536)

    @property
    def rag_chunk_size(self) -> int:
        """Get RAG chunk size"""
        return self.get("rag.chunk_size", 500)

    @property
    def rag_chunk_overlap(self) -> int:
        """Get RAG chunk overlap"""
        return self.get("rag.chunk_overlap", 50)

    @property
    def rag_top_k(self) -> int:
        """Get RAG top-k results"""
        return self.get("rag.top_k", 5)

    def get_llm_model(self, provider: str, model_type: str = "default") -> str:
        """
        Get LLM model name for a specific provider.

        Args:
            provider: Provider name ("openai" or "gemini")
            model_type: Model type ("default", "advanced", "fallback")

        Returns:
            str: Model name
        """
        return self.get(f"llm.models.{provider}.{model_type}", "gpt-4o-mini")

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
        db_path = self.database_url.replace("sqlite:///", "")
        return os.path.abspath(db_path)

    def setup_logging(self) -> None:
        """
        Configure application-wide logging based on settings.
        """
        log_level = self.log_level
        log_format = self.get("logging.format", '%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        # Ensure logs directory exists
        os.makedirs("logs", exist_ok=True)

        # Get log file paths
        app_log = self.get("logging.files.app_log", "logs/app.log")
        error_log = self.get("logging.files.error_log", "logs/error.log")

        # Configure logging
        logging.basicConfig(
            level=getattr(logging, log_level),
            format=log_format,
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler(app_log, mode='a')
            ]
        )

        logger.info(f"Logging configured at {log_level} level")
        logger.info(f"Log files: {app_log}, {error_log}")

    def get_full_config(self) -> Dict[str, Any]:
        """
        Get the complete configuration dictionary.

        Returns:
            Dict: Full configuration including YAML and env vars
        """
        return {
            **self._yaml_config,
            "api_keys": {
                "openai": bool(self.default_openai_api_key),
                "gemini": bool(self.default_gemini_api_key),
                "pinecone": bool(self.pinecone_api_key)
            }
        }

    def __repr__(self) -> str:
        """String representation hiding sensitive data"""
        return (
            f"Settings(app='{self.app_name}', "
            f"env='{self.environment}', "
            f"llm='{self.default_llm_provider}', "
            f"pinecone='{self.pinecone_index_name}')"
        )


# Global settings instance
# Import this in other modules: from app.core.config import settings
try:
    settings = Settings()
    logger.info(f"Configuration initialized: {settings.app_name} v{settings.app_version}")
except Exception as e:
    logger.error(f"Failed to initialize settings: {e}")
    logger.warning("Using default settings as fallback")
    # Create a minimal settings instance with defaults
    settings = None