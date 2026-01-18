"""
Unified Retrieval Service for Agentic AI Tutor.

Combines multiple retrieval sources with citations:
1. User-uploaded documents (RAG via Pinecone)
2. Knowledge Graph enhanced retrieval
3. Web search fallback when documents are insufficient

All responses include proper citations for transparency.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from app.core.config import settings
from app.services.rag_service import get_rag_service
from app.services.hybrid_rag_service import HybridRAGService, RetrievalMethod
from app.services.web_search_service import get_web_search_service, WebSearchResult

logger = logging.getLogger(__name__)


class SourceType(Enum):
    """Types of knowledge sources"""
    DOCUMENT = "document"  # User-uploaded document
    KNOWLEDGE_GRAPH = "knowledge_graph"  # Pre-built educational graph
    WEB = "web"  # Web search results


@dataclass
class Citation:
    """Represents a citation for retrieved information"""
    id: int
    source_type: SourceType
    title: str
    reference: str  # URL or document name
    snippet: str
    relevance_score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "source_type": self.source_type.value,
            "title": self.title,
            "reference": self.reference,
            "snippet": self.snippet[:200] + "..." if len(self.snippet) > 200 else self.snippet,
            "relevance_score": round(self.relevance_score, 3)
        }

    def format_inline(self) -> str:
        """Format as inline citation marker"""
        return f"[{self.id}]"


@dataclass
class RetrievalResponse:
    """Response from unified retrieval with context and citations"""
    context: str
    citations: List[Citation]
    sources_used: List[SourceType]
    has_documents: bool
    used_web_fallback: bool
    query: str
    retrieval_time_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "context": self.context,
            "citations": [c.to_dict() for c in self.citations],
            "sources_used": [s.value for s in self.sources_used],
            "has_documents": self.has_documents,
            "used_web_fallback": self.used_web_fallback,
            "citation_count": len(self.citations)
        }

    def get_citations_text(self) -> str:
        """Generate formatted citations section"""
        if not self.citations:
            return ""

        lines = ["\n\n**Sources:**"]
        for citation in self.citations:
            source_label = {
                SourceType.DOCUMENT: "📄",
                SourceType.KNOWLEDGE_GRAPH: "🔗",
                SourceType.WEB: "🌐"
            }.get(citation.source_type, "📎")

            lines.append(f"{source_label} [{citation.id}] {citation.title}")
            if citation.reference and citation.source_type == SourceType.WEB:
                lines.append(f"   {citation.reference}")

        return "\n".join(lines)


class UnifiedRetrievalService:
    """
    Unified retrieval service that intelligently combines:
    1. User documents (if uploaded)
    2. Knowledge graph context
    3. Web search (fallback when needed)

    All responses include citations for transparency and verifiability.
    """

    def __init__(self):
        """Initialize unified retrieval service"""
        self.rag_service = None
        self.hybrid_rag = None
        self.web_search = None

        # Lazy initialization flags
        self._rag_initialized = False
        self._hybrid_initialized = False
        self._web_initialized = False

        # Configuration
        self.min_document_results = settings.get("retrieval.min_results", 2)
        self.enable_web_fallback = settings.get("retrieval.enable_web_fallback", True)
        self.web_result_limit = settings.get("retrieval.web_result_limit", 3)

        logger.info("Unified retrieval service initialized")

    def _init_rag(self):
        """Lazy initialize RAG service"""
        if not self._rag_initialized:
            try:
                self.rag_service = get_rag_service()
                self._rag_initialized = True
            except Exception as e:
                logger.warning(f"RAG service initialization failed: {e}")
                self._rag_initialized = False

    def _init_hybrid(self):
        """Lazy initialize hybrid RAG"""
        if not self._hybrid_initialized:
            try:
                self.hybrid_rag = HybridRAGService()
                self._hybrid_initialized = True
            except Exception as e:
                logger.warning(f"Hybrid RAG initialization failed: {e}")
                self._hybrid_initialized = False

    def _init_web(self):
        """Lazy initialize web search"""
        if not self._web_initialized:
            try:
                self.web_search = get_web_search_service()
                self._web_initialized = True
            except Exception as e:
                logger.warning(f"Web search initialization failed: {e}")
                self._web_initialized = False

    def retrieve(
        self,
        query: str,
        student_id: Optional[str] = None,
        topic: Optional[str] = None,
        include_web: bool = True,
        max_results: int = 5
    ) -> RetrievalResponse:
        """
        Retrieve relevant information from all available sources.

        Strategy:
        1. First, try user's uploaded documents (if student_id provided)
        2. Add knowledge graph context for the topic
        3. If insufficient results, fall back to web search

        Args:
            query: User's question or search query
            student_id: Optional student ID for personalized documents
            topic: Optional topic for knowledge graph enhancement
            include_web: Whether to use web fallback
            max_results: Maximum total results

        Returns:
            RetrievalResponse with context and citations
        """
        import time
        start_time = time.time()

        citations = []
        context_parts = []
        sources_used = []
        citation_id = 1
        has_documents = False
        used_web_fallback = False

        # Step 1: Try document retrieval
        self._init_rag()
        if self.rag_service:
            doc_results = self._retrieve_from_documents(query, student_id, max_results)
            if doc_results:
                has_documents = True
                sources_used.append(SourceType.DOCUMENT)
                for result in doc_results:
                    citation = Citation(
                        id=citation_id,
                        source_type=SourceType.DOCUMENT,
                        title=result.get("metadata", {}).get("filename", "Uploaded Document"),
                        reference=result.get("metadata", {}).get("filename", "document"),
                        snippet=result.get("content", ""),
                        relevance_score=result.get("score", 0),
                        metadata=result.get("metadata", {})
                    )
                    citations.append(citation)
                    context_parts.append(f"{result.get('content', '')} [{citation_id}]")
                    citation_id += 1

        # Step 2: Add knowledge graph context if topic specified
        self._init_hybrid()
        if self.hybrid_rag and topic:
            kg_context = self._get_knowledge_graph_context(topic)
            if kg_context:
                sources_used.append(SourceType.KNOWLEDGE_GRAPH)
                citation = Citation(
                    id=citation_id,
                    source_type=SourceType.KNOWLEDGE_GRAPH,
                    title=f"Knowledge Graph: {topic}",
                    reference="internal_knowledge_graph",
                    snippet=kg_context,
                    relevance_score=0.8
                )
                citations.append(citation)
                context_parts.append(f"{kg_context} [{citation_id}]")
                citation_id += 1

        # Step 3: Web fallback if needed
        if include_web and self.enable_web_fallback:
            need_web = len(citations) < self.min_document_results
            if need_web:
                self._init_web()
                if self.web_search:
                    web_context, web_citations = self.web_search.get_context_from_web(
                        query, self.web_result_limit
                    )
                    if web_citations:
                        used_web_fallback = True
                        sources_used.append(SourceType.WEB)
                        for web_cite in web_citations:
                            citation = Citation(
                                id=citation_id,
                                source_type=SourceType.WEB,
                                title=web_cite["title"],
                                reference=web_cite["url"],
                                snippet=web_context.split(f"[{web_cite['id']}]")[0].split("\n\n")[-1] if f"[{web_cite['id']}]" in web_context else "",
                                relevance_score=0.7,
                                metadata={"source": web_cite.get("source", "web")}
                            )
                            citations.append(citation)
                            citation_id += 1
                        context_parts.append(web_context)

        # Combine context
        context = "\n\n".join(context_parts) if context_parts else ""

        retrieval_time = (time.time() - start_time) * 1000

        return RetrievalResponse(
            context=context,
            citations=citations,
            sources_used=list(set(sources_used)),
            has_documents=has_documents,
            used_web_fallback=used_web_fallback,
            query=query,
            retrieval_time_ms=retrieval_time
        )

    def _retrieve_from_documents(
        self,
        query: str,
        student_id: Optional[str],
        max_results: int
    ) -> List[Dict[str, Any]]:
        """Retrieve from user's uploaded documents"""
        try:
            metadata_filter = {"student_id": student_id} if student_id else None
            results = self.rag_service.search(
                query,
                top_k=max_results,
                metadata_filter=metadata_filter,
                include_metadata=True
            )
            return results
        except Exception as e:
            logger.error(f"Document retrieval failed: {e}")
            return []

    def _get_knowledge_graph_context(self, topic: str) -> str:
        """Get context from knowledge graph"""
        try:
            kg = self.hybrid_rag.knowledge_graph
            related = kg.get_related_topics(topic, max_depth=2)
            prerequisites = kg.get_prerequisites(topic)

            if not related and not prerequisites:
                return ""

            parts = []
            if prerequisites:
                parts.append(f"Prerequisites for {topic}: {', '.join(prerequisites[:3])}")
            if related:
                related_names = [r[0] for r in related[:5]]
                parts.append(f"Related concepts: {', '.join(related_names)}")

            return ". ".join(parts)
        except Exception as e:
            logger.error(f"Knowledge graph context failed: {e}")
            return ""

    def check_has_documents(self, student_id: str) -> bool:
        """Check if student has uploaded documents"""
        try:
            self._init_rag()
            if not self.rag_service:
                return False

            # Try a simple search to check for documents
            results = self.rag_service.search(
                "test",
                top_k=1,
                metadata_filter={"student_id": student_id}
            )
            return len(results) > 0
        except Exception:
            return False


# Singleton instance
_unified_retrieval: Optional[UnifiedRetrievalService] = None


def get_unified_retrieval_service() -> UnifiedRetrievalService:
    """Get or create singleton unified retrieval service"""
    global _unified_retrieval
    if _unified_retrieval is None:
        _unified_retrieval = UnifiedRetrievalService()
    return _unified_retrieval
