# edi-backend Development Guidelines

Auto-generated from all feature plans. Last updated: 2025-09-08

## Active Technologies - POC Focus
- Python 3.11+ with FastAPI, LlamaIndex, pandas (backend) (001-edi-healthcare-data)
- Next.js 14+, Shadcn UI, AI SDK 5, TypeScript (frontend) (001-edi-healthcare-data)  
- SQLite (POC database), File system storage (001-edi-healthcare-data)

## Project Structure
```
backend/
├── src/
│   ├── models/
│   ├── services/
│   └── api/
└── tests/

frontend/
├── src/
│   ├── components/
│   ├── pages/
│   └── services/
└── tests/
```

## Libraries (POC Scope)
- **file-parser**: Parse SmithRx claims files (pandas) - CLI: `file-parser --help`
- **ai-chat**: LlamaIndex integration for data Q&A - CLI: `ai-chat --help`  
- **mapping-engine**: Basic fuzzy field matching - CLI: `mapping-engine --help`

## Commands (POC)
```bash
# Parse SmithRx claims files
file-parser --file=smithrx_claims.txt --format=json --output=parsed.json

# Start AI chat session
ai-chat --file=parsed.json --index --stream

# Generate basic mappings  
mapping-engine --source=parsed.json --target=vba_basic.json --fuzzy-threshold=0.7
```

## Code Style
- TDD mandatory: RED-GREEN-Refactor cycle strictly enforced
- Libraries first: Every feature as standalone, testable library
- Direct framework usage: No wrapper classes around FastAPI/React
- Structured logging with correlation IDs for all operations

## Recent Changes
- 001-edi-healthcare-data: Added EDI healthcare data integration POC with 3-panel UI (Shadcn + AI SDK 5), LlamaIndex chat, SmithRx parsing

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->