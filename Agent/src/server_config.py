"""
Server configuration settings for different environments.
"""
from typing import Dict, Any
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class DatabaseConfig:
    """Database configuration for different environments."""
    def __init__(self):
        self.configs = {
            'development': {
                'host': os.getenv('DEV_DB_HOST', 'localhost'),
                'user': os.getenv('DEV_DB_USER', 'dev_user'),
                'password': os.getenv('DEV_DB_PASSWORD', ''),
                'database': os.getenv('DEV_DB_NAME', 'ai_agent_dev'),
                'port': int(os.getenv('DEV_DB_PORT', 3306))
            },
            'testing': {
                'host': os.getenv('TEST_DB_HOST', 'localhost'),
                'user': os.getenv('TEST_DB_USER', 'test_user'),
                'password': os.getenv('TEST_DB_PASSWORD', ''),
                'database': os.getenv('TEST_DB_NAME', 'ai_agent_test'),
                'port': int(os.getenv('TEST_DB_PORT', 3306))
            },
            'production': {
                'host': os.getenv('PROD_DB_HOST', 'localhost'),
                'user': os.getenv('PROD_DB_USER', 'prod_user'),
                'password': os.getenv('PROD_DB_PASSWORD', ''),
                'database': os.getenv('PROD_DB_NAME', 'ai_agent_prod'),
                'port': int(os.getenv('PROD_DB_PORT', 3306))
            }
        }

    def get_config(self, environment: str) -> Dict[str, Any]:
        """Get database configuration for specified environment."""
        if environment not in self.configs:
            raise ValueError(f"Unknown environment: {environment}")
        return self.configs[environment]

    def get_url(self, environment: str) -> str:
        """Get SQLAlchemy URL for specified environment."""
        config = self.get_config(environment)
        return f"mysql+mysqlconnector://{config['user']}:{config['password']}@{config['host']}:{config['port']}/{config['database']}"

class ServerConfig:
    """Server configuration settings."""
    def __init__(self):
        self.environment = os.getenv('ENVIRONMENT', 'development')
        self.api_host = os.getenv('API_HOST', '0.0.0.0')
        self.api_port = int(os.getenv('API_PORT', 8000))
        self.api_workers = int(os.getenv('API_WORKERS', 4))
        self.api_timeout = int(os.getenv('API_TIMEOUT', 60))
        self.debug = self.environment == 'development'
        
        # API documentation settings
        self.api_title = "AI Agent API"
        self.api_version = "1.0.0"
        self.api_description = "API endpoints for AI agent task management and processing"
        
        # Email processing settings
        self.max_emails = int(os.getenv('MAX_EMAILS', 50))
        self.max_tokens = int(os.getenv('MAX_TOKENS', 50000))
        
        # Model settings
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        self.gemini_api_key = os.getenv('GEMINI_API_KEY')
        self.o3_mini_api_key = os.getenv('O3_MINI_API_KEY')

# Create global instances
db_config = DatabaseConfig()
server_config = ServerConfig() 