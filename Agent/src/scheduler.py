"""
Background task scheduler for email fetching and processing.
"""
import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from get_mail import get_last_month_emails, authenticator
from process_emails import process_email_batch
from server_config import server_config

# Configure logging
logging.basicConfig(
    level=logging.INFO if not server_config.debug else logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Email fetch interval in minutes
EMAIL_FETCH_INTERVAL = 15

class EmailScheduler:
    def __init__(self):
        """Initialize the email scheduler."""
        self.scheduler = AsyncIOScheduler()
        self._setup_jobs()
        
    def _setup_jobs(self):
        """Set up scheduled jobs."""
        # Add email fetching job
        self.scheduler.add_job(
            self._fetch_and_process_emails,
            trigger=IntervalTrigger(minutes=EMAIL_FETCH_INTERVAL),
            id='fetch_emails',
            name='Fetch and process emails',
            replace_existing=True
        )
        
    async def _fetch_and_process_emails(self):
        """Fetch and process emails."""
        try:
            logger.info("Starting scheduled email fetch and process")
            
            # Authenticate and fetch emails
            service = authenticator()
            get_last_month_emails(service)
            
            # Process fetched emails
            await process_email_batch()
            
            logger.info("Completed scheduled email fetch and process")
            
        except Exception as e:
            logger.error(f"Error in scheduled email fetch: {str(e)}")
    
    def start(self):
        """Start the scheduler."""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("Email scheduler started")
    
    def stop(self):
        """Stop the scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Email scheduler stopped") 