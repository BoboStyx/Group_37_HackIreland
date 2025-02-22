"""
Configuration settings for the AI agent system.
"""
import os
from typing import Optional
from dotenv import load_dotenv

def load_env_config() -> None:
    """Load environment variables from .env file."""
    # Try to load from .env file
    if os.path.exists(".env"):
        load_dotenv()
    else:
        print("Warning: .env file not found. Using default or system environment variables.")

def get_required_env(key: str) -> str:
    """
    Get a required environment variable.
    
    Args:
        key: The environment variable key
    
    Returns:
        str: The environment variable value
    
    Raises:
        ValueError: If the environment variable is not set
    """
    value = os.getenv(key)
    if value is None:
        raise ValueError(f"Required environment variable '{key}' is not set. "
                       f"Please check your .env file or system environment variables.")
    return value

def get_optional_env(key: str, default: str) -> str:
    """
    Get an optional environment variable with a default value.
    
    Args:
        key: The environment variable key
        default: The default value if not set
    
    Returns:
        str: The environment variable value or default
    """
    return os.getenv(key, default)

# Load environment variables
load_env_config()

# API Keys
OPENAI_API_KEY: Optional[str] = None
O3_MINI_API_KEY: Optional[str] = None

try:
    OPENAI_API_KEY = get_required_env("OPENAI_API_KEY")
    O3_MINI_API_KEY = get_required_env("O3_MINI_API_KEY")
except ValueError as e:
    print(f"Error loading API keys: {str(e)}")
    print("Some functionality may be limited.")

# Model Configuration
GPT4_MODEL = "gpt-4o"
O3_MINI_MODEL = "o3-mini"

# Database Configuration
DATABASE_URL = get_optional_env("DATABASE_URL", "sqlite:///ai_agent.db")

# API Configuration
API_HOST = get_optional_env("API_HOST", "0.0.0.0")
API_PORT = int(get_optional_env("API_PORT", "8000"))
API_TITLE = "AI Agent API"
API_VERSION = "1.0.0"
API_DESCRIPTION = "RESTful API for interacting with the AI agent system"

# Logging Configuration
LOG_LEVEL = get_optional_env("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Agent Configuration
MAX_RETRIES = int(get_optional_env("MAX_RETRIES", "3"))
TIMEOUT = int(get_optional_env("TIMEOUT", "30"))
TEMPERATURE = float(get_optional_env("TEMPERATURE", "0.7"))

# Task Processing Configuration
MAX_TOKENS = int(get_optional_env("MAX_TOKENS", "1000"))  # Maximum tokens per task chunk
MAX_EMAILS = int(get_optional_env("MAX_EMAILS", "5"))  # Maximum emails/tasks per chunk
URGENCY_ORDER = [5, 4, 3, 2, 1]  # Process tasks in order of urgency (5 highest)
HALF_FINISHED_PRIORITY = 4  # Priority level for half-finished tasks
HIGH_PRIORITY_URGENCY_LEVELS = [5, 4, 3]  # Urgency levels considered high priority for task summaries 