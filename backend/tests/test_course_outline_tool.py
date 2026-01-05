"""Tests for CourseOutlineTool"""

import json
from unittest.mock import Mock, patch

import pytest
from models import Source
from search_tools import CourseOutlineTool
from tests.fixtures import (
    SAMPLE_COURSE_MCP,
    SAMPLE_COURSE_NO_LESSONS,
    SAMPLE_COURSE_NO_LINK,
    create_chromadb_course_result,
    create_empty_chromadb_result,
)


class TestCourseOutlineTool:
    """Test suite for CourseOutlineTool.execute() method"""

    def test_execute_with_valid_course_name(self, course_outline_tool, sample_chromadb_course_result):
        """Test successful course outline retrieval with valid course name"""
        # Mock the course_catalog.query() to return valid result
        course_outline_tool.store.course_catalog.query.return_value = sample_chromadb_course_result

        # Execute the tool
        result = course_outline_tool.execute(course_name="MCP")

        # Verify query was called correctly
        course_outline_tool.store.course_catalog.query.assert_called_once_with(query_texts=["MCP"], n_results=1)

        # Verify result contains expected content
        assert "Course: Introduction to MCP Servers" in result
        assert "Course Link: https://example.com/mcp-course" in result
        assert "Lessons (3 total):" in result
        assert "Lesson 1: Getting Started with MCP" in result
        assert "Lesson 2: Building Your First Server" in result
        assert "Lesson 3: Advanced MCP Patterns" in result

        # Verify sources are tracked
        assert len(course_outline_tool.last_sources) == 1
        assert course_outline_tool.last_sources[0].text == "Introduction to MCP Servers"
        assert course_outline_tool.last_sources[0].url == "https://example.com/mcp-course"

    def test_execute_with_partial_course_name(self, course_outline_tool, sample_chromadb_course_result):
        """Test semantic search finds course with partial name match"""
        # Mock the semantic search to find full course title from partial
        course_outline_tool.store.course_catalog.query.return_value = sample_chromadb_course_result

        # Execute with partial name
        result = course_outline_tool.execute(course_name="Introduction")

        # Verify semantic search was called with partial name
        course_outline_tool.store.course_catalog.query.assert_called_once_with(
            query_texts=["Introduction"], n_results=1
        )

        # Verify correct course was found
        assert "Course: Introduction to MCP Servers" in result
        assert "Lessons (3 total):" in result

    def test_execute_with_nonexistent_course(self, course_outline_tool, sample_chromadb_empty_result):
        """Test error handling when course doesn't exist - THIS SHOULD CURRENTLY FAIL"""
        # Mock query to return empty results
        course_outline_tool.store.course_catalog.query.return_value = sample_chromadb_empty_result

        # Execute with nonexistent course name
        result = course_outline_tool.execute(course_name="NonexistentCourse")

        # Should return error message (will currently crash with IndexError)
        assert "No course found matching 'NonexistentCourse'" in result
        assert len(course_outline_tool.last_sources) == 0

    def test_execute_with_empty_query_results(self, course_outline_tool):
        """Test handling of truly empty query results - THIS SHOULD CURRENTLY FAIL"""
        # Create completely empty ChromaDB result structure
        empty_result = {
            "documents": [[]],  # Empty list at index 0
            "metadatas": [[]],  # Empty list at index 0
            "distances": [[]],
        }

        course_outline_tool.store.course_catalog.query.return_value = empty_result

        # Execute - this should handle empty lists gracefully
        result = course_outline_tool.execute(course_name="Test")

        # Should return error message, not crash
        assert "No course found matching 'Test'" in result

    def test_execute_with_malformed_lessons_json(self, course_outline_tool):
        """Test error handling with malformed JSON in lessons_json field"""
        # Create result with invalid JSON
        malformed_result = {
            "documents": [["Test Course"]],
            "metadatas": [
                [
                    {
                        "title": "Test Course",
                        "instructor": "Test Instructor",
                        "course_link": "https://example.com/test",
                        "lessons_json": "{ invalid json",  # Malformed JSON
                        "lesson_count": 1,
                    }
                ]
            ],
            "distances": [[0.1]],
        }

        course_outline_tool.store.course_catalog.query.return_value = malformed_result

        # Execute - should catch JSON parsing error
        result = course_outline_tool.execute(course_name="Test")

        # Should return error message
        assert "Error retrieving course outline" in result

    def test_execute_with_missing_course_link(self, course_outline_tool):
        """Test output when course_link is missing"""
        # Create result without course_link
        result_no_link = create_chromadb_course_result(SAMPLE_COURSE_NO_LINK)
        course_outline_tool.store.course_catalog.query.return_value = result_no_link

        # Execute
        result = course_outline_tool.execute(course_name="Test")

        # Verify output doesn't include course link line
        assert "Course: Course Without Link" in result
        assert "Course Link:" not in result  # Should skip this line when None
        assert "Lessons (1 total):" in result

        # Verify source tracked with None URL
        assert len(course_outline_tool.last_sources) == 1
        assert course_outline_tool.last_sources[0].url is None

    def test_execute_with_no_lessons(self, course_outline_tool):
        """Test output when course has no lessons"""
        # Create result for course with no lessons
        result_no_lessons = create_chromadb_course_result(SAMPLE_COURSE_NO_LESSONS)
        course_outline_tool.store.course_catalog.query.return_value = result_no_lessons

        # Execute
        result = course_outline_tool.execute(course_name="Empty")

        # Verify output shows empty lessons list
        assert "Course: Empty Course" in result
        assert "Lessons (0 total):" in result
        # Should not have any lesson lines
        assert "Lesson 1:" not in result

    def test_execute_with_chromadb_exception(self, course_outline_tool):
        """Test exception handling when ChromaDB query fails"""
        # Mock query to raise an exception
        course_outline_tool.store.course_catalog.query.side_effect = Exception("Database connection error")

        # Execute - should catch exception and return error message
        result = course_outline_tool.execute(course_name="Test")

        # Should return error message, not crash
        assert "Error retrieving course outline" in result
        assert "Database connection error" in result

    def test_get_tool_definition(self, course_outline_tool):
        """Test that tool definition is correctly formatted"""
        definition = course_outline_tool.get_tool_definition()

        # Verify structure
        assert definition["name"] == "get_course_outline"
        assert "description" in definition
        assert "input_schema" in definition

        # Verify input schema
        schema = definition["input_schema"]
        assert schema["type"] == "object"
        assert "course_name" in schema["properties"]
        assert "course_name" in schema["required"]

        # Verify description mentions partial matches
        course_name_desc = schema["properties"]["course_name"]["description"]
        assert "partial matches" in course_name_desc.lower()
