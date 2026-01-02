# User Query Flow: Frontend to Backend

This document traces the complete process of handling a user query through the RAG chatbot system, from frontend interaction to final response display.

---

## Overview

The query flow involves:
1. **Frontend** - User interaction and API communication
2. **API Layer** - FastAPI endpoint handling
3. **RAG System** - Query orchestration
4. **AI Generator** - Claude API integration with tool use
5. **Search Tools** - Tool execution management
6. **Vector Store** - Semantic search with ChromaDB
7. **Response Path** - Formatted results back to user

---

## Step-by-Step Flow

### **Step 1: User Interaction (Frontend)**

**File**: `frontend/script.js:45-96`

When a user types a query and clicks send:

```javascript
// User types query and clicks send
sendMessage() {  // Line 45
  const query = chatInput.value.trim();

  // Send POST request to backend
  fetch(`${API_URL}/query`, {  // Line 63
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      query: query,
      session_id: currentSessionId  // Maintains conversation context
    })
  })
}
```

**Example Request Body**:
```json
{
  "query": "What is prompt caching?",
  "session_id": "session_12345"
}
```

---

### **Step 2: API Endpoint Receives Request**

**File**: `backend/app.py:56-74`

The FastAPI endpoint receives and validates the request:

```python
@app.post("/api/query", response_model=QueryResponse)
async def query_documents(request: QueryRequest):
    # Create session if not provided
    session_id = request.session_id or rag_system.session_manager.create_session()

    # Process query using RAG system
    answer, sources = rag_system.query(request.query, session_id)

    return QueryResponse(
        answer=answer,
        sources=sources,
        session_id=session_id
    )
```

**Key Actions**:
- Creates new session ID if none provided
- Delegates query processing to RAG system
- Returns structured response with answer, sources, and session ID

---

### **Step 3: RAG System Orchestration**

**File**: `backend/rag_system.py:102-140`

The RAG system coordinates all components:

```python
def query(self, query: str, session_id: Optional[str] = None):
    # 1. Prepare prompt
    prompt = f"""Answer this question about course materials: {query}"""

    # 2. Get conversation history for context
    history = None
    if session_id:
        history = self.session_manager.get_conversation_history(session_id)
        # Returns: "User: previous question\nAssistant: previous answer"

    # 3. Generate response using AI with tools
    response = self.ai_generator.generate_response(
        query=prompt,
        conversation_history=history,
        tools=self.tool_manager.get_tool_definitions(),  # Tool schemas
        tool_manager=self.tool_manager
    )

    # 4. Get sources from the search tool
    sources = self.tool_manager.get_last_sources()

    # 5. Update conversation history
    self.session_manager.add_exchange(session_id, query, response)

    return response, sources
```

**Key Actions**:
1. Retrieves conversation history for context
2. Prepares tool definitions for Claude
3. Generates AI response with tool access
4. Extracts sources from tool execution
5. Updates session history for future context

---

### **Step 4: Claude AI Decision Making**

**File**: `backend/ai_generator.py:43-87`

The AI Generator prepares and sends the request to Claude:

```python
def generate_response(self, query, conversation_history, tools, tool_manager):
    # Build system prompt with conversation context
    system_content = f"{self.SYSTEM_PROMPT}\n\nPrevious conversation:\n{conversation_history}"

    # Prepare API call with tools
    api_params = {
        "model": "claude-sonnet-4-20250514",
        "temperature": 0,
        "max_tokens": 800,
        "messages": [{"role": "user", "content": query}],
        "system": system_content,
        "tools": tools,  # Search tool definition
        "tool_choice": {"type": "auto"}
    }

    # Call Claude API
    response = self.client.messages.create(**api_params)

    # Check if Claude wants to use a tool
    if response.stop_reason == "tool_use":
        return self._handle_tool_execution(response, api_params, tool_manager)

    # Direct answer without tool use
    return response.content[0].text
```

**Claude's Decision Process**:
- Analyzes the query against its system prompt
- Determines if course content search is needed
- For course-specific questions: Uses `search_course_content` tool
- For general questions: Answers directly from knowledge

---

### **Step 5: Tool Execution Handler**

**File**: `backend/ai_generator.py:89-135`

When Claude decides to use a tool, this handler manages the execution:

```python
def _handle_tool_execution(self, initial_response, base_params, tool_manager):
    messages = base_params["messages"].copy()

    # Add Claude's tool use request
    messages.append({"role": "assistant", "content": initial_response.content})

    # Execute tool calls
    tool_results = []
    for content_block in initial_response.content:
        if content_block.type == "tool_use":
            # Execute the search tool
            tool_result = tool_manager.execute_tool(
                content_block.name,  # "search_course_content"
                **content_block.input  # {query: "prompt caching", course_name: None, ...}
            )

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": content_block.id,
                "content": tool_result  # Formatted search results
            })

    # Send tool results back to Claude
    messages.append({"role": "user", "content": tool_results})
    final_response = self.client.messages.create(messages=messages, ...)

    return final_response.content[0].text
```

**Key Actions**:
1. Extracts tool call parameters from Claude's response
2. Executes tools via Tool Manager
3. Formats tool results for Claude
4. Makes second API call with tool results
5. Returns Claude's synthesized answer

---

### **Step 6: Tool Manager Dispatches Request**

**File**: `backend/search_tools.py:135-140`

The Tool Manager routes the tool call to the appropriate handler:

```python
def execute_tool(self, tool_name: str, **kwargs):
    # tool_name = "search_course_content"
    # kwargs = {query: "prompt caching", course_name: None, lesson_number: None}

    return self.tools[tool_name].execute(**kwargs)
    # Calls CourseSearchTool.execute()
```

**Tool Registry**:
- Maintains a dictionary of available tools
- Each tool implements the `Tool` interface
- Currently supports: `search_course_content`

---

### **Step 7: Course Search Tool Execution**

**File**: `backend/search_tools.py:52-86`

The CourseSearchTool executes the actual search:

```python
def execute(self, query: str, course_name: Optional[str], lesson_number: Optional[int]):
    # Call vector store search
    results = self.store.search(
        query=query,
        course_name=course_name,
        lesson_number=lesson_number
    )

    # Handle errors or empty results
    if results.error:
        return results.error
    if results.is_empty():
        return "No relevant content found."

    # Format results with context
    return self._format_results(results)
```

**Parameters**:
- `query`: The search query text
- `course_name`: Optional course filter (supports fuzzy matching)
- `lesson_number`: Optional lesson number filter

---

### **Step 8: Vector Store Semantic Search**

**File**: `backend/vector_store.py:61-100`

The Vector Store performs semantic search using ChromaDB:

```python
def search(self, query: str, course_name: Optional[str], lesson_number: Optional[int]):
    # Step 1: Resolve course name if provided (fuzzy matching)
    course_title = None
    if course_name:
        course_title = self._resolve_course_name(course_name)
        # Uses semantic search on course_catalog collection

    # Step 2: Build metadata filter
    filter_dict = self._build_filter(course_title, lesson_number)
    # e.g., {"course_title": "Building Towards Computer Use"}

    # Step 3: Search course content with embeddings
    results = self.course_content.query(
        query_texts=[query],  # Converted to embeddings automatically
        n_results=5,          # Top 5 chunks
        where=filter_dict     # Metadata filters
    )

    return SearchResults.from_chroma(results)
```

**ChromaDB Process**:
1. **Embedding Generation**: Converts query text → vector using `all-MiniLM-L6-v2`
2. **Similarity Search**: Compares against stored chunk embeddings (cosine similarity)
3. **Metadata Filtering**: Applies course and lesson filters
4. **Ranking**: Returns top 5 most semantically similar chunks

**Course Name Resolution** (`vector_store.py:102-116`):
```python
def _resolve_course_name(self, course_name: str) -> Optional[str]:
    """Use vector search to find best matching course by name"""
    results = self.course_catalog.query(
        query_texts=[course_name],
        n_results=1
    )

    if results['documents'][0] and results['metadatas'][0]:
        return results['metadatas'][0][0]['title']

    return None
```

This allows fuzzy matching (e.g., "computer use" matches "Building Towards Computer Use").

---

### **Step 9: Format Search Results**

**File**: `backend/search_tools.py:88-114`

Results are formatted with context for Claude:

```python
def _format_results(self, results: SearchResults):
    formatted = []
    sources = []

    for doc, meta in zip(results.documents, results.metadata):
        course_title = meta.get('course_title')
        lesson_num = meta.get('lesson_number')

        # Build context header
        header = f"[{course_title} - Lesson {lesson_num}]"

        # Track source for UI
        sources.append(f"{course_title} - Lesson {lesson_num}")

        formatted.append(f"{header}\n{doc}")

    # Store sources for later retrieval
    self.last_sources = sources

    return "\n\n".join(formatted)
```

**Example Formatted Output to Claude**:
```
[Building Towards Computer Use - Lesson 4]
Prompt caching retains some of the results of processing prompts
between invocations, which can be a large cost and latency saver...

[Building Towards Computer Use - Lesson 5]
With prompt caching, you can reduce costs by up to 90% when reusing
the same prompt content across multiple API calls...
```

**Source Tracking**:
- Sources stored in `self.last_sources`
- Retrieved later by RAG system
- Displayed in UI for transparency

---

### **Step 10: Claude Generates Final Answer**

Claude receives the tool results and synthesizes a response.

**Input to Claude**:
- **System prompt**: "You are an AI assistant specialized in course materials..."
- **Tool results**: Formatted search results from Step 9
- **Original query**: "What is prompt caching?"
- **Conversation history**: Previous exchanges in the session

**Claude's Processing**:
1. Analyzes search results
2. Extracts relevant information
3. Synthesizes coherent answer
4. Follows response protocol (brief, educational, no meta-commentary)

**Example Output**:
```
Prompt caching is a feature that retains processing results between
API calls, reducing costs and latency when reusing the same prompt
content. It can save up to 90% on costs for repeated requests by
caching parts of your prompt that don't change between calls.
```

---

### **Step 11: Response Returned to API**

**File**: `backend/rag_system.py:129-140`

The RAG system collects sources and updates history:

```python
# Get sources from tool manager
sources = self.tool_manager.get_last_sources()
# Returns: ["Building Towards Computer Use - Lesson 4", ...]

# Update session history
self.session_manager.add_exchange(session_id, query, response)

return response, sources
```

**File**: `backend/app.py:68-72`

The API endpoint formats the final response:

```python
return QueryResponse(
    answer="Prompt caching is a feature...",
    sources=["Building Towards Computer Use - Lesson 4", ...],
    session_id="session_12345"
)
```

**Response JSON**:
```json
{
  "answer": "Prompt caching is a feature that retains...",
  "sources": [
    "Building Towards Computer Use - Lesson 4",
    "Building Towards Computer Use - Lesson 5"
  ],
  "session_id": "session_12345"
}
```

---

### **Step 12: Frontend Displays Response**

**File**: `frontend/script.js:76-85`

The frontend receives and processes the response:

```javascript
const data = await response.json();

// Update session ID
currentSessionId = data.session_id;

// Remove loading indicator
loadingMessage.remove();

// Display answer and sources
addMessage(data.answer, 'assistant', data.sources);
```

**File**: `frontend/script.js:113-138`

Messages are rendered with markdown and sources:

```javascript
function addMessage(content, type, sources) {
    // Convert markdown to HTML
    const displayContent = marked.parse(content);

    let html = `<div class="message-content">${displayContent}</div>`;

    // Add collapsible sources section
    if (sources && sources.length > 0) {
        html += `
            <details class="sources-collapsible">
                <summary>Sources</summary>
                <div>${sources.join(', ')}</div>
            </details>
        `;
    }

    // Append to chat
    chatMessages.appendChild(messageDiv);
}
```

**UI Features**:
- Markdown rendering for formatted responses
- Collapsible sources section
- Auto-scroll to latest message
- Loading indicator during processing

---

## Complete Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│ FRONTEND (script.js)                                        │
│ User types: "What is prompt caching?"                       │
│ → POST /api/query {query, session_id}                       │
└─────────────────────┬───────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────────┐
│ BACKEND API (app.py:56)                                     │
│ @app.post("/api/query")                                     │
│ → rag_system.query(query, session_id)                       │
└─────────────────────┬───────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────────┐
│ RAG SYSTEM (rag_system.py:102)                              │
│ 1. Get conversation history                                 │
│ 2. Prepare tools (search_course_content)                    │
│ 3. → ai_generator.generate_response()                       │
└─────────────────────┬───────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────────┐
│ AI GENERATOR (ai_generator.py:43)                           │
│ 1. Build system prompt + history                            │
│ 2. → Claude API with tools                                  │
│ 3. Claude decides: USE TOOL                                 │
│ 4. → _handle_tool_execution()                               │
└─────────────────────┬───────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────────┐
│ TOOL EXECUTION (ai_generator.py:89)                         │
│ Extract tool call: {name: "search_course_content",          │
│                     input: {query: "prompt caching"}}       │
│ → tool_manager.execute_tool()                               │
└─────────────────────┬───────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────────┐
│ SEARCH TOOL (search_tools.py:52)                            │
│ CourseSearchTool.execute()                                  │
│ → vector_store.search(query, course_name, lesson_number)   │
└─────────────────────┬───────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────────┐
│ VECTOR STORE (vector_store.py:61)                           │
│ 1. Resolve course name (if provided)                        │
│ 2. Build metadata filters                                   │
│ 3. → ChromaDB.query() with embeddings                       │
│    - Convert query to vector                                │
│    - Semantic similarity search                             │
│    - Apply filters                                          │
│ 4. Return top 5 chunks                                      │
└─────────────────────┬───────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────────┐
│ FORMAT RESULTS (search_tools.py:88)                         │
│ Format: "[Course - Lesson N]\ncontent..."                   │
│ Store sources: ["Course - Lesson N", ...]                   │
│ → Return formatted text to Claude                           │
└─────────────────────┬───────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────────┐
│ CLAUDE FINAL RESPONSE (ai_generator.py:134)                 │
│ Receives tool results → Synthesizes answer                  │
│ → Returns: "Prompt caching is a feature..."                 │
└─────────────────────┬───────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────────┐
│ RAG SYSTEM COMPLETION (rag_system.py:129)                   │
│ 1. Get sources from tool_manager                            │
│ 2. Update session history                                   │
│ 3. → Return (response, sources)                             │
└─────────────────────┬───────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────────┐
│ API RESPONSE (app.py:68)                                    │
│ Return JSON: {answer, sources, session_id}                  │
└─────────────────────┬───────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────────┐
│ FRONTEND DISPLAY (script.js:85)                             │
│ 1. Remove loading indicator                                 │
│ 2. Render markdown answer                                   │
│ 3. Show collapsible sources                                 │
│ 4. Update session_id for next query                         │
└─────────────────────────────────────────────────────────────┘
```

---

## Key Components

### 1. Session Management

**File**: `backend/session_manager.py`

- Creates unique session IDs for each conversation
- Maintains message history per session
- Limits history to prevent context overflow (max 4 messages)
- Formats conversation for AI context

**Example Session History**:
```
User: What is prompt caching?
Assistant: Prompt caching is a feature...
User: How much can it save?
Assistant: It can save up to 90% on costs...
```

### 2. Tool System

**Architecture**:
- **Tool Interface** (`search_tools.py:6-17`): Abstract base class
- **CourseSearchTool** (`search_tools.py:20-114`): Implements search functionality
- **ToolManager** (`search_tools.py:116-154`): Registers and executes tools

**Tool Definition** (sent to Claude):
```json
{
  "name": "search_course_content",
  "description": "Search course materials with smart course name matching...",
  "input_schema": {
    "type": "object",
    "properties": {
      "query": {"type": "string", "description": "What to search for"},
      "course_name": {"type": "string", "description": "Course title filter"},
      "lesson_number": {"type": "integer", "description": "Lesson filter"}
    },
    "required": ["query"]
  }
}
```

### 3. Vector Search

**Two ChromaDB Collections**:

1. **course_catalog** - Course metadata
   - Stores: Course titles, instructors, links, lesson info
   - Used for: Fuzzy course name matching

2. **course_content** - Actual content
   - Stores: Text chunks with embeddings
   - Metadata: course_title, lesson_number, chunk_index
   - Used for: Semantic content search

**Search Process**:
1. Query → Embedding (sentence-transformers)
2. Cosine similarity against stored embeddings
3. Metadata filtering (course, lesson)
4. Top-k retrieval (k=5 by default)

### 4. Conversation Context

**System Prompt** (`ai_generator.py:8-30`):
- Defines AI's role and behavior
- Sets tool usage guidelines
- Specifies response format requirements

**Context Building**:
```python
system_content = f"{SYSTEM_PROMPT}\n\nPrevious conversation:\n{history}"
```

This gives Claude awareness of:
- Its role as a course materials assistant
- Available tools and when to use them
- Previous conversation turns for continuity

---

## Performance Characteristics

### Typical Query Timeline

1. **Frontend → Backend**: ~50ms (network latency)
2. **Session History Retrieval**: <1ms (in-memory)
3. **Claude API Call #1** (with tools): ~1-2s
4. **Tool Execution**:
   - Vector search: ~100-200ms
   - Result formatting: <10ms
5. **Claude API Call #2** (with results): ~1-2s
6. **Response Formatting**: <10ms
7. **Backend → Frontend**: ~50ms

**Total**: ~2-4 seconds

### Optimization Features

1. **Prompt Caching** (implied): Reuses system prompt across calls
2. **Sentence-based Chunking**: Maintains semantic coherence
3. **Chunk Overlap**: Prevents context loss at boundaries
4. **In-memory Sessions**: Fast history retrieval
5. **ChromaDB Indexing**: Efficient vector similarity search

---

## Error Handling

### Frontend
- Network errors → Display error message
- Loading states → Show animated indicator
- Failed requests → User-friendly error display

### Backend
- Invalid requests → HTTP 400 with validation errors
- Processing errors → HTTP 500 with error details
- Empty search results → "No relevant content found" message

### Vector Store
- Course not found → Clear error message
- Search failures → Graceful degradation
- Embedding errors → Logged and returned

---

## Data Flow Summary

```
User Query
    ↓
Session Context + Query
    ↓
Claude Decision (General vs Course-specific)
    ↓
Tool Call (if course-specific)
    ↓
Vector Search (embeddings + filters)
    ↓
Top-5 Chunks
    ↓
Formatted Results
    ↓
Claude Synthesis
    ↓
Answer + Sources
    ↓
UI Display
```

---

## Configuration

### AI Generator Settings (`config.py`)
- **Model**: `claude-sonnet-4-20250514`
- **Temperature**: 0 (deterministic)
- **Max Tokens**: 800

### Vector Store Settings (`config.py`)
- **Embedding Model**: `all-MiniLM-L6-v2`
- **Chunk Size**: 800 characters
- **Chunk Overlap**: 100 characters
- **Max Results**: 5 chunks

### Session Settings (`config.py`)
- **Max History**: 4 messages (2 exchanges)

---

## Notable Design Patterns

### 1. Tool-Based RAG
Instead of always retrieving context, Claude autonomously decides when to search. This:
- Reduces unnecessary searches for general questions
- Allows Claude to use its knowledge when appropriate
- Provides more natural conversation flow

### 2. Two-Collection Strategy
Separating course metadata from content enables:
- Fast course name resolution
- Flexible filtering
- Efficient metadata queries

### 3. Agentic Workflow
The tool execution loop allows Claude to:
- Make informed decisions about searching
- Use multiple tools if needed (extensible)
- Provide context-aware responses

### 4. Source Tracking
Maintaining sources throughout the pipeline:
- Builds user trust
- Enables fact verification
- Improves transparency

---

## Extension Points

The system is designed for easy extension:

1. **New Tools**: Implement `Tool` interface in `search_tools.py`
2. **New Document Types**: Extend `DocumentProcessor.read_file()`
3. **New Search Filters**: Add parameters to `VectorStore.search()`
4. **New Collections**: Create additional ChromaDB collections
5. **Advanced Features**:
   - Multi-modal search (images)
   - Hybrid search (keyword + semantic)
   - Re-ranking algorithms
   - Citation extraction

---

## Conclusion

This RAG system demonstrates a modern architecture combining:
- **Semantic search** for intelligent retrieval
- **Tool-calling LLMs** for autonomous decision-making
- **Session management** for conversational context
- **Source tracking** for transparency

The entire flow is optimized for:
- **Performance**: 2-4 second typical response time
- **Accuracy**: Semantic search with metadata filtering
- **User Experience**: Clear sources and natural responses
- **Extensibility**: Modular design for easy enhancement
