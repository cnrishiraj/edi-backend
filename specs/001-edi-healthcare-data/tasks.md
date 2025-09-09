# Tasks: EDI Healthcare Data Integration POC

**Input**: Design documents from `/specs/001-edi-healthcare-data/`
**Prerequisites**: plan.md ✓, research.md ✓, data-model.md ✓, contracts/ ✓

## POC Focus & Libraries
- **Backend**: FastAPI + LlamaIndex + pandas (SmithRx parsing)
- **Frontend**: Next.js 14+ + Shadcn UI + AI SDK 5 (3-panel layout)
- **Database**: SQLite (simplified for POC)
- **Libraries**: file-parser, ai-chat, mapping-engine

## Path Structure
- `backend/src/` - FastAPI application
- `frontend/src/` - Next.js application  
- `backend/tests/` - Backend tests
- `frontend/tests/` - Frontend tests

## Phase 3.1: Setup

- [ ] T001 Create POC project structure (backend/ and frontend/ directories)
- [ ] T002 Initialize FastAPI backend with dependencies (fastapi, llamaindex, pandas, sqlalchemy)  
- [ ] T003 Initialize Next.js frontend with dependencies (shadcn-ui, ai-sdk, zustand)
- [ ] T004 [P] Configure backend linting (ruff, black, mypy)
- [ ] T005 [P] Configure frontend linting (eslint, prettier, typescript)
- [ ] T006 [P] Setup SQLite database schema from data-model.md

## Phase 3.2: Tests First (TDD) ⚠️ MUST COMPLETE BEFORE 3.3
**CRITICAL: These tests MUST be written and MUST FAIL before ANY implementation**

### Contract Tests [P]
- [ ] T007 [P] Contract test POST /files/upload in backend/tests/contract/test_file_upload_api.py
- [ ] T008 [P] Contract test GET /files/{file_id}/status in backend/tests/contract/test_file_status_api.py  
- [ ] T009 [P] Contract test POST /chat/stream in backend/tests/contract/test_chat_api.py
- [ ] T010 [P] Contract test POST /chat/index/{file_id} in backend/tests/contract/test_chat_index_api.py
- [ ] T011 [P] Contract test POST /mappings/generate in backend/tests/contract/test_mapping_api.py
- [ ] T012 [P] Contract test GET /mappings/{mapping_id} in backend/tests/contract/test_mapping_get_api.py

### Integration Tests [P] 
- [ ] T013 [P] Integration test 3-panel UI layout in frontend/tests/integration/test_three_panel_layout.test.tsx
- [ ] T014 [P] Integration test file upload workflow in frontend/tests/integration/test_file_upload_flow.test.tsx
- [ ] T015 [P] Integration test AI chat streaming in frontend/tests/integration/test_ai_chat_stream.test.tsx
- [ ] T016 [P] Integration test mapping generation in frontend/tests/integration/test_mapping_generation.test.tsx
- [ ] T017 [P] Integration test end-to-end POC workflow in backend/tests/integration/test_poc_workflow.py

## Phase 3.3: Core Implementation (ONLY after tests are failing)

### Data Models [P]
- [ ] T018 [P] File model in backend/src/models/file.py
- [ ] T019 [P] Mapping model in backend/src/models/mapping.py  
- [ ] T020 [P] Conversation model in backend/src/models/conversation.py
- [ ] T021 [P] ChatMessage model in backend/src/models/chat_message.py
- [ ] T022 [P] ProcessingJob model in backend/src/models/processing_job.py

### Libraries [P]
- [ ] T023 [P] file-parser library in backend/src/lib/file_parser.py (SmithRx parsing with pandas)
- [ ] T024 [P] ai-chat library in backend/src/lib/ai_chat.py (LlamaIndex integration) 
- [ ] T025 [P] mapping-engine library in backend/src/lib/mapping_engine.py (basic fuzzy matching)

### Backend API Services
- [ ] T026 FileService CRUD operations in backend/src/services/file_service.py
- [ ] T027 ChatService with LlamaIndex integration in backend/src/services/chat_service.py
- [ ] T028 MappingService with fuzzy matching in backend/src/services/mapping_service.py
- [ ] T029 POST /files/upload endpoint in backend/src/api/file_routes.py
- [ ] T030 GET /files/{file_id}/status endpoint in backend/src/api/file_routes.py
- [ ] T031 POST /chat/stream endpoint in backend/src/api/chat_routes.py
- [ ] T032 POST /chat/index/{file_id} endpoint in backend/src/api/chat_routes.py
- [ ] T033 POST /mappings/generate endpoint in backend/src/api/mapping_routes.py
- [ ] T034 GET /mappings/{mapping_id} endpoint in backend/src/api/mapping_routes.py

### Frontend Components
- [ ] T035 ResizablePanelGroup 3-panel layout in frontend/src/components/ThreePanelLayout.tsx
- [ ] T036 File upload panel with Shadcn dropzone in frontend/src/components/FileUploadPanel.tsx  
- [ ] T037 AI chat panel with AI SDK 5 streaming in frontend/src/components/AiChatPanel.tsx
- [ ] T038 Mapping view panel with editable mappings in frontend/src/components/MappingPanel.tsx
- [ ] T039 File upload store with Zustand in frontend/src/stores/fileStore.ts
- [ ] T040 Chat store with message history in frontend/src/stores/chatStore.ts
- [ ] T041 Mapping store with field mappings in frontend/src/stores/mappingStore.ts

## Phase 3.4: Integration

- [ ] T042 Connect FileService to SQLite database in backend/src/database.py
- [ ] T043 Server-Sent Events for real-time updates in backend/src/middleware/sse_middleware.py
- [ ] T044 CORS middleware for frontend communication in backend/src/middleware/cors_middleware.py
- [ ] T045 File upload with progress tracking in frontend/src/hooks/useFileUpload.ts
- [ ] T046 AI chat with streaming responses in frontend/src/hooks/useAiChat.ts
- [ ] T047 Real-time status updates via SSE in frontend/src/hooks/useRealTimeUpdates.ts

## Phase 3.5: Polish

### Unit Tests [P]
- [ ] T048 [P] Unit tests for SmithRx parsing in backend/tests/unit/test_file_parser.py
- [ ] T049 [P] Unit tests for fuzzy field matching in backend/tests/unit/test_mapping_engine.py
- [ ] T050 [P] Unit tests for LlamaIndex integration in backend/tests/unit/test_ai_chat.py
- [ ] T051 [P] Unit tests for React components in frontend/tests/unit/components.test.tsx

### Performance & Validation
- [ ] T052 Performance tests (file upload <30s, chat <3s) in backend/tests/performance/test_poc_performance.py
- [ ] T053 Create sample SmithRx test data in backend/tests/fixtures/smithrx_claims_sample.txt
- [ ] T054 Manual POC demonstration script following quickstart.md
- [ ] T055 Error handling and user feedback for failed operations
- [ ] T056 [P] Update backend README with setup instructions
- [ ] T057 [P] Update frontend README with component documentation

## Dependencies

**Sequential Dependencies**:
- Setup (T001-T006) before Tests (T007-T017)
- Tests (T007-T017) before Implementation (T018-T041)
- Models (T018-T022) before Services (T026-T028)
- Services (T026-T028) before API endpoints (T029-T034)
- Stores (T039-T041) before Integration (T042-T047)
- Implementation before Polish (T048-T057)

**Critical Blocking Dependencies**:
- T018 (File model) blocks T026 (FileService)
- T023 (file-parser) blocks T029 (upload endpoint)
- T024 (ai-chat) blocks T031 (chat stream endpoint)
- T025 (mapping-engine) blocks T033 (mapping generate endpoint)
- T035 (3-panel layout) blocks T036-T038 (individual panels)

## Parallel Execution Examples

**Phase 3.2 - Contract Tests (Launch together)**:
```
Task: "Contract test POST /files/upload in backend/tests/contract/test_file_upload_api.py"
Task: "Contract test POST /chat/stream in backend/tests/contract/test_chat_api.py"
Task: "Contract test POST /mappings/generate in backend/tests/contract/test_mapping_api.py"
```

**Phase 3.3 - Models (Launch together)**:
```
Task: "File model in backend/src/models/file.py"
Task: "Mapping model in backend/src/models/mapping.py"
Task: "Conversation model in backend/src/models/conversation.py"
```

**Phase 3.3 - Libraries (Launch together)**:
```
Task: "file-parser library in backend/src/lib/file_parser.py"
Task: "ai-chat library in backend/src/lib/ai_chat.py"  
Task: "mapping-engine library in backend/src/lib/mapping_engine.py"
```

## POC Success Validation

**Technical Criteria** (via T052):
- File upload completes in <30 seconds
- AI chat responds in <3 seconds
- Mapping generation completes in <60 seconds
- 3-panel layout responsive and smooth

**Functional Criteria** (via T054):
- Upload SmithRx file → see in file panel
- Chat "How many claims?" → AI responds accurately
- View generated mappings with confidence scores
- Edit mappings in intuitive interface

## Notes

- **[P] tasks**: Different files, no dependencies - can run in parallel
- **TDD Enforcement**: All contract and integration tests MUST fail before implementation
- **POC Focus**: Single file type (SmithRx), basic fuzzy matching, SQLite database
- **Modern Stack**: Shadcn UI components, AI SDK 5 streaming, LlamaIndex backend
- **File Structure**: backend/ and frontend/ directories for web application structure

## Validation Checklist ✓

- [x] All contracts have corresponding tests (T007-T012)
- [x] All entities have model tasks (T018-T022)  
- [x] All tests come before implementation (Phase 3.2 before 3.3)
- [x] Parallel tasks truly independent (different files)
- [x] Each task specifies exact file path
- [x] No task modifies same file as another [P] task
- [x] POC workflow matches quickstart demonstration
- [x] Modern UI/UX stack properly integrated (Shadcn + AI SDK 5)