"""Tests for CourseSearchTool"""

from unittest.mock import Mock, patch

import pytest
from models import Source
from search_tools import CourseSearchTool
from tests.fixtures import (
    SAMPLE_SEARCH_RESULTS_EMPTY,
    SAMPLE_SEARCH_RESULTS_ERROR,
    SAMPLE_SEARCH_RESULTS_VALID,
)
from vector_store import SearchResults


class TestCourseSearchTool:
    """Test suite for CourseSearchTool.execute() method"""

    def test_execute_with_valid_query_no_filters(self, course_search_tool):
        """Test successful search with no filters"""
        # Setup mock to return valid results
        valid_results = SearchResults(
            documents=["Content about MCP servers", "More MCP content"],
            metadata=[
                {
                    "course_title": "Introduction to MCP Servers",
                    "lesson_number": 1,
                    "chunk_index": 0,
                },
                {
                    "course_title": "Introduction to MCP Servers",
                    "lesson_number": 2,
                    "chunk_index": 0,
                },
            ],
            distances=[0.1, 0.2],
        )
        course_search_tool.store.search.return_value = valid_results

        # Execute search
        result = course_search_tool.execute(query="What is MCP?")

        # Verify search was called
        course_search_tool.store.search.assert_called_once_with(
            query="What is MCP?", course_name=None, lesson_number=None
        )

        # Verify formatted output
        assert "[Introduction to MCP Servers - Lesson 1]" in result
        assert "Content about MCP servers" in result
        assert "[Introduction to MCP Servers - Lesson 2]" in result
        assert "More MCP content" in result

        # Verify sources tracked
        assert len(course_search_tool.last_sources) > 0

    def test_execute_with_course_filter(self, course_search_tool):
        """Test search with course_name parameter"""
        valid_results = SearchResults(
            documents=["Filtered content"],
            metadata=[{"course_title": "MCP Course", "lesson_number": 1, "chunk_index": 0}],
            distances=[0.1],
        )
        course_search_tool.store.search.return_value = valid_results

        # Execute with course filter
        result = course_search_tool.execute(query="test query", course_name="MCP")

        # Verify course_name was passed
        course_search_tool.store.search.assert_called_once_with(
            query="test query", course_name="MCP", lesson_number=None
        )

        # Verify result contains content
        assert "Filtered content" in result

    def test_execute_with_lesson_filter(self, course_search_tool):
        """Test search with lesson_number parameter"""
        valid_results = SearchResults(
            documents=["Lesson specific content"],
            metadata=[{"course_title": "Test Course", "lesson_number": 2, "chunk_index": 0}],
            distances=[0.1],
        )
        course_search_tool.store.search.return_value = valid_results

        # Execute with lesson filter
        result = course_search_tool.execute(query="test query", lesson_number=2)

        # Verify lesson_number was passed
        course_search_tool.store.search.assert_called_once_with(query="test query", course_name=None, lesson_number=2)

        # Verify result
        assert "Lesson specific content" in result
        assert "Lesson 2" in result

    def test_execute_with_empty_results(self, course_search_tool):
        """Test handling of empty search results"""
        course_search_tool.store.search.return_value = SAMPLE_SEARCH_RESULTS_EMPTY

        # Execute search
        result = course_search_tool.execute(query="nonexistent content")

        # Should return "no content found" message
        assert "No relevant content found" in result
        # Sources should be empty or cleared
        assert len(course_search_tool.last_sources) == 0

    def test_execute_with_search_error(self, course_search_tool):
        """Test handling of search errors"""
        course_search_tool.store.search.return_value = SAMPLE_SEARCH_RESULTS_ERROR

        # Execute search
        result = course_search_tool.execute(query="test query")

        # Should return the error message
        assert "Search failed: Connection error" in result

    def test_format_results_with_missing_metadata(self, course_search_tool):
        """Test _format_results with incomplete metadata"""
        # Create results with missing metadata fields
        incomplete_results = SearchResults(
            documents=["Document without full metadata"],
            metadata=[{"chunk_index": 0}],  # Missing course_title and lesson_number
            distances=[0.1],
        )
        course_search_tool.store.search.return_value = incomplete_results

        # Execute - should handle missing metadata gracefully
        result = course_search_tool.execute(query="test")

        # Should still return some result without crashing
        assert "Document without full metadata" in result

    def test_format_results_link_retrieval_failure(self, course_search_tool):
        """Test handling when get_lesson_link() raises exception - THIS SHOULD CURRENTLY FAIL"""
        valid_results = SearchResults(
            documents=["Test content"],
            metadata=[{"course_title": "Test Course", "lesson_number": 1, "chunk_index": 0}],
            distances=[0.1],
        )
        course_search_tool.store.search.return_value = valid_results

        # Mock link retrieval to raise exception
        course_search_tool.store.get_lesson_link.side_effect = Exception("Link retrieval failed")
        course_search_tool.store.get_course_link.side_effect = Exception("Link retrieval failed")

        # Execute - should handle link retrieval errors gracefully
        result = course_search_tool.execute(query="test")

        # Should still return content without crashing (currently will fail)
        assert "Test content" in result

        # Sources should be created with None URLs as fallback
        assert len(course_search_tool.last_sources) > 0

    def test_format_results_duplicate_sources(self, course_search_tool):
        """Test that duplicate sources are deduplicated"""
        # Create results with duplicate course/lesson combinations
        duplicate_results = SearchResults(
            documents=["Content 1", "Content 2", "Content 3"],
            metadata=[
                {"course_title": "Test Course", "lesson_number": 1, "chunk_index": 0},
                {"course_title": "Test Course", "lesson_number": 1, "chunk_index": 1},  # Duplicate
                {"course_title": "Test Course", "lesson_number": 2, "chunk_index": 0},
            ],
            distances=[0.1, 0.15, 0.2],
        )
        course_search_tool.store.search.return_value = duplicate_results

        # Execute
        result = course_search_tool.execute(query="test")

        # Verify sources are deduplicated (should have 2 unique sources, not 3)
        assert len(course_search_tool.last_sources) == 2

        # Verify both unique lessons are represented
        source_texts = [s.text for s in course_search_tool.last_sources]
        assert any("Lesson 1" in text for text in source_texts)
        assert any("Lesson 2" in text for text in source_texts)

    def test_get_tool_definition(self, course_search_tool):
        """Test that tool definition is correctly formatted"""
        definition = course_search_tool.get_tool_definition()

        # Verify structure
        assert definition["name"] == "search_course_content"
        assert "description" in definition
        assert "input_schema" in definition

        # Verify input schema
        schema = definition["input_schema"]
        assert schema["type"] == "object"
        assert "query" in schema["properties"]
        assert "course_name" in schema["properties"]
        assert "lesson_number" in schema["properties"]

        # Verify required fields
        assert "query" in schema["required"]
        assert "course_name" not in schema["required"]  # Optional
        assert "lesson_number" not in schema["required"]  # Optional
