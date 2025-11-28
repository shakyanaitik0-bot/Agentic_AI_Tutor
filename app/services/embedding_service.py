"""
Embedding Service for Agentic AI Tutor.
Supports both OpenAI embeddings (paid) and Sentence Transformers (free, local).
"""
import time
import logging
from typing import List, Optional, Dict, Any, Literal
from dotenv import load_dotenv

load_dotenv()

from app.core.config import settings

logger = logging.getLogger(__name__)

# Type alias for embedding provider
EmbeddingProvider = Literal["openai", "sentence-transformers"]


class EmbeddingService:
    """
    Unified embedding service supporting multiple providers.

    Providers:
    - OpenAI: High quality, requires API key and credits (PAID)
    - Sentence Transformers: Good quality, runs locally, completely free (FREE)

    Features:
    - Batch embedding generation for efficiency
    - Automatic retry with exponential backoff (OpenAI)
    - Cost estimation (OpenAI)
    - GPU acceleration support (Sentence Transformers)
    """

    def __init__(
        self,
        provider: Optional[EmbeddingProvider] = None,
        model: Optional[str] = None
    ):
        """
        Initialize embedding service.

        Args:
            provider: Embedding provider ("openai" or "sentence-transformers"). Defaults to config.
            model: Model name. If None, uses provider defaults from config.

        Raises:
            ValueError: If provider is invalid or requirements are missing
        """
        self.provider = provider or settings.get("embeddings.provider", "sentence-transformers")
        self.batch_size = settings.get("embeddings.batch_size", 100)

        # Initialize provider-specific client
        if self.provider == "openai":
            self._init_openai(model)
        elif self.provider == "sentence-transformers":
            self._init_sentence_transformers(model)
        else:
            raise ValueError(f"Invalid provider: {self.provider}. Must be 'openai' or 'sentence-transformers'")

        logger.info(f"Embedding service initialized: provider={self.provider}, model={self.model}, dimension={self.get_embedding_dimension()}")

    def _init_openai(self, model: Optional[str]):
        """Initialize OpenAI embedding client"""
        try:
            from openai import OpenAI, OpenAIError
            self.OpenAIError = OpenAIError
        except ImportError:
            raise ImportError("OpenAI package not installed. Run: pip install openai")

        self.model = model or settings.get("embeddings.openai_model", "text-embedding-3-small")
        api_key = settings.default_openai_api_key

        if not api_key:
            raise ValueError("No OpenAI API key provided for embedding service")

        self.client = OpenAI(
            api_key=api_key,
            timeout=settings.get("embeddings.timeout", 30)
        )

    def _init_sentence_transformers(self, model: Optional[str]):
        """Initialize Sentence Transformers model"""
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise ImportError(
                "Sentence Transformers not installed. Run: pip install sentence-transformers torch"
            )

        self.model = model or settings.get("embeddings.sentence_transformer_model", "all-MiniLM-L6-v2")
        device = settings.get("embeddings.device", "cpu")

        logger.info(f"Loading Sentence Transformer model: {self.model} on {device}")
        self.client = SentenceTransformer(self.model, device=device)
        logger.info(f"Model loaded successfully")

    def embed_text(self, text: str, retry_count: int = 3) -> List[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Text to embed
            retry_count: Number of retries on failure (OpenAI only)

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
            retry_count: Number of retries on failure (OpenAI only)

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

            # Get embeddings for this batch
            if self.provider == "openai":
                batch_embeddings = self._embed_batch_openai(batch_texts, retry_count)
            elif self.provider == "sentence-transformers":
                batch_embeddings = self._embed_batch_sentence_transformers(batch_texts)

            # Place embeddings back at original indices
            for original_idx, embedding in zip(batch_original_indices, batch_embeddings):
                all_embeddings[original_idx] = embedding

        # Fill empty texts with empty embeddings
        for i in range(len(texts)):
            if all_embeddings[i] is None:
                all_embeddings[i] = []

        return all_embeddings

    def _embed_batch_openai(
        self,
        texts: List[str],
        retry_count: int
    ) -> List[List[float]]:
        """
        Generate embeddings using OpenAI with retry logic.

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
                        f"OpenAI embedding generated: {len(texts)} texts, "
                        f"{response.usage.total_tokens} tokens"
                    )

                return embeddings

            except self.OpenAIError as e:
                logger.warning(
                    f"OpenAI embedding failed (attempt {attempt + 1}/{retry_count}): {e}"
                )

                if attempt < retry_count - 1:
                    # Exponential backoff
                    sleep_time = 2 ** attempt
                    logger.info(f"Retrying in {sleep_time} seconds...")
                    time.sleep(sleep_time)
                else:
                    logger.error(f"All {retry_count} attempts failed for OpenAI embedding")
                    raise

    def _embed_batch_sentence_transformers(
        self,
        texts: List[str]
    ) -> List[List[float]]:
        """
        Generate embeddings using Sentence Transformers (local, no API calls).

        Args:
            texts: List of texts to embed

        Returns:
            List[List[float]]: Embedding vectors
        """
        try:
            # Generate embeddings (runs locally on CPU/GPU)
            embeddings = self.client.encode(
                texts,
                show_progress_bar=False,
                convert_to_numpy=True
            )

            # Convert numpy arrays to lists
            embeddings_list = [emb.tolist() for emb in embeddings]

            logger.debug(f"Sentence Transformers embedding generated: {len(texts)} texts")
            return embeddings_list

        except Exception as e:
            logger.error(f"Sentence Transformers embedding failed: {e}")
            raise

    def get_embedding_dimension(self) -> int:
        """
        Get the dimension of embeddings for the current model.

        Returns:
            int: Embedding dimension
        """
        if self.provider == "openai":
            # OpenAI model dimension mapping
            dimensions = {
                "text-embedding-3-small": 1536,
                "text-embedding-3-large": 3072,
                "text-embedding-ada-002": 1536
            }
            return dimensions.get(self.model, 1536)

        elif self.provider == "sentence-transformers":
            # Sentence Transformer model dimension mapping
            dimensions = {
                "all-MiniLM-L6-v2": 384,
                "all-mpnet-base-v2": 768,
                "BAAI/bge-small-en-v1.5": 384,
                "BAAI/bge-base-en-v1.5": 768
            }
            return dimensions.get(self.model, 384)

        return 384  # Default fallback

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

        For Sentence Transformers: Always free (runs locally)
        For OpenAI: Based on current pricing

        Args:
            texts: List of texts to embed

        Returns:
            Dict: Cost estimation with token count and price
        """
        if self.provider == "sentence-transformers":
            return {
                "model": self.model,
                "provider": "sentence-transformers",
                "text_count": len(texts),
                "estimated_tokens": sum(self.estimate_tokens(text) for text in texts),
                "cost_usd": 0.0,
                "note": "Sentence Transformers runs locally - completely free!"
            }

        # OpenAI pricing
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
            "provider": "openai",
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
            "provider": self.provider,
            "model": self.model,
            "dimension": self.get_embedding_dimension(),
            "batch_size": self.batch_size,
            "is_free": self.provider == "sentence-transformers"
        }

    def __repr__(self) -> str:
        """String representation"""
        return f"EmbeddingService(provider='{self.provider}', model='{self.model}', dimension={self.get_embedding_dimension()})"


def create_embedding_service(
    provider: Optional[EmbeddingProvider] = None,
    model: Optional[str] = None
) -> EmbeddingService:
    """
    Factory function to create embedding service instance.

    Args:
        provider: Embedding provider ("openai" or "sentence-transformers")
        model: Optional model name

    Returns:
        EmbeddingService: Configured embedding service instance
    """
    return EmbeddingService(provider=provider, model=model)