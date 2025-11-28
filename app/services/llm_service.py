"""
LLM Service for Agentic AI Tutor.
Unified interface for OpenAI and Gemini APIs with automatic retry and error handling.
"""
import time
import logging
from typing import List, Dict, Optional, Any, Literal
from openai import OpenAI, OpenAIError
import google.generativeai as genai
from google.generativeai.types import GenerationConfig
import tiktoken

from app.core.config import settings

logger = logging.getLogger(__name__)

# Type alias for LLM provider
LLMProvider = Literal["openai", "gemini"]


class LLMService:
    """
    Unified LLM service supporting both OpenAI and Gemini.

    Features:
    - Dynamic provider selection (OpenAI or Gemini)
    - Automatic retry with exponential backoff
    - Token counting and cost tracking
    - Consistent interface across providers
    - Error handling and fallback mechanisms
    """

    def __init__(
        self,
        provider: Optional[LLMProvider] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None
    ):
        """
        Initialize LLM service with specified provider.

        Args:
            provider: LLM provider to use ("openai" or "gemini"). Defaults to config.
            api_key: API key for the provider. If None, uses config default.
            model: Model name to use. If None, uses provider defaults.

        Raises:
            ValueError: If provider is invalid or API key is missing
        """
        self.provider = provider or settings.default_llm_provider
        self.api_key = api_key
        self.model = model or self._get_default_model()

        # Validate provider
        if self.provider not in ["openai", "gemini"]:
            raise ValueError(f"Invalid provider: {self.provider}. Must be 'openai' or 'gemini'")

        # Get API key with fallback
        if not self.api_key:
            self.api_key = settings.get_llm_api_key(self.provider)

        if not self.api_key:
            raise ValueError(f"No API key provided for {self.provider}")

        # Initialize provider-specific client
        self._init_client()

        # Token counter for OpenAI
        self.token_encoder = None
        if self.provider == "openai":
            try:
                self.token_encoder = tiktoken.encoding_for_model(self.model)
            except KeyError:
                # Fallback to cl100k_base for newer models
                self.token_encoder = tiktoken.get_encoding("cl100k_base")

        logger.info(f"LLM Service initialized: provider={self.provider}, model={self.model}")

    def _get_default_model(self) -> str:
        """
        Get default model name for the provider.

        Returns:
            str: Default model name
        """
        defaults = {
            "openai": "gpt-4o-mini",  # Fast and cost-effective
            "gemini": "gemini-2.5-flash"  # Fast Gemini model
        }
        return defaults.get(self.provider, "gpt-4o-mini")

    def _init_client(self) -> None:
        """Initialize the provider-specific API client"""
        if self.provider == "openai":
            self.client = OpenAI(
                api_key=self.api_key,
                timeout=settings.llm_timeout
            )
            logger.debug("OpenAI client initialized")

        elif self.provider == "gemini":
            genai.configure(api_key=self.api_key)
            self.client = genai.GenerativeModel(self.model)
            logger.debug("Gemini client initialized")

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        system_prompt: Optional[str] = None,
        retry_count: int = 3
    ) -> str:
        """
        Generate chat completion using the configured LLM provider.

        Args:
            messages: List of message dicts with 'role' and 'content' keys
            temperature: Sampling temperature (0.0-2.0). Defaults to config.
            max_tokens: Maximum tokens to generate. Defaults to config.
            system_prompt: Optional system prompt (prepended to messages)
            retry_count: Number of retries on failure

        Returns:
            str: Generated response text

        Raises:
            Exception: If all retries fail
        """
        temperature = temperature or settings.llm_temperature
        max_tokens = max_tokens or settings.llm_max_tokens

        # Add system prompt if provided
        if system_prompt:
            messages = [{"role": "system", "content": system_prompt}] + messages

        # Retry logic with exponential backoff
        for attempt in range(retry_count):
            try:
                if self.provider == "openai":
                    response = self._openai_completion(messages, temperature, max_tokens)
                elif self.provider == "gemini":
                    response = self._gemini_completion(messages, temperature, max_tokens)
                else:
                    raise ValueError(f"Unsupported provider: {self.provider}")

                logger.debug(f"LLM completion successful (attempt {attempt + 1})")
                return response

            except Exception as e:
                logger.warning(f"LLM completion failed (attempt {attempt + 1}/{retry_count}): {e}")

                if attempt < retry_count - 1:
                    # Exponential backoff: 1s, 2s, 4s
                    sleep_time = 2 ** attempt
                    logger.info(f"Retrying in {sleep_time} seconds...")
                    time.sleep(sleep_time)
                else:
                    logger.error(f"All {retry_count} attempts failed for LLM completion")
                    raise

    def _openai_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int
    ) -> str:
        """
        Generate completion using OpenAI API.

        Args:
            messages: Conversation messages
            temperature: Sampling temperature
            max_tokens: Maximum tokens

        Returns:
            str: Generated response
        """
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )

        content = response.choices[0].message.content

        # Log token usage
        if hasattr(response, 'usage'):
            logger.debug(
                f"OpenAI tokens - prompt: {response.usage.prompt_tokens}, "
                f"completion: {response.usage.completion_tokens}, "
                f"total: {response.usage.total_tokens}"
            )

        return content

    def _gemini_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int
    ) -> str:
        """
        Generate completion using Gemini API.

        Args:
            messages: Conversation messages
            temperature: Sampling temperature
            max_tokens: Maximum tokens

        Returns:
            str: Generated response
        """
        # Convert OpenAI-style messages to Gemini format
        gemini_messages = self._convert_to_gemini_format(messages)

        # Configure generation parameters
        generation_config = GenerationConfig(
            temperature=temperature,
            max_output_tokens=max_tokens
        )

        # Generate response
        response = self.client.generate_content(
            gemini_messages,
            generation_config=generation_config
        )

        return response.text

    def _convert_to_gemini_format(self, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        Convert OpenAI message format to Gemini format.

        OpenAI uses: {"role": "user"/"assistant"/"system", "content": "..."}
        Gemini uses: {"role": "user"/"model", "parts": ["..."]}

        Args:
            messages: OpenAI-style messages

        Returns:
            List[Dict]: Gemini-formatted messages
        """
        gemini_messages = []
        system_context = []

        for msg in messages:
            role = msg["role"]
            content = msg["content"]

            # Handle system messages by prepending to first user message
            if role == "system":
                system_context.append(content)
                continue

            # Convert role names
            gemini_role = "model" if role == "assistant" else "user"

            # Add system context to first user message
            if gemini_role == "user" and system_context:
                content = "\n\n".join(system_context) + "\n\n" + content
                system_context = []

            gemini_messages.append({
                "role": gemini_role,
                "parts": [content]
            })

        return gemini_messages

    def count_tokens(self, text: str) -> int:
        """
        Count tokens in text.

        Note: Only accurate for OpenAI. Gemini uses approximation.

        Args:
            text: Text to count tokens for

        Returns:
            int: Estimated token count
        """
        if self.provider == "openai" and self.token_encoder:
            return len(self.token_encoder.encode(text))
        else:
            # Rough approximation: 1 token ≈ 4 characters
            return len(text) // 4

    def count_messages_tokens(self, messages: List[Dict[str, str]]) -> int:
        """
        Count total tokens in a message list.

        Args:
            messages: List of messages

        Returns:
            int: Total token count
        """
        total = 0
        for message in messages:
            total += self.count_tokens(message.get("content", ""))
            # Add overhead for message formatting (role, etc.)
            total += 4

        return total

    def switch_provider(
        self,
        provider: LLMProvider,
        api_key: Optional[str] = None,
        model: Optional[str] = None
    ) -> None:
        """
        Switch to a different LLM provider.

        Useful for fallback scenarios or user preference changes.

        Args:
            provider: New provider to use ("openai" or "gemini")
            api_key: Optional new API key
            model: Optional new model name
        """
        logger.info(f"Switching LLM provider from {self.provider} to {provider}")

        self.provider = provider
        if api_key:
            self.api_key = api_key
        else:
            self.api_key = settings.get_llm_api_key(provider)

        if not self.api_key:
            raise ValueError(f"No API key available for provider: {provider}")

        self.model = model or self._get_default_model()
        self._init_client()

        logger.info(f"LLM provider switched successfully to {provider} with model {self.model}")

    def is_available(self) -> bool:
        """
        Check if the LLM service is available and functional.

        Returns:
            bool: True if service can be used, False otherwise
        """
        try:
            # Test with a minimal completion
            test_messages = [{"role": "user", "content": "Hi"}]
            response = self.chat_completion(
                messages=test_messages,
                max_tokens=5,
                retry_count=1
            )
            return bool(response)
        except Exception as e:
            logger.error(f"LLM availability check failed: {e}")
            return False

    def get_model_info(self) -> Dict[str, Any]:
        """
        Get information about the current model configuration.

        Returns:
            Dict: Model information including provider, model name, and settings
        """
        return {
            "provider": self.provider,
            "model": self.model,
            "temperature": settings.llm_temperature,
            "max_tokens": settings.llm_max_tokens,
            "timeout": settings.llm_timeout,
            "has_api_key": bool(self.api_key)
        }

    def __repr__(self) -> str:
        """String representation"""
        return f"LLMService(provider='{self.provider}', model='{self.model}')"


def create_llm_service(
    provider: Optional[LLMProvider] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None
) -> LLMService:
    """
    Factory function to create LLM service instance.

    Args:
        provider: LLM provider ("openai" or "gemini")
        api_key: Optional API key
        model: Optional model name

    Returns:
        LLMService: Configured LLM service instance
    """
    return LLMService(provider=provider, api_key=api_key, model=model)