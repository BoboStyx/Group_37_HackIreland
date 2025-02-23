"""
Test script for manually testing all components of the AI Agent system.
"""
import os
import json
import requests
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any
import logging

from server_config import server_config
from database import init_db, get_db
from email_processor import EmailProcessor
from get_mail import authenticator, get_last_month_emails

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SystemTester:
    def __init__(self):
        self.api_url = f"http://{server_config.api_host}:{server_config.api_port}"
        self.email_processor = EmailProcessor(use_test_db=True)
    
    async def test_health(self):
        """Test API health endpoint."""
        logger.info("Testing API health...")
        try:
            response = requests.get(f"{self.api_url}/health")
            logger.info(f"Health check response: {response.json()}")
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return False
    
    async def test_process_input(self, text: str, context: Dict[str, Any] = None):
        """Test processing user input."""
        logger.info(f"Testing input processing: {text}")
        try:
            response = requests.post(
                f"{self.api_url}/process",
                json={"text": text, "context": context or {}}
            )
            logger.info(f"Process response: {response.json()}")
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Process input failed: {str(e)}")
            return False
    
    async def test_tasks(self, urgency: int = None):
        """Test task retrieval."""
        logger.info("Testing task retrieval...")
        try:
            url = f"{self.api_url}/tasks"
            if urgency is not None:
                url += f"?urgency={urgency}"
            response = requests.get(url)
            logger.info(f"Tasks response: {response.json()}")
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Task retrieval failed: {str(e)}")
            return False
    
    async def test_update_task(self, task_id: int, status: str):
        """Test task update."""
        logger.info(f"Testing task update: ID {task_id} -> {status}")
        try:
            response = requests.post(
                f"{self.api_url}/update_task",
                json={
                    "task_id": task_id,
                    "status": status,
                    "alert_at": (datetime.now() + timedelta(days=1)).isoformat()
                }
            )
            logger.info(f"Update response: {response.json()}")
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Task update failed: {str(e)}")
            return False
    
    async def test_think_deep(self, prompt: str):
        """Test deep thinking with O3-mini."""
        logger.info(f"Testing deep thinking: {prompt}")
        try:
            response = requests.post(
                f"{self.api_url}/think_deep",
                json={"prompt": prompt}
            )
            logger.info(f"Think deep response: {response.json()}")
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Deep thinking failed: {str(e)}")
            return False
    
    async def test_email_processing(self):
        """Test email processing."""
        logger.info("Testing email processing...")
        try:
            async with get_db() as db:
                results = await self.email_processor.process_emails(db)
            logger.info(f"Email processing results: {json.dumps(results, indent=2)}")
            return True
        except Exception as e:
            logger.error(f"Email processing failed: {str(e)}")
            return False
    
    async def test_gmail_integration(self):
        """Test Gmail integration."""
        logger.info("Testing Gmail integration...")
        try:
            service = authenticator()
            get_last_month_emails(service)
            return True
        except Exception as e:
            logger.error(f"Gmail integration failed: {str(e)}")
            return False

async def run_tests():
    """Run all system tests."""
    tester = SystemTester()
    
    # Test API health
    if not await tester.test_health():
        logger.error("Health check failed. Ensure the API server is running.")
        return
    
    # Test various components
    tests = [
        # Test task processing
        ("process_input", "Create a high priority task for reviewing the project proposal", {"urgency": "high"}),
        ("process_input", "Schedule a meeting with the team for next week", None),
        
        # Test task retrieval
        ("tasks", None, None),
        ("tasks", 5, None),  # High priority tasks
        
        # Test deep thinking
        ("think_deep", "Analyze the implications of using multiple AI models for task processing", None),
        
        # Test email processing
        ("email_processing", None, None),
        
        # Test Gmail integration (if credentials available)
        ("gmail_integration", None, None)
    ]
    
    for test_name, arg1, arg2 in tests:
        logger.info(f"\nRunning test: {test_name}")
        try:
            if test_name == "process_input":
                await tester.test_process_input(arg1, arg2)
            elif test_name == "tasks":
                await tester.test_tasks(arg1)
            elif test_name == "think_deep":
                await tester.test_think_deep(arg1)
            elif test_name == "email_processing":
                await tester.test_email_processing()
            elif test_name == "gmail_integration":
                await tester.test_gmail_integration()
        except Exception as e:
            logger.error(f"Test {test_name} failed: {str(e)}")

if __name__ == "__main__":
    # Initialize database if needed
    try:
        init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {str(e)}")
    
    # Run tests
    asyncio.run(run_tests()) 