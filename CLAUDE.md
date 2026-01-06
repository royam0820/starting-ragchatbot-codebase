
# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Course Materials RAG (Retrieval-Augmented Generation) System that allows users to query educational course content using semantic search and AI-powered responses. The system uses ChromaDB for vector storage, Anthropic's Claude API with tool calling for AI generation, and FastAPI for the web interface.

## Development Commands

**IMPORTANT**: This project uses `uv` for ALL package and dependency management.
- ✅ Always use `uv` commands (uv sync, uv add, uv remove, uv run)
- ❌ Never use `pip` directly (pip install, pip uninstall, etc.)

### Setup
```bash
# Install dependencies
uv sync

# Set up environment variables (required)
# Create .env file with: ANTHROPIC_API_KEY=your_key_here
```

### Running the Application
```bash
# Quick start (recommended)
./run.sh

# Manual start
cd backend
uv run uvicorn app:app --reload --host localhost --port 8000
```

### Dependency Management
```bash
# Add a new dependency
uv add package_name

# Add a dev dependency
uv add --dev package_name

# Remove a dependency
uv remove package_name

# Update dependencies
uv sync
```

### Code Quality

This project uses automated code quality tools to maintain consistency and catch issues early.

**Quick Commands:**
```bash
# Format code (run before committing)
./format.sh

# Run all quality checks
./quality_check.sh
```

**Individual Tools:**
```bash
# Format code with black (120 char line length)
uv run black backend/

# Sort imports with isort
uv run isort backend/

# Lint with flake8
uv run flake8 backend/

# Type check with mypy
uv run mypy backend/
```

**Configuration:**
- **Black**: Configured in `pyproject.toml` with 120 char line length
- **isort**: Configured to be compatible with Black
- **flake8**: Configured in `.flake8` (excludes E501 line length warnings since Black handles formatting)
- **mypy**: Configured in `pyproject.toml` with moderate strictness

**Important Notes:**
- Always run `./format.sh` before committing code
- The quality check script runs in CI/CD (checks only, no modifications)
- Test files may have unused imports for fixtures - this is acceptable

The application runs at `http://localhost:8000` (web interface) and `http://localhost:8000/docs` (API documentation).

### Testing Queries
Use the web UI at `http://localhost:8000` or hit the API directly:
```bash
curl -X POST "http://localhost:8000/api/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is prompt caching?"}'
```

## Architecture

### RAG Pipeline Flow

The system follows this query processing flow:

1. **User Query** → FastAPI endpoint (`/api/query`)
2. **RAGSystem** orchestrates the entire flow (backend/rag_system.py:102)
3. **AIGenerator** receives query with tool definitions (backend/ai_generator.py:43)
4. **Claude API** decides whether to use the search tool based on the query type
5. **If tool is used**: CourseSearchTool executes the search (backend/search_tools.py:52)
   - Searches course catalog for matching course name (semantic search)
   - Searches course content with optional filters
   - Returns formatted results with metadata
6. **AIGenerator** receives tool results and synthesizes final response
7. **SessionManager** stores conversation history
8. **Response returned** with answer and sources

### Core Components

**RAGSystem** (backend/rag_system.py)
- Main orchestrator that coordinates all components
- Manages document ingestion and query processing
- Initializes: DocumentProcessor, VectorStore, AIGenerator, SessionManager, ToolManager

**VectorStore** (backend/vector_store.py)
- Uses ChromaDB with two collections:
  - `course_catalog`: Course metadata (title, instructor, lessons) for semantic course name matching
  - `course_content`: Chunked course content with metadata (course_title, lesson_number, chunk_index)
- Key method: `search()` performs two-step search:
  1. Resolve course name using semantic search if course_name provided
  2. Search content with filters (course_title and/or lesson_number)

**AIGenerator** (backend/ai_generator.py)
- Handles Anthropic Claude API interactions
- Implements tool calling pattern (request → tool execution → final response)
- Uses static system prompt optimized for course queries
- Temperature set to 0 for consistent responses

**CourseSearchTool** (backend/search_tools.py:20)
- Implements Anthropic tool calling interface
- Provides semantic course name matching (partial matches work)
- Supports optional lesson_number filtering
- Tracks sources for UI display via `last_sources` attribute

**DocumentProcessor** (backend/document_processor.py)
- Parses course documents with expected format:
  ```
  Course Title: [title]
  Course Link: [url]
  Course Instructor: [name]

  Lesson N: [lesson title]
  Lesson Link: [url]
  [lesson content...]
  ```
- Creates sentence-based chunks with configurable size/overlap
- Adds context to chunks: `"Course {title} Lesson {N} content: {chunk}"`

**SessionManager** (backend/session_manager.py)
- Maintains conversation history per session
- Configurable history limit (default: 2 messages)
- Formats history for Claude API context

### Configuration

All settings in `backend/config.py`:
- `ANTHROPIC_MODEL`: "claude-sonnet-4-20250514"
- `EMBEDDING_MODEL`: "all-MiniLM-L6-v2" (sentence-transformers)
- `CHUNK_SIZE`: 800 characters
- `CHUNK_OVERLAP`: 100 characters
- `MAX_RESULTS`: 5 search results
- `MAX_HISTORY`: 2 conversation messages

### Data Models

Three core Pydantic models in `backend/models.py`:
- **Course**: title (unique ID), course_link, instructor, lessons[]
- **Lesson**: lesson_number, title, lesson_link
- **CourseChunk**: content, course_title, lesson_number, chunk_index

### Document Loading

On application startup (backend/app.py:88), the system:
1. Checks for `../docs` folder
2. Loads all `.pdf`, `.docx`, `.txt` files
3. Skips courses already in vector store (compares by course title)
4. Processes documents → extracts metadata → creates chunks → stores in ChromaDB

To force a complete rebuild, call `add_course_folder()` with `clear_existing=True`.

### Frontend

Simple vanilla JavaScript SPA (frontend/):
- `index.html`: Chat interface structure
- `script.js`: API calls to `/api/query` and `/api/courses`
- `style.css`: Styling
- Served via FastAPI StaticFiles with no-cache headers for development

## Important Implementation Details

### Two-Collection Strategy
The system uses separate ChromaDB collections for different purposes:
- **course_catalog**: Enables fuzzy course name matching (user says "MCP" → finds "Introduction to MCP Servers")
- **course_content**: Stores actual content chunks for retrieval

### Tool Calling Pattern
The AI decides when to search based on query type:
- General knowledge questions: Answers without searching
- Course-specific questions: Uses search tool first, then synthesizes
- System prompt enforces "one search per query maximum" to control costs

### Source Tracking
Sources flow through this path:
1. `CourseSearchTool` stores sources in `last_sources` during search
2. `ToolManager.get_last_sources()` retrieves them after AI completes
3. `RAGSystem.query()` returns sources with response
4. `ToolManager.reset_sources()` clears for next query

### Chunk Context Enrichment
Each chunk includes metadata in content for better retrieval:
- First chunk of lesson: `"Lesson {N} content: {chunk}"`
- Subsequent chunks: `"Course {title} Lesson {N} content: {chunk}"`
- This helps Claude understand context without separate metadata lookup

## Dependencies

**Production:**
- Python 3.13+
- uv (package manager)
- chromadb 1.0.15
- anthropic 0.58.2
- sentence-transformers 5.0.0
- fastapi 0.116.1
- uvicorn 0.35.0

**Development:**
- black 25.12.0+ (code formatter)
- isort 7.0.0+ (import sorter)
- flake8 7.3.0+ (linter)
- mypy 1.19.1+ (type checker)
- pytest 9.0.2+ (testing framework)
- pytest-cov 7.0.0+ (coverage reporting)
- pytest-mock 3.15.1+ (mocking utilities)

## File Locations

- Course documents: `docs/` (auto-loaded on startup)
- ChromaDB storage: `backend/chroma_db/` (created automatically)
- Environment config: `.env` in project root
- Frontend: `frontend/` (served at root path `/`)
- Backend: `backend/` (all Python modules)
