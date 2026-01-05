"""Pytest configuration and shared fixtures"""

import os
import sys
from typing import Any, Dict, List
from unittest.mock import MagicMock, Mock, patch

import pytest

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai_generator import AIGenerator
from models import Course, Lesson, Source
from rag_system import RAGSystem
from search_tools import CourseOutlineTool, CourseSearchTool, ToolManager
from session_manager import SessionManager
from tests.fixtures import (
    SAMPLE_COURSE_MCP,
    SAMPLE_SEARCH_RESULTS_VALID,
    SAMPLE_SOURCES,
    create_chromadb_course_result,
    create_empty_chromadb_result,
)
from vector_store import SearchResults, VectorStore

# FastAPI and testing imports
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def mock_chroma_collection():
    """Create a mock ChromaDB collection"""
    collection = Mock()
    collection.query = Mock()
    collection.get = Mock()
    collection.add = Mock()
    return collection


@pytest.fixture
def mock_vector_store(mock_chroma_collection):
    """Create a mock VectorStore with mocked collections"""
    store = Mock(spec=VectorStore)
    store.course_catalog = mock_chroma_collection
    store.course_content = mock_chroma_collection
    store.max_results = 5

    # Mock methods
    store.search = Mock(return_value=SAMPLE_SEARCH_RESULTS_VALID)
    store.get_course_link = Mock(return_value="https://example.com/course")
    store.get_lesson_link = Mock(return_value="https://example.com/lesson")
    store.add_course_metadata = Mock()
    store.add_course_content = Mock()

    return store


@pytest.fixture
def course_search_tool(mock_vector_store):
    """Create a CourseSearchTool with mocked vector store"""
    return CourseSearchTool(mock_vector_store)


@pytest.fixture
def course_outline_tool(mock_vector_store):
    """Create a CourseOutlineTool with mocked vector store"""
    return CourseOutlineTool(mock_vector_store)


@pytest.fixture
def tool_manager(course_search_tool, course_outline_tool):
    """Create a ToolManager with registered tools"""
    manager = ToolManager()
    manager.register_tool(course_search_tool)
    manager.register_tool(course_outline_tool)
    return manager


@pytest.fixture
def mock_anthropic_client():
    """Create a mock Anthropic client"""
    client = Mock()
    client.messages = Mock()
    client.messages.create = Mock()
    return client


@pytest.fixture
def ai_generator(mock_anthropic_client):
    """Create an AIGenerator with mocked Anthropic client"""
    gen = AIGenerator(api_key="test_key", model="claude-sonnet-4")
    gen.client = mock_anthropic_client
    return gen


@pytest.fixture
def session_manager():
    """Create a SessionManager instance"""
    return SessionManager(max_history=2)


@pytest.fixture
def mock_config():
    """Create a mock configuration object"""
    config = Mock()
    config.CHUNK_SIZE = 800
    config.CHUNK_OVERLAP = 100
    config.CHROMA_PATH = "/tmp/test_chroma"
    config.EMBEDDING_MODEL = "all-MiniLM-L6-v2"
    config.MAX_RESULTS = 5
    config.ANTHROPIC_API_KEY = "test_key"
    config.ANTHROPIC_MODEL = "claude-sonnet-4"
    config.MAX_HISTORY = 2
    return config


@pytest.fixture
def mock_rag_system(mock_config, mock_vector_store, ai_generator, session_manager, tool_manager):
    """Create a RAGSystem with all mocked dependencies"""
    system = Mock(spec=RAGSystem)
    system.config = mock_config
    system.vector_store = mock_vector_store
    system.ai_generator = ai_generator
    system.session_manager = session_manager
    system.tool_manager = tool_manager
    system.search_tool = tool_manager.tools.get("search_course_content")
    system.outline_tool = tool_manager.tools.get("get_course_outline")

    # Mock query method
    system.query = Mock(return_value=("Test response", []))

    return system


@pytest.fixture
def sample_search_results_valid():
    """Valid search results fixture"""
    return SearchResults(
        documents=["Document 1", "Document 2"],
        metadata=[
            {"course_title": "Test Course", "lesson_number": 1},
            {"course_title": "Test Course", "lesson_number": 2},
        ],
        distances=[0.1, 0.2],
    )


@pytest.fixture
def sample_search_results_empty():
    """Empty search results fixture"""
    return SearchResults(documents=[], metadata=[], distances=[])


@pytest.fixture
def sample_search_results_error():
    """Error search results fixture"""
    return SearchResults(documents=[], metadata=[], distances=[], error="Test error message")


@pytest.fixture
def sample_course_mcp():
    """Sample MCP course fixture"""
    return SAMPLE_COURSE_MCP


@pytest.fixture
def sample_chromadb_course_result():
    """Sample ChromaDB course result"""
    return create_chromadb_course_result(SAMPLE_COURSE_MCP)


@pytest.fixture
def sample_chromadb_empty_result():
    """Sample empty ChromaDB result"""
    return create_empty_chromadb_result()


# ============================================================================
# API Testing Fixtures
# ============================================================================

@pytest.fixture
def test_app():
    """
    Create a test FastAPI app without static file mounting.
    This avoids issues with the frontend directory not existing in tests.
    """
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
    from typing import List, Optional

    # Import models
    from models import Source

    # Create test app
    app = FastAPI(title="Course Materials RAG System - Test", root_path="")

    # Enable CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Request/Response models
    class QueryRequest(BaseModel):
        query: str
        session_id: Optional[str] = None

    class QueryResponse(BaseModel):
        answer: str
        sources: List[Source]
        session_id: str

    class CourseStats(BaseModel):
        total_courses: int
        course_titles: List[str]

    # Store rag_system reference for mocking
    app.state.rag_system = None

    # Define endpoints
    @app.post("/api/query", response_model=QueryResponse)
    async def query_documents(request: QueryRequest):
        try:
            session_id = request.session_id
            if not session_id:
                session_id = app.state.rag_system.session_manager.create_session()

            answer, sources = app.state.rag_system.query(request.query, session_id)

            return QueryResponse(
                answer=answer,
                sources=sources,
                session_id=session_id
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/courses", response_model=CourseStats)
    async def get_course_stats():
        try:
            analytics = app.state.rag_system.get_course_analytics()
            return CourseStats(
                total_courses=analytics["total_courses"],
                course_titles=analytics["course_titles"]
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.delete("/api/session/{session_id}")
    async def clear_session(session_id: str):
        try:
            app.state.rag_system.session_manager.clear_session(session_id)
            return {"status": "success", "message": f"Session {session_id} cleared"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return app


@pytest.fixture
def mock_rag_for_api(mock_config, mock_vector_store):
    """
    Create a fully mocked RAGSystem for API testing.
    This fixture provides a complete mock with all necessary methods.
    """
    rag = Mock(spec=RAGSystem)

    # Mock session manager
    session_manager = Mock(spec=SessionManager)
    session_manager.create_session = Mock(return_value="test-session-123")
    session_manager.clear_session = Mock()
    rag.session_manager = session_manager

    # Mock query method - returns answer and sources
    rag.query = Mock(return_value=("This is a test answer about MCP servers.", SAMPLE_SOURCES))

    # Mock course analytics
    rag.get_course_analytics = Mock(return_value={
        "total_courses": 2,
        "course_titles": ["Introduction to MCP Servers", "Prompt Caching Techniques"]
    })

    # Mock vector store
    rag.vector_store = mock_vector_store

    return rag


@pytest.fixture
def client(test_app, mock_rag_for_api):
    """
    Create a TestClient with mocked RAG system.
    This client can be used to test API endpoints without dependencies.
    """
    test_app.state.rag_system = mock_rag_for_api
    return TestClient(test_app)
