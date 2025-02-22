"""
Tests for the CLI interface using pytest framework.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import io
import sys
import asyncio

from Agent.cli import AgentCLI, main
from Agent.database import init_db, engine, Base

class TestCLI:
    @pytest.fixture(autouse=True)
    async def setup_method(self):
        """Set up test fixtures before each test method."""
        # Create all tables
        Base.metadata.drop_all(bind=engine)  # Clean slate
        Base.metadata.create_all(bind=engine)
        
        self.cli = AgentCLI()
        # Create a string buffer to capture stdout
        self.stdout = io.StringIO()
        self.real_stdout = sys.stdout
        sys.stdout = self.stdout
        yield
        # Cleanup
        sys.stdout = self.real_stdout
        self.stdout.close()

    @pytest.mark.asyncio
    async def test_show_help(self):
        """Test the help command output."""
        self.cli._show_help()
        output = self.stdout.getvalue()
        
        # Verify all help messages are present
        assert "Available commands:" in output
        assert "help  - Show this help message" in output
        assert "tasks - Process and manage tasks" in output
        assert "exit  - Exit the program" in output
    
    @pytest.mark.asyncio
    async def test_interactive_mode_exit(self):
        """Test that the exit command properly exits interactive mode."""
        # Run the interactive mode
        with patch('builtins.input', side_effect=['exit']):
            await self.cli.interactive_mode()
        
        # Verify welcome message was printed
        output = self.stdout.getvalue()
        assert "AI Agent CLI" in output
        assert "Type 'exit' to quit" in output
    
    @pytest.mark.asyncio
    async def test_interactive_mode_help(self):
        """Test help command in interactive mode."""
        with patch('builtins.input', side_effect=['help', 'exit']):
            await self.cli.interactive_mode()
        
        output = self.stdout.getvalue()
        assert "Available commands:" in output
        assert "help  - Show this help message" in output
    
    @pytest.mark.asyncio
    async def test_interactive_mode_process(self):
        """Test processing user input in interactive mode."""
        # Setup mock response
        mock_chunk = MagicMock()
        mock_chunk.choices = [MagicMock()]
        mock_chunk.choices[0].delta.content = "Test response"
        
        # Setup mock client
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=[mock_chunk])
        
        with patch('Agent.chatgpt_agent.AsyncOpenAI', return_value=mock_client), \
             patch('Agent.chatgpt_agent.OPENAI_API_KEY', 'test-key'), \
             patch('builtins.input', side_effect=['test input', 'exit']):
            await self.cli.interactive_mode()
            
            # Verify response was printed
            output = self.stdout.getvalue()
            assert "Test response" in output
    
    @pytest.mark.asyncio
    async def test_interactive_mode_error(self):
        """Test error handling in interactive mode."""
        # Setup mock to raise an exception
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=Exception("Test error"))
        
        with patch('Agent.chatgpt_agent.AsyncOpenAI', return_value=mock_client), \
             patch('Agent.chatgpt_agent.OPENAI_API_KEY', 'test-key'), \
             patch('builtins.input', side_effect=['test input', 'exit']):
            await self.cli.interactive_mode()
            
            # Verify error message was printed
            output = self.stdout.getvalue()
            assert "Error occurred: Test error" in output
    
    @pytest.mark.asyncio
    @patch('asyncio.run')
    @patch('sys.argv', ['cli.py'])
    async def test_main_function(self, mock_run):
        """Test the main entry point function."""
        main()
        mock_run.assert_called_once()
        
        # Ensure the coroutine is awaited
        args = mock_run.call_args[0]
        assert asyncio.iscoroutine(args[0])
    
    @pytest.mark.asyncio
    @patch('asyncio.run')
    @patch('sys.argv', ['cli.py', '--debug'])
    async def test_main_function_debug(self, mock_run):
        """Test the main function with debug flag."""
        import logging
        main()
        
        # Verify debug logging was enabled
        assert logging.getLogger().level == logging.DEBUG
        mock_run.assert_called_once()
        
        # Ensure the coroutine is awaited
        args = mock_run.call_args[0]
        assert asyncio.iscoroutine(args[0]) 