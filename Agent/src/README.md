# AI Agent Project

This project implements an AI agent system that combines multiple language models (ChatGPT-4 and O3-mini) for enhanced reasoning and task execution capabilities.

## Project Structure

```
project/
├── agent.py             # Main AI flow
├── cli.py              # Terminal interface
├── api.py              # Web API endpoints
├── config.py           # Configuration constants
├── database.py         # SQL database interactions
├── chatgpt_agent.py    # ChatGPT-4 interactions
├── o3_mini.py          # O3-mini integration
└── tests/              # Test files
```

## Features

### Natural Language Task Management
The AI agent can understand and process natural language requests to:
- Modify task priorities ("this task is more urgent now")
- Update task status ("mark this as completed")
- Add notes to tasks ("add a note that John will help with this")
- Set reminders ("remind me about this next week")
- Change task descriptions ("update the description to include...")

### Intelligent Task Processing
- Automatically prioritizes tasks by urgency (levels 1-5)
- Handles half-completed tasks with special priority
- Processes tasks in chunks for efficient handling
- Generates clear summaries of task groups

### Smart Model Selection
- Uses ChatGPT-4 for regular interactions
- Switches to O3-mini for complex analysis
- Automatic fallback between models

### Database Integration
- Real-time task updates and modifications
- Persistent conversation history
- Structured user profiles
- Comprehensive task tracking

## Setup

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Unix/MacOS
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment variables:
- Copy `.env.example` to `.env`
- Add your API keys and configuration
- Set up your MySQL database connection

4. Initialize the database:
```bash
./setup_database.sh -u your_username -p
```

## Usage

### Command Line Interface
```bash
python cli.py
```

Example interactions:
```
> Show me my urgent tasks
[AI shows tasks prioritized by urgency]

> This security patch is more critical now
[AI updates task urgency and adds a note explaining the change]

> Remind me about the client meeting tomorrow morning
[AI sets a reminder and confirms]

> I need help breaking down the documentation task
[AI analyzes the task and provides detailed subtasks]
```

### Web API
```bash
uvicorn api:app --host 0.0.0.0 --port 8000
```

## Development

### Adding New Features
- Follow the existing pattern in `agent.py`
- Add database operations in `database.py`
- Update tests accordingly
- Document changes in docstrings

### Testing
```bash
pytest tests/
```

### Code Style
- Follow PEP 8 guidelines
- Use type hints
- Include docstrings for all functions
- Log important operations

## Configuration

Key settings in `.env`:
```env
# API Keys
OPENAI_API_KEY=your_key_here
O3_MINI_API_KEY=your_key_here

# Database
DATABASE_URL=mysql://user:pass@localhost/ai_agent

# Agent Settings
MAX_TOKENS=1000
MAX_EMAILS=5
LOG_LEVEL=INFO
```

## License

MIT License 