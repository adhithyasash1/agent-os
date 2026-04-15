# AgentOS

Production-grade, local-first AI agent platform.

## 🚀 Setup

### Prerequisites
- Ollama installed and running.
- Neo4j (local or via Docker).
- ChromaDB (managed locally).

### Backend Setup
1. Create virtual environment:
   ```bash
   /opt/homebrew/bin/python3 -m venv venv
   source venv/bin/activate
   pip install -r backend/requirements.txt
   ```
2. Start the backend:
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

### Frontend Setup
1. Install dependencies:
   ```bash
   cd frontend
   npm install
   ```
2. Run development server:
   ```bash
   npm run dev
   ```

## 🏗️ Architecture
- **Engine**: LangGraph
- **LLM**: Ollama (Qwen 2.5)
- **Memory**: mem0 + Chroma + Neo4j
- **Tools**: MCP + Playwright
- **Eval**: DeepEval + RAGAS
- **Observe**: Langfuse

## 📂 Structure
- `/backend`: FastAPI service.
- `/frontend`: Next.js dashboard.
- `/data`: Local storage.
