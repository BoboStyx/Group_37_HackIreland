"""
Command-line interface for interacting with the AI agent.
"""
import asyncio
import argparse
import sys
from typing import Optional

from .agent import AIAgent
from .config import LOG_LEVEL
import logging

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
        print("AI Agent CLI (Type 'exit' to quit, 'help' for commands)")
        
        while True:
            try:
                user_input = input("\nYou: ").strip()
                
                if user_input.lower() == 'exit':
                    break
                elif user_input.lower() == 'help':
                    self._show_help()
                    continue
                elif user_input.lower() == 'tasks':
                    await self.agent.process_tasks()
                    continue
                elif not user_input:
                    continue

                response = await self.agent.process_input(user_input, self.context)
                print(f"\nAI: {response}")

            except KeyboardInterrupt:
                print("\nExiting...")
                break
            except Exception as e:
                logger.error(f"Error: {str(e)}")
                print(f"\nError occurred: {str(e)}")

    def _show_help(self):
        """Display help information."""
        print("\nAvailable commands:")
        print("  help  - Show this help message")
        print("  tasks - Process and manage tasks")
        print("  exit  - Exit the program")
        print("\nYou can type any question or command to interact with the AI agent.")

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