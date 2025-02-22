"""
O3-mini model integration for deep thinking tasks.
"""
from typing import Optional, Dict, Any, AsyncGenerator
import logging
from openai import AsyncOpenAI
import json

from config import O3_MINI_API_KEY, O3_MINI_MODEL

logger = logging.getLogger(__name__)

class O3MiniAgent:
    def __init__(self):
        """Initialize the O3-mini agent."""
        if not O3_MINI_API_KEY:
            logger.error("O3-mini API key not found. O3-mini functionality will not be available.")
            self.is_available = False
        else:
            self.client = AsyncOpenAI(api_key=O3_MINI_API_KEY)
            self.is_available = True

    async def process(self, user_input: str, context: Optional[Dict[str, Any]] = None) -> AsyncGenerator[str, None]:
        """
        Process user input using the O3-mini model.
        
        Args:
            user_input: The user's input text
            context: Optional context dictionary
        
        Returns:
            AsyncGenerator[str, None]: The model's response chunks
        
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
            async for chunk in self.think_deep(self._prepare_prompt(user_input, context)):
                yield chunk

        except Exception as e:
            logger.error(f"Error in O3-mini processing: {str(e)}")
            raise

    async def think_deep(self, problem_prompt: str) -> AsyncGenerator[str, None]:
        """
        Use o3-mini to think deeply about a complex problem.
        
        This method is specifically designed for problems that require deeper analysis
        and complex reasoning. It utilizes the o3-mini API to process the prompt and
        return a well-thought-out response.
        
        Args:
            problem_prompt (str): A detailed prompt describing the problem that needs
                                deep analysis.
        
        Returns:
            AsyncGenerator[str, None]: The computed result or analysis from o3-mini.
            
        Raises:
            RuntimeError: If the O3-mini functionality is not available
        """
        if not self.is_available:
            raise RuntimeError("O3-mini functionality is not available.")

        try:
            stream = await self.client.chat.completions.create(
                model=O3_MINI_MODEL,
                messages=[
                    {"role": "system", "content": "You are an AI assistant specialized in deep analysis and complex reasoning."},
                    {"role": "user", "content": problem_prompt}
                ],
                temperature=0.7,
                stream=True
            )
            
            async for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    yield chunk.choices[0].delta.content
            
        except Exception as e:
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
            return f"{system_prompt}\n\nContext:\n{history}\n\nUser: {user_input}"
        
        return f"{system_prompt}\n\nUser: {user_input}" 