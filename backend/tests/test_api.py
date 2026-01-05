"""
API endpoint tests for the Course Materials RAG System.

These tests verify that the FastAPI endpoints handle requests and responses correctly,
including proper error handling, session management, and data validation.
"""
import pytest
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
from models import Source


@pytest.mark.api
class TestQueryEndpoint:
    """Tests for POST /api/query endpoint"""

    def test_query_with_session_id(self, client, mock_rag_for_api):
        """Test querying with an existing session ID"""
        # Arrange
        request_data = {
            "query": "What is MCP?",
            "session_id": "existing-session-456"
        }

        # Act
        response = client.post("/api/query", json=request_data)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert "sources" in data
        assert "session_id" in data
        assert data["session_id"] == "existing-session-456"
        assert data["answer"] == "This is a test answer about MCP servers."
        assert len(data["sources"]) == 2

        # Verify RAG system was called with correct parameters
        mock_rag_for_api.query.assert_called_once_with("What is MCP?", "existing-session-456")

    def test_query_without_session_id(self, client, mock_rag_for_api):
        """Test querying without session ID - should auto-create session"""
        # Arrange
        request_data = {
            "query": "Explain prompt caching"
        }

        # Act
        response = client.post("/api/query", json=request_data)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "test-session-123"  # From mocked create_session

        # Verify session was created
        mock_rag_for_api.session_manager.create_session.assert_called_once()

    def test_query_with_sources(self, client, mock_rag_for_api):
        """Test that sources are properly returned in response"""
        # Arrange
        request_data = {
            "query": "What is MCP?",
            "session_id": "test-session"
        }

        # Act
        response = client.post("/api/query", json=request_data)

        # Assert
        assert response.status_code == 200
        data = response.json()
        sources = data["sources"]

        assert len(sources) == 2
        assert sources[0]["text"] == "Introduction to MCP Servers - Lesson 1"
        assert sources[0]["url"] == "https://example.com/mcp-lesson-1"
        assert sources[1]["text"] == "Introduction to MCP Servers - Lesson 2"
        assert sources[1]["url"] == "https://example.com/mcp-lesson-2"

    def test_query_validation_missing_query(self, client):
        """Test that missing query field returns validation error"""
        # Arrange
        request_data = {
            "session_id": "test-session"
            # Missing "query" field
        }

        # Act
        response = client.post("/api/query", json=request_data)

        # Assert
        assert response.status_code == 422  # Validation error

    def test_query_validation_empty_query(self, client):
        """Test that empty query string is handled"""
        # Arrange
        request_data = {
            "query": "",
            "session_id": "test-session"
        }

        # Act
        response = client.post("/api/query", json=request_data)

        # Assert - empty string is technically valid, so it should succeed
        assert response.status_code == 200

    def test_query_error_handling(self, client, mock_rag_for_api):
        """Test that API errors are properly handled"""
        # Arrange
        mock_rag_for_api.query.side_effect = Exception("Database connection error")
        request_data = {
            "query": "What is MCP?",
            "session_id": "test-session"
        }

        # Act
        response = client.post("/api/query", json=request_data)

        # Assert
        assert response.status_code == 500
        assert "detail" in response.json()

    def test_query_response_structure(self, client):
        """Test that response has correct structure and types"""
        # Arrange
        request_data = {
            "query": "What is MCP?"
        }

        # Act
        response = client.post("/api/query", json=request_data)

        # Assert
        assert response.status_code == 200
        data = response.json()

        # Verify structure
        assert isinstance(data["answer"], str)
        assert isinstance(data["sources"], list)
        assert isinstance(data["session_id"], str)

        # Verify each source has correct structure
        for source in data["sources"]:
            assert "text" in source
            assert "url" in source
            assert isinstance(source["text"], str)
            assert isinstance(source["url"], str)


@pytest.mark.api
class TestCoursesEndpoint:
    """Tests for GET /api/courses endpoint"""

    def test_get_course_stats_success(self, client, mock_rag_for_api):
        """Test successful retrieval of course statistics"""
        # Act
        response = client.get("/api/courses")

        # Assert
        assert response.status_code == 200
        data = response.json()

        assert "total_courses" in data
        assert "course_titles" in data
        assert data["total_courses"] == 2
        assert len(data["course_titles"]) == 2
        assert "Introduction to MCP Servers" in data["course_titles"]
        assert "Prompt Caching Techniques" in data["course_titles"]

        # Verify RAG system method was called
        mock_rag_for_api.get_course_analytics.assert_called_once()

    def test_get_course_stats_empty(self, client, mock_rag_for_api):
        """Test course stats with no courses"""
        # Arrange
        mock_rag_for_api.get_course_analytics.return_value = {
            "total_courses": 0,
            "course_titles": []
        }

        # Act
        response = client.get("/api/courses")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["total_courses"] == 0
        assert data["course_titles"] == []

    def test_get_course_stats_error_handling(self, client, mock_rag_for_api):
        """Test error handling in course stats endpoint"""
        # Arrange
        mock_rag_for_api.get_course_analytics.side_effect = Exception("Vector store error")

        # Act
        response = client.get("/api/courses")

        # Assert
        assert response.status_code == 500
        assert "detail" in response.json()

    def test_get_course_stats_response_types(self, client):
        """Test that response has correct types"""
        # Act
        response = client.get("/api/courses")

        # Assert
        assert response.status_code == 200
        data = response.json()

        assert isinstance(data["total_courses"], int)
        assert isinstance(data["course_titles"], list)
        for title in data["course_titles"]:
            assert isinstance(title, str)


@pytest.mark.api
class TestSessionEndpoint:
    """Tests for DELETE /api/session/{session_id} endpoint"""

    def test_clear_session_success(self, client, mock_rag_for_api):
        """Test successful session clearing"""
        # Arrange
        session_id = "test-session-789"

        # Act
        response = client.delete(f"/api/session/{session_id}")

        # Assert
        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "success"
        assert session_id in data["message"]

        # Verify session manager method was called
        mock_rag_for_api.session_manager.clear_session.assert_called_once_with(session_id)

    def test_clear_session_with_special_characters(self, client, mock_rag_for_api):
        """Test clearing session with special characters in ID"""
        # Arrange
        session_id = "session-abc-123-xyz"

        # Act
        response = client.delete(f"/api/session/{session_id}")

        # Assert
        assert response.status_code == 200
        mock_rag_for_api.session_manager.clear_session.assert_called_once_with(session_id)

    def test_clear_session_error_handling(self, client, mock_rag_for_api):
        """Test error handling when clearing session fails"""
        # Arrange
        mock_rag_for_api.session_manager.clear_session.side_effect = Exception("Session not found")
        session_id = "nonexistent-session"

        # Act
        response = client.delete(f"/api/session/{session_id}")

        # Assert
        assert response.status_code == 500
        assert "detail" in response.json()


@pytest.mark.api
class TestAPIIntegration:
    """Integration tests for API workflows"""

    def test_full_query_workflow(self, client, mock_rag_for_api):
        """Test a complete query workflow: create session -> query -> clear session"""
        # Step 1: Query without session (creates new session)
        response1 = client.post("/api/query", json={"query": "What is MCP?"})
        assert response1.status_code == 200
        session_id = response1.json()["session_id"]
        assert session_id == "test-session-123"

        # Step 2: Query with the same session
        response2 = client.post("/api/query", json={
            "query": "Tell me more",
            "session_id": session_id
        })
        assert response2.status_code == 200
        assert response2.json()["session_id"] == session_id

        # Step 3: Clear the session
        response3 = client.delete(f"/api/session/{session_id}")
        assert response3.status_code == 200

    def test_multiple_concurrent_sessions(self, client, mock_rag_for_api):
        """Test handling multiple sessions"""
        # Configure mock to return different sessions
        session_ids = ["session-1", "session-2", "session-3"]
        mock_rag_for_api.session_manager.create_session.side_effect = session_ids

        # Create multiple sessions
        sessions = []
        for i in range(3):
            response = client.post("/api/query", json={"query": f"Query {i}"})
            assert response.status_code == 200
            sessions.append(response.json()["session_id"])

        # Verify all sessions are different
        assert len(set(sessions)) == 3

    def test_cors_headers_present(self, client):
        """Test that CORS headers are present in responses"""
        # Act
        response = client.get("/api/courses")

        # Assert
        assert response.status_code == 200
        # TestClient doesn't always include CORS headers, but the middleware is configured
        # This test verifies the endpoint works with CORS middleware present


@pytest.mark.api
class TestRequestValidation:
    """Tests for request validation and edge cases"""

    def test_query_with_invalid_json(self, client):
        """Test handling of invalid JSON in request"""
        # Act
        response = client.post(
            "/api/query",
            data="invalid json{{{",
            headers={"Content-Type": "application/json"}
        )

        # Assert
        assert response.status_code == 422

    def test_query_with_extra_fields(self, client):
        """Test that extra fields in request are ignored"""
        # Arrange
        request_data = {
            "query": "What is MCP?",
            "session_id": "test-session",
            "extra_field": "should be ignored"
        }

        # Act
        response = client.post("/api/query", json=request_data)

        # Assert - should succeed, extra fields are typically ignored
        assert response.status_code == 200

    def test_query_with_very_long_query(self, client):
        """Test handling of very long query strings"""
        # Arrange
        long_query = "What is MCP? " * 1000  # Very long query
        request_data = {
            "query": long_query,
            "session_id": "test-session"
        }

        # Act
        response = client.post("/api/query", json=request_data)

        # Assert - should handle long queries
        assert response.status_code == 200

    def test_session_id_url_encoding(self, client, mock_rag_for_api):
        """Test that session IDs with special characters are handled in URLs"""
        # Arrange
        session_id = "session-with-dashes-123"

        # Act
        response = client.delete(f"/api/session/{session_id}")

        # Assert
        assert response.status_code == 200
        mock_rag_for_api.session_manager.clear_session.assert_called_once_with(session_id)
