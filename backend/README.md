# EDI Healthcare Data Integration POC - Backend

FastAPI backend with LlamaIndex for AI-powered healthcare data processing.

## Setup

1. Create virtual environment:
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set environment variables:
```bash
export OPENAI_API_KEY="your-openai-key"
```

4. Run development server:
```bash
uvicorn main:app --reload --port 8000
```

## API Documentation

Once running, visit:
- API docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health

## Project Structure

```
backend/
├── src/
│   ├── api/          # FastAPI route handlers
│   ├── lib/          # Core libraries (file-parser, ai-chat, mapping-engine)
│   ├── models/       # SQLAlchemy data models  
│   ├── services/     # Business logic services
│   └── middleware/   # Custom middleware
├── tests/
│   ├── contract/     # API contract tests
│   ├── integration/  # Integration tests
│   ├── unit/         # Unit tests
│   ├── performance/  # Performance tests
│   └── fixtures/     # Test data
├── main.py           # FastAPI application entry point
└── requirements.txt  # Python dependencies
```

## Libraries

- **file-parser**: Parse SmithRx claims files with pandas
- **ai-chat**: LlamaIndex integration for data Q&A
- **mapping-engine**: Basic fuzzy field matching

## Development

### Linting and Formatting

```bash
# Format code with Black
black .

# Lint with Ruff  
ruff check .
ruff check --fix .  # Auto-fix issues

# Type check with MyPy
mypy src/

# Install pre-commit hooks
pre-commit install
```

### Testing

```bash
# Run all tests
pytest

# Run specific test types
pytest tests/contract/
pytest tests/integration/
pytest tests/unit/
```