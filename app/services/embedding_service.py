"""
Embedding Service for Agentic AI Tutor.
Generates vector embeddings using OpenAI's embedding models for RAG.
"""
import time
import logging
from typing import List, Optional, Dict, Any
from openai import OpenAI, OpenAIError

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Service for generating text embeddings using OpenAI.

    Features:
    - Batch embedding generation for efficiency
    - Automatic retry with exponential backoff
    - Token counting and cost tracking
    - Support for different embedding models
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None
    ):
        """
        Initialize embedding service.

        Args:
            api_key: OpenAI API key. If None, uses config default.
            model: Embedding model name. If None, uses config default.

        Raises:
            ValueError: If API key is missing
        """
        self.api_key = api_key or settings.default_openai_api_key
        self.model = model or settings.embedding_model

        if not self.api_key:
            raise ValueError("No OpenAI API key provided for embedding service")

        # Initialize OpenAI client
        self.client = OpenAI(
            api_key=self.api_key,
            timeout=settings.get("embeddings.timeout", 30)
        )

        # Get batch size from config
        self.batch_size = settings.get("embeddings.batch_size", 100)

        logger.info(f"Embedding service initialized with model: {self.model}")

    def embed_text(self, text: str, retry_count: int = 3) -> List[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Text to embed
            retry_count: Number of retries on failure

        Returns:
            List[float]: Embedding vector

        Raises:
            Exception: If all retries fail
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for embedding")
            return []

        # Use batch method with single text
        embeddings = self.embed_batch([text], retry_count=retry_count)
        return embeddings[0] if embeddings else []

    def embed_batch(
        self,
        texts: List[str],
        retry_count: int = 3
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple texts in batch.

        Automatically splits large batches into smaller chunks based on batch_size.

        Args:
            texts: List of texts to embed
            retry_count: Number of retries on failure

        Returns:
            List[List[float]]: List of embedding vectors

        Raises:
            Exception: If all retries fail
        """
        if not texts:
            logger.warning("Empty text list provided for batch embedding")
            return []

        # Filter out empty texts but keep track of indices
        text_indices = [(i, text) for i, text in enumerate(texts) if text and text.strip()]

        if not text_indices:
            logger.warning("All texts in batch are empty")
            return [[] for _ in texts]

        # Split into batches if needed
        all_embeddings = [None] * len(texts)  # Placeholder for all embeddings

        for batch_start in range(0, len(text_indices), self.batch_size):
            batch_end = min(batch_start + self.batch_size, len(text_indices))
            batch = text_indices[batch_start:batch_end]

            # Extract texts and indices
            batch_texts = [text for _, text in batch]
            batch_original_indices = [idx for idx, _ in batch]

            logger.debug(
                f"Processing batch {batch_start // self.batch_size + 1}: "
                f"{len(batch_texts)} texts"
            )

            # Get embeddings for this batch with retry logic
            batch_embeddings = self._embed_batch_with_retry(
                batch_texts,
                retry_count
            )

            # Place embeddings back at original indices
            for original_idx, embedding in zip(batch_original_indices, batch_embeddings):
                all_embeddings[original_idx] = embedding

        # Fill empty texts with empty embeddings
        for i in range(len(texts)):
            if all_embeddings[i] is None:
                all_embeddings[i] = []

        return all_embeddings

    def _embed_batch_with_retry(
        self,
        texts: List[str],
        retry_count: int
    ) -> List[List[float]]:
        """
        Generate embeddings with retry logic.

        Args:
            texts: List of texts to embed
            retry_count: Number of retries on failure

        Returns:
            List[List[float]]: Embedding vectors

        Raises:
            Exception: If all retries fail
        """
        for attempt in range(retry_count):
            try:
                # Call OpenAI API
                response = self.client.embeddings.create(
                    model=self.model,
                    input=texts
                )

                # Extract embeddings
                embeddings = [item.embedding for item in response.data]

                # Log usage statistics
                if hasattr(response, 'usage'):
                    logger.debug(
                        f"Embedding generated: {len(texts)} texts, "
                        f"{response.usage.total_tokens} tokens"
                    )

                return embeddings

            except OpenAIError as e:
                logger.warning(
                    f"Embedding failed (attempt {attempt + 1}/{retry_count}): {e}"
                )

                if attempt < retry_count - 1:
                    # Exponential backoff
                    sleep_time = 2 ** attempt
                    logger.info(f"Retrying in {sleep_time} seconds...")
                    time.sleep(sleep_time)
                else:
                    logger.error(f"All {retry_count} attempts failed for embedding")
                    raise

    def get_embedding_dimension(self) -> int:
        """
        Get the dimension of embeddings for the current model.

        Returns:
            int: Embedding dimension (e.g., 1536 for text-embedding-3-small)
        """
        # Model dimension mapping
        dimensions = {
            "text-embedding-3-small": 1536,
            "text-embedding-3-large": 3072,
            "text-embedding-ada-002": 1536
        }

        return dimensions.get(self.model, 1536)

    def estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for a text.

        Uses rough approximation: 1 token ≈ 4 characters

        Args:
            text: Text to estimate tokens for

        Returns:
            int: Estimated token count
        """
        return len(text) // 4

    def estimate_cost(self, texts: List[str]) -> Dict[str, Any]:
        """
        Estimate the cost of embedding a list of texts.

        Pricing (as of 2024):
        - text-embedding-3-small: $0.02 / 1M tokens
        - text-embedding-3-large: $0.13 / 1M tokens

        Args:
            texts: List of texts to embed

        Returns:
            Dict: Cost estimation with token count and price
        """
        # Estimate total tokens
        total_tokens = sum(self.estimate_tokens(text) for text in texts)

        # Pricing per million tokens (USD)
        pricing = {
            "text-embedding-3-small": 0.02,
            "text-embedding-3-large": 0.13,
            "text-embedding-ada-002": 0.10
        }

        price_per_million = pricing.get(self.model, 0.02)
        estimated_cost = (total_tokens / 1_000_000) * price_per_million

        return {
            "model": self.model,
            "text_count": len(texts),
            "estimated_tokens": total_tokens,
            "cost_usd": round(estimated_cost, 6),
            "price_per_million_tokens": price_per_million
        }

    def is_available(self) -> bool:
        """
        Check if the embedding service is available and functional.

        Returns:
            bool: True if service can be used, False otherwise
        """
        try:
            # Test with a minimal embedding
            test_embedding = self.embed_text("test", retry_count=1)
            return len(test_embedding) > 0
        except Exception as e:
            logger.error(f"Embedding service availability check failed: {e}")
            return False

    def get_service_info(self) -> Dict[str, Any]:
        """
        Get information about the embedding service configuration.

        Returns:
            Dict: Service information
        """
        return {
            "model": self.model,
            "dimension": self.get_embedding_dimension(),
            "batch_size": self.batch_size,
            "has_api_key": bool(self.api_key)
        }

    def __repr__(self) -> str:
        """String representation"""
        return f"EmbeddingService(model='{self.model}', dimension={self.get_embedding_dimension()})"


def create_embedding_service(
    api_key: Optional[str] = None,
    model: Optional[str] = None
) -> EmbeddingService:
    """
    Factory function to create embedding service instance.

    Args:
        api_key: Optional OpenAI API key
        model: Optional model name

    Returns:
        EmbeddingService: Configured embedding service instance
    """
    return EmbeddingService(api_key=api_key, model=model)