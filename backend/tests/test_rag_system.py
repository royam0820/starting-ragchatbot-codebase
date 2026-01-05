"""Tests for RAGSystem integration"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from rag_system import RAGSystem
from vector_store import SearchResults
from models import Source
from tests.fixtures import (
    create_anthropic_text_response,
    create_anthropic_tool_use_response,
    SAMPLE_SOURCES
)


class TestRAGSystem:
    """Integration tests for RAGSystem.query()"""

    @patch('rag_system.DocumentProcessor')
    @patch('rag_system.VectorStore')
    @patch('rag_system.AIGenerator')
    @patch('rag_system.SessionManager')
    @patch('rag_system.CourseSearchTool')
    @patch('rag_system.CourseOutlineTool')
    def test_query_without_session(self, mock_outline_tool, mock_search_tool,
                                   mock_session_mgr, mock_ai_gen, mock_vector_store,
                                   mock_doc_proc, mock_config):
        """Test query without session_id"""
        # Create RAG system with mocked components
        rag = RAGSystem(mock_config)

        # Mock AI generator response
        rag.ai_generator.generate_response = Mock(return_value="Test response")

        # Mock tool manager
        rag.tool_manager.get_last_sources = Mock(return_value=[])

        # Query without session
        answer, sources = rag.query("Test question", session_id=None)

        # Verify response
        assert answer == "Test response"
        assert sources == []

        # Verify AI generator called without history
        rag.ai_generator.generate_response.assert_called_once()
        call_args = rag.ai_generator.generate_response.call_args
        assert call_args[1].get('conversation_history') is None

    @patch('rag_system.DocumentProcessor')
    @patch('rag_system.VectorStore')
    @patch('rag_system.AIGenerator')
    @patch('rag_system.SessionManager')
    @patch('rag_system.CourseSearchTool')
    @patch('rag_system.CourseOutlineTool')
    def test_query_with_session(self, mock_outline_tool, mock_search_tool,
                               mock_session_mgr, mock_ai_gen, mock_vector_store,
                               mock_doc_proc, mock_config):
        """Test query with session_id maintains history"""
        # Create RAG system
        rag = RAGSystem(mock_config)

        # Mock session manager
        test_history = "Previous conversation"
        rag.session_manager.get_conversation_history = Mock(return_value=test_history)
        rag.session_manager.add_exchange = Mock()

        # Mock AI response
        rag.ai_generator.generate_response = Mock(return_value="Response with history")

        # Mock tool manager
        rag.tool_manager.get_last_sources = Mock(return_value=[])

        # Query with session
        answer, sources = rag.query("Follow-up question", session_id="test_session")

        # Verify history was retrieved
        rag.session_manager.get_conversation_history.assert_called_once_with("test_session")

        # Verify AI received history
        call_args = rag.ai_generator.generate_response.call_args
        assert call_args[1].get('conversation_history') == test_history

        # Verify exchange was added to history
        rag.session_manager.add_exchange.assert_called_once_with(
            "test_session",
            "Follow-up question",
            "Response with history"
        )

    @patch('rag_system.DocumentProcessor')
    @patch('rag_system.VectorStore')
    @patch('rag_system.AIGenerator')
    @patch('rag_system.SessionManager')
    @patch('rag_system.CourseSearchTool')
    @patch('rag_system.CourseOutlineTool')
    def test_query_content_search_flow(self, mock_outline_tool, mock_search_tool,
                                       mock_session_mgr, mock_ai_gen, mock_vector_store,
                                       mock_doc_proc, mock_config):
        """Test full content search flow"""
        # Create RAG system
        rag = RAGSystem(mock_config)

        # Mock AI to trigger tool use then return response
        rag.ai_generator.generate_response = Mock(return_value="Content about MCP")

        # Mock tool manager sources
        test_sources = SAMPLE_SOURCES
        rag.tool_manager.get_last_sources = Mock(return_value=test_sources)
        rag.tool_manager.reset_sources = Mock()

        # Query
        answer, sources = rag.query("What is MCP?", session_id=None)

        # Verify answer
        assert answer == "Content about MCP"

        # Verify sources were retrieved
        rag.tool_manager.get_last_sources.assert_called_once()
        assert sources == test_sources

        # Verify sources were reset after retrieval
        rag.tool_manager.reset_sources.assert_called_once()

    @patch('rag_system.DocumentProcessor')
    @patch('rag_system.VectorStore')
    @patch('rag_system.AIGenerator')
    @patch('rag_system.SessionManager')
    @patch('rag_system.CourseSearchTool')
    @patch('rag_system.CourseOutlineTool')
    def test_query_outline_tool_flow(self, mock_outline_tool, mock_search_tool,
                                     mock_session_mgr, mock_ai_gen, mock_vector_store,
                                     mock_doc_proc, mock_config):
        """Test outline query flow"""
        # Create RAG system
        rag = RAGSystem(mock_config)

        # Mock AI response for outline query
        rag.ai_generator.generate_response = Mock(return_value="The course has 3 lessons...")

        # Mock sources
        outline_source = [Source(text="MCP Course", url="https://example.com/mcp")]
        rag.tool_manager.get_last_sources = Mock(return_value=outline_source)
        rag.tool_manager.reset_sources = Mock()

        # Query
        answer, sources = rag.query("What lessons are in the MCP course?", session_id=None)

        # Verify response
        assert answer == "The course has 3 lessons..."
        assert sources == outline_source

        # Verify tool definitions were passed to AI
        call_args = rag.ai_generator.generate_response.call_args
        assert 'tools' in call_args[1]

    @patch('rag_system.DocumentProcessor')
    @patch('rag_system.VectorStore')
    @patch('rag_system.AIGenerator')
    @patch('rag_system.SessionManager')
    @patch('rag_system.CourseSearchTool')
    @patch('rag_system.CourseOutlineTool')
    def test_query_with_tool_execution_failure(self, mock_outline_tool, mock_search_tool,
                                               mock_session_mgr, mock_ai_gen, mock_vector_store,
                                               mock_doc_proc, mock_config):
        """Test handling when tool execution returns error"""
        # Create RAG system
        rag = RAGSystem(mock_config)

        # Mock AI to handle error and return message
        rag.ai_generator.generate_response = Mock(return_value="I couldn't find that information")

        # Mock empty sources (tool failed)
        rag.tool_manager.get_last_sources = Mock(return_value=[])
        rag.tool_manager.reset_sources = Mock()

        # Query
        answer, sources = rag.query("Search for nonexistent content", session_id=None)

        # Should not crash, should return error message
        assert answer == "I couldn't find that information"
        assert sources == []

    @patch('rag_system.DocumentProcessor')
    @patch('rag_system.VectorStore')
    @patch('rag_system.AIGenerator')
    @patch('rag_system.SessionManager')
    @patch('rag_system.CourseSearchTool')
    @patch('rag_system.CourseOutlineTool')
    def test_query_with_ai_generator_exception(self, mock_outline_tool, mock_search_tool,
                                               mock_session_mgr, mock_ai_gen, mock_vector_store,
                                               mock_doc_proc, mock_config):
        """Test handling when AI generator raises exception"""
        # Create RAG system
        rag = RAGSystem(mock_config)

        # Mock AI to raise exception
        rag.ai_generator.generate_response = Mock(side_effect=Exception("API error"))

        # Query - should propagate exception
        with pytest.raises(Exception) as exc_info:
            rag.query("Test question", session_id=None)

        assert "API error" in str(exc_info.value)

    @patch('rag_system.DocumentProcessor')
    @patch('rag_system.VectorStore')
    @patch('rag_system.AIGenerator')
    @patch('rag_system.SessionManager')
    @patch('rag_system.CourseSearchTool')
    @patch('rag_system.CourseOutlineTool')
    def test_query_general_knowledge_no_tools(self, mock_outline_tool, mock_search_tool,
                                             mock_session_mgr, mock_ai_gen, mock_vector_store,
                                             mock_doc_proc, mock_config):
        """Test general knowledge question doesn't use tools"""
        # Create RAG system
        rag = RAGSystem(mock_config)

        # Mock AI to respond without tools
        rag.ai_generator.generate_response = Mock(return_value="General knowledge answer")

        # Mock empty sources (no tool used)
        rag.tool_manager.get_last_sources = Mock(return_value=[])
        rag.tool_manager.reset_sources = Mock()

        # Query general knowledge
        answer, sources = rag.query("What is 2+2?", session_id=None)

        # Should have answer but no sources
        assert answer == "General knowledge answer"
        assert sources == []

    @patch('rag_system.DocumentProcessor')
    @patch('rag_system.VectorStore')
    @patch('rag_system.AIGenerator')
    @patch('rag_system.SessionManager')
    @patch('rag_system.CourseSearchTool')
    @patch('rag_system.CourseOutlineTool')
    def test_query_with_multiple_sessions(self, mock_outline_tool, mock_search_tool,
                                          mock_session_mgr, mock_ai_gen, mock_vector_store,
                                          mock_doc_proc, mock_config):
        """Test that multiple sessions maintain separate histories"""
        # Create RAG system
        rag = RAGSystem(mock_config)

        # Mock session manager with different histories
        def get_history(session_id):
            if session_id == "session1":
                return "Session 1 history"
            elif session_id == "session2":
                return "Session 2 history"
            return None

        rag.session_manager.get_conversation_history = Mock(side_effect=get_history)
        rag.session_manager.add_exchange = Mock()

        # Mock AI
        rag.ai_generator.generate_response = Mock(return_value="Response")
        rag.tool_manager.get_last_sources = Mock(return_value=[])
        rag.tool_manager.reset_sources = Mock()

        # Query session 1
        rag.query("Question 1", session_id="session1")
        call1_history = rag.ai_generator.generate_response.call_args[1].get('conversation_history')

        # Query session 2
        rag.query("Question 2", session_id="session2")
        call2_history = rag.ai_generator.generate_response.call_args[1].get('conversation_history')

        # Verify different histories were used
        assert call1_history != call2_history
        assert call1_history == "Session 1 history"
        assert call2_history == "Session 2 history"
