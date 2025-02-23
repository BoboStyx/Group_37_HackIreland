# AI Agent System

A robust AI agent system that combines multiple language models (ChatGPT-4, Gemini Pro, and O3-mini) for enhanced reasoning, task execution, and email processing capabilities.

python -m uvicorn api:app --reload --host 0.0.0.0 --port 8000

## Project Structure

```
project/
├── agent.py             # Main AI agent logic
├── api.py              # FastAPI web endpoints
├── cli.py              # Terminal interface
├── config.py           # Legacy configuration (deprecated)
├── server_config.py    # New server configuration system
├── database.py         # Database models and operations
├── email_processor.py  # Email analysis with Gemini AI
├── get_mail.py         # Gmail integration
├── Pull.py            # Email database operations
├── chatgpt_agent.py    # ChatGPT-4 interactions
├── o3_mini.py          # O3-mini integration
└── tests/              # Test files
```

## Features

### Multi-Model AI Processing
- ChatGPT-4 for natural language understanding and task management
- Gemini Pro for email analysis and task extraction
- O3-mini for complex reasoning and deep analysis
- Automatic model selection and fallback

### Email Integration
- Gmail API integration for email fetching
- Intelligent email analysis and task extraction
- Automatic task creation from email content
- Opportunity detection from communications

### Task Management
- Natural language task processing
- Automatic task prioritization (urgency levels 1-5)
- Smart deadline detection and handling
- Task grouping and summarization

### Server Features
- FastAPI-based REST API
- Multi-environment support (development, testing, production)
- Comprehensive error handling and logging
- Health monitoring endpoints

### Database Integration
- Multi-environment database support
- Connection pooling and management
- Robust error handling
- Transaction management

## Setup

1. Create and activate virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Unix/MacOS
.\venv\Scripts\activate   # On Windows
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment:
- Copy `.env.example` to `.env`
- Set environment variables:
```env
# Environment
ENVIRONMENT=development  # development, testing, or production

# Server Settings
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=4
API_TIMEOUT=60

# Database Configuration
DEV_DB_HOST=localhost
DEV_DB_USER=dev_user
DEV_DB_PASSWORD=dev_password
DEV_DB_NAME=ai_agent_dev
DEV_DB_PORT=3306

TEST_DB_HOST=localhost
TEST_DB_USER=test_user
TEST_DB_PASSWORD=test_password
TEST_DB_NAME=ai_agent_test
TEST_DB_PORT=3306

PROD_DB_HOST=your_prod_host
PROD_DB_USER=prod_user
PROD_DB_PASSWORD=prod_password
PROD_DB_NAME=ai_agent_prod
PROD_DB_PORT=3306

# API Keys
OPENAI_API_KEY=your_openai_key
GEMINI_API_KEY=your_gemini_key
O3_MINI_API_KEY=your_o3_key

# Gmail API
GMAIL_CREDENTIALS_FILE=credentials.json

# Model Settings
GEMINI_TEMPERATURE=0.7
GEMINI_TOP_K=40
GEMINI_TOP_P=0.95
GEMINI_MAX_TOKENS=1024

# Processing Limits
MAX_EMAILS=50
MAX_TOKENS=50000
```

4. Set up Gmail API:
- Create a Google Cloud project
- Enable Gmail API
- Download credentials and save as `credentials.json`

5. Initialize database:
```bash
python -c "from database import init_db; init_db()"
```

## Usage

### Start API Server
```bash
# Development
uvicorn api:app --reload --host 0.0.0.0 --port 8000

# Production
uvicorn api:app --host 0.0.0.0 --port 8000 --workers 4
```

### API Endpoints

#### Task Management
```
POST /process          # Process user input
GET  /tasks           # Get task summaries
POST /update_task     # Update task status
POST /think_deep      # Deep analysis with O3-mini
GET  /health          # Server health check
```

Example task processing:
```bash
curl -X POST http://localhost:8000/process \
  -H "Content-Type: application/json" \
  -d '{"text": "Schedule a meeting with John about the project", "context": {"urgency": "high"}}'
```

### Email Processing
Run the email processor:
```bash
python get_mail.py
```

This will:
1. Authenticate with Gmail
2. Fetch recent unread emails
3. Analyze content using Gemini AI
4. Create tasks and opportunities
5. Mark emails as read

## Development

### Adding New Features
1. Update database models in `database.py`
2. Add API endpoints in `api.py`
3. Implement business logic in appropriate modules
4. Add error handling and logging
5. Update tests

### Code Style
- Follow PEP 8
- Use type hints
- Add docstrings (Google style)
- Implement proper error handling
- Add logging statements

### Testing
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=. tests/

# Generate coverage report
coverage html
```

### Error Handling
The system implements comprehensive error handling:
- Custom exceptions for different error types
- Proper error propagation
- Detailed error logging
- User-friendly error responses

### Logging
Logging is configured based on environment:
- Development: DEBUG level
- Production: INFO level
- Structured log format
- Separate logs for different components

## Deployment

### Docker
```bash
# Build image
docker build -t ai-agent .

# Run container
docker run -d \
  -p 8000:8000 \
  --env-file .env \
  --name ai-agent \
  ai-agent
```

### Kubernetes
Kubernetes manifests are provided in the `k8s/` directory:
```bash
kubectl apply -f k8s/
```

## License

All rights reserved.