"""Tests for AIGenerator"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from ai_generator import AIGenerator
from tests.fixtures import create_anthropic_text_response, create_anthropic_tool_use_response


class TestAIGenerator:
    """Test suite for AIGenerator tool calling integration"""

    def test_generate_response_without_tools(self, ai_generator, mock_anthropic_client):
        """Test generating response without any tools"""
        # Mock API response with simple text
        mock_response = create_anthropic_text_response("This is a test response")
        mock_anthropic_client.messages.create.return_value = mock_response

        # Generate response without tools
        result = ai_generator.generate_response(
            query="What is 2+2?",
            tools=None,
            tool_manager=None
        )

        # Verify API was called
        assert mock_anthropic_client.messages.create.called
        call_args = mock_anthropic_client.messages.create.call_args

        # Verify no tools were passed
        assert 'tools' not in call_args[1]

        # Verify response
        assert result == "This is a test response"

    def test_generate_response_with_tools_no_tool_use(self, ai_generator, mock_anthropic_client):
        """Test when tools are provided but Claude doesn't use them"""
        # Mock API response with text (not tool use)
        mock_response = create_anthropic_text_response("I can answer this without searching")
        mock_anthropic_client.messages.create.return_value = mock_response

        # Create mock tools
        mock_tools = [{"name": "search", "description": "Search tool"}]
        mock_tool_manager = Mock()

        # Generate response
        result = ai_generator.generate_response(
            query="What is Python?",
            tools=mock_tools,
            tool_manager=mock_tool_manager
        )

        # Verify tools were provided to API
        call_args = mock_anthropic_client.messages.create.call_args
        assert 'tools' in call_args[1]
        assert call_args[1]['tools'] == mock_tools

        # Verify tool manager was not used (stop_reason != "tool_use")
        mock_tool_manager.execute_tool.assert_not_called()

        # Verify response
        assert result == "I can answer this without searching"

    def test_generate_response_with_tool_use(self, ai_generator, mock_anthropic_client):
        """Test complete tool calling flow"""
        # Mock initial response with tool use
        initial_response = create_anthropic_tool_use_response(
            tool_name="search_course_content",
            tool_input={"query": "MCP servers"}
        )

        # Mock final response after tool execution
        final_response = create_anthropic_text_response("MCP servers are used for...")

        # Setup mock to return both responses
        mock_anthropic_client.messages.create.side_effect = [initial_response, final_response]

        # Create mock tool manager
        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.return_value = "Search results about MCP"

        # Generate response
        result = ai_generator.generate_response(
            query="What are MCP servers?",
            tools=[{"name": "search_course_content"}],
            tool_manager=mock_tool_manager
        )

        # Verify API was called twice (initial + after tool)
        assert mock_anthropic_client.messages.create.call_count == 2

        # Verify tool was executed
        mock_tool_manager.execute_tool.assert_called_once_with(
            "search_course_content",
            query="MCP servers"
        )

        # Verify final response
        assert result == "MCP servers are used for..."

    def test_handle_tool_execution_success(self, ai_generator, mock_anthropic_client):
        """Test _handle_tool_execution with successful tool call"""
        # Create initial response with tool use
        initial_response = create_anthropic_tool_use_response(
            tool_name="search_course_content",
            tool_input={"query": "test query"}
        )

        # Create final response
        final_response = create_anthropic_text_response("Based on the search...")

        mock_anthropic_client.messages.create.return_value = final_response

        # Create mock tool manager
        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.return_value = "Tool result content"

        # Create base params
        base_params = {
            "messages": [{"role": "user", "content": "test query"}],
            "system": "System prompt",
            "model": "claude-sonnet-4",
            "temperature": 0,
            "max_tokens": 800
        }

        # Call _handle_tool_execution
        result = ai_generator._handle_tool_execution(
            initial_response=initial_response,
            base_params=base_params,
            tool_manager=mock_tool_manager
        )

        # Verify tool was executed
        mock_tool_manager.execute_tool.assert_called_once()

        # Verify second API call was made with tool results
        assert mock_anthropic_client.messages.create.called
        call_args = mock_anthropic_client.messages.create.call_args

        # Verify messages include tool results
        messages = call_args[1]['messages']
        assert len(messages) == 3  # original + assistant + tool_result

        # Verify result
        assert result == "Based on the search..."

    def test_handle_tool_execution_with_tool_error(self, ai_generator, mock_anthropic_client):
        """Test handling when tool returns an error string"""
        # Create tool use response
        initial_response = create_anthropic_tool_use_response(
            tool_name="search_course_content",
            tool_input={"query": "test"}
        )

        # Create final response
        final_response = create_anthropic_text_response("I couldn't find that information")

        mock_anthropic_client.messages.create.return_value = final_response

        # Mock tool to return error string
        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.return_value = "No relevant content found"

        base_params = {
            "messages": [{"role": "user", "content": "test"}],
            "system": "System prompt",
            "model": "claude-sonnet-4",
            "temperature": 0,
            "max_tokens": 800
        }

        # Execute
        result = ai_generator._handle_tool_execution(
            initial_response=initial_response,
            base_params=base_params,
            tool_manager=mock_tool_manager
        )

        # Should still complete successfully
        assert result == "I couldn't find that information"

    def test_handle_tool_execution_with_tool_exception(self, ai_generator, mock_anthropic_client):
        """Test handling when tool execution raises exception - Should handle gracefully"""
        # Create tool use response
        initial_response = create_anthropic_tool_use_response(
            tool_name="search_course_content",
            tool_input={"query": "test"}
        )

        # Create final response after error is handled
        final_response = create_anthropic_text_response("I encountered an error")
        mock_anthropic_client.messages.create.return_value = final_response

        # Mock tool manager to raise exception
        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.side_effect = Exception("Tool execution failed")

        base_params = {
            "messages": [{"role": "user", "content": "test"}],
            "system": "System prompt",
            "model": "claude-sonnet-4",
            "temperature": 0,
            "max_tokens": 800
        }

        # Execute - should handle exception gracefully by catching it and passing error to Claude
        result = ai_generator._handle_tool_execution(
            initial_response=initial_response,
            base_params=base_params,
            tool_manager=mock_tool_manager
        )

        # Should not crash and should return a response
        assert result == "I encountered an error"

        # Verify the error was passed to Claude as a tool result
        call_args = mock_anthropic_client.messages.create.call_args
        messages = call_args[1]['messages']

        # Find the tool result message
        tool_result_message = messages[-1]  # Last message should be tool results
        assert tool_result_message['role'] == 'user'
        tool_results = tool_result_message['content']
        assert len(tool_results) > 0
        assert "Tool execution error" in tool_results[0]['content']

    def test_generate_response_with_conversation_history(self, ai_generator, mock_anthropic_client):
        """Test that conversation history is included in system content"""
        # Mock response
        mock_response = create_anthropic_text_response("Response with history")
        mock_anthropic_client.messages.create.return_value = mock_response

        # Generate with history
        history = "User: Hello\nAssistant: Hi there!"
        result = ai_generator.generate_response(
            query="Follow-up question",
            conversation_history=history
        )

        # Verify API was called with history in system content
        call_args = mock_anthropic_client.messages.create.call_args
        system_content = call_args[1]['system']

        assert "Previous conversation:" in system_content
        assert history in system_content

    def test_tool_choice_auto_mode(self, ai_generator, mock_anthropic_client):
        """Test that tool_choice is set to auto when tools are provided"""
        # Mock response
        mock_response = create_anthropic_text_response("Test response")
        mock_anthropic_client.messages.create.return_value = mock_response

        # Generate with tools
        mock_tools = [{"name": "test_tool"}]
        result = ai_generator.generate_response(
            query="Test query",
            tools=mock_tools
        )

        # Verify tool_choice was set to auto
        call_args = mock_anthropic_client.messages.create.call_args
        assert 'tool_choice' in call_args[1]
        assert call_args[1]['tool_choice'] == {"type": "auto"}
