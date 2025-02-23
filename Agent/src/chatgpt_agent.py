"""
ChatGPT-4 integration and prompt management.
"""
from typing import Optional, Dict, Any, AsyncGenerator
import logging
from openai import AsyncOpenAI
import json
from config import OPENAI_API_KEY, GPT4_MODEL, TEMPERATURE
from o3_mini import O3MiniAgent
from datetime import datetime
import re

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

    def _is_action_directive(self, text: str) -> bool:
        """Check if text is part of an action directive."""
        # Patterns for task and profile actions
        task_patterns = [
            r'\[ACTION:(\w+):(\d+):([^\]]*)\]',
            r'\[ACTION:(\w+):task_id:([^\]:]+):([^\]]*)\]',
            r'\[ACTION:(\w+):task_id:([^\]]*)\]'
        ]
        profile_pattern = r'\[ACTION:profile:(\w+):([^\]]*)\]'
        
        # Check if text starts with '[' and matches any action pattern
        if not text.startswith('['):
            return False
            
        for pattern in task_patterns:
            if re.match(pattern, text):
                return True
        
        if re.match(profile_pattern, text):
            return True
            
        return False

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
            
            buffer = ""  # Buffer for accumulating potential action directive text
            
            async for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    content = chunk.choices[0].delta.content
                    buffer += content
                    
                    # If buffer starts with '[', accumulate until we can determine if it's an action
                    if buffer.startswith('['):
                        # If we have a complete action directive, process it and clear buffer
                        if ']' in buffer:
                            action_end = buffer.index(']') + 1
                            potential_action = buffer[:action_end]
                            remaining_text = buffer[action_end:]
                            
                            if self._is_action_directive(potential_action):
                                # Skip yielding the action directive
                                # Yield remaining text if any
                                if remaining_text:
                                    yield remaining_text
                            else:
                                # Not an action directive, yield entire buffer
                                yield buffer
                            buffer = ""
                        # Otherwise keep accumulating
                        continue
                    else:
                        # No potential action directive, yield buffer
                        yield buffer
                        buffer = ""
            
            # Handle any remaining buffer
            if buffer and not self._is_action_directive(buffer):
                yield buffer

        except Exception as e:
            logger.error(f"Error in ChatGPT processing: {str(e)}")
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
        # Get base system prompt
        system_prompt = self._get_system_prompt()
        
        # Add profile information if available
        if context and "profile" in context:
            profile = context["profile"]
            # If a name exists in the profile, explicitly include it in the system prompt
            if isinstance(profile, dict) and "name" in profile and profile["name"]:
                system_prompt += f"\n\nUser's Name: {profile['name']}"
            
            # Convert datetime objects to ISO format strings in profile
            def datetime_handler(obj):
                if isinstance(obj, datetime):
                    return obj.isoformat()
                raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
            
            profile_json = json.dumps(profile, indent=2, default=datetime_handler)
            system_prompt += f"\n\nCurrent user profile:\n{profile_json}\n\nMake sure to reference and use this profile information naturally in your responses."
        
        # Add debug logging to see what's happening
        logger.info(f"System prompt name section: {'Users Name: ' + context['profile']['name'] if context and 'profile' in context and 'name' in context['profile'] else 'No name found'}")
        
        messages = [
            {"role": "system", "content": system_prompt},
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
        - If has_tasks is true, mention the number of tasks (task_count) and suggest they can view them by typing 'tasks'
        - If has_tasks is false, directly state there are no current tasks and offer to help find opportunities
        - Keep greetings brief and focused
        - Never ask about tasks when you have the task status in context
        - Never use emojis or overly casual language
        - Only mention tasks once in your greeting

        When discussing tasks:
        - Show genuine interest in helping users succeed
        - Provide clear, actionable next steps
        - Be honest if a task seems less important
        - Offer to think deeply about complex problems
        - Suggest breaking down overwhelming tasks
        - Be proactive about setting reminders
        - Present tasks in order of urgency
        - Focus on one task at a time
        - Let the user drive the conversation pace
        - Adapt task descriptions to match the user's profile and preferences
        - When setting reminders or discussing times:
          * ALWAYS use the current_time from context for accurate timing
          * Format times in UTC and mention the timezone
          * Consider user_timezone (Europe/Dublin) when discussing times
          * Be explicit about dates and times in your responses
        - When a user mentions new tasks or information:
          * For new tasks: [ACTION:create_task:{"description":"task description", "urgency":1-5, "deadline":"date", "notes":"additional details"}]
          * For adding notes: [ACTION:notes:task_id:note content]
        - When a user indicates a task is complete or needs modification, use action directives:
          * For completion: [ACTION:complete:task_id:reason]
          * For reminders: [ACTION:remind:task_id:3h]  # Use time format like 3h, 2d
          * For help/breakdown: [ACTION:help:task_id:details]
          * For email drafts: [ACTION:draft_email:task_id:{"subject":"...","to":"..."}]

        When no tasks are present:
        - Directly acknowledge the absence of tasks
        - If profile exists, suggest opportunities based on their interests and goals
        - Recommend information sources aligned with their professional background
        - Focus on their specific industry sectors and career aspirations
        - Maintain a professional tone

        Using profile information:
        - ALWAYS use the user's name and background information when available
        - Tailor ALL responses to match their communication style and preferences
        - Reference their specific skills and experiences when relevant
        - Adapt task descriptions to align with their work style
        - Consider their stated goals and aspirations in recommendations
        - Match your communication style to their preferences
        - If asked about profile information, share it naturally
        - When discussing tasks, frame them in terms of their interests and strengths
        - When learning new information about the user, use profile action directives:
          * For new insights: [ACTION:profile:update:{"key":"value","reason":"explanation"}]
          * For preferences: [ACTION:profile:preference:{"key":"value","reason":"explanation"}]
          * For goals: [ACTION:profile:goal:{"description":"...","timeframe":"..."}]

        Communication style:
        - Use a natural but professional tone
        - Be clear and structured in explanations
        - Ask clarifying questions when needed
        - Acknowledge user concerns and preferences
        - Maintain formality while being approachable
        - Never use emojis or excessive punctuation
        - Never repeat yourself or give redundant prompts
        - Match your style to the user's preferences from their profile
        - Always include relevant times and dates in UTC when discussing schedules

        Remember to:
        - Keep track of task context and user preferences
        - Suggest deep thinking mode for complex problems
        - Be proactive about follow-ups and reminders
        - Always maintain a helpful and positive attitude
        - Help users find the right balance between staying informed and being overwhelmed
        - Use profile information to personalize ALL interactions
        - Use action directives when tasks need to be modified or completed
        - Use profile action directives when learning new information about the user
        - ALWAYS reference current_time when discussing timing or schedules
        - Consider the user's timezone (Europe/Dublin) when suggesting times"""

    async def process_input(self, user_input: str, context: Optional[Dict] = None) -> str:
        """
        Process user input and return a response.
        
        Args:
            user_input (str): The user's input text
            context (Optional[Dict]): Optional context dictionary containing conversation history and profile
            
        Returns:
            str: The agent's response
        """
        try:
            # Initialize context if None
            if context is None:
                context = {}

            # Always retrieve the latest profile information and add/update it in context
            from profile_manager import ProfileManager
            profile_manager = ProfileManager()
            profile = await profile_manager.get_profile()
            if profile:
                context['profile'] = profile
                logger.info("Latest profile added to context in agent process_input")
            
            # Prepare messages with profile-aware context
            messages = self._prepare_messages(user_input, context)
            
            # Get response from OpenAI
            response = await self.client.chat.completions.create(
                model=GPT4_MODEL,
                messages=messages,
                temperature=0.7,
                max_tokens=1000
            )
            
            # Extract and return the response text
            response_text = response.choices[0].message.content.strip()
            
            # Update conversation history in context
            if 'history' not in context:
                context['history'] = []
            context['history'].append({
                'user': user_input,
                'assistant': response_text,
                'model': GPT4_MODEL
            })
            
            return response_text
            
        except Exception as e:
            logger.error(f"Error processing input: {str(e)}")
            return "I apologize, but I encountered an error processing your input. Please try again." 