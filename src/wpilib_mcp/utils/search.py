"""BM25 search implementation for documentation indexing."""

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher, get_close_matches
from typing import Generic, TypeVar

from rank_bm25 import BM25Okapi


T = TypeVar("T")


# FRC-specific terms that should NEVER be treated as stop words
FRC_PRESERVED_TERMS = {
    # Protocols & buses
    "can", "pwm", "i2c", "spi", "dio", "usb", "uart",
    # Control theory
    "pid", "ff", "kp", "ki", "kd", "kv", "ka", "ks",
    # Hardware
    "neo", "cim", "bag", "led", "imu",
    # Units/measurements
    "rpm", "fps", "mps", "rad", "deg",
    # Other FRC terms
    "frc", "wpi", "rev", "ctre", "rio",
}

# FRC synonym dictionary for query expansion
FRC_SYNONYMS = {
    # Motor controllers
    "motor controller": ["sparkmax", "spark max", "talonfx", "talon fx", "spark flex", "sparkflex"],
    "sparkmax": ["spark max", "motor controller", "rev motor controller"],
    "spark max": ["sparkmax", "motor controller", "rev motor controller"],
    "talonfx": ["talon fx", "motor controller", "ctre motor controller", "falcon"],
    "talon fx": ["talonfx", "motor controller", "ctre motor controller", "falcon"],
    "falcon": ["talonfx", "talon fx", "falcon 500"],
    "kraken": ["talonfx", "talon fx", "kraken x60"],

    # Motors
    "neo": ["neo motor", "rev neo", "brushless motor"],
    "neo 550": ["neo550", "small neo"],
    "falcon 500": ["falcon", "talonfx integrated"],
    "cim": ["cim motor", "brushed motor"],

    # Sensors
    "cancoder": ["can coder", "ctre encoder", "absolute encoder"],
    "can coder": ["cancoder", "ctre encoder"],
    "through bore encoder": ["rev encoder", "throughbore"],
    "pigeon": ["pigeon 2", "pigeon2", "imu", "gyro"],
    "navx": ["nav x", "gyro", "imu"],

    # Control
    "pid": ["pid controller", "pid control", "closed loop"],
    "pid controller": ["pid", "closed loop control"],
    "feedforward": ["ff", "feed forward", "kv ka"],
    "motion magic": ["motion profiling", "s-curve", "trapezoidal"],
    "motion profile": ["motion magic", "trajectory", "path following"],

    # Programming
    "command based": ["command-based", "commands", "subsystems"],
    "command-based": ["command based", "commands", "subsystems"],
    "timed robot": ["timedrobot", "iterative robot"],
    "subsystem": ["subsystems", "command based"],

    # CAN bus
    "can bus": ["canbus", "can network", "can wiring"],
    "canbus": ["can bus", "can network"],
}

# Known FRC terms for fuzzy matching suggestions
FRC_KNOWN_TERMS = {
    "sparkmax", "sparkflex", "talonfx", "cancoder", "pigeon", "navx",
    "neo", "falcon", "kraken", "cim", "redline", "bag",
    "pid", "feedforward", "motionmagic", "trajectory",
    "commandbased", "subsystem", "timedrobot",
    "canbus", "pwm", "dio", "i2c", "spi",
    "wpilib", "revlib", "phoenix", "photonvision",
    "drivetrain", "swerve", "mecanum", "differential",
    "encoder", "gyro", "accelerometer", "lidar", "limelight",
}


@dataclass
class ScoredResult(Generic[T]):
    """A search result with BM25 score and confidence."""

    item: T
    score: float
    confidence: float = 0.0  # Normalized 0.0-1.0 confidence

    def __lt__(self, other: "ScoredResult") -> bool:
        """Compare by score (higher is better)."""
        return self.score > other.score


@dataclass
class SearchResponse(Generic[T]):
    """Enhanced search response with metadata."""

    results: list[ScoredResult[T]]
    query_tokens: list[str]
    expanded_terms: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)

    @property
    def has_results(self) -> bool:
        return len(self.results) > 0

    @property
    def top_confidence(self) -> float:
        """Return confidence of top result, or 0 if no results."""
        return self.results[0].confidence if self.results else 0.0


class BM25SearchIndex(Generic[T]):
    """
    BM25-based search index for documentation.

    Generic over the item type stored in the index.
    """

    # Common stop words - FRC terms are EXCLUDED from this list
    STOP_WORDS = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "as", "is", "was", "are", "were", "been",
        "be", "have", "has", "had", "do", "does", "did", "will", "would",
        "could", "should", "may", "might", "must", "shall", "need",
        "this", "that", "these", "those", "it", "its", "you", "your", "we",
        "our", "they", "their", "he", "she", "him", "her", "his", "hers",
        "how", "what", "when", "where", "why", "which", "who",
    }
    # NOTE: "can" removed - it's a critical FRC term (CAN bus)
    
    def __init__(self, remove_stop_words: bool = True, enable_fuzzy: bool = True):
        """
        Initialize the search index.

        Args:
            remove_stop_words: Whether to remove common stop words from queries
            enable_fuzzy: Whether to enable fuzzy matching for typos
        """
        self.remove_stop_words = remove_stop_words
        self.enable_fuzzy = enable_fuzzy
        self._items: list[T] = []
        self._bm25: BM25Okapi | None = None
        self._corpus: list[list[str]] = []
        self._all_tokens: set[str] = set()  # For fuzzy matching
        self._max_score: float = 0.0  # For confidence normalization

    def tokenize(self, text: str) -> list[str]:
        """
        Tokenize text for BM25 indexing.

        Handles camelCase, snake_case, and preserves FRC technical terms.
        """
        # Split camelCase and PascalCase BEFORE lowercasing
        # But be smarter about FRC acronyms - don't split "CANcoder" into "CA Ncoder"
        # First, protect known compound terms
        protected = text
        for term in ["CANcoder", "CANbus", "TalonFX", "SparkMax", "SparkFlex",
                     "NavX", "REVLib", "WPILib", "NetworkTables"]:
            protected = protected.replace(term, term.lower())

        # Now split remaining camelCase
        protected = re.sub(r"([a-z])([A-Z])", r"\1 \2", protected)
        protected = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", protected)

        # Convert to lowercase
        text = protected.lower()

        # Replace underscores and hyphens with spaces
        text = re.sub(r"[_\-]", " ", text)

        # Remove non-alphanumeric except spaces
        text = re.sub(r"[^\w\s]", " ", text)

        # Split into tokens
        tokens = text.split()

        # Remove stop words if enabled, but PRESERVE FRC terms
        if self.remove_stop_words:
            tokens = [
                t for t in tokens
                if (t in FRC_PRESERVED_TERMS or t not in self.STOP_WORDS) and len(t) > 1
            ]
        else:
            tokens = [t for t in tokens if len(t) > 1]

        return tokens

    def _fuzzy_match_token(self, token: str, threshold: float = 0.8) -> list[str]:
        """
        Find fuzzy matches for a token in the corpus.

        Args:
            token: The token to match
            threshold: Minimum similarity ratio (0.0-1.0)

        Returns:
            List of similar tokens from the corpus
        """
        if not self._all_tokens or len(token) < 3:
            return []

        matches = get_close_matches(token, self._all_tokens, n=3, cutoff=threshold)
        return [m for m in matches if m != token]

    def _expand_query(self, tokens: list[str]) -> tuple[list[str], list[str]]:
        """
        Expand query tokens using FRC synonyms.

        Args:
            tokens: Original query tokens

        Returns:
            Tuple of (expanded_tokens, expansion_sources)
        """
        expanded = list(tokens)
        sources = []

        # Check for multi-word matches first
        query_text = " ".join(tokens)
        for phrase, synonyms in FRC_SYNONYMS.items():
            if phrase in query_text:
                for syn in synonyms[:2]:  # Limit expansions
                    syn_tokens = syn.lower().split()
                    for st in syn_tokens:
                        if st not in expanded and st not in self.STOP_WORDS:
                            expanded.append(st)
                            sources.append(f"{phrase} → {syn}")

        # Check individual tokens
        for token in tokens:
            if token in FRC_SYNONYMS:
                for syn in FRC_SYNONYMS[token][:2]:
                    syn_tokens = syn.lower().split()
                    for st in syn_tokens:
                        if st not in expanded and st not in self.STOP_WORDS:
                            expanded.append(st)
                            if f"{token} → {syn}" not in sources:
                                sources.append(f"{token} → {syn}")

        return expanded, sources

    def _get_suggestions(self, tokens: list[str], results_found: bool) -> list[str]:
        """
        Generate 'did you mean?' suggestions for weak/no results.

        Args:
            tokens: Query tokens
            results_found: Whether any results were found

        Returns:
            List of suggested alternative queries
        """
        suggestions = []

        for token in tokens:
            # Check against known FRC terms
            frc_matches = get_close_matches(token, FRC_KNOWN_TERMS, n=2, cutoff=0.7)
            for match in frc_matches:
                if match != token:
                    suggestions.append(f"'{token}' → '{match}'")

            # Check against corpus tokens
            if self.enable_fuzzy and self._all_tokens:
                corpus_matches = self._fuzzy_match_token(token, threshold=0.75)
                for match in corpus_matches[:1]:
                    suggestion = f"'{token}' → '{match}'"
                    if suggestion not in suggestions:
                        suggestions.append(suggestion)

        return suggestions[:5]  # Limit suggestions
    
    def build(self, items: list[T], text_extractor: callable) -> None:
        """
        Build the BM25 index from items.

        Args:
            items: List of items to index
            text_extractor: Function to extract searchable text from each item
        """
        self._items = items
        self._corpus = []
        self._all_tokens = set()

        for item in items:
            text = text_extractor(item)
            tokens = self.tokenize(text)
            self._corpus.append(tokens)
            self._all_tokens.update(tokens)

        if self._corpus:
            self._bm25 = BM25Okapi(self._corpus)
            # Calculate max possible score for normalization
            # Use a sample query to estimate
            if self._corpus:
                sample_scores = self._bm25.get_scores(list(self._all_tokens)[:10])
                self._max_score = max(sample_scores) if len(sample_scores) > 0 else 1.0
                if self._max_score == 0:
                    self._max_score = 1.0
        else:
            self._bm25 = None
            self._max_score = 1.0
    
    def search(self, query: str, max_results: int = 10) -> list[ScoredResult[T]]:
        """
        Search the index for matching items.

        Args:
            query: Search query string
            max_results: Maximum number of results to return

        Returns:
            List of ScoredResult objects, sorted by relevance
        """
        response = self.search_enhanced(query, max_results)
        return response.results

    def search_enhanced(
        self,
        query: str,
        max_results: int = 10,
        expand_query: bool = True,
        include_suggestions: bool = True,
    ) -> SearchResponse[T]:
        """
        Enhanced search with query expansion, confidence scores, and suggestions.

        Args:
            query: Search query string
            max_results: Maximum number of results to return
            expand_query: Whether to expand query with synonyms
            include_suggestions: Whether to include 'did you mean?' suggestions

        Returns:
            SearchResponse with results, confidence scores, and metadata
        """
        if self._bm25 is None or not self._items:
            return SearchResponse(results=[], query_tokens=[], suggestions=[])

        # Tokenize query
        query_tokens = self.tokenize(query)
        if not query_tokens:
            # Try fuzzy matching on original query words
            original_words = query.lower().split()
            suggestions = self._get_suggestions(original_words, False) if include_suggestions else []
            return SearchResponse(
                results=[],
                query_tokens=[],
                suggestions=suggestions,
            )

        # Expand query with synonyms
        expanded_terms = []
        search_tokens = query_tokens
        if expand_query:
            search_tokens, expanded_terms = self._expand_query(query_tokens)

        # Add fuzzy matches for tokens
        if self.enable_fuzzy:
            for token in query_tokens:
                fuzzy_matches = self._fuzzy_match_token(token)
                for match in fuzzy_matches[:1]:  # Limit fuzzy expansions
                    if match not in search_tokens:
                        search_tokens.append(match)

        # Get BM25 scores
        scores = self._bm25.get_scores(search_tokens)

        # Calculate confidence scores (normalize to 0-1)
        max_score_in_results = max(scores) if len(scores) > 0 and max(scores) > 0 else 1.0

        # Create scored results with confidence
        results = []
        for i, score in enumerate(scores):
            if score > 0:
                # Confidence based on relative score within results
                confidence = min(1.0, score / max_score_in_results)
                results.append(ScoredResult(
                    item=self._items[i],
                    score=score,
                    confidence=round(confidence, 3)
                ))

        # Sort by score (descending) and limit
        results.sort()
        results = results[:max_results]

        # Generate suggestions if results are weak or empty
        suggestions = []
        if include_suggestions:
            weak_results = len(results) < 3 or (results and results[0].confidence < 0.5)
            if weak_results or not results:
                suggestions = self._get_suggestions(query_tokens, len(results) > 0)

        return SearchResponse(
            results=results,
            query_tokens=query_tokens,
            expanded_terms=expanded_terms,
            suggestions=suggestions,
        )
    
    def search_with_filter(
        self,
        query: str,
        filter_fn: callable,
        max_results: int = 10,
        expand_query: bool = True,
    ) -> list[ScoredResult[T]]:
        """
        Search with an additional filter function.

        Args:
            query: Search query string
            filter_fn: Function that returns True for items to include
            max_results: Maximum number of results to return
            expand_query: Whether to expand query with synonyms

        Returns:
            Filtered list of ScoredResult objects
        """
        if self._bm25 is None or not self._items:
            return []

        query_tokens = self.tokenize(query)
        if not query_tokens:
            return []

        # Expand query with synonyms
        search_tokens = query_tokens
        if expand_query:
            search_tokens, _ = self._expand_query(query_tokens)

        # Add fuzzy matches
        if self.enable_fuzzy:
            for token in query_tokens:
                fuzzy_matches = self._fuzzy_match_token(token)
                for match in fuzzy_matches[:1]:
                    if match not in search_tokens:
                        search_tokens.append(match)

        scores = self._bm25.get_scores(search_tokens)

        # Calculate max for confidence
        max_score = max(scores) if len(scores) > 0 and max(scores) > 0 else 1.0

        results = []
        for i, score in enumerate(scores):
            if score > 0 and filter_fn(self._items[i]):
                confidence = min(1.0, score / max_score)
                results.append(ScoredResult(
                    item=self._items[i],
                    score=score,
                    confidence=round(confidence, 3)
                ))

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
    max_results: int = 10,
    normalize_scores: bool = True,
) -> list[ScoredResult[T]]:
    """
    Merge multiple search result lists by score.

    Args:
        result_lists: List of search result lists from different sources
        max_results: Maximum total results to return
        normalize_scores: Whether to normalize scores across sources

    Returns:
        Merged and sorted list of results
    """
    if normalize_scores:
        # Normalize scores per source to make them comparable
        normalized_lists = []
        for results in result_lists:
            if not results:
                continue
            max_score = max(r.score for r in results) if results else 1.0
            if max_score == 0:
                max_score = 1.0
            normalized = []
            for r in results:
                normalized.append(ScoredResult(
                    item=r.item,
                    score=r.score / max_score,  # Normalize to 0-1
                    confidence=r.confidence,
                ))
            normalized_lists.append(normalized)
        result_lists = normalized_lists

    all_results = []
    for results in result_lists:
        all_results.extend(results)

    # Sort by score (ScoredResult.__lt__ handles this)
    all_results.sort()

    return all_results[:max_results]


def merge_search_responses(
    responses: list[SearchResponse[T]],
    max_results: int = 10,
) -> SearchResponse[T]:
    """
    Merge multiple SearchResponse objects.

    Args:
        responses: List of SearchResponse objects
        max_results: Maximum total results

    Returns:
        Merged SearchResponse
    """
    all_results = merge_search_results(
        [r.results for r in responses],
        max_results=max_results,
        normalize_scores=True,
    )

    # Combine metadata
    all_tokens = []
    all_expanded = []
    all_suggestions = []

    for resp in responses:
        all_tokens.extend(resp.query_tokens)
        all_expanded.extend(resp.expanded_terms)
        all_suggestions.extend(resp.suggestions)

    return SearchResponse(
        results=all_results,
        query_tokens=list(set(all_tokens)),
        expanded_terms=list(set(all_expanded)),
        suggestions=list(set(all_suggestions))[:5],
    )




