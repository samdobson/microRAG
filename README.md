# microRAG

**A RAG development starter kit.**

## Quick Start

1. **Start the application**:
   ```bash
   docker-compose up -d
   ```

2. **Wait for Ollama model download** (first run only):
   The system will automatically download the Qwen3-0.6B model on first startup, which may take a few minutes.

3. **Access the application**:
   - Frontend: http://localhost:3001
   - Backend API: http://localhost:8000
   - Qdrant UI: http://localhost:6333/dashboard

4. **Upload documents**:
   - Drag and drop `.txt` or `.md` files
   - Or click "Choose Files" to select files

5. **Start chatting**:
   - Ask questions about your uploaded documents
   - The AI will provide answers based on the document content

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   React App     │    │   FastAPI       │    │   Qdrant        │
│   (Frontend)    │───▶│   (Backend)     │───▶│   (Vector DB)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │   Ollama        │
                       │   (LLM)         │
                       └─────────────────┘
```


## Development

### Backend Development
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

### Frontend Development  
```bash
cd frontend
npm install
npm start
```

