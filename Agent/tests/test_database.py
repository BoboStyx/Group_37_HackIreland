"""
Tests for database operations using unittest framework.
"""
import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime

from Agent.database import (
    get_tasks_by_urgency, update_task_status,
    Conversation, AgentTask, Task, init_db
)

class TestDatabaseOperations(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.fake_task = {
            'id': 1,
            'description': 'Test task',
            'urgency': 5,
            'status': 'pending',
            'alertAt': None
        }

    @patch('Agent.database.engine.connect')
    def test_get_tasks_by_urgency(self, mock_connect):
        """Test retrieving tasks by urgency level."""
        # Create a fake connection and cursor result
        fake_connection = MagicMock()
        fake_cursor = [self.fake_task]
        fake_connection.__enter__.return_value.execute.return_value = fake_cursor
        mock_connect.return_value = fake_connection
        
        # Execute the function and verify results
        tasks = get_tasks_by_urgency(5)
        
        # Assertions
        self.assertIsInstance(tasks, list)
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]['description'], 'Test task')
        self.assertEqual(tasks[0]['urgency'], 5)
        
        # Verify SQL execution
        fake_connection.__enter__.return_value.execute.assert_called_once()
    
    @patch('Agent.database.engine.connect')
    def test_update_task_status(self, mock_connect):
        """Test updating task status and alert time."""
        # Setup mock
        fake_connection = MagicMock()
        mock_connect.return_value = fake_connection
        
        # Test data
        task_id = 1
        new_status = 'completed'
        alert_time = datetime.utcnow()
        
        # Execute function
        update_task_status(task_id, new_status, alert_time)
        
        # Verify SQL execution and commit
        fake_connection.__enter__.return_value.execute.assert_called_once()
        fake_connection.__enter__.return_value.commit.assert_called_once()
    
    @patch('Agent.database.engine.connect')
    def test_update_task_status_no_alert(self, mock_connect):
        """Test updating task status without alert time."""
        fake_connection = MagicMock()
        mock_connect.return_value = fake_connection
        
        update_task_status(1, 'completed', None)
        
        fake_connection.__enter__.return_value.execute.assert_called_once()
        fake_connection.__enter__.return_value.commit.assert_called_once()
    
    def test_conversation_model(self):
        """Test Conversation model creation."""
        conv = Conversation(
            user_input="test input",
            agent_response="test response",
            model_used="gpt-4",
            timestamp=datetime.utcnow()
        )
        
        self.assertEqual(conv.user_input, "test input")
        self.assertEqual(conv.agent_response, "test response")
        self.assertEqual(conv.model_used, "gpt-4")
    
    def test_task_model(self):
        """Test Task model creation."""
        task = Task(
            description="test task",
            urgency=5,
            status="pending"
        )
        
        self.assertEqual(task.description, "test task")
        self.assertEqual(task.urgency, 5)
        self.assertEqual(task.status, "pending")

if __name__ == '__main__':
    unittest.main() 