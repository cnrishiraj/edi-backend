# EDI Healthcare Data Integration POC: Technical Research Report

## 1. Frontend Architecture (3-Panel Layout)

**Decision**: **Next.js 14+ with Shadcn UI and AI SDK 5**

**Rationale**: 
- Shadcn UI provides modern, accessible components with excellent TypeScript support
- AI SDK 5 offers streamlined integration with LLMs and real-time streaming
- Next.js 14+ App Router enables efficient 3-panel layout with RSC
- Built-in optimization for file uploads and real-time updates

**Alternatives Considered**:
- **Material-UI with custom AI integration**: More complex setup, heavier bundle
- **Chakra UI with LangChain**: Less modern components, complex AI streaming
- **Custom components with OpenAI SDK**: Too much boilerplate for POC

**Implementation Considerations**:
- Use `ResizablePanelGroup` from Shadcn for 3-panel layout
- AI SDK 5's `useChat` hook for streaming responses
- `uploadthing` or native Next.js file upload for EDI files
- Real-time updates via Server-Sent Events or WebSockets

## 2. Backend AI Integration

**Decision**: **LlamaIndex with FastAPI integration**

**Rationale**:
- LlamaIndex excels at document question-answering and data exploration
- Native support for structured data querying (CSV, JSON, databases)
- Simple FastAPI integration with async support
- Can index uploaded files for immediate chat functionality

**Alternatives Considered**:
- **LangChain**: More complex for simple document Q&A use case
- **Direct OpenAI API**: Requires custom document indexing and context management
- **Anthropic Claude API**: Limited file analysis capabilities

**Implementation Considerations**:
- Use `VectorStoreIndex` for uploaded file indexing
- `JSONReader` and `CSVReader` for structured data ingestion
- Stream responses using FastAPI's `StreamingResponse`
- Context-aware queries with file metadata

## 3. EDI File Processing (POC Scope)

**Decision**: **Python pandas with custom SmithRx parser**

**Rationale**:
- POC focuses on single file type (SmithRx claims)
- Pandas sufficient for basic flat file parsing and JSON conversion
- Faster development than full EDI library integration
- Easy integration with LlamaIndex for AI chat

**Alternatives Considered**:
- **pyx12**: Overkill for POC, complex setup for single file type
- **Custom regex parsing**: Too fragile even for POC
- **Online EDI parsing services**: External dependencies, security concerns

**Implementation Considerations**:
- Fixed-width or delimiter-based parsing for SmithRx format
- JSON output with field metadata for AI chat context
- Basic validation (required fields, data types)
- Error handling with user-friendly messages

## 4. Mapping Generation (Simplified)

**Decision**: **Rule-based matching with fuzzy string similarity**

**Rationale**:
- POC can use simpler approach than ML-based matching
- Fuzzy string matching (fuzzywuzzy) provides good field name similarity
- Rule-based approach more predictable and debuggable for POC
- Easy to extend with ML in full implementation

**Alternatives Considered**:
- **SMAT/ML-based matching**: Too complex for POC scope
- **Manual mapping only**: Doesn't demonstrate auto-mapping capability
- **Simple exact matching**: Too rigid for real-world field variations

**Implementation Considerations**:
- Pre-defined VBA schema mapping rules
- Levenshtein distance + semantic similarity scoring
- Confidence thresholds for auto vs. manual mapping
- Visual feedback in UI for mapping quality

## 5. Real-time Communication

**Decision**: **Server-Sent Events (SSE) with FastAPI**

**Rationale**:
- Simpler than WebSockets for one-way updates (file processing status)
- Native browser support, works well with AI SDK 5 streaming
- FastAPI has excellent SSE support with async generators
- Perfect for progress updates and AI chat streaming

**Alternatives Considered**:
- **WebSockets**: Bidirectional capability not needed for POC
- **Polling**: Less efficient, poor user experience
- **Socket.io**: Adds complexity and dependencies

**Implementation Considerations**:
- `/events` endpoint for file processing updates
- AI chat streaming via separate `/chat/stream` endpoint
- Client-side EventSource for real-time updates
- Proper error handling and reconnection logic

## 6. State Management

**Decision**: **React Context + Zustand for complex state**

**Rationale**:
- React Context sufficient for 3-panel layout communication
- Zustand for complex state (file metadata, mapping data, chat history)
- Lightweight, TypeScript-friendly state management
- Avoids Redux complexity for POC

**Alternatives Considered**:
- **Redux Toolkit**: Too much boilerplate for POC
- **Jotai**: Atomic approach overkill for 3-panel layout
- **Pure React state**: Insufficient for cross-panel data sharing

**Implementation Considerations**:
- `FileStore` for uploaded files and processing status
- `ChatStore` for AI conversation history and context
- `MappingStore` for field mappings and validation results
- Shared state across 3 panels with proper TypeScript types

## 7. Database (POC Minimal)

**Decision**: **SQLite with async SQLAlchemy**

**Rationale**:
- Simplest database setup for POC
- SQLAlchemy async support for FastAPI integration
- Easy migration to PostgreSQL for production
- File-based storage perfect for POC deployment

**Alternatives Considered**:
- **PostgreSQL**: Overkill for POC, requires additional setup
- **JSON files**: Insufficient for relational data and queries
- **In-memory storage**: Data lost on restart

**Implementation Considerations**:
- Simple schema: files, mappings, processing_jobs
- Async database sessions with proper connection handling
- Basic migrations using Alembic
- Easy backup/restore for POC demonstrations

## POC Architecture Overview

```
┌─────────────────────┬─────────────────────┬─────────────────────┐
│   File Upload       │    AI Chat          │   Mapping View      │
│   Panel             │    Panel            │   Panel             │
├─────────────────────┼─────────────────────┼─────────────────────┤
│ • Drag & drop       │ • Chat with file    │ • Generated         │
│ • Upload progress   │ • LlamaIndex Q&A    │   mappings          │
│ • File list         │ • Streaming         │ • Confidence        │
│ • Processing status │   responses         │   scores            │
│                     │ • Context aware     │ • Manual edits      │
└─────────────────────┴─────────────────────┴─────────────────────┘
                                │
                    ┌───────────▼──────────┐
                    │   FastAPI Backend    │
                    │ • LlamaIndex         │
                    │ • File processing    │
                    │ • Mapping generation │
                    │ • SQLite storage     │
                    └──────────────────────┘
```

## POC Success Criteria

**Technical Validation**:
- 3-panel responsive layout working smoothly
- File upload with progress and real-time updates
- AI chat responds to questions about uploaded file
- Basic auto-mapping with visual confidence indicators
- Clean, modern UI using Shadcn components

**User Experience**:
- Upload SmithRx claims file → see in file panel
- Ask "How many claims are in this file?" → AI responds
- View generated mappings with confidence scores
- Edit mappings in intuitive interface
- See processing status updates in real-time

**Performance Targets (POC)**:
- File upload (up to 10MB): <30 seconds
- AI chat response: <3 seconds first response
- Mapping generation: <60 seconds for typical file
- UI responsiveness: No blocking operations

This POC approach validates the core concept while using modern, developer-friendly technologies that can scale to the full implementation.