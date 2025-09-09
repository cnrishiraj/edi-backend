# EDI Healthcare Data Integration POC - Frontend

Next.js 14+ frontend with Shadcn UI and AI SDK 5 for 3-panel healthcare data processing interface.

## Setup

1. Install dependencies:
```bash
cd frontend
npm install
```

2. Run development server:
```bash
npm run dev
```

3. Open http://localhost:3000

## Tech Stack

- **Next.js 14+** with App Router
- **Shadcn UI** for modern, accessible components
- **AI SDK 5** for streaming chat interfaces
- **Tailwind CSS** for styling
- **TypeScript** for type safety
- **Zustand** for state management
- **Vitest** for testing

## 3-Panel Layout

The main interface consists of three resizable panels:

1. **File Upload Panel** - Drag & drop SmithRx claims files
2. **AI Chat Panel** - Natural language queries about data
3. **Mapping Panel** - Visual field mapping with confidence scores

## Project Structure

```
frontend/
├── src/
│   ├── app/              # Next.js App Router pages
│   ├── components/       # Shadcn UI components
│   ├── stores/           # Zustand state management
│   ├── hooks/            # Custom React hooks
│   └── lib/              # Utility functions
├── tests/
│   ├── integration/      # Integration tests
│   └── unit/             # Unit tests
└── package.json          # Dependencies
```

## Development

### Code Quality

```bash
# Linting
npm run lint         # Run ESLint
npm run lint:fix     # Fix ESLint issues

# Formatting  
npm run format       # Format with Prettier
npm run format:check # Check formatting

# Type checking
npm run type-check   # TypeScript type checking
```

### Available Scripts

```bash
npm run dev          # Start development server
npm run build        # Build for production  
npm run start        # Start production server
npm run test         # Run Vitest tests
npm run test:ui      # Run tests with UI
```

## Components (To Be Implemented)

- **ThreePanelLayout** - Main resizable panel container
- **FileUploadPanel** - File upload with progress
- **AiChatPanel** - Chat interface with AI SDK 5
- **MappingPanel** - Field mapping visualization

## State Management

- **fileStore** - File upload state and metadata
- **chatStore** - AI conversation history
- **mappingStore** - Field mappings and confidence scores