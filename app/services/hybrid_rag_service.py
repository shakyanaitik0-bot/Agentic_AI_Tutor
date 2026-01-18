"""
Hybrid RAG Service for Agentic AI Tutor.

Production-grade retrieval system combining:
1. Dense Retrieval: Semantic search via Pinecone + Sentence Transformers
2. Sparse Retrieval: BM25 keyword matching for exact terms
3. Knowledge Graph: Topic relationships and prerequisites
4. Cross-Encoder Re-ranking: Quality scoring of retrieved results

This implementation follows industry best practices for production RAG systems.
"""

import logging
import hashlib
import pickle
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

import networkx as nx
from rank_bm25 import BM25Okapi
from cachetools import TTLCache, LRUCache

from app.core.config import settings
from app.services.rag_service import RAGService

logger = logging.getLogger(__name__)


class RetrievalMethod(Enum):
    """Retrieval methods for hybrid search"""

    DENSE = "dense"  # Vector similarity (semantic)
    SPARSE = "sparse"  # BM25 keyword matching
    HYBRID = "hybrid"  # Combined dense + sparse
    GRAPH_ENHANCED = "graph"  # Hybrid + knowledge graph


@dataclass
class RetrievalResult:
    """Represents a single retrieval result with metadata"""

    doc_id: str
    content: str
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    retrieval_method: str = "unknown"
    dense_score: float = 0.0
    sparse_score: float = 0.0
    rerank_score: float = 0.0
    graph_boost: float = 0.0


@dataclass
class KnowledgeNode:
    """Represents a topic/concept in the knowledge graph"""

    topic: str
    subtopics: List[str] = field(default_factory=list)
    prerequisites: List[str] = field(default_factory=list)
    related_topics: List[str] = field(default_factory=list)
    difficulty_level: str = "medium"
    exam_types: List[str] = field(default_factory=list)


class EducationKnowledgeGraph:
    """
    Knowledge Graph for educational content relationships.

    Tracks:
    - Topic prerequisites (Calculus requires Algebra)
    - Related concepts (Derivatives related to Rate of Change)
    - Topic hierarchy (Physics > Mechanics > Kinematics)
    - Cross-subject connections (Math in Physics)
    """

    def __init__(self, persist_path: Optional[str] = None):
        """
        Initialize knowledge graph.

        Args:
            persist_path: Optional path to persist graph to disk
        """
        self.graph = nx.DiGraph()
        self.persist_path = persist_path or "data/knowledge_graph.gpickle"

        # Initialize with educational domain knowledge
        self._initialize_base_knowledge()

        # Try to load persisted graph
        self._load_graph()

        logger.info(
            f"Knowledge graph initialized: {self.graph.number_of_nodes()} nodes, {self.graph.number_of_edges()} edges"
        )

    def _initialize_base_knowledge(self):
        """Initialize with foundational educational relationships"""

        # Mathematics hierarchy
        math_topics = {
            "Mathematics": {
                "subtopics": [
                    "Algebra",
                    "Calculus",
                    "Geometry",
                    "Trigonometry",
                    "Statistics",
                    "Probability",
                ],
                "exam_types": ["JEE", "SAT", "GRE"],
            },
            "Algebra": {
                "subtopics": [
                    "Linear Equations",
                    "Quadratic Equations",
                    "Polynomials",
                    "Inequalities",
                ],
                "prerequisites": [],
                "exam_types": ["JEE", "SAT", "GRE"],
            },
            "Calculus": {
                "subtopics": ["Limits", "Derivatives", "Integrals", "Differential Equations"],
                "prerequisites": ["Algebra", "Trigonometry"],
                "exam_types": ["JEE", "GRE"],
            },
            "Derivatives": {
                "subtopics": [
                    "Chain Rule",
                    "Product Rule",
                    "Quotient Rule",
                    "Implicit Differentiation",
                ],
                "prerequisites": ["Limits", "Algebra"],
                "related": ["Rate of Change", "Slope", "Tangent Lines"],
                "exam_types": ["JEE", "GRE"],
            },
            "Integrals": {
                "subtopics": [
                    "Definite Integrals",
                    "Indefinite Integrals",
                    "Integration Techniques",
                ],
                "prerequisites": ["Derivatives"],
                "related": ["Area Under Curve", "Accumulation"],
                "exam_types": ["JEE", "GRE"],
            },
            "Probability": {
                "subtopics": [
                    "Conditional Probability",
                    "Bayes Theorem",
                    "Random Variables",
                    "Distributions",
                ],
                "prerequisites": ["Algebra", "Statistics"],
                "exam_types": ["JEE", "SAT", "GRE"],
            },
            "Statistics": {
                "subtopics": ["Mean", "Median", "Mode", "Standard Deviation", "Variance"],
                "prerequisites": ["Algebra"],
                "exam_types": ["SAT", "GRE"],
            },
            "Trigonometry": {
                "subtopics": ["Sine", "Cosine", "Tangent", "Identities", "Inverse Trig"],
                "prerequisites": ["Algebra", "Geometry"],
                "exam_types": ["JEE", "SAT"],
            },
            "Geometry": {
                "subtopics": ["Triangles", "Circles", "Coordinate Geometry", "3D Geometry"],
                "prerequisites": ["Algebra"],
                "exam_types": ["JEE", "SAT", "GRE"],
            },
        }

        # Physics hierarchy
        physics_topics = {
            "Physics": {
                "subtopics": [
                    "Mechanics",
                    "Thermodynamics",
                    "Electromagnetism",
                    "Optics",
                    "Modern Physics",
                ],
                "exam_types": ["JEE"],
            },
            "Mechanics": {
                "subtopics": ["Kinematics", "Dynamics", "Work Energy Power", "Rotational Motion"],
                "prerequisites": ["Calculus", "Trigonometry"],
                "exam_types": ["JEE"],
            },
            "Kinematics": {
                "subtopics": [
                    "Motion in 1D",
                    "Motion in 2D",
                    "Projectile Motion",
                    "Relative Motion",
                ],
                "prerequisites": ["Algebra", "Calculus"],
                "related": ["Derivatives", "Integrals"],
                "exam_types": ["JEE"],
            },
            "Thermodynamics": {
                "subtopics": ["Laws of Thermodynamics", "Heat Transfer", "Entropy"],
                "prerequisites": ["Calculus"],
                "exam_types": ["JEE"],
            },
            "Electromagnetism": {
                "subtopics": ["Electrostatics", "Current Electricity", "Magnetism", "EMI"],
                "prerequisites": ["Calculus", "Mechanics"],
                "exam_types": ["JEE"],
            },
        }

        # Chemistry hierarchy
        chemistry_topics = {
            "Chemistry": {
                "subtopics": ["Physical Chemistry", "Organic Chemistry", "Inorganic Chemistry"],
                "exam_types": ["JEE"],
            },
            "Physical Chemistry": {
                "subtopics": [
                    "Atomic Structure",
                    "Chemical Bonding",
                    "Thermodynamics",
                    "Equilibrium",
                ],
                "prerequisites": ["Mathematics"],
                "exam_types": ["JEE"],
            },
            "Organic Chemistry": {
                "subtopics": ["Hydrocarbons", "Functional Groups", "Reactions", "Stereochemistry"],
                "prerequisites": ["Chemical Bonding"],
                "exam_types": ["JEE"],
            },
        }

        # GRE-specific topics
        gre_topics = {
            "Verbal Reasoning": {
                "subtopics": ["Reading Comprehension", "Text Completion", "Sentence Equivalence"],
                "exam_types": ["GRE"],
            },
            "Quantitative Reasoning": {
                "subtopics": ["Arithmetic", "Algebra", "Geometry", "Data Analysis"],
                "prerequisites": ["Mathematics"],
                "exam_types": ["GRE"],
            },
            "Analytical Writing": {
                "subtopics": ["Issue Task", "Argument Task"],
                "exam_types": ["GRE"],
            },
        }

        # SAT-specific topics
        sat_topics = {
            "SAT Math": {
                "subtopics": ["Heart of Algebra", "Problem Solving", "Passport to Advanced Math"],
                "prerequisites": ["Algebra"],
                "exam_types": ["SAT"],
            },
            "SAT Reading": {
                "subtopics": ["Evidence-Based Reading", "Vocabulary in Context"],
                "exam_types": ["SAT"],
            },
            "SAT Writing": {"subtopics": ["Grammar", "Expression of Ideas"], "exam_types": ["SAT"]},
        }

        # Combine all topics
        all_topics = {
            **math_topics,
            **physics_topics,
            **chemistry_topics,
            **gre_topics,
            **sat_topics,
        }

        # Add nodes and edges to graph
        for topic, data in all_topics.items():
            self.graph.add_node(topic, **data)

            # Add prerequisite edges
            for prereq in data.get("prerequisites", []):
                self.graph.add_edge(prereq, topic, relationship="prerequisite_for")

            # Add subtopic edges
            for subtopic in data.get("subtopics", []):
                self.graph.add_edge(topic, subtopic, relationship="contains")

            # Add related topic edges (bidirectional)
            for related in data.get("related", []):
                self.graph.add_edge(topic, related, relationship="related_to")
                self.graph.add_edge(related, topic, relationship="related_to")

    def add_topic(self, node: KnowledgeNode):
        """Add a new topic to the knowledge graph"""
        self.graph.add_node(
            node.topic,
            subtopics=node.subtopics,
            prerequisites=node.prerequisites,
            related_topics=node.related_topics,
            difficulty_level=node.difficulty_level,
            exam_types=node.exam_types,
        )

        # Add edges
        for prereq in node.prerequisites:
            if prereq in self.graph:
                self.graph.add_edge(prereq, node.topic, relationship="prerequisite_for")

        for related in node.related_topics:
            if related in self.graph:
                self.graph.add_edge(node.topic, related, relationship="related_to")

        self._save_graph()

    def get_related_topics(self, topic: str, max_depth: int = 2) -> List[Tuple[str, float]]:
        """
        Get related topics with relevance scores.

        Args:
            topic: Starting topic
            max_depth: Maximum graph traversal depth

        Returns:
            List of (topic, relevance_score) tuples
        """
        if topic not in self.graph:
            # Try case-insensitive match
            topic_lower = topic.lower()
            for node in self.graph.nodes():
                if node.lower() == topic_lower:
                    topic = node
                    break
            else:
                return []

        related = []
        visited = set()

        def traverse(current: str, depth: int, score: float):
            if depth > max_depth or current in visited:
                return
            visited.add(current)

            if current != topic:
                related.append((current, score))

            # Traverse neighbors with decaying score
            for neighbor in self.graph.neighbors(current):
                edge_data = self.graph.get_edge_data(current, neighbor)
                relationship = edge_data.get("relationship", "related_to")

                # Score based on relationship type
                decay = {"prerequisite_for": 0.8, "contains": 0.9, "related_to": 0.7}.get(
                    relationship, 0.5
                )

                traverse(neighbor, depth + 1, score * decay)

            # Also traverse predecessors
            for predecessor in self.graph.predecessors(current):
                edge_data = self.graph.get_edge_data(predecessor, current)
                relationship = edge_data.get("relationship", "related_to")

                decay = {
                    "prerequisite_for": 0.6,  # Prerequisites are less directly related
                    "contains": 0.8,
                    "related_to": 0.7,
                }.get(relationship, 0.5)

                traverse(predecessor, depth + 1, score * decay)

        traverse(topic, 0, 1.0)

        # Sort by relevance score
        related.sort(key=lambda x: x[1], reverse=True)
        return related[:10]  # Top 10 related topics

    def get_prerequisites(self, topic: str) -> List[str]:
        """Get all prerequisites for a topic (transitive)"""
        if topic not in self.graph:
            return []

        prerequisites = set()

        def find_prereqs(current: str):
            for predecessor in self.graph.predecessors(current):
                edge_data = self.graph.get_edge_data(predecessor, current)
                if edge_data.get("relationship") == "prerequisite_for":
                    if predecessor not in prerequisites:
                        prerequisites.add(predecessor)
                        find_prereqs(predecessor)

        find_prereqs(topic)
        return list(prerequisites)

    def get_learning_path(self, from_topic: str, to_topic: str) -> List[str]:
        """Get recommended learning path between two topics"""
        try:
            path = nx.shortest_path(self.graph, from_topic, to_topic)
            return path
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return []

    def get_topics_for_exam(self, exam_type: str) -> List[str]:
        """Get all topics relevant to an exam type"""
        topics = []
        for node, data in self.graph.nodes(data=True):
            if exam_type in data.get("exam_types", []):
                topics.append(node)
        return topics

    def _save_graph(self):
        """Persist graph to disk"""
        try:
            path = Path(self.persist_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "wb") as f:
                pickle.dump(self.graph, f)
            logger.debug(f"Knowledge graph saved to {self.persist_path}")
        except Exception as e:
            logger.warning(f"Failed to save knowledge graph: {e}")

    def _load_graph(self):
        """Load persisted graph from disk"""
        try:
            path = Path(self.persist_path)
            if path.exists():
                with open(path, "rb") as f:
                    loaded_graph = pickle.load(f)
                    # Merge with base knowledge
                    self.graph = nx.compose(self.graph, loaded_graph)
                logger.info(f"Loaded knowledge graph from {self.persist_path}")
        except Exception as e:
            logger.warning(f"Failed to load knowledge graph: {e}")


class BM25Index:
    """
    BM25 sparse retrieval index for keyword matching.

    Complements dense retrieval by handling:
    - Exact term matches
    - Technical vocabulary
    - Acronyms and abbreviations
    """

    def __init__(self):
        """Initialize BM25 index"""
        self.documents: List[Dict[str, Any]] = []
        self.corpus: List[List[str]] = []
        self.bm25: Optional[BM25Okapi] = None
        self.doc_id_to_idx: Dict[str, int] = {}

    def add_documents(self, documents: List[Dict[str, Any]]):
        """
        Add documents to the BM25 index.

        Args:
            documents: List of documents with 'id', 'content', 'metadata' keys
        """
        for doc in documents:
            if doc["id"] not in self.doc_id_to_idx:
                idx = len(self.documents)
                self.documents.append(doc)
                self.doc_id_to_idx[doc["id"]] = idx

                # Tokenize content for BM25
                tokens = self._tokenize(doc["content"])
                self.corpus.append(tokens)

        # Rebuild BM25 index
        if self.corpus:
            self.bm25 = BM25Okapi(self.corpus)
            logger.debug(f"BM25 index rebuilt with {len(self.documents)} documents")

    def search(self, query: str, top_k: int = 10) -> List[Tuple[str, float]]:
        """
        Search documents using BM25.

        Args:
            query: Search query
            top_k: Number of results to return

        Returns:
            List of (doc_id, score) tuples
        """
        if not self.bm25 or not self.corpus:
            return []

        query_tokens = self._tokenize(query)
        scores = self.bm25.get_scores(query_tokens)

        # Get top-k indices
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]

        results = []
        for idx in top_indices:
            if scores[idx] > 0:  # Only include non-zero scores
                doc_id = self.documents[idx]["id"]
                results.append((doc_id, scores[idx]))

        return results

    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenization for BM25"""
        # Lowercase and split on non-alphanumeric
        import re

        tokens = re.findall(r"\b\w+\b", text.lower())
        # Remove very short tokens and stopwords
        stopwords = {
            "the",
            "a",
            "an",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "being",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "could",
            "should",
            "may",
            "might",
            "must",
            "shall",
            "can",
            "need",
            "dare",
            "to",
            "of",
            "in",
            "for",
            "on",
            "with",
            "at",
            "by",
            "from",
            "as",
            "into",
            "through",
            "during",
            "before",
            "after",
            "above",
            "below",
            "between",
            "under",
            "again",
            "further",
            "then",
            "once",
            "here",
            "there",
            "when",
            "where",
            "why",
            "how",
            "all",
            "each",
            "few",
            "more",
            "most",
            "other",
            "some",
            "such",
            "no",
            "nor",
            "not",
            "only",
            "own",
            "same",
            "so",
            "than",
            "too",
            "very",
            "just",
            "and",
            "but",
            "if",
            "or",
            "because",
            "until",
            "while",
            "this",
            "that",
            "these",
            "those",
            "it",
        }
        return [t for t in tokens if len(t) > 2 and t not in stopwords]


class CrossEncoderReranker:
    """
    Cross-encoder model for re-ranking retrieval results.

    Uses a small, efficient cross-encoder model that runs locally (free).
    Significantly improves retrieval quality by scoring query-document pairs.
    """

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        """
        Initialize cross-encoder reranker.

        Args:
            model_name: HuggingFace model name (default is small and fast)
        """
        self.model_name = model_name
        self.model = None
        self._initialized = False

    def _lazy_init(self):
        """Lazy initialization to avoid loading model until needed"""
        if self._initialized:
            return

        try:
            from sentence_transformers import CrossEncoder

            self.model = CrossEncoder(self.model_name, max_length=512)
            self._initialized = True
            logger.info(f"Cross-encoder reranker initialized: {self.model_name}")
        except Exception as e:
            logger.warning(f"Failed to initialize cross-encoder: {e}. Re-ranking disabled.")
            self._initialized = True  # Don't retry

    def rerank(
        self, query: str, documents: List[Dict[str, Any]], top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Re-rank documents using cross-encoder.

        Args:
            query: Search query
            documents: List of documents with 'content' key
            top_k: Number of results to return

        Returns:
            Re-ranked documents with 'rerank_score' added
        """
        self._lazy_init()

        if not self.model or not documents:
            return documents[:top_k]

        try:
            # Create query-document pairs
            pairs = [(query, doc.get("content", "")) for doc in documents]

            # Get cross-encoder scores
            scores = self.model.predict(pairs)

            # Add scores to documents
            for doc, score in zip(documents, scores):
                doc["rerank_score"] = float(score)

            # Sort by rerank score
            documents.sort(key=lambda x: x.get("rerank_score", 0), reverse=True)

            return documents[:top_k]

        except Exception as e:
            logger.warning(f"Re-ranking failed: {e}")
            return documents[:top_k]


class HybridRAGService:
    """
    Production-grade Hybrid RAG Service.

    Combines multiple retrieval strategies:
    1. Dense Retrieval (Pinecone + embeddings)
    2. Sparse Retrieval (BM25)
    3. Knowledge Graph Enhancement
    4. Cross-Encoder Re-ranking

    Uses Reciprocal Rank Fusion (RRF) to combine results.
    """

    def __init__(
        self,
        rag_service: Optional[RAGService] = None,
        enable_bm25: bool = True,
        enable_knowledge_graph: bool = True,
        enable_reranking: bool = True,
    ):
        """
        Initialize Hybrid RAG Service.

        Args:
            rag_service: Base RAG service for dense retrieval
            enable_bm25: Enable BM25 sparse retrieval
            enable_knowledge_graph: Enable knowledge graph enhancement
            enable_reranking: Enable cross-encoder re-ranking
        """
        # Initialize dense retrieval (Pinecone)
        self.rag_service = rag_service
        self._rag_initialized = False

        # Initialize sparse retrieval (BM25)
        self.enable_bm25 = enable_bm25
        self.bm25_index = BM25Index() if enable_bm25 else None

        # Initialize knowledge graph
        self.enable_knowledge_graph = enable_knowledge_graph
        self.knowledge_graph = EducationKnowledgeGraph() if enable_knowledge_graph else None

        # Initialize re-ranker
        self.enable_reranking = enable_reranking
        self.reranker = CrossEncoderReranker() if enable_reranking else None

        # Caching
        self.query_cache = TTLCache(maxsize=1000, ttl=3600)  # 1 hour TTL
        self.embedding_cache = LRUCache(maxsize=5000)

        # Configuration
        self.dense_weight = settings.get("hybrid_rag.dense_weight", 0.5)
        self.sparse_weight = settings.get("hybrid_rag.sparse_weight", 0.3)
        self.graph_weight = settings.get("hybrid_rag.graph_weight", 0.2)
        self.rrf_k = settings.get("hybrid_rag.rrf_k", 60)  # RRF constant

        logger.info(
            f"Hybrid RAG initialized: bm25={enable_bm25}, "
            f"knowledge_graph={enable_knowledge_graph}, reranking={enable_reranking}"
        )

    def _ensure_rag_service(self):
        """Lazy initialization of RAG service"""
        if not self._rag_initialized:
            if self.rag_service is None:
                from app.services.rag_service import get_rag_service

                self.rag_service = get_rag_service()
            self._rag_initialized = True

    def add_documents(
        self, documents: List[Dict[str, Any]], metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Add documents to all indices (dense + sparse).

        Args:
            documents: List of documents with 'text' and 'metadata'
            metadata: Additional metadata to add to all documents

        Returns:
            Statistics about the upload
        """
        self._ensure_rag_service()

        stats = {"dense_uploaded": 0, "sparse_indexed": 0, "errors": []}

        # Prepare documents
        prepared_docs = []
        for doc in documents:
            doc_id = doc.get("id") or hashlib.md5(doc["text"].encode()).hexdigest()
            prepared = {
                "id": doc_id,
                "content": doc["text"],
                "metadata": {**doc.get("metadata", {}), **(metadata or {})},
            }
            prepared_docs.append(prepared)

        # Upload to dense index (Pinecone)
        try:
            result = self.rag_service.add_documents(documents, metadata)
            stats["dense_uploaded"] = result.get("uploaded", 0)
        except Exception as e:
            logger.error(f"Dense index upload failed: {e}")
            stats["errors"].append(f"Dense upload: {str(e)}")

        # Add to BM25 index
        if self.bm25_index:
            try:
                self.bm25_index.add_documents(prepared_docs)
                stats["sparse_indexed"] = len(prepared_docs)
            except Exception as e:
                logger.error(f"BM25 index update failed: {e}")
                stats["errors"].append(f"BM25 index: {str(e)}")

        return stats

    def search(
        self,
        query: str,
        top_k: int = 5,
        method: RetrievalMethod = RetrievalMethod.HYBRID,
        metadata_filter: Optional[Dict[str, Any]] = None,
        exam_type: Optional[str] = None,
        topic_hint: Optional[str] = None,
        use_cache: bool = True,
    ) -> List[RetrievalResult]:
        """
        Hybrid search combining multiple retrieval strategies.

        Args:
            query: Search query
            top_k: Number of results to return
            method: Retrieval method to use
            metadata_filter: Filter for dense retrieval
            exam_type: Optional exam type for graph filtering
            topic_hint: Optional topic for graph enhancement
            use_cache: Whether to use query cache

        Returns:
            List of RetrievalResult objects
        """
        self._ensure_rag_service()

        # Check cache
        cache_key = f"{query}:{top_k}:{method.value}:{metadata_filter}:{topic_hint}"
        if use_cache and cache_key in self.query_cache:
            logger.debug(f"Cache hit for query: {query[:50]}...")
            return self.query_cache[cache_key]

        results: Dict[str, RetrievalResult] = {}

        # 1. Dense Retrieval (Pinecone)
        if method in [
            RetrievalMethod.DENSE,
            RetrievalMethod.HYBRID,
            RetrievalMethod.GRAPH_ENHANCED,
        ]:
            dense_results = self._dense_search(query, top_k * 2, metadata_filter)
            for rank, result in enumerate(dense_results):
                doc_id = result["id"]
                if doc_id not in results:
                    results[doc_id] = RetrievalResult(
                        doc_id=doc_id,
                        content=result.get("content", ""),
                        score=0.0,
                        metadata=result.get("metadata", {}),
                        retrieval_method="dense",
                    )
                results[doc_id].dense_score = result.get("score", 0.0)

        # 2. Sparse Retrieval (BM25)
        if method in [
            RetrievalMethod.SPARSE,
            RetrievalMethod.HYBRID,
            RetrievalMethod.GRAPH_ENHANCED,
        ]:
            if self.bm25_index:
                sparse_results = self.bm25_index.search(query, top_k * 2)
                for rank, (doc_id, score) in enumerate(sparse_results):
                    if doc_id not in results:
                        # Get content from BM25 index
                        doc_idx = self.bm25_index.doc_id_to_idx.get(doc_id)
                        if doc_idx is not None:
                            doc = self.bm25_index.documents[doc_idx]
                            results[doc_id] = RetrievalResult(
                                doc_id=doc_id,
                                content=doc.get("content", ""),
                                score=0.0,
                                metadata=doc.get("metadata", {}),
                                retrieval_method="sparse",
                            )
                    if doc_id in results:
                        results[doc_id].sparse_score = score

        # 3. Knowledge Graph Enhancement
        if method == RetrievalMethod.GRAPH_ENHANCED and self.knowledge_graph:
            graph_boost = self._get_graph_boost(query, topic_hint, exam_type)
            for doc_id, result in results.items():
                # Check if document topic matches related topics
                doc_topic = result.metadata.get("topic", "").lower()
                for related_topic, relevance in graph_boost:
                    if related_topic.lower() in doc_topic or doc_topic in related_topic.lower():
                        result.graph_boost = max(result.graph_boost, relevance * 0.5)

        # 4. Reciprocal Rank Fusion
        final_results = self._reciprocal_rank_fusion(list(results.values()))

        # 5. Re-ranking (if enabled)
        if self.enable_reranking and self.reranker and len(final_results) > 0:
            docs_for_rerank = [
                {"id": r.doc_id, "content": r.content, "score": r.score, "metadata": r.metadata}
                for r in final_results[: top_k * 2]
            ]
            reranked = self.reranker.rerank(query, docs_for_rerank, top_k)

            # Update scores
            reranked_ids = {d["id"]: d.get("rerank_score", 0) for d in reranked}
            for result in final_results:
                if result.doc_id in reranked_ids:
                    result.rerank_score = reranked_ids[result.doc_id]
                    # Boost final score with rerank score
                    result.score = (result.score + result.rerank_score) / 2

            # Re-sort by combined score
            final_results.sort(key=lambda x: x.score, reverse=True)

        # Limit to top_k
        final_results = final_results[:top_k]

        # Cache results
        if use_cache:
            self.query_cache[cache_key] = final_results

        logger.info(
            f"Hybrid search: query='{query[:50]}...', method={method.value}, results={len(final_results)}"
        )
        return final_results

    def _dense_search(
        self, query: str, top_k: int, metadata_filter: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Perform dense (vector) search"""
        try:
            return self.rag_service.search(
                query=query, top_k=top_k, metadata_filter=metadata_filter
            )
        except Exception as e:
            logger.error(f"Dense search failed: {e}")
            return []

    def _get_graph_boost(
        self, query: str, topic_hint: Optional[str], exam_type: Optional[str]
    ) -> List[Tuple[str, float]]:
        """Get relevance boost from knowledge graph"""
        if not self.knowledge_graph:
            return []

        # Extract potential topics from query
        query_topics = []
        if topic_hint:
            query_topics.append(topic_hint)

        # Check query against known topics
        query_lower = query.lower()
        for node in self.knowledge_graph.graph.nodes():
            if node.lower() in query_lower:
                query_topics.append(node)

        # Get related topics
        all_related = []
        for topic in query_topics[:3]:  # Limit to avoid explosion
            related = self.knowledge_graph.get_related_topics(topic, max_depth=2)
            all_related.extend(related)

        # Filter by exam type if provided
        if exam_type and all_related:
            exam_topics = set(self.knowledge_graph.get_topics_for_exam(exam_type))
            all_related = [(t, s) for t, s in all_related if t in exam_topics]

        return all_related

    def _reciprocal_rank_fusion(self, results: List[RetrievalResult]) -> List[RetrievalResult]:
        """
        Combine results using Reciprocal Rank Fusion (RRF).

        RRF score = sum(1 / (k + rank_i)) for each retrieval method
        """
        # Rank by each score type
        dense_ranked = sorted(results, key=lambda x: x.dense_score, reverse=True)
        sparse_ranked = sorted(results, key=lambda x: x.sparse_score, reverse=True)

        # Calculate RRF scores
        for i, result in enumerate(dense_ranked):
            result.score += self.dense_weight * (1.0 / (self.rrf_k + i + 1))

        for i, result in enumerate(sparse_ranked):
            result.score += self.sparse_weight * (1.0 / (self.rrf_k + i + 1))

        # Add graph boost
        for result in results:
            result.score += self.graph_weight * result.graph_boost

        # Sort by final score
        results.sort(key=lambda x: x.score, reverse=True)
        return results

    def get_context(
        self,
        query: str,
        max_tokens: int = 3000,
        method: RetrievalMethod = RetrievalMethod.HYBRID,
        **search_kwargs,
    ) -> Tuple[str, List[RetrievalResult]]:
        """
        Get contextual information for a query.

        Args:
            query: Search query
            max_tokens: Maximum tokens for context
            method: Retrieval method
            **search_kwargs: Additional search arguments

        Returns:
            Tuple of (context_string, source_results)
        """
        results = self.search(query, top_k=10, method=method, **search_kwargs)

        if not results:
            return "", []

        # Build context within token limit
        context_parts = []
        total_tokens = 0
        used_results = []

        for result in results:
            # Estimate tokens
            content_tokens = len(result.content) // 4

            if total_tokens + content_tokens > max_tokens:
                break

            context_parts.append(result.content)
            total_tokens += content_tokens
            used_results.append(result)

        context = "\n\n---\n\n".join(context_parts)
        return context, used_results

    def get_stats(self) -> Dict[str, Any]:
        """Get service statistics"""
        stats = {
            "bm25_enabled": self.enable_bm25,
            "knowledge_graph_enabled": self.enable_knowledge_graph,
            "reranking_enabled": self.enable_reranking,
            "cache_size": len(self.query_cache),
            "cache_hits": getattr(self.query_cache, "hits", 0),
            "cache_misses": getattr(self.query_cache, "misses", 0),
        }

        if self.bm25_index:
            stats["bm25_documents"] = len(self.bm25_index.documents)

        if self.knowledge_graph:
            stats["knowledge_graph_nodes"] = self.knowledge_graph.graph.number_of_nodes()
            stats["knowledge_graph_edges"] = self.knowledge_graph.graph.number_of_edges()

        if self._rag_initialized and self.rag_service:
            try:
                pinecone_stats = self.rag_service.get_stats()
                stats["pinecone_vectors"] = pinecone_stats.get("total_vectors", 0)
            except:
                pass

        return stats


# Global singleton instance
_hybrid_rag_instance: Optional[HybridRAGService] = None


def get_hybrid_rag_service() -> HybridRAGService:
    """Get or create singleton Hybrid RAG service"""
    global _hybrid_rag_instance

    if _hybrid_rag_instance is None:
        _hybrid_rag_instance = HybridRAGService()

    return _hybrid_rag_instance
