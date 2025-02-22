"""
Tests for the main AI agent functionality using unittest framework.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime

from Agent.agent import AIAgent
from Agent.config import MAX_EMAILS, MAX_TOKENS
from Agent.database import SessionLocal, init_db, engine, Base

class TestAIAgent:
    @pytest.fixture(autouse=True)
    def setup_method(self):
        """Set up test fixtures before each test method."""
        # Create all tables
        Base.metadata.drop_all(bind=engine)  # Clean slate
        Base.metadata.create_all(bind=engine)
        
        self.db = SessionLocal()
        self.agent = AIAgent()
        self.sample_tasks = [
            {'id': 1, 'description': 'Task 1', 'urgency': 5, 'status': 'pending'},
            {'id': 2, 'description': 'Task 2', 'urgency': 4, 'status': 'pending'},
            {'id': 3, 'description': 'Task 3', 'urgency': 5, 'status': 'pending'},
            {'id': 4, 'description': 'Task 4', 'urgency': 3, 'status': 'pending'},
            {'id': 5, 'description': 'Task 5', 'urgency': 4, 'status': 'pending'}
        ]
        yield
        # Cleanup
        if self.db:
            self.db.close()

    def test_chunk_tasks_exact_limit(self):
        """Test chunking tasks when count equals MAX_EMAILS."""
        tasks = self.sample_tasks[:MAX_EMAILS]
        chunks = self.agent._chunk_tasks(tasks)
        
        assert len(chunks) == 1
        assert len(chunks[0]) == MAX_EMAILS
        assert chunks[0][0]['description'] == 'Task 1'
    
    def test_chunk_tasks_over_limit(self):
        """Test chunking tasks when count exceeds MAX_EMAILS."""
        # Create more tasks than MAX_EMAILS
        extra_tasks = self.sample_tasks * 2
        chunks = self.agent._chunk_tasks(extra_tasks)
        
        assert len(chunks) > 1
        assert len(chunks[0]) <= MAX_EMAILS
    
    def test_chunk_tasks_empty(self):
        """Test chunking with empty task list."""
        chunks = self.agent._chunk_tasks([])
        assert len(chunks) == 0
    
    @pytest.mark.asyncio
    async def test_process_input_chatgpt(self):
        """Test processing input using ChatGPT."""
        # Setup mock response
        mock_chunk = MagicMock()
        mock_chunk.choices = [MagicMock()]
        mock_chunk.choices[0].delta.content = "Test response"
        
        # Setup mock client
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=[mock_chunk])
        
        with patch('Agent.chatgpt_agent.AsyncOpenAI', return_value=mock_client), \
             patch('Agent.chatgpt_agent.OPENAI_API_KEY', 'test-key'):
            response = await self.agent.process_input("Test input")
            assert "Test response" in response
    
    @pytest.mark.asyncio
    async def test_process_input_o3mini(self):
        """Test processing input using O3-mini for deep thinking."""
        # Setup mock
        mock_instance = AsyncMock()
        mock_instance.process = AsyncMock(return_value="Deep thinking response")
        mock_instance.is_available = True
        
        with patch('Agent.o3_mini.O3MiniAgent', return_value=mock_instance):
            response = await self.agent.process_input("analyze this complex problem")
            assert "Deep thinking response" in response
            mock_instance.process.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_process_tasks(self):
        """Test the task processing workflow."""
        # Setup mocks
        with patch('Agent.agent.get_tasks_by_urgency', return_value=self.sample_tasks), \
             patch('Agent.agent.update_task_status') as mock_update:
            
            # Mock the ChatGPT response
            async def mock_summary_gen():
                yield "Task summary"
            
            with patch('Agent.chatgpt_agent.ChatGPTAgent.summarize_tasks', return_value=mock_summary_gen()), \
                 patch('builtins.input', side_effect=['1', 'complete']):
                await self.agent.process_tasks()
                
                # Verify task status was updated
                mock_update.assert_called_with(1, 'completed', None)
    
    def test_requires_deep_thinking(self):
        """Test the deep thinking detection logic."""
        # Should return True for analytical keywords
        assert self.agent._requires_deep_thinking("analyze this problem")
        assert self.agent._requires_deep_thinking("compare these options")
        
        # Should return False for simple queries
        assert not self.agent._requires_deep_thinking("what time is it")
        assert not self.agent._requires_deep_thinking("hello")

if __name__ == '__main__':
    pytest.main() 