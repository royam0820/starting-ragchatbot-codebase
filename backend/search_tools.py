from typing import Dict, Any, Optional, Protocol
from abc import ABC, abstractmethod
from vector_store import VectorStore, SearchResults


class Tool(ABC):
    """Abstract base class for all tools"""
    
    @abstractmethod
    def get_tool_definition(self) -> Dict[str, Any]:
        """Return Anthropic tool definition for this tool"""
        pass
    
    @abstractmethod
    def execute(self, **kwargs) -> str:
        """Execute the tool with given parameters"""
        pass


class CourseSearchTool(Tool):
    """Tool for searching course content with semantic course name matching"""
    
    def __init__(self, vector_store: VectorStore):
        self.store = vector_store
        self.last_sources = []  # Track sources from last search
    
    def get_tool_definition(self) -> Dict[str, Any]:
        """Return Anthropic tool definition for this tool"""
        return {
            "name": "search_course_content",
            "description": "Search course materials with smart course name matching and lesson filtering",
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string", 
                        "description": "What to search for in the course content"
                    },
                    "course_name": {
                        "type": "string",
                        "description": "Course title (partial matches work, e.g. 'MCP', 'Introduction')"
                    },
                    "lesson_number": {
                        "type": "integer",
                        "description": "Specific lesson number to search within (e.g. 1, 2, 3)"
                    }
                },
                "required": ["query"]
            }
        }
    
    def execute(self, query: str, course_name: Optional[str] = None, lesson_number: Optional[int] = None) -> str:
        """
        Execute the search tool with given parameters.
        
        Args:
            query: What to search for
            course_name: Optional course filter
            lesson_number: Optional lesson filter
            
        Returns:
            Formatted search results or error message
        """
        
        # Use the vector store's unified search interface
        results = self.store.search(
            query=query,
            course_name=course_name,
            lesson_number=lesson_number
        )
        
        # Handle errors
        if results.error:
            return results.error
        
        # Handle empty results
        if results.is_empty():
            filter_info = ""
            if course_name:
                filter_info += f" in course '{course_name}'"
            if lesson_number:
                filter_info += f" in lesson {lesson_number}"
            return f"No relevant content found{filter_info}."
        
        # Format and return results
        return self._format_results(results)
    
    def _format_results(self, results: SearchResults) -> str:
        """Format search results with course and lesson context"""
        from models import Source

        formatted = []
        sources = []  # Track sources for the UI as Source objects
        seen_sources = set()  # Track unique sources to avoid duplicates

        for doc, meta in zip(results.documents, results.metadata):
            course_title = meta.get('course_title', 'unknown')
            lesson_num = meta.get('lesson_number')

            # Build context header
            header = f"[{course_title}"
            if lesson_num is not None:
                header += f" - Lesson {lesson_num}"
            header += "]"

            # Build source with link
            source_text = course_title
            if lesson_num is not None:
                source_text += f" - Lesson {lesson_num}"

            # Create unique key for deduplication
            source_key = f"{course_title}:{lesson_num}"

            # Only add if not already seen
            if source_key not in seen_sources:
                seen_sources.add(source_key)

                # Fetch the appropriate link with error handling
                link = None
                try:
                    if lesson_num is not None:
                        # Try to get lesson link
                        link = self.store.get_lesson_link(course_title, lesson_num)

                    # If no lesson link or no lesson number, try course link as fallback
                    if link is None:
                        link = self.store.get_course_link(course_title)
                except Exception as e:
                    # Log error but continue with None link
                    print(f"Warning: Could not retrieve link for {course_title}: {e}")
                    link = None

                # Create Source object
                sources.append(Source(text=source_text, url=link))

            formatted.append(f"{header}\n{doc}")

        # Store sources for retrieval
        self.last_sources = sources

        return "\n\n".join(formatted)


class CourseOutlineTool(Tool):
    """Tool for retrieving course outline with all lessons"""

    def __init__(self, vector_store: VectorStore):
        self.store = vector_store
        self.last_sources = []  # Track sources from last query

    def get_tool_definition(self) -> Dict[str, Any]:
        """Return Anthropic tool definition for this tool"""
        return {
            "name": "get_course_outline",
            "description": "Get the complete outline of a course including title, link, and all lessons with their numbers and titles",
            "input_schema": {
                "type": "object",
                "properties": {
                    "course_name": {
                        "type": "string",
                        "description": "Course title to get the outline for (partial matches work, e.g. 'MCP', 'Introduction')"
                    }
                },
                "required": ["course_name"]
            }
        }

    def execute(self, course_name: str) -> str:
        """
        Execute the course outline tool with given course name.

        Args:
            course_name: Course name/title to look up

        Returns:
            Formatted course outline with title, link, and lessons
        """
        import json
        from models import Source

        # Step 1: Resolve course name using semantic search
        try:
            results = self.store.course_catalog.query(
                query_texts=[course_name],
                n_results=1
            )

            # Validate results structure
            if (not results or
                'documents' not in results or
                'metadatas' not in results or
                not results['documents'] or
                len(results['documents'][0]) == 0 or
                not results['metadatas'] or
                len(results['metadatas'][0]) == 0):
                return f"No course found matching '{course_name}'"

            # Now safe to access metadata
            metadata = results['metadatas'][0][0]
            course_title = metadata.get('title', 'Unknown')
            course_link = metadata.get('course_link')
            lessons_json = metadata.get('lessons_json')

            # Parse lessons
            lessons = []
            if lessons_json:
                lessons = json.loads(lessons_json)

            # Format the outline
            formatted = [f"Course: {course_title}"]

            if course_link:
                formatted.append(f"Course Link: {course_link}")

            formatted.append(f"\nLessons ({len(lessons)} total):")

            for lesson in lessons:
                lesson_num = lesson.get('lesson_number')
                lesson_title = lesson.get('lesson_title', 'Untitled')
                formatted.append(f"  Lesson {lesson_num}: {lesson_title}")

            # Track source for UI
            source_text = course_title
            self.last_sources = [Source(text=source_text, url=course_link)]

            return "\n".join(formatted)

        except Exception as e:
            return f"Error retrieving course outline: {str(e)}"


class ToolManager:
    """Manages available tools for the AI"""
    
    def __init__(self):
        self.tools = {}
    
    def register_tool(self, tool: Tool):
        """Register any tool that implements the Tool interface"""
        tool_def = tool.get_tool_definition()
        tool_name = tool_def.get("name")
        if not tool_name:
            raise ValueError("Tool must have a 'name' in its definition")
        self.tools[tool_name] = tool

    
    def get_tool_definitions(self) -> list:
        """Get all tool definitions for Anthropic tool calling"""
        return [tool.get_tool_definition() for tool in self.tools.values()]
    
    def execute_tool(self, tool_name: str, **kwargs) -> str:
        """Execute a tool by name with given parameters"""
        if tool_name not in self.tools:
            return f"Tool '{tool_name}' not found"
        
        return self.tools[tool_name].execute(**kwargs)
    
    def get_last_sources(self) -> list:
        """Get sources from the last search operation"""
        # Check all tools for last_sources attribute
        for tool in self.tools.values():
            if hasattr(tool, 'last_sources') and tool.last_sources:
                return tool.last_sources
        return []

    def reset_sources(self):
        """Reset sources from all tools that track sources"""
        for tool in self.tools.values():
            if hasattr(tool, 'last_sources'):
                tool.last_sources = []