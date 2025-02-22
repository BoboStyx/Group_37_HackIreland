"""
O3-mini model integration for deep thinking tasks.
"""
from typing import Optional, Dict, Any
import logging
import requests
import json

from .config import O3_MINI_API_KEY

logger = logging.getLogger(__name__)

# Replace with actual o3-mini endpoint URL if available
O3_MINI_ENDPOINT = "https://api.o3-mini.example.com/v1/solve"

class O3MiniAgent:
    def __init__(self):
        """Initialize the O3-mini agent."""
        if not O3_MINI_API_KEY:
            logger.error("O3-mini API key not found. O3-mini functionality will not be available.")
            self.is_available = False
        else:
            self.is_available = True

    async def process(self, user_input: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        Process user input using the O3-mini model.
        
        Args:
            user_input: The user's input text
            context: Optional context dictionary
        
        Returns:
            str: The model's response
        
        Raises:
            RuntimeError: If the O3-mini functionality is not available
        """
        if not self.is_available:
            raise RuntimeError(
                "O3-mini functionality is not available. "
                "Please check your O3-mini API key in the .env file."
            )

        try:
            # Use think_deep for processing
            return await self.think_deep(self._prepare_prompt(user_input, context))

        except Exception as e:
            logger.error(f"Error in O3-mini processing: {str(e)}")
            raise

    async def think_deep(self, problem_prompt: str) -> str:
        """
        Use o3-mini to think deeply about a complex problem.
        
        This method is specifically designed for problems that require deeper analysis
        and complex reasoning. It utilizes the o3-mini API to process the prompt and
        return a well-thought-out response.
        
        Args:
            problem_prompt (str): A detailed prompt describing the problem that needs
                                deep analysis.
        
        Returns:
            str: The computed result or analysis from o3-mini.
            
        Raises:
            RuntimeError: If the O3-mini functionality is not available
            requests.RequestException: If there's an error communicating with the API
        """
        if not self.is_available:
            raise RuntimeError("O3-mini functionality is not available.")

        payload = {
            "prompt": problem_prompt,
            "max_tokens": 700,  # Adjust as necessary
            "temperature": 0.7,  # Balanced between creativity and focus
            "stream": True  # Enable streaming for real-time responses
        }
        
        headers = {
            "Authorization": f"Bearer {O3_MINI_API_KEY}",
            "Content-Type": "application/json"
        }

        try:
            response = requests.post(O3_MINI_ENDPOINT, json=payload, headers=headers)
            response.raise_for_status()
            result = response.json()
            
            # Extract and clean the response
            return self._clean_response(result.get("text", "No result returned"))
            
        except requests.RequestException as e:
            logger.error(f"Error in O3-mini API call: {str(e)}")
            raise

    def _prepare_prompt(self, user_input: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        Prepare the prompt for the O3-mini model.
        
        Args:
            user_input: The user's input text
            context: Optional context dictionary
        
        Returns:
            str: The prepared prompt
        """
        system_prompt = "You are an AI assistant specialized in deep analysis and complex reasoning."
        
        if context and "history" in context:
            history = "\n".join([f"{msg['role']}: {msg['content']}" for msg in context["history"]])
            return f"{system_prompt}\n\nContext:\n{history}\n\nUser: {user_input}\nAssistant:"
        
        return f"{system_prompt}\n\nUser: {user_input}\nAssistant:"

    def _clean_response(self, response: str) -> str:
        """
        Clean the model's response by removing any artifacts.
        
        Args:
            response: The raw model response
        
        Returns:
            str: The cleaned response
        """
        # Remove any unwanted artifacts or formatting
        response = response.strip()
        
        # Remove any system-specific markers
        response = response.replace("Assistant:", "").strip()
        response = response.replace("User:", "").strip()
        
        return response 