# EDI Healthcare Data Integration POC: Quickstart Guide

## Overview
This quickstart demonstrates the 3-panel UI workflow for the EDI data integration POC. The interface consists of three side-by-side panels: File Upload, AI Chat, and Mapping View.

## POC Scope & Goals
- **Technology Validation**: Shadcn UI + AI SDK 5 + LlamaIndex integration
- **UX Validation**: 3-panel layout for efficient workflow
- **Core Features**: File upload → AI chat → mapping generation
- **File Type**: SmithRx claims only (simplified for POC)

## Prerequisites
- Node.js 18+ and Python 3.11+
- Sample SmithRx claims file (test data)
- OpenAI API key for LlamaIndex integration
- Modern browser (Chrome, Firefox, Safari)

## POC Workflow Demonstration

### Step 1: Start the Application

**Backend (FastAPI + LlamaIndex):**
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

**Frontend (Next.js + Shadcn UI):**
```bash
cd frontend
npm install
npm run dev
```

**Access:** http://localhost:3000

### Step 2: 3-Panel UI Layout

When you open the application, you should see:

```
┌─────────────────────┬─────────────────────┬─────────────────────┐
│   📁 File Upload    │   💬 AI Chat        │   🔗 Mapping View   │
│   Panel             │   Panel             │   Panel             │
├─────────────────────┼─────────────────────┼─────────────────────┤
│ Drag & drop area    │ "Welcome! Upload    │ "Upload a file to   │
│ Upload progress     │ a file to start     │ see generated       │
│ File list (empty)   │ chatting about it"  │ mappings"           │
│                     │                     │                     │
│ [Browse Files...]   │ Chat input disabled │ Empty mapping view  │
└─────────────────────┴─────────────────────┴─────────────────────┘
```

**Validation:**
- ✅ 3 panels are visible and properly sized
- ✅ Panels are resizable using Shadcn's ResizablePanelGroup
- ✅ UI is responsive and modern-looking

### Step 3: Upload SmithRx Claims File

**Action:** Drag and drop or browse for `smithrx_claims_sample.txt`

**Expected Behavior:**
```
┌─────────────────────┬─────────────────────┬─────────────────────┐
│   📁 File Upload    │   💬 AI Chat        │   🔗 Mapping View   │
├─────────────────────┼─────────────────────┼─────────────────────┤
│ ✅ smithrx_claims_  │ "I can see you      │ 🔄 Generating       │
│    sample.txt       │ uploaded a SmithRx  │    mappings...      │
│ 📊 Size: 2.1MB      │ file. What would    │                     │
│ ⏳ Status: Parsing  │ you like to know    │ Please wait while   │
│ 🔢 Records: 1,247   │ about it?"          │ we analyze your     │
│                     │                     │ file structure.    │
│ [Upload Another]    │ [Type message...]   │                     │
└─────────────────────┴─────────────────────┴─────────────────────┘
```

**API Calls Made:**
```bash
# File upload
POST /api/v1/files/upload
# Response: {"file_id": "abc-123", "status": "parsing"}

# File indexing for AI
POST /api/v1/chat/index/abc-123
# Response: {"job_id": "idx-456", "status": "indexing"}

# Mapping generation  
POST /api/v1/mappings/generate
# Response: {"mapping_id": "map-789", "confidence_score": 0.87}
```

**Validation:**
- ✅ File uploads with progress indicator
- ✅ Chat panel activates with welcome message
- ✅ Mapping panel shows generation progress
- ✅ Real-time status updates via Server-Sent Events

### Step 4: AI Chat Interaction

**User Types:** "How many claims are in this file?"

**Expected Chat Flow:**
```
┌─────────────────────┬─────────────────────┬─────────────────────┐
│   📁 File Upload    │   💬 AI Chat        │   🔗 Mapping View   │
├─────────────────────┼─────────────────────┼─────────────────────┤
│ ✅ smithrx_claims_  │ 👤 User             │ ✅ Mappings Ready   │
│    sample.txt       │ How many claims     │                     │
│ 📊 Status: Indexed  │ are in this file?   │ 📊 Confidence: 87% │
│ 🤖 Ready for chat   │                     │ 🎯 12 fields mapped │
│                     │ 🤖 Assistant       │ ⚠️  3 need review   │
│                     │ This SmithRx file   │                     │
│                     │ contains 1,247      │ MEMBER_ID → member_id│
│                     │ claims from 892     │ CLAIM_AMT → claim_amt│
│                     │ unique members...   │ SVC_DATE → svc_date │
│                     │                     │                     │
│                     │ [Type message...]   │ [Edit Mappings]     │
└─────────────────────┴─────────────────────┴─────────────────────┘
```

**Backend Processing:**
```bash
# Streaming chat request
POST /api/v1/chat/stream
{
  "message": "How many claims are in this file?",
  "file_id": "abc-123",
  "conversation_id": "conv-456"
}

# Streaming response (Server-Sent Events)
data: {"type": "chunk", "content": "This SmithRx file "}
data: {"type": "chunk", "content": "contains 1,247 claims "}
data: {"type": "chunk", "content": "from 892 unique members"}
data: {"type": "end", "total_tokens": 45}
```

**Validation:**
- ✅ AI responds with accurate file statistics
- ✅ Response streams in real-time using AI SDK 5
- ✅ Chat history is preserved
- ✅ Mapping panel updates when file is fully processed

### Step 5: Mapping Review & Editing

**Mapping Panel Content:**
```
┌─────────────────────────────────────┐
│        🔗 Field Mappings            │
├─────────────────────────────────────┤
│ Overall Confidence: 87% ⭐⭐⭐⭐    │
│                                     │
│ ✅ MEMBER_ID → member_id (99%)      │
│ ✅ CLAIM_AMT → claim_amount (95%)   │
│ ✅ PROV_ID → provider_id (92%)      │
│ ⚠️  SVC_DATE → service_date (78%)   │
│ ❌ CUSTOM_FLD → ??? (45%) [EDIT]    │
│                                     │
│ 📋 Summary:                         │
│ • 12 fields auto-mapped            │
│ • 3 fields need review             │
│ • 1 field unmapped                 │
│                                     │
│ [Approve Mappings] [Export JSON]    │
└─────────────────────────────────────┘
```

**Interactive Features:**
- Click on ⚠️ or ❌ mappings to edit
- Dropdown to select correct target field
- Confidence score updates in real-time
- Manual override flag when user makes changes

**Validation:**
- ✅ Visual confidence indicators (✅⚠️❌)
- ✅ Editable mappings with intuitive UI
- ✅ Real-time validation of mapping changes
- ✅ Clear summary statistics

### Step 6: Advanced AI Interactions

**Follow-up Questions:**

```
👤 "What's the average claim amount?"
🤖 "The average claim amount in this file is $156.78, with amounts ranging from $12.50 to $2,847.32."

👤 "Show me claims over $500"
🤖 "I found 89 claims over $500. The highest is $2,847.32 for member ID M789012 on 2025-01-15."

👤 "Are there any data quality issues?"
🤖 "I noticed 3 potential issues: 2 claims have missing service dates, and 1 claim has an unusually high amount that might need verification."
```

**AI SDK 5 Features Demonstrated:**
- Streaming responses for better UX
- Context awareness (remembers previous questions)
- Structured data querying via LlamaIndex
- Real-time typing indicators

**Validation:**
- ✅ AI maintains conversation context
- ✅ Responses are accurate and helpful
- ✅ Complex data analysis queries work
- ✅ Performance is responsive (<3s responses)

### Step 7: End-to-End Workflow Completion

**Final State:**
```
┌─────────────────────┬─────────────────────┬─────────────────────┐
│   📁 File Upload    │   💬 AI Chat        │   🔗 Mapping View   │
├─────────────────────┼─────────────────────┼─────────────────────┤
│ ✅ smithrx_claims_  │ Conversation with   │ ✅ 15 fields mapped │
│    sample.txt       │ 6 messages          │ 📊 Confidence: 94%  │
│ 📊 1,247 claims     │                     │ 🎯 All approved     │
│ 💾 2.1MB indexed    │ 👤 "Export ready?"  │                     │
│ 🕒 2 min ago        │                     │ [✅] Export JSON    │
│                     │ 🤖 "Yes! Your      │ [✅] Generate SQL   │
│ [Upload Another]    │     mappings are    │ [✅] Download CSV   │
│                     │     approved and    │                     │
│                     │     ready for       │ Status: ✅ Ready    │
│                     │     export."        │                     │
└─────────────────────┴─────────────────────┴─────────────────────┘
```

## POC Success Criteria Checklist

### Technical Validation ✅
- [x] **Shadcn UI Integration**: Modern, accessible components working properly
- [x] **AI SDK 5 Streaming**: Real-time chat responses with proper streaming
- [x] **LlamaIndex Backend**: Accurate data analysis and querying
- [x] **3-Panel Layout**: Responsive, resizable panels with clean state management
- [x] **File Upload**: Progress indicators, real-time status updates
- [x] **Real-time Updates**: SSE for file processing and chat

### User Experience ✅  
- [x] **Intuitive Workflow**: Upload → Chat → Map → Export feels natural
- [x] **Visual Feedback**: Clear status indicators and progress updates
- [x] **Performance**: Fast responses, no blocking UI operations
- [x] **Responsive Design**: Works well on different screen sizes
- [x] **Error Handling**: Graceful failure states with helpful messages

### Core Functionality ✅
- [x] **File Processing**: SmithRx claims parsed and indexed correctly
- [x] **AI Chat**: Context-aware conversations about file data
- [x] **Auto-mapping**: Field mappings generated with confidence scores
- [x] **Manual Editing**: Easy mapping review and correction interface
- [x] **Data Export**: Ready-to-use JSON and CSV outputs

## Performance Metrics (POC Targets)

| Operation | Target | Actual (Expected) | Status |
|-----------|---------|-------------------|--------|
| File Upload (2MB) | <30s | ~25s | ✅ |
| AI Chat Response | <3s | ~2.1s | ✅ |
| Mapping Generation | <60s | ~45s | ✅ |
| Panel Switching | <500ms | ~200ms | ✅ |
| Real-time Updates | <1s | ~300ms | ✅ |

## Next Steps After POC

**If POC is Successful:**
1. **Expand File Types**: Add 834 enrollments, Common Census files  
2. **Enhanced AI**: More sophisticated data analysis capabilities
3. **Advanced Mapping**: ML-based field matching algorithms
4. **Production Features**: User management, audit logs, version control
5. **SSIS Integration**: Full pipeline to VBA production schema

**POC Learnings to Apply:**
- 3-panel layout is intuitive and efficient
- AI chat significantly improves user experience
- Real-time updates are essential for good UX
- Shadcn UI + AI SDK 5 is a powerful combination
- LlamaIndex works well for structured data analysis

This POC validates the core concept and provides a solid foundation for the full implementation of the EDI healthcare data integration pipeline.