#!./venv/bin/python
"""
Main script for processing emails and creating tasks using Gemini AI.
"""
import asyncio
import logging
from typing import Optional, Dict, Any
import json
from sqlalchemy.ext.asyncio import AsyncSession
from contextlib import asynccontextmanager

from email_processor import EmailProcessor
from Agent.src.database import (
    UserProfile,
    SessionLocal,
    get_db
)
from config import (
    is_test_environment,
    get_email_config,
    get_task_config,
    get_ai_config
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def get_async_db():
    """Async database session context manager."""
    async with SessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

async def process_email_batch():
    """Process a batch of emails and create tasks/opportunities."""
    try:
        # Get configuration
        email_config = get_email_config()
        task_config = get_task_config()
        ai_config = get_ai_config()
        
        # Initialize email processor with appropriate environment
        processor = EmailProcessor(use_test_db=is_test_environment())
        
        # Process emails using async database session
        async with get_async_db() as db:
            logger.info("Starting email processing")
            created_items = await processor.process_emails(db)
            
            # Log results
            tasks = [item for item in created_items if item['type'] == 'task']
            opportunities = [item for item in created_items if item['type'] == 'opportunity']
            
            logger.info(f"Processing complete. Created {len(tasks)} tasks and {len(opportunities)} opportunities")
            
            # Detailed logging
            if tasks:
                logger.info("Created tasks:")
                for task in tasks:
                    logger.info(f"- Task #{task['id']} (Urgency: {task['urgency']}) from '{task['source_email']}'")
            
            if opportunities:
                logger.info("Created opportunities:")
                for opp in opportunities:
                    logger.info(f"- Opportunity #{opp['id']} (Relevance: {opp['relevance']}%) from '{opp['source_email']}'")
            
            return created_items
        
    except Exception as e:
        logger.error(f"Error in email processing: {str(e)}")
        return []

async def main():
    """Main entry point for email processing."""
    try:
        # Log environment and configuration
        env = "test" if is_test_environment() else "production"
        logger.info(f"Starting email processing in {env} environment")
        
        # Log configuration
        email_config = get_email_config()
        logger.info(f"Email batch size: {email_config['batch_size']}")
        logger.info(f"Relevance threshold: {email_config['relevance_threshold']}%")
        
        # Process emails
        created_items = await process_email_batch()
        
        # Output summary
        print("\nProcessing Summary:")
        print(f"Environment: {env}")
        print(f"Total items created: {len(created_items)}")
        print(f"Tasks: {len([i for i in created_items if i['type'] == 'task'])}")
        print(f"Opportunities: {len([i for i in created_items if i['type'] == 'opportunity'])}")
        
        # Additional statistics
        if created_items:
            urgent_tasks = len([i for i in created_items if i['type'] == 'task' and i['urgency'] >= 4])
            high_relevance_opps = len([i for i in created_items if i['type'] == 'opportunity' and i['relevance'] >= 75])
            
            print("\nDetailed Statistics:")
            print(f"Urgent tasks (urgency ≥ 4): {urgent_tasks}")
            print(f"High-relevance opportunities (≥ 75%): {high_relevance_opps}")
        
    except Exception as e:
        logger.error(f"Error in main: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(main()) 