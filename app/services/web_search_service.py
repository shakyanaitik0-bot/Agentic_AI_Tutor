"""
Web Search Service for Agentic AI Tutor.

Provides web search capabilities when:
1. User hasn't uploaded documents
2. RAG retrieval returns insufficient results
3. User explicitly requests web information

Uses DuckDuckGo (free, no API key) as primary search with fallback options.
"""

import logging
import asyncio
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import quote_plus
import hashlib
import json
import re

import requests
from cachetools import TTLCache

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class WebSearchResult:
    """Represents a web search result with citation info"""
    title: str
    url: str
    snippet: str
    source: str  # e.g., "web", "wikipedia", "educational"
    relevance_score: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def citation(self) -> str:
        """Generate formatted citation"""
        return f"[{self.title}]({self.url})"

    @property
    def citation_id(self) -> str:
        """Generate unique citation ID"""
        return hashlib.md5(self.url.encode()).hexdigest()[:8]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "source": self.source,
            "relevance_score": self.relevance_score,
            "citation": self.citation,
            "citation_id": self.citation_id
        }


class WebSearchService:
    """
    Web search service with multiple providers and caching.

    Features:
    - DuckDuckGo instant answers (free, no API key)
    - Wikipedia API for educational content
    - Result caching to reduce API calls
    - Educational content prioritization
    """

    def __init__(self):
        """Initialize web search service"""
        # Cache search results for 1 hour
        self.cache = TTLCache(maxsize=500, ttl=3600)

        # Educational domain preferences
        self.educational_domains = [
            "wikipedia.org", "khanacademy.org", "mathworld.wolfram.com",
            "britannica.com", "sciencedirect.com", "arxiv.org",
            "mit.edu", "stanford.edu", "coursera.org", "edx.org",
            "byjus.com", "vedantu.com", "toppr.com"
        ]

        # Request headers
        self.headers = {
            "User-Agent": "Mozilla/5.0 (compatible; AgenticTutor/1.0; Educational)"
        }

        logger.info("Web search service initialized")

    def search(
        self,
        query: str,
        max_results: int = 5,
        educational_boost: bool = True
    ) -> List[WebSearchResult]:
        """
        Perform web search with educational content prioritization.

        Args:
            query: Search query
            max_results: Maximum number of results
            educational_boost: Whether to prioritize educational sources

        Returns:
            List of WebSearchResult objects
        """
        cache_key = f"search:{query}:{max_results}"
        if cache_key in self.cache:
            logger.debug(f"Cache hit for query: {query[:50]}")
            return self.cache[cache_key]

        results = []

        # Try DuckDuckGo instant answers first (best for educational content)
        ddg_results = self._search_duckduckgo(query, max_results)
        results.extend(ddg_results)

        # Add Wikipedia results for educational queries
        wiki_results = self._search_wikipedia(query, min(3, max_results))
        results.extend(wiki_results)

        # Remove duplicates by URL
        seen_urls = set()
        unique_results = []
        for r in results:
            if r.url not in seen_urls:
                seen_urls.add(r.url)
                unique_results.append(r)

        # Score and rank results
        if educational_boost:
            unique_results = self._rank_educational(unique_results)

        # Limit results
        final_results = unique_results[:max_results]

        # Cache results
        self.cache[cache_key] = final_results

        logger.info(f"Web search for '{query[:50]}' returned {len(final_results)} results")
        return final_results

    def _search_duckduckgo(self, query: str, max_results: int) -> List[WebSearchResult]:
        """
        Search using DuckDuckGo instant answers API (free, no key needed).
        """
        results = []
        try:
            # DuckDuckGo instant answer API
            url = f"https://api.duckduckgo.com/?q={quote_plus(query)}&format=json&no_html=1&skip_disambig=1"

            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            data = response.json()

            # Extract abstract (main answer)
            if data.get("Abstract"):
                results.append(WebSearchResult(
                    title=data.get("Heading", query),
                    url=data.get("AbstractURL", ""),
                    snippet=data.get("Abstract", ""),
                    source="duckduckgo_abstract",
                    relevance_score=0.9
                ))

            # Extract related topics
            for topic in data.get("RelatedTopics", [])[:max_results]:
                if isinstance(topic, dict) and topic.get("Text"):
                    results.append(WebSearchResult(
                        title=topic.get("Text", "")[:100],
                        url=topic.get("FirstURL", ""),
                        snippet=topic.get("Text", ""),
                        source="duckduckgo_related",
                        relevance_score=0.7
                    ))

            # Extract definition if available
            if data.get("Definition"):
                results.append(WebSearchResult(
                    title=f"Definition: {query}",
                    url=data.get("DefinitionURL", ""),
                    snippet=data.get("Definition", ""),
                    source="duckduckgo_definition",
                    relevance_score=0.85
                ))

        except Exception as e:
            logger.warning(f"DuckDuckGo search failed: {e}")

        return results

    def _search_wikipedia(self, query: str, max_results: int) -> List[WebSearchResult]:
        """
        Search Wikipedia for educational content.
        """
        results = []
        try:
            # Wikipedia API search
            search_url = "https://en.wikipedia.org/w/api.php"
            params = {
                "action": "query",
                "list": "search",
                "srsearch": query,
                "srlimit": max_results,
                "format": "json",
                "srprop": "snippet|titlesnippet"
            }

            response = requests.get(search_url, params=params, headers=self.headers, timeout=10)
            response.raise_for_status()
            data = response.json()

            for item in data.get("query", {}).get("search", []):
                # Clean HTML from snippet
                snippet = re.sub(r'<[^>]+>', '', item.get("snippet", ""))

                results.append(WebSearchResult(
                    title=item.get("title", ""),
                    url=f"https://en.wikipedia.org/wiki/{quote_plus(item.get('title', '').replace(' ', '_'))}",
                    snippet=snippet,
                    source="wikipedia",
                    relevance_score=0.8
                ))

        except Exception as e:
            logger.warning(f"Wikipedia search failed: {e}")

        return results

    def _rank_educational(self, results: List[WebSearchResult]) -> List[WebSearchResult]:
        """
        Re-rank results to prioritize educational sources.
        """
        for result in results:
            # Boost score for educational domains
            for domain in self.educational_domains:
                if domain in result.url.lower():
                    result.relevance_score *= 1.3
                    break

            # Boost Wikipedia even more
            if "wikipedia.org" in result.url.lower():
                result.relevance_score *= 1.2

        # Sort by relevance score
        return sorted(results, key=lambda x: x.relevance_score, reverse=True)

    def get_context_from_web(
        self,
        query: str,
        max_results: int = 5
    ) -> tuple[str, List[Dict[str, Any]]]:
        """
        Get formatted context and citations from web search.

        Args:
            query: Search query
            max_results: Maximum results to include

        Returns:
            Tuple of (context_string, citations_list)
        """
        results = self.search(query, max_results)

        if not results:
            return "", []

        # Build context with inline citations
        context_parts = []
        citations = []

        for i, result in enumerate(results, 1):
            citation_marker = f"[{i}]"
            context_parts.append(f"{result.snippet} {citation_marker}")
            citations.append({
                "id": i,
                "citation_id": result.citation_id,
                "title": result.title,
                "url": result.url,
                "source": result.source
            })

        context = "\n\n".join(context_parts)

        return context, citations


# Singleton instance
_web_search_service: Optional[WebSearchService] = None


def get_web_search_service() -> WebSearchService:
    """Get or create singleton web search service"""
    global _web_search_service
    if _web_search_service is None:
        _web_search_service = WebSearchService()
    return _web_search_service
