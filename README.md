# AI Agent System

A sophisticated AI agent system that combines multiple language models (ChatGPT-4 and O3-mini) for enhanced reasoning and task execution capabilities. The system provides both a CLI and API interface for interaction, with support for task management, deep thinking analysis, and conversation history.

## Features

- Dual AI Model Integration (ChatGPT-4 and O3-mini)
- Interactive CLI Interface
- RESTful API with FastAPI
- Task Management System
- Conversation History Tracking
- Deep Thinking Analysis Mode
- SQLAlchemy Database Integration

## Project Structure

```
project/
├── Agent/                  # Main package directory
│   ├── __init__.py        # Package initialization
│   ├── agent.py           # Core AI agent implementation
│   ├── api.py             # FastAPI web endpoints
│   ├── cli.py             # Command-line interface
│   ├── config.py          # Configuration settings
│   ├── database.py        # Database models and operations
│   ├── chatgpt_agent.py   # ChatGPT-4 integration
│   └── o3_mini.py         # O3-mini model integration
├── tests/                 # Test directory
│   └── ...               # Test files
├── requirements.txt       # Project dependencies
└── README.md             # This file
```

### Key Components and Modification Points

- `agent.py`: Core agent class (`AIAgent`) that coordinates between models
  - Modify `_requires_deep_thinking()` to adjust when O3-mini is used
  - Extend `process_tasks()` to add new task processing capabilities
  - Add new methods to `AIAgent` class for additional functionality

- `chatgpt_agent.py`: ChatGPT integration
  - Modify `_get_system_prompt()` to change the agent's behavior
  - Adjust `process()` method for different response handling
  - Update `summarize_tasks()` to change task summary format

- `o3_mini.py`: O3-mini model integration
  - Customize `think_deep()` for specialized analysis
  - Modify `_prepare_prompt()` to adjust model input
  - Update `_clean_response()` for different output formatting

- `api.py`: FastAPI endpoints
  - Add new endpoints in the `app` instance
  - Modify existing endpoint handlers (e.g., `process_input()`, `get_tasks()`)
  - Update API models in the Pydantic classes

- `cli.py`: Command-line interface
  - Add new commands in `interactive_mode()`
  - Modify `_show_help()` to update command documentation
  - Extend `AgentCLI` class with new features

- `config.py`: Configuration settings
  - Add new environment variables
  - Modify default values
  - Add new configuration sections

- `database.py`: Database models and operations
  - Add new database models by extending `Base`
  - Modify existing models (e.g., `Conversation`, `Task`)
  - Add new database operations

## Prerequisites

- Python 3.8 or higher
- pip (Python package installer)
- Virtual environment (recommended)
- OpenAI API key
- O3-mini API key (optional)

## Setup Instructions

1. Clone the repository:
```bash
git clone <repository-url>
cd ai-agent-system
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
# On macOS/Linux:
source venv/bin/activate
# On Windows:
.\venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file in the root directory with the following configuration:
```env
# Required API Keys
OPENAI_API_KEY=your_openai_api_key_here
O3_MINI_API_KEY=your_o3_mini_api_key_here

# Optional Configuration
DATABASE_URL=sqlite:///ai_agent.db
API_HOST=0.0.0.0
API_PORT=8000
LOG_LEVEL=INFO

# Agent Configuration
MAX_RETRIES=3
TIMEOUT=30
TEMPERATURE=0.7
```

5. Initialize the database:
```python
from Agent.database import init_db
init_db()
```

## Usage

### Command Line Interface (CLI)

Run the CLI with:
```bash
python -m Agent.cli
```

Available commands in CLI:
- `help` - Show available commands
- `tasks` - Process and manage tasks
- `exit` - Exit the program

Example interaction:
```bash
You: help
AI: Available commands:
    help  - Show this help message
    tasks - Process and manage tasks
    exit  - Exit the program

You: tasks
AI: Processing tasks...
[Task summaries will be displayed]
```

### API Server

Start the API server with:
```bash
python -m Agent.api
```

The API will be available at `http://localhost:8000` by default.

API Endpoints:
- `POST /process` - Process user input
  ```json
  {
    "text": "Your input text here",
    "context": {
      "history": []
    }
  }
  ```
- `GET /tasks` - Retrieve task summaries
- `POST /update_task` - Update task status
  ```json
  {
    "task_id": 1,
    "status": "completed",
    "alert_at": null
  }
  ```
- `POST /think_deep` - Use deep thinking mode
  ```json
  {
    "prompt": "Your complex analysis prompt here"
  }
  ```
- `GET /health` - Health check endpoint

API documentation will be available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Testing

Run the test suite with:
```bash
pytest tests/
```

For coverage report:
```bash
pytest --cov=Agent tests/
```

To run specific test categories:
```bash
pytest tests/test_agent.py  # Test core agent functionality
pytest tests/test_api.py    # Test API endpoints
pytest tests/test_cli.py    # Test CLI interface
```

## Development

### Code Style

The project follows PEP 8 style guidelines. Use the following tools for code formatting:
```bash
black Agent/
isort Agent/
flake8 Agent/
```

### Type Checking

Run static type checking with:
```bash
mypy Agent/
```

### Adding New Features

1. Core Agent Features:
   - Add new methods to `AIAgent` class in `agent.py`
   - Update model integration in `chatgpt_agent.py` or `o3_mini.py`
   - Add corresponding database models in `database.py`

2. API Endpoints:
   - Add new Pydantic models in `api.py`
   - Create new endpoint functions
   - Update API documentation

3. CLI Commands:
   - Add new command handlers in `cli.py`
   - Update help documentation
   - Add new interactive features

4. Configuration:
   - Add new settings to `config.py`
   - Update `.env` file structure
   - Document new configuration options

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

### Pull Request Guidelines

- Include tests for new functionality
- Update documentation for new features
- Follow existing code style
- Add type hints for new functions
- Include example usage in docstrings

## License

Copyright © 2024 Group 37 HackTrinity. All Rights Reserved.

This software and associated documentation files (the "Software") are proprietary and confidential. 
Unauthorized copying, transfer, or reproduction of the contents of this Software, via any medium is strictly prohibited.

The Software is provided by copyright holders "as is" and any express or implied warranties are disclaimed. 
In no event shall the copyright holders be liable for any direct, indirect, incidental, special, exemplary, 
or consequential damages arising in any way out of the use of this Software.

