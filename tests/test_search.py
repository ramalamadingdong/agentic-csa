"""Tests for BM25 search functionality."""

import pytest

from wpilib_mcp.utils.search import BM25SearchIndex, ScoredResult, merge_search_results


class TestBM25SearchIndex:
    """Test cases for BM25SearchIndex."""
    
    def test_build_index(self):
        """Test building a search index."""
        index = BM25SearchIndex()
        items = ["Hello world", "Python programming", "Robot control"]
        
        index.build(items, text_extractor=lambda x: x)
        
        assert index.size == 3
        assert index.is_built
    
    def test_empty_index(self):
        """Test searching empty index returns no results."""
        index = BM25SearchIndex()
        
        results = index.search("test query")
        
        assert results == []
    
    def test_basic_search(self):
        """Test basic search functionality."""
        index = BM25SearchIndex()
        items = [
            "Commands represent robot actions",
            "Subsystems are hardware abstractions",
            "PID controllers minimize error"
        ]
        
        index.build(items, text_extractor=lambda x: x)
        results = index.search("robot commands", max_results=2)
        
        assert len(results) <= 2
        assert all(isinstance(r, ScoredResult) for r in results)
        # First result should be about commands
        assert "commands" in results[0].item.lower() or "robot" in results[0].item.lower()
    
    def test_search_with_filter(self):
        """Test search with filter function."""
        index = BM25SearchIndex()
        # Use documents with varied content for better BM25 discrimination
        items = [
            {"text": "Java SparkMax motor controller configuration guide", "lang": "Java"},
            {"text": "Python sensor reading and data processing tutorial", "lang": "Python"},
            {"text": "C++ PID controller implementation example", "lang": "C++"},
        ]
        
        index.build(items, text_extractor=lambda x: x["text"])
        
        # Search for Java-specific content with filter
        results = index.search_with_filter(
            "SparkMax motor",
            filter_fn=lambda x: x["lang"] == "Java",
            max_results=5
        )
        
        assert len(results) == 1
        assert results[0].item["lang"] == "Java"
    
    def test_tokenization(self):
        """Test tokenization handles different formats."""
        index = BM25SearchIndex()
        
        # Test camelCase
        tokens = index.tokenize("getMotorPosition")
        assert "get" in tokens
        assert "motor" in tokens
        assert "position" in tokens
        
        # Test snake_case
        tokens = index.tokenize("get_motor_position")
        assert "get" in tokens
        assert "motor" in tokens
        
        # Test stop words removal
        tokens = index.tokenize("the motor is running")
        assert "the" not in tokens
        assert "is" not in tokens
        assert "motor" in tokens
    
    def test_no_results_for_unrelated_query(self):
        """Test that unrelated queries return no results."""
        index = BM25SearchIndex()
        items = ["Robot programming with WPILib"]
        
        index.build(items, text_extractor=lambda x: x)
        results = index.search("xyz123 nonexistent term")
        
        # Should return empty or very low scores
        assert len(results) == 0 or all(r.score < 0.1 for r in results)


class TestMergeResults:
    """Test cases for result merging."""
    
    def test_merge_empty_lists(self):
        """Test merging empty lists."""
        result = merge_search_results([])
        assert result == []
    
    def test_merge_single_list(self):
        """Test merging a single list."""
        results = [
            ScoredResult(item="a", score=0.5),
            ScoredResult(item="b", score=0.3),
        ]
        
        merged = merge_search_results([results])
        
        assert len(merged) == 2
        assert merged[0].score >= merged[1].score
    
    def test_merge_multiple_lists(self):
        """Test merging multiple lists by score."""
        list1 = [
            ScoredResult(item="a", score=0.9),
            ScoredResult(item="b", score=0.5),
        ]
        list2 = [
            ScoredResult(item="c", score=0.7),
            ScoredResult(item="d", score=0.3),
        ]
        
        merged = merge_search_results([list1, list2], max_results=3)
        
        assert len(merged) == 3
        # Should be sorted by score (descending)
        assert merged[0].score >= merged[1].score >= merged[2].score
        # Highest score should be "a"
        assert merged[0].item == "a"
    
    def test_merge_respects_max_results(self):
        """Test that merge respects max_results limit."""
        results = [
            ScoredResult(item=str(i), score=1.0 - i * 0.1)
            for i in range(10)
        ]
        
        merged = merge_search_results([results], max_results=3)
        
        assert len(merged) == 3


class TestScoredResult:
    """Test cases for ScoredResult."""
    
    def test_comparison(self):
        """Test that results compare by score (higher is 'less than')."""
        high = ScoredResult(item="high", score=0.9)
        low = ScoredResult(item="low", score=0.1)
        
        # Higher score should sort first (be "less than")
        assert high < low
        
        # Verify sorting works
        items = [low, high]
        items.sort()
        assert items[0].score > items[1].score




