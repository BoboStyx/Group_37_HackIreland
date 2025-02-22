"""
ChatGPT-4 integration and prompt management.
"""
from typing import Optional, Dict, Any, AsyncGenerator
import logging
from openai import AsyncOpenAI
import json
from .config import OPENAI_API_KEY, GPT4_MODEL, TEMPERATURE
from .o3_mini import O3MiniAgent

logger = logging.getLogger(__name__)

# Replace with actual ChatGPT-4o endpoint URL if available
CHATGPT_ENDPOINT = "https://api.openai.com/v1/chat/completions"

class ChatGPTAgent:
    def __init__(self):
        """Initialize the ChatGPT agent."""
        if not OPENAI_API_KEY:
            logger.error("OpenAI API key not found. ChatGPT functionality will not be available.")
            self.is_available = False
        else:
            # Initialize with just the API key as per documentation
            self.client = AsyncOpenAI(api_key=OPENAI_API_KEY)
            self.is_available = True
            self.o3_mini = O3MiniAgent()  # Initialize O3MiniAgent

    async def process(self, user_input: str, context: Optional[Dict[str, Any]] = None, deep_thinking: bool = False) -> AsyncGenerator[str, None]:
        """
        Process user input using ChatGPT-4.
        
        Args:
            user_input: The user's input text
            context: Optional context dictionary for conversation history
            deep_thinking: Whether to use deep thinking mode with O3-mini
        
        Returns:
            AsyncGenerator[str, None]: The model's response chunks
        
        Raises:
            RuntimeError: If the ChatGPT functionality is not available
        """
        if not self.is_available:
            raise RuntimeError(
                "ChatGPT functionality is not available. "
                "Please check your OpenAI API key in the .env file."
            )

        try:
            if deep_thinking and self.o3_mini.is_available:
                # Use O3-mini for deep thinking tasks
                async for chunk in self.o3_mini.think_deep(user_input):
                    yield chunk

            messages = self._prepare_messages(user_input, context)
            
            async for chunk in await self.client.chat.completions.create(
                model=GPT4_MODEL,
                messages=messages,
                temperature=TEMPERATURE,
                stream=True  # Enable streaming
            ):
                if chunk.choices[0].delta.content is not None:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            logger.error(f"Error in ChatGPT processing: {str(e)}")
            raise

    async def summarize_tasks(self, task_chunk: str) -> AsyncGenerator[str, None]:
        """
        Send a chunk of tasks to ChatGPT-4o and return a summarized rundown.
        
        Args:
            task_chunk (str): A string containing a chunk of tasks to be summarized
        
        Returns:
            AsyncGenerator[str, None]: Summary chunks provided by ChatGPT-4o
        """
        if not self.is_available:
            raise RuntimeError("ChatGPT functionality is not available.")

        prompt_template = """Please provide a concise summary of the following tasks, 
        highlighting key priorities and deadlines:

        <TASK_CHUNK>

        Format the summary in bullet points, organized by priority."""

        prompt = prompt_template.replace("<TASK_CHUNK>", task_chunk)
        
        try:
            async for chunk in await self.client.chat.completions.create(
                model=GPT4_MODEL,
                messages=[
                    {"role": "system", "content": "You are a task summarization assistant."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5,  # Lower temperature for more focused summaries
                stream=True
            ):
                if chunk.choices[0].delta.content is not None:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            logger.error(f"Error in task summarization: {str(e)}")
            raise

    async def generate_action_prompt(self, task: dict) -> AsyncGenerator[str, None]:
        """
        Generate a prompt explaining the task and asking the user for the next step.
        
        Args:
            task (dict): A dictionary representing a single task with keys such as:
                - id: Task identifier
                - description: Task description
                - urgency: Task urgency level
                - deadline: Task deadline (if any)
                - category: Task category or type
        
        Returns:
            AsyncGenerator[str, None]: Prompt chunks for the user that:
                1. Highlights the importance or excitement of the task
                2. Offers options for assistance (help, remind, skip)
                3. Provides context-aware suggestions based on task properties
        """
        if not self.is_available:
            raise RuntimeError("ChatGPT functionality is not available.")

        # Create a context-rich prompt for the AI
        system_prompt = """You are an enthusiastic and helpful task assistant. 
        Your goal is to motivate the user about their task while offering practical next steps.
        Keep responses engaging but concise."""

        task_prompt = f"""Generate an engaging prompt for this task:
        Task ID: {task.get('id')}
        Description: {task.get('description', 'No description provided')}
        Urgency: {task.get('urgency', 'Not specified')}
        Deadline: {task.get('deadline', 'No deadline')}
        Category: {task.get('category', 'Uncategorized')}

        Create a response that:
        1. Shows why this task matters
        2. Suggests possible next steps
        3. Asks if they want help deciding, a reminder, or to handle it themselves"""

        try:
            async for chunk in await self.client.chat.completions.create(
                model=GPT4_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": task_prompt}
                ],
                temperature=0.7,  # Balanced between creativity and focus
                stream=True
            ):
                if chunk.choices[0].delta.content is not None:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            logger.error(f"Error generating action prompt: {str(e)}")
            raise

    def _prepare_messages(self, user_input: str, context: Optional[Dict[str, Any]] = None) -> list:
        """
        Prepare the messages for the ChatGPT API.
        
        Args:
            user_input: The user's input text
            context: Optional context dictionary
        
        Returns:
            list: List of message dictionaries for the API
        """
        messages = [
            {"role": "system", "content": self._get_system_prompt()},
        ]

        # Add context if provided
        if context and "history" in context:
            messages.extend(context["history"])

        # Add the current user input
        messages.append({"role": "user", "content": user_input})

        return messages

    def _get_system_prompt(self) -> str:
        """
        Get the system prompt for the ChatGPT model.
        
        Returns:
            str: The system prompt
        """
        return """You are an AI assistant with expertise in various domains. 
        Your responses should be helpful, accurate, and appropriately detailed. 
        When you're not sure about something, acknowledge the uncertainty.
        For complex problems that require deeper analysis, suggest using deep thinking mode.
        Focus on providing practical, actionable information when possible.""" 