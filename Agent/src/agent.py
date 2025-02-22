"""
Main AI agent implementation coordinating between different models and tasks.
"""
from typing import Optional, Dict, Any, List
import logging
from datetime import datetime

from .chatgpt_agent import ChatGPTAgent
from .o3_mini import O3MiniAgent
from .database import SessionLocal, Conversation, AgentTask, Task, get_tasks_by_urgency, update_task_status
from .config import (
    MAX_RETRIES, TIMEOUT, MAX_TOKENS, MAX_EMAILS,
    URGENCY_ORDER, HALF_FINISHED_PRIORITY
)

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

    async def process_input(self, user_input: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        Process user input and return the appropriate response.
        
        Args:
            user_input: The user's input text
            context: Optional context dictionary for maintaining conversation state
        
        Returns:
            str: The agent's response
        
        Raises:
            RuntimeError: If no models are available
        """
        if not self.chatgpt.is_available and not self.o3_mini.is_available:
            raise RuntimeError(
                "No AI models are available. Please check your API keys in the .env file."
            )

        try:
            # Log the incoming request
            logger.info(f"Processing user input: {user_input[:100]}...")

            # Create a new task
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

            try:
                if use_o3_mini:
                    response = await self.o3_mini.process(user_input, context)
                    model_used = "o3-mini"
                else:
                    if not self.chatgpt.is_available:
                        raise RuntimeError("ChatGPT is not available and this input requires it")
                    response = await self.chatgpt.process(user_input, context)
                    model_used = "gpt-4"

            except Exception as model_error:
                # If primary model fails, try fallback to the other model
                logger.warning(f"Primary model failed: {str(model_error)}")
                if use_o3_mini and self.chatgpt.is_available:
                    logger.info("Falling back to ChatGPT")
                    response = await self.chatgpt.process(user_input, context)
                    model_used = "gpt-4"
                elif not use_o3_mini and self.o3_mini.is_available:
                    logger.info("Falling back to O3-mini")
                    response = await self.o3_mini.process(user_input, context)
                    model_used = "o3-mini"
                else:
                    raise

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

            return response

        except Exception as e:
            logger.error(f"Error processing input: {str(e)}")
            if task:
                task.status = "failed"
                task.result = str(e)
                self.db.commit()
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

    async def process_tasks(self) -> None:
        """
        Main task processing loop that:
        1. Loads tasks by urgency
        2. Chunks them appropriately
        3. Gets summaries and presents them
        4. Handles user interaction
        5. Updates task status
        """
        try:
            # Get all tasks ordered by urgency
            all_tasks = []
            for urgency in URGENCY_ORDER:
                tasks = get_tasks_by_urgency(urgency)
                all_tasks.extend(tasks)

                # Handle half-finished tasks with special priority
                if urgency == HALF_FINISHED_PRIORITY:
                    half_finished = [t for t in tasks if t['status'] == 'half-completed']
                    all_tasks.extend(half_finished)

            if not all_tasks:
                logger.info("No tasks available for processing")
                return

            # Chunk tasks for processing
            task_chunks = self._chunk_tasks(all_tasks)
            
            for chunk in task_chunks:
                # Get summary from ChatGPT
                chunk_text = self._format_tasks_for_summary(chunk)
                summary = await self.chatgpt.summarize_tasks(chunk_text)
                print("\nTask Summary:")
                print(summary)

                # Get user input for task selection
                while True:
                    user_input = input("\nEnter task ID to process, 'help' for assistance, or press Enter to continue: ").strip()
                    
                    if not user_input:
                        break
                    elif user_input.lower() == 'help':
                        self._show_task_help()
                        continue
                    elif user_input.isdigit():
                        task_id = int(user_input)
                        task = next((t for t in chunk if t['id'] == task_id), None)
                        
                        if task:
                            await self._process_selected_task(task)
                        else:
                            print(f"Task {task_id} not found in current chunk")
                    else:
                        print("Invalid input. Please enter a task ID or press Enter to continue")

        except Exception as e:
            logger.error(f"Error in task processing: {str(e)}")
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

    def _format_tasks_for_summary(self, tasks: List[dict]) -> str:
        """
        Format a list of tasks into a string for summarization.
        
        Args:
            tasks: List of task dictionaries
        
        Returns:
            Formatted string of tasks
        """
        formatted_tasks = []
        for task in tasks:
            task_str = f"Task {task['id']}: {task['description']}\n"
            task_str += f"Urgency: {task['urgency']}\n"
            task_str += f"Status: {task['status']}\n"
            if task.get('alertAt'):
                task_str += f"Alert At: {task['alertAt']}\n"
            formatted_tasks.append(task_str)
        
        return "\n".join(formatted_tasks)

    async def _process_selected_task(self, task: dict) -> None:
        """
        Process a selected task by generating an action prompt and handling user input.
        
        Args:
            task: Task dictionary
        """
        # Generate and display action prompt
        action_prompt = await self.chatgpt.generate_action_prompt(task)
        print("\n" + action_prompt)

        # Get user action
        action = input("\nYour command (help/remind/skip/complete): ").strip().lower()
        
        # Process the action
        if action == 'help':
            # Mark as half-completed and set a reminder
            update_task_status(
                task['id'],
                'half-completed',
                datetime.utcnow()  # You might want to add some time delta
            )
            print(f"Task {task['id']} marked as needing help. A reminder has been set.")
            
        elif action == 'remind':
            # Keep current status but set a reminder
            reminder_time = datetime.utcnow()  # You might want to add some time delta
            update_task_status(task['id'], task['status'], reminder_time)
            print(f"Reminder set for task {task['id']}.")
            
        elif action == 'complete':
            # Mark as completed with no reminder
            update_task_status(task['id'], 'completed', None)
            print(f"Task {task['id']} marked as completed.")
            
        elif action == 'skip':
            print(f"Skipping task {task['id']}.")
            
        else:
            print("Invalid command. No changes made to the task.")

    def _show_task_help(self) -> None:
        """Display help information for task processing."""
        print("\nTask Processing Commands:")
        print("  help    - Show this help message")
        print("  remind  - Set a reminder for the task")
        print("  skip    - Skip this task for now")
        print("  complete - Mark the task as completed")
        print("\nOr press Enter to continue to the next chunk of tasks.")

    def __del__(self):
        """Cleanup resources."""
        if hasattr(self, 'db') and self.db is not None:
            try:
                self.db.close()
            except Exception as e:
                logger.error(f"Error closing database connection: {str(e)}") 