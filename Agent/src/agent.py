"""
Main AI agent implementation coordinating between different models and tasks.
"""
from typing import Optional, Dict, Any, List, AsyncGenerator
import logging
from datetime import datetime, timedelta
import json
import re

from chatgpt_agent import ChatGPTAgent
from o3_mini import O3MiniAgent
from database import SessionLocal, Conversation, AgentTask, Task, get_tasks_by_urgency, update_task_status, get_task_by_id, update_task_urgency, append_task_notes, create_task, update_task_description
from config import (
    MAX_RETRIES, TIMEOUT, MAX_TOKENS, MAX_EMAILS,
    URGENCY_ORDER, HALF_FINISHED_PRIORITY
)
from profile_manager import ProfileManager

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AIAgent:
    def __init__(self):
        """Initialize the AI agent with its component models."""
        self.chatgpt = ChatGPTAgent()
        self.o3_mini = O3MiniAgent()
        self.db = None  # Initialize as None
        try:
            self.db = SessionLocal()
        except Exception as e:
            logger.error(f"Failed to initialize database: {str(e)}")

        # Log availability of models
        if not self.chatgpt.is_available:
            logger.warning("ChatGPT model is not available")
        if not self.o3_mini.is_available:
            logger.warning("O3-mini model is not available")

    async def process_input(self, user_input: str, context: Optional[Dict[str, Any]] = None) -> AsyncGenerator[str, None]:
        """
        Process user input and return the appropriate response.
        
        Args:
            user_input: The user's input text
            context: Optional context dictionary for maintaining conversation state
                    Special keys:
                    - is_greeting: True if this is the initial greeting
                    - has_tasks: Whether there are any tasks
                    - task_count: Number of current tasks
                    - tasks: List of available tasks
                    - history: List of previous message exchanges
                    - current_task_id: ID of the task currently being discussed
                    - profile: User profile information
        
        Returns:
            AsyncGenerator[str, None]: The agent's response chunks
        
        Raises:
            RuntimeError: If no models are available
        """
        if not self.chatgpt.is_available and not self.o3_mini.is_available:
            raise RuntimeError("No AI models are available.")

        try:
            # Process input for profile insights first
            learned_something = False
            profile_insight = None
            if not context.get('is_greeting'):  # Skip profile processing for greetings
                profile_manager = ProfileManager()
                profile, insight = await profile_manager.process_input(user_input, is_direct_input=False)
                if insight:
                    # Update context with new profile information
                    if context is None:
                        context = {}
                    context['profile'] = profile
                    logger.info(f"Updated user profile from conversation: {insight}")
                    learned_something = True
                    profile_insight = insight

            # If this is a greeting, create a special prompt
            if context and context.get('is_greeting'):
                items = context.get('tasks', [])
                task_count = len([i for i in items if i.get('type', 'task') == 'task'])
                info_count = len([i for i in items if i.get('type') != 'task'])
                
                greeting_prompt = f"""You are a helpful AI assistant with access to both tasks and interesting information/opportunities.

                Current status:
                - Tasks: {task_count} active tasks
                - Information/Opportunities: {info_count} items
                
                Available items:
                {self._format_tasks_for_ai(items)}
                
                Create a warm, friendly greeting that:
                1. Acknowledges both tasks and information/opportunities
                2. Mentions the number of tasks that need attention
                3. Hints at interesting opportunities if any exist
                4. Suggests what we should focus on first, considering:
                   - Task urgency and deadlines
                   - Task complexity and dependencies
                   - User's recent activity (if any in conversation history)
                   - Balance between tasks and opportunities
                5. Keeps it concise and conversational
                6. Avoids mentioning specific commands
                7. Makes it clear you can help with both urgent tasks and exploring interesting opportunities
                
                Make it feel like a natural conversation starter with a helpful colleague who knows what needs attention."""
                
                # Create a new context dictionary that preserves all existing keys
                greeting_context = context.copy()
                greeting_context.update({
                    "role": "greeter",
                    "style": "warm",
                    "focus": "welcoming",
                    "history": context.get('history', [])
                })
                
                # Get latest profile if not already in context
                if 'profile' not in greeting_context:
                    profile_manager = ProfileManager()
                    profile = await profile_manager.get_profile()
                    if profile:
                        greeting_context['profile'] = profile
                
                async for chunk in self.chatgpt.process(greeting_prompt, greeting_context):
                    yield chunk
                return

            # For everything else, process naturally with task context
            if context and 'tasks' in context:
                async for chunk in self.handle_task_input(user_input, context['tasks'], context):
                    yield chunk
                
                # If we learned something about the user, mention it naturally
                if learned_something and profile_insight:
                    yield f"\n\nBy the way, I noticed something about you, and saved it to my memory to improve our interactions: {profile_insight}"
                return

            # Create a new conversation entry
            task = AgentTask(
                task_type="process_input",
                status="in_progress"
            )
            self.db.add(task)
            self.db.commit()

            # Determine which model to use
            use_o3_mini = (
                self.o3_mini.is_available and 
                self._requires_deep_thinking(user_input)
            )

            response_chunks = []
            try:
                if use_o3_mini:
                    async for chunk in self.o3_mini.process(user_input, context):
                        response_chunks.append(chunk)
                        yield chunk
                    model_used = "o3-mini"
                else:
                    if not self.chatgpt.is_available:
                        raise RuntimeError("ChatGPT is not available and this input requires it")
                    async for chunk in self.chatgpt.process(user_input, context):
                        response_chunks.append(chunk)
                        yield chunk
                    model_used = "gpt-4"

                # If we learned something about the user, mention it naturally after the response
                if learned_something and profile_insight:
                    yield f"\n\nBy the way, I noticed something about you: {profile_insight}"

            except Exception as model_error:
                # If primary model fails, try fallback to the other model
                logger.warning(f"Primary model failed: {str(model_error)}")
                response_chunks = []
                if use_o3_mini and self.chatgpt.is_available:
                    logger.info("Falling back to ChatGPT")
                    async for chunk in self.chatgpt.process(user_input, context):
                        response_chunks.append(chunk)
                        yield chunk
                    model_used = "gpt-4"
                elif not use_o3_mini and self.o3_mini.is_available:
                    logger.info("Falling back to O3-mini")
                    async for chunk in self.o3_mini.process(user_input, context):
                        response_chunks.append(chunk)
                        yield chunk
                    model_used = "o3-mini"
                else:
                    raise

                # If we learned something about the user, mention it naturally after the fallback response
                if learned_something and profile_insight:
                    yield f"\n\nBy the way, I noticed something about you: {profile_insight}"

            response = "".join(response_chunks)

            # Store the conversation
            conversation = Conversation(
                user_input=user_input,
                agent_response=response,
                model_used=model_used
            )
            self.db.add(conversation)

            # Update task status
            task.status = "completed"
            task.result = response
            self.db.commit()

        except Exception as e:
            logger.error(f"Error processing input: {str(e)}")
            raise

    def _requires_deep_thinking(self, input_text: str) -> bool:
        """
        Determine if the input requires the O3-mini model for deep thinking.
        
        Args:
            input_text: The input text to analyze
        
        Returns:
            bool: True if O3-mini should be used, False for ChatGPT
        """
        # Add logic to determine which model to use
        # This is a simple implementation that can be enhanced
        deep_thinking_keywords = {'analyze', 'compare', 'evaluate', 'synthesize'}
        return any(keyword in input_text.lower() for keyword in deep_thinking_keywords)

    async def get_task_count(self) -> int:
        """
        Get the total count of active tasks.
        
        Returns:
            int: The number of active tasks
        """
        try:
            count = 0
            for urgency in URGENCY_ORDER:
                tasks = get_tasks_by_urgency(urgency)
                if tasks:
                    count += len(tasks)
                
                # Include half-finished tasks in the count
                if urgency == HALF_FINISHED_PRIORITY:
                    half_finished = [t for t in tasks if t.get('status') == 'half-completed']
                    count += len(half_finished)
            
            return count
            
        except Exception as e:
            logger.error(f"Error getting task count: {str(e)}")
            raise

    async def get_tasks(self) -> List[dict]:
        """
        Retrieve all tasks and information items ordered by urgency.
        
        Returns:
            List[dict]: List of all tasks and information items
        """
        try:
            all_items = []
            for urgency in URGENCY_ORDER:
                items = get_tasks_by_urgency(urgency)
                if items:  # Only extend if we got items
                    # Filter out completed tasks
                    active_items = [item for item in items if item.get('status') != 'completed']
                    all_items.extend(active_items)

                # Handle half-finished tasks with special priority
                if urgency == HALF_FINISHED_PRIORITY:
                    half_finished = [t for t in items if t.get('status') == 'half-completed']
                    if half_finished:
                        all_items.extend(half_finished)

            return all_items

        except Exception as e:
            logger.error(f"Error retrieving tasks: {str(e)}")
            raise

    def _chunk_tasks(self, tasks: List[dict]) -> List[List[dict]]:
        """
        Split tasks into chunks based on MAX_TOKENS or MAX_EMAILS.
        
        Args:
            tasks: List of task dictionaries
        
        Returns:
            List of task chunks
        """
        chunks = []
        current_chunk = []
        current_size = 0

        for task in tasks:
            # Estimate token count (rough approximation)
            task_size = len(str(task)) // 4  # Rough estimate of tokens
            
            if (len(current_chunk) >= MAX_EMAILS or 
                current_size + task_size > MAX_TOKENS):
                if current_chunk:  # Don't add empty chunks
                    chunks.append(current_chunk)
                current_chunk = [task]
                current_size = task_size
            else:
                current_chunk.append(task)
                current_size += task_size

        if current_chunk:  # Add the last chunk if not empty
            chunks.append(current_chunk)

        return chunks

    async def present_tasks(self, tasks: List[dict]) -> str:
        """
        Have the AI present the tasks in a conversational way.
        
        Args:
            tasks: List of task dictionaries
        
        Returns:
            str: The AI's conversational presentation of the tasks
        """
        try:
            # Group tasks by urgency
            tasks_by_urgency = {}
            half_finished = []
            
            for task in tasks:
                urgency = task.get('urgency', 0)
                status = task.get('status', '')
                
                if status == 'half-completed':
                    half_finished.append(task)
                else:
                    if urgency not in tasks_by_urgency:
                        tasks_by_urgency[urgency] = []
                    tasks_by_urgency[urgency].append(task)
            
            # Create a natural introduction
            prompt = """You are a friendly, helpful AI assistant. Present the most urgent tasks in a casual, 
            conversational way. Don't list everything at once - just give a quick overview of what needs attention,
            focusing mainly on urgency level 5 tasks and any half-finished tasks.
            
            Be brief but engaging. After mentioning the most urgent items, ask if the user would like to:
            1. Look at any specific task in more detail
            2. See more tasks
            3. Get help prioritizing
            
            Make it feel like a natural conversation with a helpful colleague.
            
            Current tasks by urgency:
            """
            
            # Add urgency 5 tasks first
            if 5 in tasks_by_urgency:
                prompt += "\nUrgency 5 (Most urgent):\n"
                for task in tasks_by_urgency[5]:
                    prompt += f"[Task #{task.get('id')}]: {task.get('description')}\n"
            
            # Add half-finished tasks
            if half_finished:
                prompt += "\nHalf-finished tasks:\n"
                for task in half_finished:
                    prompt += f"[Task #{task.get('id')}]: {task.get('description')} (Status: In progress)\n"
            
            # Add a note about other tasks
            other_count = sum(len(tasks) for urgency, tasks in tasks_by_urgency.items() if urgency < 5)
            if other_count > 0:
                prompt += f"\nThere are also {other_count} other tasks with lower urgency levels that we can look at later.\n"
            
            # Get the AI's response
            response = ""
            async for chunk in self.chatgpt.process(prompt, {
                "role": "task_presenter",
                "style": "conversational",
                "focus": "high_priority"
            }):
                response += chunk
            
            return response

        except Exception as e:
            logger.error(f"Error presenting tasks: {str(e)}")
            raise

    def _format_tasks_for_ai(self, items: List[dict]) -> str:
        """
        Format tasks and information items for AI consumption.
        
        Args:
            items: List of tasks and information items
            
        Returns:
            str: Formatted string of items
        """
        formatted = []
        
        # Group items by type
        tasks = [i for i in items if i.get('type', 'task') == 'task']
        info_items = [i for i in items if i.get('type') == 'info']
        
        # Format tasks
        if tasks:
            formatted.append("Tasks:")
            for task in tasks:
                task_str = f"[Task #{task['id']}]: {task['description']}"
                if task.get('urgency'):
                    task_str += f" (Urgency: {task['urgency']})"
                if task.get('status'):
                    task_str += f" - {task['status']}"
                if task.get('notes'):
                    task_str += f"\n  Notes: {task['notes']}"
                formatted.append(task_str)
        
        # Format information items
        if info_items:
            if tasks:  # Add a blank line if we had tasks
                formatted.append("")
            formatted.append("Interesting Information:")
            for item in info_items:
                info_str = f"[Info #{item['id']}]: {item['description']}"
                if item.get('source'):
                    info_str += f"\n  Source: {item['source']}"
                if item.get('notes'):
                    info_str += f"\n  Notes: {item['notes']}"
                formatted.append(info_str)
        
        if not formatted:
            return "No items available."
            
        return "\n".join(formatted)

    async def process_selected_task(self, task_id: int) -> AsyncGenerator[str, None]:
        """
        Process a selected task by generating an action prompt and handling user interaction.
        
        Args:
            task_id: The ID of the task to process
            
        Returns:
            AsyncGenerator[str, None]: The AI's response chunks
            
        Raises:
            ValueError: If the task is not found
        """
        try:
            # Get the task from the database
            task = get_task_by_id(task_id)
            if not task:
                raise ValueError(f"Task {task_id} not found")

            # Create a conversational prompt about this task
            task_prompt = f"""You are a helpful AI assistant discussing a specific task with the user.
            Be engaging and supportive, like a colleague helping to tackle a challenge together.
            
            Current task:
            [Task #{task.get('id')}]: {task.get('description')}
            Urgency: {task.get('urgency')}
            Status: {task.get('status')}
            
            First, briefly explain why this task is important or exciting, and what impact it might have.
            Then, offer to:
            1. Help break it down into smaller steps
            2. Set a reminder for later
            3. Provide specific assistance or guidance
            4. Mark it as complete if it's done
            
            Make it conversational and encouraging, but keep it concise."""

            # Get the AI's response
            response = ""
            print("\nAI: ", end="", flush=True)
            async for chunk in self.chatgpt.process(task_prompt, {
                "role": "task_helper",
                "style": "supportive",
                "focus": "action_oriented"
            }):
                response += chunk
                print(chunk, end="", flush=True)
            print()  # Add a newline after streaming

            while True:
                print("\nWhat would you like to do? You can:")
                print("1. Get help breaking it down")
                print("2. Set a reminder")
                print("3. Mark as complete")
                print("4. Get specific assistance")
                print("5. Go back to task list")
                
                action = input("\nYour choice (1-5): ").strip()
                
                if action == "5":
                    break
                elif action == "1":
                    # Help break down the task
                    breakdown_prompt = f"Help break down this task into manageable steps: {task.get('description')}"
                    breakdown = ""
                    print("\nAI: ", end="", flush=True)
                    async for chunk in self.chatgpt.process(breakdown_prompt, {
                        "role": "task_breakdown",
                        "style": "helpful",
                        "focus": "actionable_steps"
                    }):
                        breakdown += chunk
                        print(chunk, end="", flush=True)
                    print()  # Add a newline after streaming
                    
                    # Mark as half-completed
                    update_task_status(task_id, 'half-completed', datetime.utcnow())
                    print("\nAI: I've marked this task as in progress. We can come back to it anytime.")
                    break
                    
                elif action == "2":
                    print("\nWhen would you like to be reminded? (Examples: '2h' for 2 hours, '3d' for 3 days, or enter a specific date/time)")
                    reminder_input = input("Reminder time: ").strip().lower()
                    
                    # Parse the reminder time
                    try:
                        if reminder_input.endswith('h'):
                            hours = int(reminder_input[:-1])
                            reminder_time = datetime.utcnow() + timedelta(hours=hours)
                        elif reminder_input.endswith('d'):
                            days = int(reminder_input[:-1])
                            reminder_time = datetime.utcnow() + timedelta(days=days)
                        elif reminder_input == "next debrief":
                            reminder_time = "next_debrief"
                        else:
                            # Try to parse as datetime
                            reminder_time = datetime.strptime(reminder_input, "%Y-%m-%d %H:%M")
                        
                        update_task_status(task_id, task.get('status'), reminder_time)
                        print(f"\nAI: I'll remind you about this task at the specified time.")
                        break
                    except ValueError:
                        print("\nAI: I didn't understand that time format. Please try again.")
                        continue
                    
                elif action == "3":
                    update_task_status(task_id, 'completed', None)
                    print("\nAI: Great job! I've marked this task as completed. Is there anything else you'd like to look at?")
                    break
                    
                elif action == "4":
                    # Get specific assistance
                    print("\nWhat specific aspect would you like help with?")
                    aspect = input("Your focus: ").strip()
                    
                    # Use deep thinking for complex assistance
                    if self._requires_deep_thinking(aspect):
                        print("\nAI: This seems like it needs some careful thought. Would you like me to analyze this deeply? (y/n)")
                        if input().strip().lower() == 'y':
                            response = ""
                            print("\nAI: ", end="", flush=True)
                            async for chunk in self.o3_mini.think_deep(
                                f"Help with this specific aspect of the task: {aspect}\nTask context: {task.get('description')}"
                            ):
                                response += chunk
                                print(chunk, end="", flush=True)
                            print()  # Add a newline after streaming
                    else:
                        assistance = ""
                        print("\nAI: ", end="", flush=True)
                        async for chunk in self.chatgpt.process(
                            f"Provide specific help with this aspect: {aspect}\nTask context: {task.get('description')}",
                            {"role": "specific_helper"}
                        ):
                            assistance += chunk
                            print(chunk, end="", flush=True)
                        print()  # Add a newline after streaming
                    continue
                    
                else:
                    print("\nAI: I didn't catch that. Please choose a number between 1 and 5.")
                    continue

            # Yield any changes from action processing
            yield "\n" + response.replace(response, "").strip()

        except Exception as e:
            logger.error(f"Error processing selected task: {str(e)}")
            raise

    async def update_task_priority(self, task_id: int, new_urgency: int, reason: str) -> None:
        """
        Update a task's urgency level and add a note explaining why.
        
        Args:
            task_id: The ID of the task to update
            new_urgency: The new urgency level (1-5)
            reason: The reason for the urgency change
            
        Raises:
            ValueError: If the task is not found or urgency is invalid
        """
        try:
            # First verify the task exists
            task = get_task_by_id(task_id)
            if not task:
                raise ValueError(f"Task {task_id} not found")

            # Update the urgency
            update_task_urgency(task_id, new_urgency)
            
            # Add a note about the change
            note = f"Urgency changed from {task['urgency']} to {new_urgency}. Reason: {reason}"
            append_task_notes(task_id, note)
            
            logger.info(f"Updated urgency for task {task_id} to {new_urgency}")
            
        except Exception as e:
            logger.error(f"Error updating task priority: {str(e)}")
            raise

    async def add_task_notes(self, task_id: int, notes: str) -> None:
        """
        Add additional notes to a task.
        
        Args:
            task_id: The ID of the task
            notes: The notes to add
            
        Raises:
            ValueError: If the task is not found
        """
        try:
            if not get_task_by_id(task_id):
                raise ValueError(f"Task {task_id} not found")
                
            append_task_notes(task_id, notes)
            logger.info(f"Added notes to task {task_id}")
            
        except Exception as e:
            logger.error(f"Error adding task notes: {str(e)}")
            raise

    async def create_new_task(self, description: str, urgency: int, alert_at: Optional[datetime] = None) -> int:
        """
        Create a new task in the system.
        
        Args:
            description: The task description
            urgency: The urgency level (1-5)
            alert_at: Optional datetime for when to alert about this task
            
        Returns:
            int: The ID of the newly created task
            
        Raises:
            ValueError: If urgency is invalid
        """
        try:
            task_id = create_task(description, urgency, alert_at=alert_at)
            logger.info(f"Created new task with ID {task_id}")
            return task_id
            
        except Exception as e:
            logger.error(f"Error creating new task: {str(e)}")
            raise

    async def _identify_task_modification(self, user_input: str, task_id: int) -> Optional[Dict[str, Any]]:
        """
        Analyze user input to identify task modifications.
        
        Args:
            user_input: The user's input text
            task_id: The ID of the current task being discussed
            
        Returns:
            Optional[Dict[str, Any]]: Modification details if identified, None otherwise
            The dictionary contains:
            - type: The type of modification ('urgency', 'status', 'notes', 'description', 'reminder')
            - value: The new value to set
            - reason: The reason for the change (if applicable)
            - task_id: The ID of the task to modify
        """
        # Get the current task
        task = get_task_by_id(task_id)
        if not task:
            logger.warning(f"Task {task_id} not found during modification analysis")
            return None

        try:
            # Use ChatGPT to analyze the input for modifications
            analysis_prompt = f"""Analyze this user input for task modifications:
            Task ID: {task_id}
            Current Task Status: {task.get('status', 'unknown')}
            Current Urgency: {task.get('urgency', 0)}
            User Input: {user_input}

            If this input suggests any task modifications, format them as JSON:
            {{
                "type": "urgency|status|notes|description|reminder",
                "value": "the new value",
                "reason": "reason for change",
                "task_id": {task_id}
            }}
            
            Important: For description modifications, you can ONLY APPEND information. Never suggest replacing or removing existing description content.
            If you need to indicate that some part of the description is no longer accurate or relevant, append a note explaining what's incorrect or outdated.
            
            Examples:
            - "this is urgent" -> {{"type": "urgency", "value": "5", "reason": "User indicated high urgency", "task_id": {task_id}}}
            - "mark as done" -> {{"type": "status", "value": "completed", "reason": "User requested completion", "task_id": {task_id}}}
            - "remind me tomorrow" -> {{"type": "reminder", "value": "2024-02-23T09:00:00", "reason": "User requested tomorrow reminder", "task_id": {task_id}}}
            - "the deadline changed to next week" -> {{"type": "description", "value": "Update: Previous deadline is no longer accurate. New deadline is next week.", "reason": "User indicated deadline change", "task_id": {task_id}}}

            The user's requests for these modifications may also be implicit.
            They may off-handedly mention something connected to the task, which should be appended to the task description.
            They may talk in a more urgent tone about the task, which may also be a modification.
            If no modifications are suggested, respond with "null".
            """

            modification_json = ""
            async for chunk in self.chatgpt.process(analysis_prompt, {"system_role": "task_analyzer"}):
                modification_json += chunk

            # Parse the response
            try:
                modification = json.loads(modification_json.strip())
                if modification:
                    logger.info(f"Identified task modification: {modification}")
                    # Ensure task_id is included
                    modification['task_id'] = task_id
                    return modification
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse modification JSON: {e}")
                return None

        except Exception as e:
            logger.error(f"Error identifying task modification: {str(e)}")
            return None

        return None

    async def _apply_task_modification(self, modification: Dict[str, Any]) -> Optional[str]:
        """
        Apply identified task modifications and generate a response.
        
        Args:
            modification: The modification details from _identify_task_modification
            
        Returns:
            Optional[str]: A response describing the modification, or None if no modification was made
        """
        try:
            task_id = modification.get('task_id')
            mod_type = modification.get('type')
            value = modification.get('value')
            reason = modification.get('reason', 'No reason provided')

            if not all([task_id, mod_type, value]):
                logger.warning("Missing required modification fields")
                return None

            # Verify task exists
            task = get_task_by_id(task_id)
            if not task:
                logger.warning(f"Task {task_id} not found during modification")
                return None

            response = None
            if mod_type == 'urgency':
                try:
                    urgency = int(value)
                    if 1 <= urgency <= 5:
                        await self.update_task_priority(task_id, urgency, reason)
                        response = f"I've updated the task urgency to {urgency}. {reason}"
                    else:
                        logger.warning(f"Invalid urgency value: {urgency}")
                except ValueError:
                    logger.warning(f"Failed to convert urgency value: {value}")
            
            elif mod_type == 'status':
                valid_statuses = {'pending', 'completed', 'half-completed'}
                if value in valid_statuses:
                    update_task_status(task_id, value, None)
                    response = f"I've marked the task as {value}. {reason}"
                else:
                    logger.warning(f"Invalid status value: {value}")
            
            elif mod_type == 'notes' or mod_type == 'description':  # Handle both notes and description as appends
                if value.strip():
                    await self.add_task_notes(task_id, value)
                    response = f"I've added this information to the task: {value}"
                else:
                    logger.warning("Empty notes/description value")
            
            elif mod_type == 'reminder':
                try:
                    from datetime import datetime
                    alert_time = datetime.fromisoformat(value)
                    update_task_status(task_id, task.get('status', 'pending'), alert_time)
                    response = f"I've set a reminder for {alert_time.strftime('%Y-%m-%d %H:%M')}. {reason}"
                except ValueError as e:
                    logger.warning(f"Invalid datetime format: {e}")
            else:
                logger.warning(f"Unknown modification type: {mod_type}")

            if response:
                logger.info(f"Applied task modification: {mod_type} to task {task_id}")
                return response
            else:
                logger.warning(f"Failed to apply modification: {modification}")

        except Exception as e:
            logger.error(f"Error applying task modification: {str(e)}")
            
        return None

    def __del__(self):
        """Cleanup resources."""
        if hasattr(self, 'db') and self.db is not None:
            try:
                self.db.close()
            except Exception as e:
                logger.error(f"Error closing database connection: {str(e)}")

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

    async def handle_task_input(self, user_input: str, available_items: List[dict], context: Optional[Dict[str, Any]] = None) -> AsyncGenerator[str, None]:
        try:
            # Initialize context if None
            if context is None:
                context = {}
            
            # Create a new context dictionary that preserves all existing keys
            new_context = context.copy()
            
            # Add current datetime to context
            current_time = datetime.utcnow()
            new_context.update({
                "role": "task_helper",
                "style": "conversational",
                "focus": "context_aware",
                "current_item": None,
                "available_tasks": available_items,
                "current_time": current_time.isoformat(),
                "current_time_readable": current_time.strftime("%Y-%m-%d %H:%M:%S UTC"),
                "user_timezone": "Europe/Dublin"  # Since you're in Ireland
            })
            
            logger.info(f"Processing input at {current_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
            
            # Handle any datetime objects in the context
            def process_context(obj):
                if isinstance(obj, dict):
                    return {k: process_context(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [process_context(item) for item in obj]
                elif isinstance(obj, datetime):
                    return obj.isoformat()
                return obj
            
            new_context = process_context(new_context)
            
            # Get current task ID if available
            current_task_id = None
            if 'current_task_id' in context:
                current_task_id = context['current_task_id']
            elif 'current_item' in context and context['current_item']:
                current_task_id = context['current_item'].get('id')
            
            # Check for task modifications if we have a current task
            if current_task_id:
                modification = await self._identify_task_modification(user_input, current_task_id)
                if modification:
                    response = await self._apply_task_modification(modification)
                    if response:
                        yield response
                        return
            
            # Get response from ChatGPT
            response = ""
            buffer = ""  # Buffer for accumulating potential action directive text
            
            async for chunk in self.chatgpt.process(user_input, new_context):
                buffer += chunk
                
                # If buffer starts with '[', accumulate until we can determine if it's an action
                if buffer.startswith('['):
                    # If we have a complete action directive, process it and clear buffer
                    if ']' in buffer:
                        action_end = buffer.index(']') + 1
                        potential_action = buffer[:action_end]
                        remaining_text = buffer[action_end:]
                        
                        if self._is_action_directive(potential_action):
                            # Add to response but don't yield
                            response += potential_action
                            # Yield remaining text if any
                            if remaining_text:
                                yield remaining_text
                        else:
                            # Not an action directive, yield entire buffer
                            yield buffer
                    else:
                        # Otherwise keep accumulating
                        continue
                else:
                    # No potential action directive, yield buffer
                    yield buffer
                    buffer = ""
                
                response += chunk
            
            # Handle any remaining buffer
            if buffer:
                if not self._is_action_directive(buffer):
                    yield buffer
                else:
                    response += buffer
            
            # Extract and handle any actions from the response
            actions = self._extract_actions(response)
            for action in actions:
                action_response = await self._handle_action(action, response)
                if action_response:
                    yield action_response

        except Exception as e:
            logger.error(f"Error handling input: {str(e)}")
            raise

    async def _discuss_specific_item(self, item: dict) -> AsyncGenerator[str, None]:
        """
        Generate a natural discussion about a specific task or information item.
        
        Args:
            item: The item dictionary
            
        Returns:
            AsyncGenerator[str, None]: The AI's response chunks about the item
        """
        is_task = item.get('type', 'task') == 'task'
        prompt = f"""You are a helpful AI assistant discussing a specific {'task' if is_task else 'information item'}. The item is:
        [{'Task' if is_task else 'Info'} #{item.get('id')}]: {item.get('description')}
        {'Urgency: ' + str(item.get('urgency')) if is_task else ''}
        {'Status: ' + item.get('status', '') if is_task else ''}
        
        If this is a task:
        1. Explain why it's important and what impact it might have
        2. Suggest ways to help:
           - Breaking it down into smaller steps
           - Setting a reminder
           - Providing specific guidance
           - Marking it as complete
        
        If this is an information item:
        1. Explain why it's interesting or valuable
        2. Suggest ways to explore it further:
           - Related topics to investigate
           - Potential applications
           - People who might be interested
        
        Be conversational and encouraging, but keep it concise.
        If they might need deep thinking help, mention that you can analyze it more deeply."""

        async for chunk in self.chatgpt.process(prompt, {
            "role": "item_discussion",
            "style": "supportive",
            "focus": "engagement"
        }):
            yield chunk

    def _extract_actions(self, response: str) -> List[dict]:
        """Extract action directives from the AI's response."""
        actions = []
        logger.info(f"Extracting actions from response: {response}")
        
        # Match task actions - handle both numeric IDs and named parameters
        task_patterns = [
            r'\[ACTION:(\w+):(\d+):([^\]]*)\]',  # Numeric ID pattern
            r'\[ACTION:(\w+):task_id:([^\]:]+):([^\]]*)\]',  # Named parameter pattern
            r'\[ACTION:(\w+):task_id:([^\]]*)\]',  # Simple named parameter pattern
            r'\[ACTION:create_task:([^\]]*)\]'  # Create task pattern
        ]
        
        for pattern in task_patterns:
            task_matches = re.findall(pattern, response)
            for match in task_matches:
                if isinstance(match, tuple):
                    if len(match) == 3:
                        action_type, task_id_or_value, details = match
                        # For numeric pattern
                        try:
                            task_id = int(task_id_or_value)
                        except ValueError:
                            # For named parameter pattern where task_id might be a value
                            task_id = None
                            details = task_id_or_value
                    elif len(match) == 2:
                        # For simple named parameter pattern
                        action_type, details = match
                        task_id = None
                else:
                    # For create task pattern
                    action_type = 'create_task'
                    details = match
                    task_id = None
                
                action = {
                    'type': action_type,
                    'task_id': task_id,
                    'details': details
                }
                logger.info(f"Extracted task action: {action}")
                actions.append(action)
        
        # Match profile actions
        profile_pattern = r'\[ACTION:profile:(\w+):([^\]]*)\]'
        profile_matches = re.findall(profile_pattern, response)
        for subtype, details in profile_matches:
            action = {
                'type': 'profile',
                'subtype': subtype,
                'details': details
            }
            logger.info(f"Extracted profile action: {action}")
            actions.append(action)
        
        return actions

    async def _handle_action(self, action: dict, response: str) -> str:
        """Handle an action directive and update the response."""
        try:
            action_feedback = None
            logger.info(f"Processing action: {action}")
            
            # Handle create_task action
            if action['type'] == 'create_task':
                try:
                    task_details = json.loads(action['details'])
                    description = task_details.get('description')
                    urgency = task_details.get('urgency', 3)  # Default urgency of 3
                    deadline = task_details.get('deadline')
                    notes = task_details.get('notes')
                    
                    # Create the task
                    task_id = await self.create_new_task(description, urgency)
                    
                    # Add notes if provided
                    if notes:
                        await self.add_task_notes(task_id, notes)
                    
                    action_feedback = f"\n[✓ Created new task #{task_id}: {description}]"
                    logger.info(f"Created new task {task_id}. Details: {task_details}")
                    
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid task creation details: {e}")
                    action_feedback = "\n[❌ Failed to create task - invalid format]"
                except Exception as e:
                    logger.error(f"Error creating task: {e}")
                    action_feedback = "\n[❌ Failed to create task]"
            
            # If we don't have a task_id but have details that look like a time specification
            elif action['type'] == 'remind' and not action['task_id']:
                # Get the most recent task from context
                tasks = await self.get_tasks()
                if not tasks:
                    logger.error("No tasks found when trying to set reminder")
                    return response
                
                # Find the first incomplete task
                task = next((t for t in tasks if t.get('status') != 'completed'), None)
                if not task:
                    logger.error("No incomplete tasks found when trying to set reminder")
                    return response
                
                action['task_id'] = task['id']
                logger.info(f"Using task ID {action['task_id']} for reminder")
            
            if not action['task_id'] and action['type'] not in ['profile', 'explore', 'create_task']:
                logger.error(f"No task ID provided for action: {action}")
                return response
            
            if action['type'] == 'complete':
                task_id = action['task_id']
                update_task_status(task_id, 'completed', None)
                action_feedback = f"\n[✓ Task #{task_id} has been marked as completed]"
                logger.info(f"Task {task_id} marked as completed. Details: {action['details']}")
                
            elif action['type'] == 'remind':
                task_id = action['task_id']
                # Parse the time from details
                time_details = action['details']
                if isinstance(time_details, str):
                    # Extract numeric value and unit
                    match = re.match(r'(\d+)_?([hd])(ours?|ays?)?', time_details)
                    if match:
                        value, unit = match.group(1), match.group(2)
                        time_details = f"{value}{unit}"
                
                reminder_time = self._parse_reminder_time(time_details)
                
                if reminder_time:
                    update_task_status(task_id, 'pending', reminder_time)
                    if isinstance(reminder_time, datetime):
                        time_str = reminder_time.strftime('%Y-%m-%d %H:%M')
                        action_feedback = f"\n[⏰ Reminder set for Task #{task_id} at {time_str}]"
                        logger.info(f"Reminder set for task {task_id} at {time_str}")
                    else:
                        action_feedback = f"\n[⏰ Reminder set for Task #{task_id} at {reminder_time}]"
                        logger.info(f"Special reminder set for task {task_id}: {reminder_time}")
                else:
                    action_feedback = f"\n[❌ Failed to set reminder for Task #{task_id} - invalid time format]"
                    logger.error(f"Failed to parse reminder time for task {task_id}: {action['details']}")
                    
            elif action['type'] == 'help':
                task_id = action['task_id']
                update_task_status(task_id, 'half-completed', datetime.utcnow())
                action_feedback = f"\n[📝 Task #{task_id} has been marked as in-progress]"
                logger.info(f"Task {task_id} marked as in-progress. Help requested: {action['details']}")
                
            elif action['type'] == 'notes':
                task_id = action['task_id']
                await self.add_task_notes(task_id, action['details'])
                action_feedback = f"\n[📝 Added note to Task #{task_id}]"
                logger.info(f"Added note to task {task_id}: {action['details']}")
            
            elif action['type'] == 'draft_email':
                task_id = action['task_id']
                try:
                    if isinstance(action['details'], str):
                        details_str = action['details'].strip()
                        if not details_str.startswith('{'):
                            details_str = '{' + details_str + '}'
                        email_details = json.loads(details_str)
                    else:
                        email_details = action['details']
                    
                    draft = await self._draft_email(task_id, email_details)
                    response = re.sub(
                        r'\[ACTION:draft_email:[^\]]*\]',
                        f"\nHere's a draft email for you:\n\n{draft}",
                        response
                    )
                    action_feedback = f"\n[📧 Email draft created for Task #{task_id}]"
                    logger.info(f"Email draft created for task {task_id}. Recipients: {email_details.get('to', 'Not specified')}")
                except (json.JSONDecodeError, TypeError) as e:
                    logger.error(f"Invalid email details format for task {task_id}: {e}")
                    response = re.sub(r'\[ACTION:draft_email:[^\]]*\]', '', response)
                    action_feedback = f"\n[❌ Failed to create email draft - invalid format]"
                    
            elif action['type'] == 'profile':
                try:
                    # Handle different profile action subtypes
                    if action['details'].startswith('{'):
                        details = json.loads(action['details'])
                    else:
                        details = {'value': action['details']}
                    
                    profile_manager = ProfileManager()
                    if 'update' in action['subtype']:
                        # Update profile with new information
                        profile, insight = await profile_manager.process_input(
                            json.dumps(details),
                            is_direct_input=False
                        )
                        if insight:
                            action_feedback = f"\n[👤 Profile updated: {insight}]"
                            logger.info(f"Profile updated with new insight: {insight}")
                        else:
                            action_feedback = "\n[👤 Profile updated]"
                            logger.info("Profile updated without new insights")
                    elif 'preference' in action['subtype']:
                        # Add user preference
                        profile, insight = await profile_manager.process_input(
                            f"User preference: {json.dumps(details)}",
                            is_direct_input=False
                        )
                        action_feedback = f"\n[👤 Added preference to profile]"
                        logger.info(f"Added user preference to profile: {details}")
                    elif 'goal' in action['subtype']:
                        # Add user goal
                        profile, insight = await profile_manager.process_input(
                            f"User goal: {json.dumps(details)}",
                            is_direct_input=False
                        )
                        action_feedback = f"\n[👤 Added goal to profile]"
                        logger.info(f"Added user goal to profile: {details}")
                    
                except Exception as e:
                    logger.error(f"Error handling profile action: {str(e)}")
                    action_feedback = "\n[❌ Failed to update profile]"
                    
            elif action['type'] == 'explore':
                task_id = action['task_id']
                action_feedback = f"\n[🔍 Exploring details for Item #{task_id}]"
                logger.info(f"Exploring item {task_id}. Details: {action['details']}")
            
            # Remove any remaining action directives from the response
            response = re.sub(r'\[ACTION:[^\]]*\]', '', response).strip()
            
            # Add action feedback if available
            if action_feedback:
                response += action_feedback
                logger.info(f"Action completed successfully: {action['type']}")
            
            return response
            
        except Exception as e:
            logger.error(f"Error handling action: {str(e)}")
            # If there's an error, just return the response without the action directives
            return re.sub(r'\[ACTION:[^\]]*\]', '', response).strip()

    async def _draft_email(self, task_id: int, details: Dict[str, str]) -> str:
        """
        Draft an email related to a task.
        
        Args:
            task_id: The task ID
            details: Email details including subject and recipients
            
        Returns:
            str: The drafted email
        """
        task = get_task_by_id(task_id)
        if not task:
            return "Error: Task not found"

        prompt = f"""Draft a professional email about this task:
        Task: {task.get('description')}
        Subject: {details.get('subject', 'Task Update')}
        To: {details.get('to', '[Recipient]')}

        Requirements:
        1. Keep it concise and professional
        2. Include key details from the task
        3. Use appropriate tone for business communication
        4. Include clear next steps or expectations
        5. Format with proper email structure (To, Subject, Body)"""

        email = ""
        async for chunk in self.chatgpt.process(prompt, {
            "role": "email_drafter",
            "style": "professional",
            "focus": "clarity"
        }):
            email += chunk
        
        return email

    def _parse_reminder_time(self, time_str: str) -> Optional[datetime]:
        """Parse a reminder time string into a datetime."""
        try:
            if time_str == "next_debrief":
                return "next_debrief"
            elif time_str.endswith('h'):
                hours = int(time_str[:-1])
                return datetime.utcnow() + timedelta(hours=hours)
            elif time_str.endswith('d'):
                days = int(time_str[:-1])
                return datetime.utcnow() + timedelta(days=days)
            else:
                return datetime.strptime(time_str, "%Y-%m-%d %H:%M")
        except:
            return None 