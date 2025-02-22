# AI Agent Project

This project implements an AI agent system that combines multiple language models (ChatGPT-4 and O3-mini) for enhanced reasoning and task execution capabilities.

## Project Structure

```
project/
├── agent.py             # Main AI flow
├── cli.py               # Terminal interface
├── api.py               # Web API endpoints
├── config.py            # Configuration constants
├── database.py          # SQL database interactions
├── chatgpt_agent.py     # ChatGPT-4 interactions
├── o3_mini.py          # O3-mini integration
└── tests/              # Test files
```

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

## Usage

1. Run the CLI interface:
```bash
python cli.py
```

2. Run tests:
```bash
pytest tests/
```

## Development

- Use `pytest` for running tests
- Follow PEP 8 style guidelines
- Document new features and changes

## License

MIT License 