import asyncio
import argparse
import sys
from typing import Optional
import logging

from agent import AIAgent
from config import LOG_LEVEL

# Configure logging
logging.basicConfig(level=LOG_LEVEL)
logger = logging.getLogger(__name__)

class AgentCLI:
    def __init__(self):
        """Initialize the CLI interface."""
        self.agent = AIAgent()
        self.context = {}

    async def interactive_mode(self):
        """Run the agent in interactive mode."""
        print("AI Agent CLI - Your Personal Task Assistant")
        
        try:
            # Check tasks first
            tasks = await self.agent.process_tasks()
            
            # Initial greeting with task context
            greeting = await self.agent.process_input(
                "Greet the user warmly and acknowledge the current task status.", 
                {
                    "is_greeting": True,
                    "has_tasks": bool(tasks),
                    "task_count": len(tasks) if tasks else 0,
                    "should_be_direct": True  # Signal to be direct about task status
                }
            )
            print(f"\nAI: {greeting}")

            # Only show task prompt if there are actual tasks
            if tasks:
                print("\nAI: Would you like to go through these tasks together? You can say 'tasks' to view them in detail, or ask me anything else.")
        except Exception as e:
            logger.error(f"Error during initial greeting: {str(e)}")
            print("\nAI: Hello! I encountered a small issue getting started, but I'm ready to help now.")
        
        while True:
            try:
                user_input = input("\nYou: ").strip()

                if not user_input:
                    continue
                
                command = user_input.lower()
                
                if command == 'exit':
                    print("\nAI: Goodbye! Let me know if you need anything else.")
                    break
                elif command == 'help':
                    self._show_help()
                    continue
                elif command == 'tasks':
                    # Process tasks and get summaries
                    tasks = await self.agent.process_tasks()
                    
                    if not tasks:
                        print("\nAI: You're all caught up with your tasks. Would you like me to help you discover new opportunities? I can help filter through newsletters and updates to find what matters most to you.")
                        continue
                    
                    # Keep prompting for task interaction until user wants to exit
                    while True:
                        task_input = input("\nEnter task ID, 'help' for commands, or 'back' to return: ").strip().lower()
                        
                        if not task_input:
                            continue
                        elif task_input == 'back':
                            print("\nAI: Let me know if you need help with anything else.")
                            break
                        elif task_input == 'help':
                            self._show_task_help()
                        elif task_input.isdigit():
                            task_id = int(task_input)
                            try:
                                # Process the selected task
                                await self.agent.process_selected_task(task_id)
                            except ValueError as e:
                                print(f"\nAI: {str(e)}")
                            except Exception as e:
                                logger.error(f"Error processing task {task_id}: {str(e)}")
                                print(f"\nAI: I had trouble processing task {task_id}. Would you like to try another one?")
                        else:
                            print("\nAI: I didn't catch that. Type 'help' to see what commands you can use.")
                    continue

                # For any other input, process it as a query
                try:
                    response = await self.agent.process_input(user_input, self.context)
                    print(f"\nAI: {response}")
                except Exception as e:
                    logger.error(f"Error processing input: {str(e)}")
                    print("\nAI: I ran into an issue processing that. Could you rephrase or try something else?")

            except KeyboardInterrupt:
                print("\nAI: Goodbye! Have a great day!")
                break
            except Exception as e:
                logger.error(f"Error in interactive mode: {str(e)}")
                print("\nAI: Something unexpected happened. Let's try that again.")

    def _show_help(self):
        """Display help information."""
        print("\nAvailable commands:")
        print("  help  - Show this help message")
        print("  tasks - View and manage your tasks")
        print("  exit  - Exit the program")
        print("\nYou can also type any question or command to interact with the AI agent.")

    def _show_task_help(self):
        """Display help information for task management."""
        print("\nTask Management Commands:")
        print("  [task ID] - Select a task to process")
        print("  help      - Show this help message")
        print("  back      - Return to main menu")
        print("\nWhen viewing a task, you can:")
        print("  - Mark it as complete")
        print("  - Set a reminder")
        print("  - Get help with the task")
        print("  - Skip to another task")

def main():
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(description="AI Agent Command Line Interface")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    cli = AgentCLI()
    try:
        asyncio.run(cli.interactive_mode())
    except KeyboardInterrupt:
        print("\nExiting...")
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
