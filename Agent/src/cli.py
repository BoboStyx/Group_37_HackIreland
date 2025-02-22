import asyncio
import argparse
import sys
from typing import Optional
import logging
import json
from datetime import datetime

from agent import AIAgent
from config import LOG_LEVEL
from profile_manager import ProfileManager

# Configure logging
logging.basicConfig(level=LOG_LEVEL)
logger = logging.getLogger(__name__)

class AgentCLI:
    def __init__(self):
        """Initialize the CLI interface."""
        self.agent = AIAgent()
        self.context = {}
        self.profile_manager = ProfileManager()

    async def _stream_output(self, prefix: str = "\nAI: ") -> str:
        """
        Stream the AI's response to the terminal and return the full response.
        
        Args:
            prefix: The prefix to print before the response (default: "\nAI: ")
            
        Returns:
            str: The complete response
        """
        import sys
        
        # Print the prefix without a newline
        print(prefix, end="", flush=True)
        
        # Initialize response
        full_response = ""
        
        # Return a function that can be used to stream chunks
        async def stream_chunk(chunk: str) -> None:
            nonlocal full_response
            print(chunk, end="", flush=True)
            full_response += chunk
            
        return full_response, stream_chunk

    async def interactive_mode(self):
        """Run the agent in interactive mode."""
        print("AI Agent CLI - Your Personal Task Assistant")
        
        try:
            # Initialize conversation history and load profile
            profile = await self.profile_manager.get_profile()
            self.context = {
                "history": [],  # Store conversation history
                "available_tasks": [],  # Store available tasks
                "profile": profile  # Load and maintain profile in context
            }
            
            # Get initial tasks and context
            tasks = await self.agent.get_tasks()
            task_count = len(tasks)
            
            # Initial greeting with task context
            greeting = ""
            _, stream = await self._stream_output()
            async for chunk in self.agent.process_input(
                "Greet the user warmly, acknowledge the current task status, and suggest what we should work on first.", 
                {
                    "is_greeting": True,
                    "has_tasks": task_count > 0,
                    "task_count": task_count,
                    "tasks": tasks,
                    "should_be_direct": True,
                    "available_tasks": tasks,
                    "history": self.context["history"],  # Include conversation history
                    "profile": self.context["profile"]  # Include profile in greeting
                }
            ):
                greeting += chunk
                await stream(chunk)
            
            print()  # Add a newline after streaming
            
            # Store the greeting in conversation history
            self.context["history"].append({"role": "assistant", "content": greeting})
            self.context["available_tasks"] = tasks
            
        except Exception as e:
            logger.error(f"Error during initial greeting: {str(e)}")
            print("\nAI: Hello! I encountered a small issue getting started, but I'm ready to help now.")
        
        while True:
            try:
                user_input = input("\nYou: ").strip()

                if not user_input:
                    continue
                
                # Store user input in history
                self.context["history"].append({"role": "user", "content": user_input})
                
                # Handle explicit commands first
                command = user_input.lower()
                if command == 'exit':
                    print("\nAI: Goodbye! Let me know if you need anything else.")
                    break
                elif command == 'help':
                    self._show_help()
                    continue
                elif command == 'profile':
                    await self._handle_profile_command()
                    continue
                
                # For everything else, process naturally with task context
                try:
                    # Refresh tasks to ensure we have the latest state
                    tasks = await self.agent.get_tasks()
                    self.context["available_tasks"] = tasks
                    
                    # Process the input with full context
                    response = ""
                    _, stream = await self._stream_output()
                    async for chunk in self.agent.handle_task_input(
                        user_input,
                        tasks,
                        {
                            **self.context,  # Include all context
                            "available_tasks": tasks,  # Update with latest tasks
                            "profile": await self.profile_manager.get_profile()  # Get latest profile
                        }
                    ):
                        response += chunk
                        await stream(chunk)
                    
                    print()  # Add a newline after streaming
                    
                    # Store AI response in history
                    self.context["history"].append({"role": "assistant", "content": response})
                    
                    # Keep history at a reasonable size (last 10 exchanges)
                    if len(self.context["history"]) > 20:  # 10 exchanges = 20 messages
                        self.context["history"] = self.context["history"][-20:]
                    
                except Exception as e:
                    logger.error(f"Error processing input: {str(e)}")
                    print("\nAI: I ran into an issue processing that. Could you rephrase or try something else?")

            except KeyboardInterrupt:
                print("\nAI: Goodbye! Have a great day!")
                break
            except Exception as e:
                logger.error(f"Error in interactive mode: {str(e)}")
                print("\nAI: Something unexpected happened. Let's try that again.")

    async def _handle_profile_command(self):
        """Handle the profile command and its subcommands."""
        print("\nProfile Management:")
        print("1. Add profile information")
        print("2. View current profile")
        print("3. View profile history")
        print("4. Back to main menu")

        while True:
            try:
                choice = input("\nEnter your choice (1-4): ").strip()

                if choice == '4' or not choice:
                    break
                elif choice == '1':
                    print("\nEnter or paste any information about yourself.")
                    print("This can be your background, CV, interests, goals, or anything else relevant.")
                    print("Type 'DONE' (all caps) on a new line when finished:")
                    
                    lines = []
                    while True:
                        try:
                            line = input()
                            if line == 'DONE':  # Must match exactly
                                break
                            lines.append(line)
                        except EOFError:  # Handle Ctrl+D gracefully
                            print("\nInput terminated. Type 'DONE' to finish or continue entering text.")
                            continue
                    
                    if not lines:
                        print("\nAI: No information provided. Operation cancelled.")
                        continue

                    # Process the input
                    raw_input = '\n'.join(lines)
                    profile, insight = await self.profile_manager.process_input(raw_input, is_direct_input=True)
                    
                    # Update context
                    self.context['profile'] = profile
                    
                    # Show what we learned
                    _, stream = await self._stream_output()
                    if insight:
                        await stream(f"I've updated your profile. Here's what I learned: {insight}")
                    else:
                        await stream("Profile updated successfully.")
                    print()
                    break

                elif choice == '2':
                    profile = await self.profile_manager.get_profile()
                    if profile:
                        print("\nCurrent Profile:")
                        print(json.dumps(profile, indent=2))
                    else:
                        print("\nAI: No profile information found yet.")
                    input("\nPress Enter to continue...")
                    break

                elif choice == '3':
                    profile = await self.profile_manager.get_raw_profile()
                    if profile:
                        print("\nProfile History:")
                        print("=" * 50)
                        print(profile['raw_input'])
                        print("=" * 50)
                        print(f"\nCreated: {profile['created_at']}")
                        print(f"Last Updated: {profile['updated_at']}")
                    else:
                        print("\nAI: No profile history found.")
                    input("\nPress Enter to continue...")
                    break

                else:
                    print("\nAI: Invalid choice. Please enter a number between 1 and 4.")

            except Exception as e:
                logger.error(f"Error handling profile command: {str(e)}")
                print("\nAI: I encountered an issue managing your profile. Please try again.")
                break

    def _show_help(self):
        """Display help information."""
        print("\nAvailable commands:")
        print("  help    - Show this help message")
        print("  tasks   - View and manage your tasks")
        print("  profile - Manage your user profile")
        print("  exit    - Exit the program")
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

    # Initialize the database
    from database import init_db
    init_db()

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
