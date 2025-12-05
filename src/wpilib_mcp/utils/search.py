"""BM25 search implementation for documentation indexing."""

import re
from dataclasses import dataclass
from typing import Generic, TypeVar

from rank_bm25 import BM25Okapi


T = TypeVar("T")


@dataclass
class ScoredResult(Generic[T]):
    """A search result with BM25 score."""
    
    item: T
    score: float
    
    def __lt__(self, other: "ScoredResult") -> bool:
        """Compare by score (higher is better)."""
        return self.score > other.score


class BM25SearchIndex(Generic[T]):
    """
    BM25-based search index for documentation.
    
    Generic over the item type stored in the index.
    """
    
    # Common programming-related stop words to remove
    STOP_WORDS = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "as", "is", "was", "are", "were", "been",
        "be", "have", "has", "had", "do", "does", "did", "will", "would",
        "could", "should", "may", "might", "must", "shall", "can", "need",
        "this", "that", "these", "those", "it", "its", "you", "your", "we",
        "our", "they", "their", "he", "she", "him", "her", "his", "hers"
    }
    
    def __init__(self, remove_stop_words: bool = True):
        """
        Initialize the search index.
        
        Args:
            remove_stop_words: Whether to remove common stop words from queries
        """
        self.remove_stop_words = remove_stop_words
        self._items: list[T] = []
        self._bm25: BM25Okapi | None = None
        self._corpus: list[list[str]] = []
    
    def tokenize(self, text: str) -> list[str]:
        """
        Tokenize text for BM25 indexing.
        
        Handles camelCase, snake_case, and preserves technical terms.
        """
        # Split camelCase and PascalCase BEFORE lowercasing
        text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
        text = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", text)
        
        # Convert to lowercase
        text = text.lower()
        
        # Replace underscores and hyphens with spaces
        text = re.sub(r"[_\-]", " ", text)
        
        # Remove non-alphanumeric except spaces
        text = re.sub(r"[^\w\s]", " ", text)
        
        # Split into tokens
        tokens = text.split()
        
        # Remove stop words if enabled
        if self.remove_stop_words:
            tokens = [t for t in tokens if t not in self.STOP_WORDS and len(t) > 1]
        else:
            tokens = [t for t in tokens if len(t) > 1]
        
        return tokens
    
    def build(self, items: list[T], text_extractor: callable) -> None:
        """
        Build the BM25 index from items.
        
        Args:
            items: List of items to index
            text_extractor: Function to extract searchable text from each item
        """
        self._items = items
        self._corpus = []
        
        for item in items:
            text = text_extractor(item)
            tokens = self.tokenize(text)
            self._corpus.append(tokens)
        
        if self._corpus:
            self._bm25 = BM25Okapi(self._corpus)
        else:
            self._bm25 = None
    
    def search(self, query: str, max_results: int = 10) -> list[ScoredResult[T]]:
        """
        Search the index for matching items.
        
        Args:
            query: Search query string
            max_results: Maximum number of results to return
            
        Returns:
            List of ScoredResult objects, sorted by relevance
        """
        if self._bm25 is None or not self._items:
            return []
        
        # Tokenize query
        query_tokens = self.tokenize(query)
        if not query_tokens:
            return []
        
        # Get BM25 scores
        scores = self._bm25.get_scores(query_tokens)
        
        # Create scored results
        results = []
        for i, score in enumerate(scores):
            if score > 0:
                results.append(ScoredResult(item=self._items[i], score=score))
        
        # Sort by score (descending) and limit
        results.sort()
        return results[:max_results]
    
    def search_with_filter(
        self,
        query: str,
        filter_fn: callable,
        max_results: int = 10
    ) -> list[ScoredResult[T]]:
        """
        Search with an additional filter function.
        
        Args:
            query: Search query string
            filter_fn: Function that returns True for items to include
            max_results: Maximum number of results to return
            
        Returns:
            Filtered list of ScoredResult objects
        """
        if self._bm25 is None or not self._items:
            return []
        
        query_tokens = self.tokenize(query)
        if not query_tokens:
            return []
        
        scores = self._bm25.get_scores(query_tokens)
        
        results = []
        for i, score in enumerate(scores):
            if score > 0 and filter_fn(self._items[i]):
                results.append(ScoredResult(item=self._items[i], score=score))
        
        results.sort()
        return results[:max_results]
    
    @property
    def size(self) -> int:
        """Return the number of indexed items."""
        return len(self._items)
    
    @property
    def is_built(self) -> bool:
        """Check if the index has been built."""
        return self._bm25 is not None


def merge_search_results(
    result_lists: list[list[ScoredResult[T]]],
    max_results: int = 10
) -> list[ScoredResult[T]]:
    """
    Merge multiple search result lists by score.
    
    Args:
        result_lists: List of search result lists from different sources
        max_results: Maximum total results to return
        
    Returns:
        Merged and sorted list of results
    """
    all_results = []
    for results in result_lists:
        all_results.extend(results)
    
    # Sort by score (ScoredResult.__lt__ handles this)
    all_results.sort()
    
    return all_results[:max_results]




