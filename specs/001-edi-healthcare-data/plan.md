# Implementation Plan: EDI Healthcare Data Integration POC

**Branch**: `001-edi-healthcare-data` | **Date**: 2025-09-08 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-edi-healthcare-data/spec.md`

## Execution Flow (/plan command scope)
```
1. Load feature spec from Input path
   → If not found: ERROR "No feature spec at {path}"
2. Fill Technical Context (scan for NEEDS CLARIFICATION)
   → Detect Project Type from context (web=frontend+backend, mobile=app+api)
   → Set Structure Decision based on project type
3. Evaluate Constitution Check section below
   → If violations exist: Document in Complexity Tracking
   → If no justification possible: ERROR "Simplify approach first"
   → Update Progress Tracking: Initial Constitution Check
4. Execute Phase 0 → research.md
   → If NEEDS CLARIFICATION remain: ERROR "Resolve unknowns"
5. Execute Phase 1 → contracts, data-model.md, quickstart.md, agent-specific template file (e.g., `CLAUDE.md` for Claude Code, `.github/copilot-instructions.md` for GitHub Copilot, or `GEMINI.md` for Gemini CLI).
6. Re-evaluate Constitution Check section
   → If new violations: Refactor design, return to Phase 1
   → Update Progress Tracking: Post-Design Constitution Check
7. Plan Phase 2 → Describe task generation approach (DO NOT create tasks.md)
8. STOP - Ready for /tasks command
```

**IMPORTANT**: The /plan command STOPS at step 7. Phases 2-4 are executed by other commands:
- Phase 2: /tasks command creates tasks.md
- Phase 3-4: Implementation execution (manual or via tools)

## Summary
POC for EDI healthcare data integration pipeline with 3-panel UI layout: file upload panel, AI chat interface, and mapping visualization. Focus on demonstrating core workflow with modern UI components (Shadcn UI) and AI capabilities (AI SDK 5) for natural language data exploration.

## Technical Context
**Language/Version**: Python 3.11+ (backend), TypeScript/React 18+ (frontend)
**Primary Dependencies**: FastAPI, LlamaIndex, pyx12, pandas (backend); Shadcn UI, AI SDK 5, Next.js 14+ (frontend)
**Storage**: PostgreSQL (metadata), File system (uploaded files, staging)
**Testing**: pytest (backend), Vitest + Testing Library (frontend)
**Target Platform**: Web application (desktop browsers)
**Project Type**: web - determines source structure (backend + frontend)
**Performance Goals**: File upload <30s, AI chat response <3s, mapping generation <60s
**Constraints**: POC scope - single file type (SmithRx claims), simplified mapping, basic validation
**Scale/Scope**: POC for 1-2 DIAs, 10MB max file size, 3-panel responsive UI layout

**POC-Specific Requirements**:
i want the front end to use schan ui compoents and ai sdk 5 for ai capabilities, i want the user to fist upload the file he should be able to see the uploaded files and chat window to chat with info, and see the mappings genereated its like the ui should be divided in to 3 layers layout side by side do you get it? first lets focis on creating a simple poc to see if this fits, also i want to use llamaindex in the backend

## Constitution Check
*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Simplicity**:
- Projects: **3** - backend-api, frontend-ui, tests (PASS - at limit)
- Using framework directly? **YES** - FastAPI, Next.js/Shadcn UI without wrappers (PASS)
- Single data model? **YES** - POC entities with JSON serialization (PASS)
- Avoiding patterns? **YES** - Direct FastAPI, minimal abstractions for POC (PASS)

**Architecture**:
- EVERY feature as library? **YES** - Core libraries: file-parser, ai-chat, mapping-engine (PASS)
- Libraries listed: **file-parser** (EDI parsing), **ai-chat** (LlamaIndex integration), **mapping-engine** (basic auto-mapping)
- CLI per library: **YES** - Each library exposes CLI with --help/--version/--format (PASS)
- Library docs: **YES** - llms.txt format planned for POC libraries (PASS)

**Testing (NON-NEGOTIABLE)**:
- RED-GREEN-Refactor cycle enforced? **YES** - POC tests written first (PASS)
- Git commits show tests before implementation? **YES** - Enforced via hooks (PASS)
- Order: Contract→Integration→E2E→Unit strictly followed? **YES** (PASS)
- Real dependencies used? **YES** - PostgreSQL, file system in tests (PASS)
- Integration tests for: **YES** - 3-panel UI, AI chat, file upload flow (PASS)
- FORBIDDEN: Implementation before test, skipping RED phase **ENFORCED** (PASS)

**Observability**:
- Structured logging included? **YES** - JSON logs with correlation IDs (PASS)
- Frontend logs → backend? **YES** - Unified logging for POC debugging (PASS)
- Error context sufficient? **YES** - AI chat errors, file upload failures tracked (PASS)

**Versioning**:
- Version number assigned? **YES** - v0.1.0-poc (MAJOR.MINOR.BUILD-poc) (PASS)
- BUILD increments on every change? **YES** - Automated via CI/CD (PASS)
- Breaking changes handled? **YES** - POC migration scripts (PASS)

## Project Structure

### Documentation (this feature)
```
specs/[###-feature]/
├── plan.md              # This file (/plan command output)
├── research.md          # Phase 0 output (/plan command)
├── data-model.md        # Phase 1 output (/plan command)
├── quickstart.md        # Phase 1 output (/plan command)
├── contracts/           # Phase 1 output (/plan command)
└── tasks.md             # Phase 2 output (/tasks command - NOT created by /plan)
```

### Source Code (repository root)
```
# Option 1: Single project (DEFAULT)
src/
├── models/
├── services/
├── cli/
└── lib/

tests/
├── contract/
├── integration/
└── unit/

# Option 2: Web application (when "frontend" + "backend" detected)
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

# Option 3: Mobile + API (when "iOS/Android" detected)
api/
└── [same as backend above]

ios/ or android/
└── [platform-specific structure]
```

**Structure Decision**: Option 2 (Web application) - 3-panel layout POC with modern React frontend

## Phase 0: Outline & Research
1. **Extract unknowns from Technical Context** above:
   - For each NEEDS CLARIFICATION → research task
   - For each dependency → best practices task
   - For each integration → patterns task

2. **Generate and dispatch research agents**:
   ```
   For each unknown in Technical Context:
     Task: "Research {unknown} for {feature context}"
   For each technology choice:
     Task: "Find best practices for {tech} in {domain}"
   ```

3. **Consolidate findings** in `research.md` using format:
   - Decision: [what was chosen]
   - Rationale: [why chosen]
   - Alternatives considered: [what else evaluated]

**Output**: research.md with all NEEDS CLARIFICATION resolved

## Phase 1: Design & Contracts
*Prerequisites: research.md complete*

1. **Extract entities from feature spec** → `data-model.md`:
   - Entity name, fields, relationships
   - Validation rules from requirements
   - State transitions if applicable

2. **Generate API contracts** from functional requirements:
   - For each user action → endpoint
   - Use standard REST/GraphQL patterns
   - Output OpenAPI/GraphQL schema to `/contracts/`

3. **Generate contract tests** from contracts:
   - One test file per endpoint
   - Assert request/response schemas
   - Tests must fail (no implementation yet)

4. **Extract test scenarios** from user stories:
   - Each story → integration test scenario
   - Quickstart test = story validation steps

5. **Update agent file incrementally** (O(1) operation):
   - Run `/scripts/update-agent-context.sh [claude|gemini|copilot]` for your AI assistant
   - If exists: Add only NEW tech from current plan
   - Preserve manual additions between markers
   - Update recent changes (keep last 3)
   - Keep under 150 lines for token efficiency
   - Output to repository root

**Output**: ✅ POC data-model.md created, ✅ contracts/*.yaml (upload + chat + mapping APIs), ✅ quickstart.md with 3-panel workflow demo, ✅ CLAUDE.md updated

## Phase 2: Task Planning Approach
*This section describes what the /tasks command will do - DO NOT execute during /plan*

**Task Generation Strategy (POC-focused)**:
- Load `/templates/tasks-template.md` as base
- Generate tasks from Phase 1 design docs (contracts, data model, quickstart)
- **Contract Tests**: 3 API contracts → 9 endpoint test tasks [P]
- **POC Models**: 5 entities → 5 model creation tasks [P]
- **Library Development**: 3 libraries → 9 library implementation tasks
  - file-parser: SmithRx parsing + JSON conversion
  - ai-chat: LlamaIndex integration + streaming
  - mapping-engine: Basic fuzzy matching + confidence scoring
- **3-Panel UI**: Frontend components for upload, chat, mapping panels
- **Integration Tests**: 7 quickstart scenarios → 7 E2E test tasks

**Ordering Strategy (POC Pipeline)**:
- **Phase A**: Contract tests (must fail) → POC Models → Library CLIs [P]
- **Phase B**: Backend APIs → Frontend 3-panel layout → State management
- **Phase C**: AI chat integration → File upload flow → Mapping UI
- **Phase D**: E2E tests → POC deployment → Demo preparation

**Estimated Output**: ~35 numbered, ordered tasks in tasks.md
- Contract/Model tasks: 14 tasks [many parallel]
- Backend API/Library tasks: 12 tasks [some dependencies]
- Frontend 3-panel tasks: 9 tasks [UI-focused]

**Critical Path Dependencies (POC)**:
1. SQLite schema setup → Model tests
2. File parser library → File upload functionality
3. LlamaIndex integration → AI chat components
4. Mapping engine → Mapping panel UI
5. 3-panel layout → State management across panels

**POC-Specific Considerations**:
- Focus on working software over comprehensive features
- Single file type (SmithRx) reduces complexity
- Basic mapping algorithms sufficient for demonstration
- Modern UI/UX is critical for stakeholder buy-in

**IMPORTANT**: This phase is executed by the /tasks command, NOT by /plan

## Phase 3+: Future Implementation
*These phases are beyond the scope of the /plan command*

**Phase 3**: Task execution (/tasks command creates tasks.md)  
**Phase 4**: Implementation (execute tasks.md following constitutional principles)  
**Phase 5**: Validation (run tests, execute quickstart.md, performance validation)

## Complexity Tracking
*Fill ONLY if Constitution Check has violations that must be justified*

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |


## Progress Tracking
*This checklist is updated during execution flow*

**Phase Status**:
- [x] Phase 0: Research complete (/plan command)
- [x] Phase 1: Design complete (/plan command)
- [x] Phase 2: Task planning complete (/plan command - describe approach only)
- [x] Phase 3: Tasks generated (/tasks command)
- [ ] Phase 4: Implementation complete
- [ ] Phase 5: Validation passed

**Gate Status**:
- [x] Initial Constitution Check: PASS
- [x] Post-Design Constitution Check: PASS
- [x] All NEEDS CLARIFICATION resolved
- [x] Complexity deviations documented (none required)

---
*Based on Constitution v2.1.1 - See `/memory/constitution.md`*