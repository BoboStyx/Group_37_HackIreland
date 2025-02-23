"""
Configuration settings for the email processing and task management system.
"""
import os
from typing import Dict, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database Configuration
DATABASE_CONFIG = {
    'production': {
        'host': os.getenv('DB_HOST', 'localhost'),
        'user': os.getenv('DB_USER', 'Seyi'),
        'password': os.getenv('DB_PASSWORD', 'S1906@duposiDCU'),
        'database': os.getenv('DB_NAME', 'emails_db')
    },
    'test': {
        'host': os.getenv('TEST_DB_HOST', 'localhost'),
        'user': os.getenv('TEST_DB_USER', 'test_user'),
        'password': os.getenv('TEST_DB_PASSWORD', 'test_password'),
        'database': os.getenv('TEST_DB_NAME', 'test_emails_db')
    }
}

# AI Configuration
AI_CONFIG = {
    'gemini_api_key': os.getenv('GEMINI_API_KEY'),
    'model_name': 'gemini-pro',
    'max_tokens': 1024,
    'temperature': 0.7
}

# Task Management Configuration
TASK_CONFIG = {
    'max_urgency': 5,
    'min_urgency': 1,
    'default_urgency': 3,
    'opportunity_urgency': 1,
    'urgent_threshold_days': 2
}

# Email Processing Configuration
EMAIL_CONFIG = {
    'batch_size': 50,
    'relevance_threshold': 50,  # Minimum relevance score (0-100) for opportunities
    'max_retries': 3,
    'retry_delay': 5  # seconds
}

def get_database_url(environment: str = 'production') -> str:
    """Get the database URL for the specified environment."""
    config = DATABASE_CONFIG[environment]
    return f"mysql://{config['user']}:{config['password']}@{config['host']}/{config['database']}"

def get_environment() -> str:
    """Get the current environment (production/test)."""
    return os.getenv('ENVIRONMENT', 'production').lower()

def is_test_environment() -> bool:
    """Check if currently running in test environment."""
    return get_environment() == 'test'

def get_ai_config() -> Dict[str, Any]:
    """Get AI configuration settings."""
    return AI_CONFIG.copy()

def get_task_config() -> Dict[str, Any]:
    """Get task management configuration settings."""
    return TASK_CONFIG.copy()

def get_email_config() -> Dict[str, Any]:
    """Get email processing configuration settings."""
    return EMAIL_CONFIG.copy() 