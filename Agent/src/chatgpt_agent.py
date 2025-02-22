"""
ChatGPT-4 integration and prompt management.
"""
from typing import Optional, Dict, Any, AsyncGenerator
import logging
from openai import AsyncOpenAI
import json
from config import OPENAI_API_KEY, GPT4_MODEL, TEMPERATURE
from o3_mini import O3MiniAgent

logger = logging.getLogger(__name__)

class ChatGPTAgent:
    def __init__(self):
        """Initialize the ChatGPT agent."""
        if not OPENAI_API_KEY:
            logger.error("OpenAI API key not found. ChatGPT functionality will not be available.")
            self.is_available = False
        else:
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
            
            stream = await self.client.chat.completions.create(
                model=GPT4_MODEL,
                messages=messages,
                temperature=TEMPERATURE,
                stream=True
            )
            
            async for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            logger.error(f"Error in ChatGPT processing: {str(e)}")
            raise

    async def summarize_tasks(self, task_chunk: str) -> AsyncGenerator[str, None]:
        """
        Send a chunk of tasks to ChatGPT-4 and return a summarized rundown.
        
        Args:
            task_chunk (str): A string containing a chunk of tasks to be summarized
        
        Returns:
            AsyncGenerator[str, None]: Summary chunks provided by ChatGPT-4
        """
        if not self.is_available:
            raise RuntimeError("ChatGPT functionality is not available.")

        prompt_template = """Please provide a clear and organized summary of the following tasks.
        For each task:
        1. Show the Task ID at the start of each item
        2. Highlight the urgency level
        3. Include any deadlines
        4. Provide a brief but clear description
        5. Note the current status

        Format the output as a numbered list, ordered by urgency (highest first).
        Use bullet points for any sub-details.
        
        Tasks to summarize:
        <TASK_CHUNK>"""

        prompt = prompt_template.replace("<TASK_CHUNK>", task_chunk)
        
        try:
            stream = await self.client.chat.completions.create(
                model=GPT4_MODEL,
                messages=[
                    {"role": "system", "content": "You are a task management assistant focused on clear and concise summaries."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,  # Lower temperature for more consistent formatting
                stream=True
            )
            
            async for chunk in stream:
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
                - status: Current task status
        
        Returns:
            AsyncGenerator[str, None]: Prompt chunks for the user
        """
        if not self.is_available:
            raise RuntimeError("ChatGPT functionality is not available.")

        system_prompt = """You are a proactive task management assistant.
        Your role is to:
        1. Help users understand the importance and context of their tasks
        2. Provide clear, actionable next steps
        3. Be encouraging but concise
        4. Consider task urgency and deadlines in your suggestions"""

        task_prompt = f"""Analyze this task and provide guidance:

        Task Details:
        - ID: {task.get('id')}
        - Description: {task.get('description', 'No description provided')}
        - Urgency: {task.get('urgency', 'Not specified')}
        - Deadline: {task.get('deadline', 'No deadline')}
        - Category: {task.get('category', 'Uncategorized')}
        - Current Status: {task.get('status', 'Not started')}

        Please provide:
        1. A brief assessment of the task's importance and time-sensitivity
        2. 2-3 concrete next steps or approaches to handle this task
        3. Any potential challenges to consider
        4. A clear prompt for what action to take (complete/remind/help/skip)"""

        try:
            stream = await self.client.chat.completions.create(
                model=GPT4_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": task_prompt}
                ],
                temperature=0.7,  # Balanced between creativity and focus
                stream=True
            )
            
            async for chunk in stream:
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

        if context and "history" in context:
            messages.extend(context["history"])

        messages.append({"role": "user", "content": user_input})
        return messages

    def _get_system_prompt(self) -> str:
        """
        Get the system prompt for the ChatGPT model.
        
        Returns:
            str: The system prompt
        """
        return """You are a friendly and proactive AI assistant named Aide, focused on helping users manage their tasks and projects effectively.

        Your personality:
        - Warm and approachable, but professional
        - Direct and clear in communication
        - Proactive in identifying potential issues and opportunities
        - Encouraging and supportive
        - Honest about limitations and uncertainties

        When greeting users:
        - Be direct about the current task status based on the context provided
        - If has_tasks is false, directly state there are no current tasks
        - If has_tasks is true, mention the number of tasks (task_count)
        - Keep greetings brief and focused
        - Never ask about tasks when you have the task status in context
        - Never use emojis or overly casual language

        When discussing tasks:
        - Show genuine interest in helping users succeed
        - Provide clear, actionable next steps
        - Be honest if a task seems less important
        - Offer to think deeply about complex problems
        - Suggest breaking down overwhelming tasks
        - Be proactive about setting reminders

        When no tasks are present:
        - Directly acknowledge the absence of tasks
        - Strongly encourage signing up for:
          * Professional newsletters in their field
          * Industry group notifications
          * Relevant opportunity alerts
          * Curated email digests
        - Emphasize your role in:
          * Filtering out time-wasting content
          * Identifying truly valuable opportunities
          * Prioritizing information that advances their career/goals
          * Preventing information overload
        - Explain that more information sources help you better serve them and that they needn't worry about information overload as you will ensure only the information that directly benefits them reaches them, and will filter out the rest.
        - Be very clear that while ordinarily these things can clutter an inbox, you will make sure it's actually beneficial
        - Maintain a professional tone while conveying the importance of staying informed

        Communication style:
        - Use a natural but professional tone
        - Be clear and structured in explanations
        - Ask clarifying questions when needed
        - Acknowledge user concerns and preferences
        - Maintain formality while being approachable
        - Never use emojis or excessive punctuation

        Remember to:
        - Keep track of task context and user preferences
        - Suggest deep thinking mode for complex problems
        - Be proactive about follow-ups and reminders
        - Always maintain a helpful and positive attitude
        - Help users find the right balance between staying informed and being overwhelmed""" 