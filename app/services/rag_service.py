"""
RAG (Retrieval-Augmented Generation) Service for Agentic AI Tutor.

Handles:
- Document chunking with metadata
- Embedding generation (via EmbeddingService)
- Vector storage in Pinecone
- Semantic search and retrieval
"""
import logging
import hashlib
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from pinecone import Pinecone, ServerlessSpec
from pinecone.exceptions import PineconeException

from app.core.config import settings
from app.services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


class Document:
    """Represents a document chunk with metadata"""

    def __init__(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        doc_id: Optional[str] = None
    ):
        self.content = content
        self.metadata = metadata or {}
        self.doc_id = doc_id or self._generate_id()

    def _generate_id(self) -> str:
        """Generate unique ID based on content hash"""
        content_hash = hashlib.md5(self.content.encode()).hexdigest()
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        return f"doc_{timestamp}_{content_hash[:8]}"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            "id": self.doc_id,
            "content": self.content,
            "metadata": self.metadata
        }


class RAGService:
    """
    Retrieval-Augmented Generation service using Pinecone vector database.

    Features:
    - Document chunking with overlap
    - Batch embedding and upload
    - Semantic search with metadata filtering
    - Context window management
    """

    def __init__(
        self,
        embedding_service: Optional[EmbeddingService] = None,
        index_name: Optional[str] = None
    ):
        """
        Initialize RAG service.

        Args:
            embedding_service: Optional embedding service instance
            index_name: Optional Pinecone index name (defaults to config)
        """
        # Initialize embedding service
        self.embedding_service = embedding_service or EmbeddingService()

        # Get Pinecone configuration
        self.index_name = index_name or settings.pinecone_index_name
        self.dimension = settings.pinecone_dimension
        self.metric = settings.get("pinecone.metric", "cosine")

        # RAG parameters from config
        self.chunk_size = settings.rag_chunk_size
        self.chunk_overlap = settings.rag_chunk_overlap
        self.top_k = settings.rag_top_k
        self.similarity_threshold = settings.get("rag.similarity_threshold", 0.7)

        # Initialize Pinecone client
        self._init_pinecone()

        logger.info(
            f"RAG service initialized: index={self.index_name}, "
            f"dimension={self.dimension}, chunk_size={self.chunk_size}"
        )

    def _init_pinecone(self):
        """Initialize Pinecone client and connect to index"""
        try:
            # Initialize Pinecone
            api_key = settings.pinecone_api_key
            if not api_key:
                raise ValueError("Pinecone API key not found in settings")

            self.pc = Pinecone(api_key=api_key)

            # Check if index exists
            existing_indexes = self.pc.list_indexes()
            index_names = [idx.name for idx in existing_indexes]

            if self.index_name not in index_names:
                logger.info(f"Index '{self.index_name}' not found. Creating new index...")
                self._create_index()
            else:
                logger.info(f"Connected to existing index '{self.index_name}'")

            # Connect to index
            self.index = self.pc.Index(self.index_name)

            # Get index stats
            stats = self.index.describe_index_stats()
            logger.info(f"Index stats: {stats.total_vector_count} vectors")

        except Exception as e:
            logger.error(f"Failed to initialize Pinecone: {e}")
            raise

    def _create_index(self):
        """Create new Pinecone index"""
        try:
            # Create serverless index (free tier)
            self.pc.create_index(
                name=self.index_name,
                dimension=self.dimension,
                metric=self.metric,
                spec=ServerlessSpec(
                    cloud="aws",
                    region=settings.get("pinecone.environment", "us-east-1")
                )
            )
            logger.info(f"Created new Pinecone index: {self.index_name}")

        except PineconeException as e:
            logger.error(f"Failed to create Pinecone index: {e}")
            raise

    def chunk_text(
        self,
        text: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[Document]:
        """
        Split text into chunks with overlap.

        Args:
            text: Text to chunk
            metadata: Optional metadata to attach to each chunk

        Returns:
            List[Document]: List of document chunks
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for chunking")
            return []

        # Simple word-based chunking (tokens ≈ words for estimation)
        words = text.split()
        chunks = []

        start = 0
        while start < len(words):
            # Get chunk with overlap
            end = start + self.chunk_size
            chunk_words = words[start:end]
            chunk_text = " ".join(chunk_words)

            # Create document with metadata
            chunk_metadata = {
                **(metadata or {}),
                "chunk_index": len(chunks),
                "chunk_start": start,
                "chunk_end": min(end, len(words)),
                "total_words": len(words)
            }

            doc = Document(content=chunk_text, metadata=chunk_metadata)
            chunks.append(doc)

            # Move to next chunk with overlap
            start += (self.chunk_size - self.chunk_overlap)

            # Break if we've covered all text
            if end >= len(words):
                break

        logger.debug(f"Chunked text into {len(chunks)} chunks")
        return chunks

    def upload_documents(
        self,
        documents: List[Document],
        batch_size: int = 100,
        namespace: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Upload documents to Pinecone with embeddings.

        Args:
            documents: List of documents to upload
            batch_size: Batch size for uploads
            namespace: Optional Pinecone namespace

        Returns:
            Dict: Upload statistics
        """
        if not documents:
            logger.warning("No documents provided for upload")
            return {"uploaded": 0, "failed": 0}

        logger.info(f"Uploading {len(documents)} documents to Pinecone...")

        uploaded = 0
        failed = 0

        # Process in batches
        for batch_start in range(0, len(documents), batch_size):
            batch_end = min(batch_start + batch_size, len(documents))
            batch = documents[batch_start:batch_end]

            try:
                # Extract texts for embedding
                texts = [doc.content for doc in batch]

                # Generate embeddings
                embeddings = self.embedding_service.embed_batch(texts)

                # Prepare vectors for upload
                vectors = []
                for doc, embedding in zip(batch, embeddings):
                    if embedding:  # Skip empty embeddings
                        vectors.append({
                            "id": doc.doc_id,
                            "values": embedding,
                            "metadata": {
                                **doc.metadata,
                                "content": doc.content[:1000]  # Store first 1000 chars
                            }
                        })

                # Upload to Pinecone
                if vectors:
                    self.index.upsert(vectors=vectors, namespace=namespace or "")
                    uploaded += len(vectors)
                    logger.debug(f"Uploaded batch {batch_start // batch_size + 1}: {len(vectors)} vectors")

            except Exception as e:
                logger.error(f"Failed to upload batch {batch_start // batch_size + 1}: {e}")
                failed += len(batch)

        logger.info(f"Upload complete: {uploaded} uploaded, {failed} failed")

        return {
            "uploaded": uploaded,
            "failed": failed,
            "total": len(documents)
        }

    def search(
        self,
        query: str,
        top_k: Optional[int] = None,
        metadata_filter: Optional[Dict[str, Any]] = None,
        namespace: Optional[str] = None,
        include_metadata: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Semantic search for relevant documents.

        Args:
            query: Search query
            top_k: Number of results to return (defaults to config)
            metadata_filter: Optional metadata filters
            namespace: Optional Pinecone namespace
            include_metadata: Whether to include metadata in results

        Returns:
            List[Dict]: Search results with scores and content
        """
        if not query or not query.strip():
            logger.warning("Empty query provided for search")
            return []

        top_k = top_k or self.top_k

        try:
            # Generate query embedding
            query_embedding = self.embedding_service.embed_text(query)

            if not query_embedding:
                logger.error("Failed to generate query embedding")
                return []

            # Search Pinecone
            results = self.index.query(
                vector=query_embedding,
                top_k=top_k,
                filter=metadata_filter,
                namespace=namespace or "",
                include_metadata=include_metadata
            )

            # Format results
            formatted_results = []
            for match in results.matches:
                # Filter by similarity threshold
                if match.score < self.similarity_threshold:
                    continue

                result = {
                    "id": match.id,
                    "score": match.score,
                    "content": match.metadata.get("content", "") if include_metadata else "",
                    "metadata": match.metadata if include_metadata else {}
                }
                formatted_results.append(result)

            logger.debug(
                f"Search query: '{query[:50]}...' -> {len(formatted_results)} results "
                f"(threshold: {self.similarity_threshold})"
            )

            return formatted_results

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    def get_context(
        self,
        query: str,
        max_tokens: Optional[int] = None,
        **search_kwargs
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Get contextual information for a query.

        Retrieves relevant documents and combines them into a context string,
        respecting token limits.

        Args:
            query: Search query
            max_tokens: Maximum tokens for context (defaults to config)
            **search_kwargs: Additional arguments for search()

        Returns:
            Tuple[str, List[Dict]]: (context_string, source_documents)
        """
        max_tokens = max_tokens or settings.get("rag.max_context_tokens", 3000)

        # Search for relevant documents
        results = self.search(query, **search_kwargs)

        if not results:
            logger.warning(f"No relevant documents found for query: '{query[:50]}...'")
            return "", []

        # Build context within token limit
        context_parts = []
        total_tokens = 0
        sources = []

        for result in results:
            content = result["content"]

            # Estimate tokens (rough: 1 token ≈ 4 characters)
            content_tokens = len(content) // 4

            if total_tokens + content_tokens > max_tokens:
                break

            context_parts.append(content)
            total_tokens += content_tokens
            sources.append(result)

        context = "\n\n".join(context_parts)

        logger.debug(
            f"Generated context: {len(context_parts)} chunks, "
            f"~{total_tokens} tokens"
        )

        return context, sources

    def delete_all(self, namespace: Optional[str] = None) -> bool:
        """
        Delete all vectors from the index.

        Args:
            namespace: Optional namespace to delete from

        Returns:
            bool: True if successful
        """
        try:
            self.index.delete(delete_all=True, namespace=namespace or "")
            logger.info(f"Deleted all vectors from index '{self.index_name}'")
            return True
        except Exception as e:
            logger.error(f"Failed to delete vectors: {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """Get Pinecone index statistics"""
        try:
            stats = self.index.describe_index_stats()
            return {
                "total_vectors": stats.total_vector_count,
                "dimension": self.dimension,
                "index_fullness": stats.index_fullness,
                "namespaces": stats.namespaces
            }
        except Exception as e:
            logger.error(f"Failed to get index stats: {e}")
            return {}

    def is_available(self) -> bool:
        """Check if RAG service is available"""
        try:
            stats = self.index.describe_index_stats()
            return True
        except Exception:
            return False

    def __repr__(self) -> str:
        """String representation"""
        return (
            f"RAGService(index='{self.index_name}', "
            f"dimension={self.dimension}, "
            f"chunk_size={self.chunk_size})"
        )


def create_rag_service(
    embedding_service: Optional[EmbeddingService] = None,
    index_name: Optional[str] = None
) -> RAGService:
    """
    Factory function to create RAG service instance.

    Args:
        embedding_service: Optional embedding service
        index_name: Optional index name

    Returns:
        RAGService: Configured RAG service instance
    """
    return RAGService(
        embedding_service=embedding_service,
        index_name=index_name
    )
