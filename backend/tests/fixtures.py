"""Test fixtures and sample data for RAG system tests"""
import json
from typing import Dict, Any, List
from models import Course, Lesson, Source, CourseChunk
from vector_store import SearchResults


# Sample course data
SAMPLE_COURSE_MCP = Course(
    title="Introduction to MCP Servers",
    course_link="https://example.com/mcp-course",
    instructor="John Doe",
    lessons=[
        Lesson(lesson_number=1, title="Getting Started with MCP", lesson_link="https://example.com/mcp-lesson-1"),
        Lesson(lesson_number=2, title="Building Your First Server", lesson_link="https://example.com/mcp-lesson-2"),
        Lesson(lesson_number=3, title="Advanced MCP Patterns", lesson_link="https://example.com/mcp-lesson-3"),
    ]
)

SAMPLE_COURSE_PROMPT_CACHING = Course(
    title="Prompt Caching Techniques",
    course_link="https://example.com/caching-course",
    instructor="Jane Smith",
    lessons=[
        Lesson(lesson_number=1, title="Introduction to Caching", lesson_link="https://example.com/caching-lesson-1"),
        Lesson(lesson_number=2, title="Implementation Strategies", lesson_link="https://example.com/caching-lesson-2"),
    ]
)

SAMPLE_COURSE_NO_LINK = Course(
    title="Course Without Link",
    course_link=None,
    instructor="Test Instructor",
    lessons=[
        Lesson(lesson_number=1, title="First Lesson", lesson_link=None),
    ]
)

SAMPLE_COURSE_NO_LESSONS = Course(
    title="Empty Course",
    course_link="https://example.com/empty-course",
    instructor="Empty Instructor",
    lessons=[]
)


# Sample course chunks
SAMPLE_CHUNKS_MCP = [
    CourseChunk(
        content="Course Introduction to MCP Servers Lesson 1 content: MCP (Model Context Protocol) is a standardized way to connect AI models to external data sources.",
        course_title="Introduction to MCP Servers",
        lesson_number=1,
        chunk_index=0
    ),
    CourseChunk(
        content="Course Introduction to MCP Servers Lesson 1 content: MCP servers provide a secure and efficient way to access data without exposing sensitive information.",
        course_title="Introduction to MCP Servers",
        lesson_number=1,
        chunk_index=1
    ),
    CourseChunk(
        content="Course Introduction to MCP Servers Lesson 2 content: Building an MCP server requires understanding the protocol specification and implementing the required endpoints.",
        course_title="Introduction to MCP Servers",
        lesson_number=2,
        chunk_index=2
    ),
]


# Sample ChromaDB query results
def create_chromadb_course_result(course: Course) -> Dict[str, Any]:
    """Create a ChromaDB-style query result for a course"""
    lessons_metadata = []
    for lesson in course.lessons:
        lessons_metadata.append({
            "lesson_number": lesson.lesson_number,
            "lesson_title": lesson.title,
            "lesson_link": lesson.lesson_link
        })

    return {
        'documents': [[course.title]],
        'metadatas': [[{
            'title': course.title,
            'instructor': course.instructor,
            'course_link': course.course_link,
            'lessons_json': json.dumps(lessons_metadata),
            'lesson_count': len(course.lessons)
        }]],
        'distances': [[0.1]]
    }


def create_empty_chromadb_result() -> Dict[str, Any]:
    """Create an empty ChromaDB-style query result"""
    return {
        'documents': [[]],
        'metadatas': [[]],
        'distances': [[]]
    }


def create_chromadb_content_result(chunks: List[CourseChunk]) -> Dict[str, Any]:
    """Create a ChromaDB-style query result for content search"""
    documents = [chunk.content for chunk in chunks]
    metadatas = [{
        'course_title': chunk.course_title,
        'lesson_number': chunk.lesson_number,
        'chunk_index': chunk.chunk_index
    } for chunk in chunks]
    distances = [0.1 * (i + 1) for i in range(len(chunks))]

    return {
        'documents': [documents],
        'metadatas': [metadatas],
        'distances': [distances]
    }


# Sample SearchResults objects
SAMPLE_SEARCH_RESULTS_VALID = SearchResults(
    documents=[
        "Course Introduction to MCP Servers Lesson 1 content: MCP is a protocol for connecting AI models.",
        "Course Introduction to MCP Servers Lesson 2 content: Building MCP servers is straightforward."
    ],
    metadata=[
        {'course_title': 'Introduction to MCP Servers', 'lesson_number': 1, 'chunk_index': 0},
        {'course_title': 'Introduction to MCP Servers', 'lesson_number': 2, 'chunk_index': 0}
    ],
    distances=[0.1, 0.2]
)

SAMPLE_SEARCH_RESULTS_EMPTY = SearchResults(
    documents=[],
    metadata=[],
    distances=[]
)

SAMPLE_SEARCH_RESULTS_ERROR = SearchResults(
    documents=[],
    metadata=[],
    distances=[],
    error="Search failed: Connection error"
)


# Sample tool execution results
SAMPLE_TOOL_RESULT_SEARCH = """[Introduction to MCP Servers - Lesson 1]
MCP (Model Context Protocol) is a standardized way to connect AI models to external data sources.

[Introduction to MCP Servers - Lesson 2]
Building an MCP server requires understanding the protocol specification."""

SAMPLE_TOOL_RESULT_OUTLINE = """Course: Introduction to MCP Servers
Course Link: https://example.com/mcp-course

Lessons (3 total):
  Lesson 1: Getting Started with MCP
  Lesson 2: Building Your First Server
  Lesson 3: Advanced MCP Patterns"""


# Sample Anthropic API responses
def create_anthropic_text_response(text: str) -> Any:
    """Create a mock Anthropic API response with text"""
    from unittest.mock import Mock

    response = Mock()
    response.stop_reason = "end_turn"

    content_block = Mock()
    content_block.text = text
    content_block.type = "text"

    response.content = [content_block]
    return response


def create_anthropic_tool_use_response(tool_name: str, tool_input: Dict[str, Any]) -> Any:
    """Create a mock Anthropic API response with tool use"""
    from unittest.mock import Mock

    response = Mock()
    response.stop_reason = "tool_use"

    tool_block = Mock()
    tool_block.type = "tool_use"
    tool_block.name = tool_name
    tool_block.input = tool_input
    tool_block.id = "tool_use_123"

    response.content = [tool_block]
    return response


# Sample sources
SAMPLE_SOURCES = [
    Source(text="Introduction to MCP Servers - Lesson 1", url="https://example.com/mcp-lesson-1"),
    Source(text="Introduction to MCP Servers - Lesson 2", url="https://example.com/mcp-lesson-2"),
]
