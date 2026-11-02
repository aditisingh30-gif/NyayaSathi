# NyayaSathi — AI-Based Indian Legal & Policy Information Assistant

An enterprise-grade, evidence-grounded AI assistant for querying Indian statutes, Acts, rules, regulations, and government policies from authentic legal documents.

Built with **FastAPI**, **React 18 + Vite**, **ChromaDB**, **PyMuPDF**, and **Modular LLMs** (Google Gemini, OpenAI, Local Ollama, and Grounded Synthesizer).

---

## 🌟 Key Features

1. **Evidence-Grounded Retrieval-Augmented Generation (RAG)**:
   - Every answer is strictly substantiated by authentic legal document chunks.
   - If an Act or section is unindexed or evidence is insufficient, NyayaSathi explicitly admits absence instead of fabricating provisions.
2. **Statutory Citations & Verification**:
   - Every legal answer displays verified citations: **Act Name**, **Section / Rule Number**, **Page Number**, and **Exact Excerpt Snippet**.
   - The Citation Verifier checks generated citations against retrieved evidence to help identify unsupported references.
3. **Multilingual Query Understanding**:
   - Queries can be phrased in **English**, **Hindi (Devanagari)**, or **Hinglish (Romanized Hindi)**.
   - Domain concepts (e.g., *upbhokta*, *shikayat*, *adhikar*, *aayog*, *muavza*, *dand*, *nakli*) are mapped directly to their statutory provisions.
4. **Section-Aware Statutory Ingestion**:
   - High-precision PDF parser powered by PyMuPDF (`fitz` 2.0).
   - Validates file extensions, `%PDF-` magic bytes, and enforces a 50MB file size ceiling.
   - Normalizes whitespace, merges hyphenated line breaks, and eliminates repetitive Gazette running headers/footers.
   - Generates section-aware statutory chunks preserving Act, Section, and Page metadata.
   - 384-dimensional dense vectors generated via ONNX MiniLM runtime (`all-MiniLM-L6-v2`).
   - SHA-256 duplicate detection prevents identical documents from being indexed multiple times.
5. **Modular LLM Provider Architecture**:
   - Seamlessly switch between **Google Gemini**, **OpenAI GPT**, **Local Ollama**, or the deterministic **Grounded Synthesizer**.
   - Fully operational offline without external API keys using the built-in Grounded Synthesizer.
6. **Conversation Session Management**:
   - Persistent multi-turn dialogue with context retention across follow-up questions.
   - History sidebar with conversation titles, message counts, and session deletion.
7. **Legal Document Indexing**:

   - Supports uploading and indexing official legal PDFs, including the Consumer Protection Act, 2019.
   - Uploaded documents and local ChromaDB data are not included in this GitHub repository.
   - Users must upload and index the required legal documents after setting up the application.

---

## 🛠️ Technology Stack

| Layer | Technologies |
| :--- | :--- |
| **Frontend** | React 18, Vite 6, Tailwind CSS 3, Lucide React Icons |
| **Backend** | Python 3.13, FastAPI, Uvicorn, Pydantic v2 |
| **Document Processing** | PyMuPDF (`fitz` 2.0), Statutory Regex Extractor |
| **Vector Database** | ChromaDB (v1.5.9) with persistent storage |
| **Embeddings** | `all-MiniLM-L6-v2` (384 dimensions, ONNX Runtime) |
| **LLM Providers** | Google Gemini (1.5 Flash), OpenAI (GPT-4o Mini), Ollama (LLaMA3), Grounded Synthesizer |
| **Testing** | Pytest 9.2, Pytest-Asyncio, HTTPX (45 automated tests passing) |

---

## 📁 Project Structure

```
ai_pro/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI application entrypoint & lifespan
│   │   ├── config.py                # Pydantic BaseSettings configuration
│   │   ├── api/
│   │   │   └── routes.py            # REST endpoints (Chat, Ingestion, Retrieval, Conversations)
│   │   ├── core/
│   │   │   └── logging_config.py    # Structured logging configuration
│   │   ├── database/
│   │   │   ├── vector_store.py      # ChromaDB client & SHA-256 registry
│   │   │   └── conversation_store.py# Persistent conversation manager (conversations.json)
│   │   ├── ingestion/
│   │   │   ├── validator.py         # PDF validation (magic bytes, size, corruption check)
│   │   │   ├── cleaner.py           # Text cleaner (hyphens, whitespace, headers)
│   │   │   ├── extractor.py         # PyMuPDF page & section extractor
│   │   │   └── chunker.py           # Section-aware statutory chunking
│   │   ├── retrieval/
│   │   │   ├── query_processor.py   # Multilingual mapper & section regex parser
│   │   │   └── retriever.py         # Hybrid search engine (semantic + keyword + section boost)
│   │   ├── llm/
│   │   │   ├── base.py              # BaseLLMProvider interface
│   │   │   ├── prompts.py           # Grounded legal prompts & system instructions
│   │   │   ├── gemini_provider.py   # Google Gemini API provider
│   │   │   ├── openai_provider.py   # OpenAI API provider
│   │   │   ├── ollama_provider.py   # Local Ollama offline provider
│   │   │   ├── fallback_provider.py # Grounded Synthesizer provider
│   │   │   └── factory.py           # Provider selection factory
│   │   ├── models/
│   │   │   └── schemas.py           # Pydantic API request & response schemas
│   │   └── services/
│   │       ├── embedding_service.py # ONNX MiniLM embedding service (384d)
│   │       ├── ingestion_service.py # Ingestion pipeline orchestrator
│   │       ├── citation_verifier.py # Citation verification & hallucination guard
│   │       └── chat_service.py      # End-to-end RAG chat coordinator
│   ├── tests/
│   │   ├── test_health.py           # Health & schema tests (3 tests)
│   │   ├── test_ingestion.py        # PDF extraction & ChromaDB tests (13 tests)
│   │   ├── test_retrieval.py        # Semantic & hybrid search tests (10 tests)
│   │   ├── test_chat.py             # Chat API & conversation tests (8 tests)
│   │   └── test_e2e_security.py     # E2E lifecycle & security tests (9 tests)
│   ├── requirements.txt             # Python backend dependencies
│   ├── pytest.ini                   # Pytest configuration
│   └── .env.example                 # Environment variable template
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── ChatInterface.jsx    # Complete interactive legal chat UI
│   │   │   ├── CitationCard.jsx     # Expandable statutory citation card
│   │   │   └── DocumentManager.jsx  # Legal PDF uploader & ChromaDB manager
│   │   ├── services/
│   │   │   └── api.js               # Frontend REST client
│   │   ├── App.jsx                  # Main application with tab navigation
│   │   ├── main.jsx                 # React root
│   │   └── index.css                # Tailwind CSS imports
│   ├── package.json                 # Node dependencies
│   ├── tailwind.config.js           # Tailwind CSS configuration
│   └── vite.config.js               # Vite build configuration
├── data/
│   ├── raw_documents/               # Storage for uploaded legal PDFs
│   ├── processed/                   # Extracted JSON representations for debugging
│   └── vector_store/                # Persistent ChromaDB collection & registry
├── docs/
│   └── ARCHITECTURE.md              # System design & architecture document
├── scripts/
│   ├── start_backend.bat            # Windows startup script for backend
│   ├── start_frontend.bat           # Windows startup script for frontend
│   └── run_tests.bat                # Automated test runner script
├── README.md                        # Project documentation
└── .gitignore                       # Git ignore rules
```

---

## 🚀 Quick Start Guide

### 1. Prerequisites
- **Python**: Version 3.11 or higher (tested on Python 3.13)
- **Node.js**: Version 18 or higher with `npm`

### 2. Backend Setup
```powershell
# Navigate to backend directory
cd backend

# Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create your .env file
copy .env.example .env

# (Optional) Add your GEMINI_API_KEY or OPENAI_API_KEY in .env
# If omitted, NyayaSathi runs offline using the Grounded Synthesizer

# Start the backend server
uvicorn app.main:app --reload --port 8000
```
- **Backend API**: `http://127.0.0.1:8000`
- **Interactive Swagger Docs**: `http://127.0.0.1:8000/docs`

### 3. Frontend Setup
```powershell
# In a new terminal, navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Start Vite development server
npm run dev
```
- **Frontend Web UI**: `http://localhost:5173`

---

## 📡 REST API Reference

### 1. Legal Chat & RAG
- **`POST /api/chat`**
  ```json
  // Request
  {
    "question": "What is the procedure under Section 35 of the Consumer Protection Act?",
    "conversation_id": null,
    "provider": "auto"
  }

  // Response
  {
    "conversation_id": "conv_a1b2c3d4e5f6",
    "question": "What is the procedure under Section 35 of the Consumer Protection Act?",
    "direct_answer": "Under Section 35 of The Consumer Protection Act, 2019 (Page 18), a complaint in relation to any goods sold or delivered or agreed to be sold or delivered or any service provided or agreed to be provided may be filed with a District Commission...",
    "legal_explanation": "According to the official gazette text...",
    "citations": [
      {
        "act_name": "The Consumer Protection Act, 2019",
        "section": "Section 35",
        "document_name": "doc_f3bdf90b99c1_consumer_protection_act_2019.pdf",
        "page_number": 18,
        "snippet": "35. (1) A complaint, in relation to any goods sold or delivered or agreed to be sold or delivered or any service provided or agreed to be provided, may be filed with a District Commission by (a) the consumer...",
        "relevance_score": 0.88
      }
    ],
    "disclaimer": "This chatbot provides Indian legal and policy information for educational and research purposes only. Not formal legal advice.",
    "provider_used": "grounded_synthesizer (nyayasathi-grounded-synthesizer)",
    "processing_time_seconds": 0.32
  }
  ```

### 2. Semantic & Hybrid Retrieval
- **`POST /api/retrieval/search`**
  ```json
  // Request
  {
    "query": "Who is considered a consumer under Section 2?",
    "top_k": 3,
    "relevance_threshold": 0.30
  }
  ```

### 3. Document Ingestion
- **`POST /api/documents/upload`**: Upload and index an authentic legal PDF (`multipart/form-data` with `file` and optional `act_name`).
- **`GET /api/documents`**: List all indexed legal documents with chunk counts, page counts, and metadata.
- **`GET /api/documents/{document_id}`**: Retrieve specific document metadata by ID.
- **`GET /api/documents/{document_id}/status`**: Ingestion status check.
- **`DELETE /api/documents/{document_id}`**: Remove document from vector store (`?delete_raw_file=true` to delete original file).

### 4. Conversation History
- **`GET /api/conversations`**: List previous conversation sessions.
- **`GET /api/conversations/{conversation_id}`**: Retrieve full chat history for a session.
- **`DELETE /api/conversations/{conversation_id}`**: Delete a conversation session.

---

## 🧪 Automated Testing

The project includes an end-to-end automated test suite covering all 45 test cases:

```powershell
cd backend
.\.venv\Scripts\pytest tests -v
```

### Test Suite Summary:
- **`test_health.py` (3 tests)**: Health endpoint, schema validation, non-PDF rejection.
- **`test_ingestion.py` (13 tests)**: Valid/invalid/empty/corrupt PDF handling, text cleaner, statutory chunking, ONNX embedding generation, ChromaDB persistence, duplicate upload rejection.
- **`test_retrieval.py` (10 tests)**: Query processor, section extraction, Hindi/Hinglish mapping, hybrid scoring, section boost, unsupported Act refusal, threshold filtering.
- **`test_chat.py` (8 tests)**: Citation verifier, conversation store CRUD, LLM fallback provider, full chat flow, follow-up conversation context retention.
- **`test_e2e_security.py` (9 tests)**: Complete multi-turn E2E lifecycle with a new central Act, SQL/XSS injection resilience, oversized file rejection, secret leak prevention.

**Result**: **45 passed, 0 failed (100% pass rate)**.

---

## 🔧 Troubleshooting

1. **`HTTP 409 Conflict: Document is already indexed`**:
   - The SHA-256 hash of the uploaded PDF matches a document already in ChromaDB. Delete the existing document first if you wish to re-index.
2. **`ModuleNotFoundError` or Path Issues on Windows**:
   - Always run commands with `.venv\Scripts\activate` or use the full path `backend\.venv\Scripts\pytest.exe`.
3. **No External LLM API Key**:
   - If `GEMINI_API_KEY` or `OPENAI_API_KEY` is not provided, NyayaSathi automatically uses the **Grounded Synthesizer**, providing answers extracted directly from retrieved evidence chunks.

---

## ⚠️ Legal Disclaimer
NyayaSathi provides legal and policy information for research and educational purposes only based on uploaded statutory documents. It does not constitute formal legal advice, legal opinion, or advocate-client representation under the Advocates Act, 1961.
