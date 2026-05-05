# APilus (Acıbadem-Chatblock)

An AI-powered chatbot application equipped with a smart Retrieval-Augmented Generation (RAG) pipeline to intelligently answer both university-specific queries and general questions.

## Architecture Overview

APilus uses a modular, full-stack architecture optimized for high performance and intelligent routing:

- **Frontend:** Built with React and Vite for a fast, responsive user interface.
- **Backend:** Powered by Django and Django REST Framework, providing RESTful APIs for chat management.
- **Databases & Caching:** 
  - **PostgreSQL:** Stores chat sessions and messaging history across users.
  - **Redis:** Caches previously answered questions to bypass redundant LLM API calls and drastically reduce response times.
- **AI & RAG Pipeline:**
  - Integrates **LangChain** and **FAISS** (Facebook AI Similarity Search) to index domain-specific documents.
  - **Dynamic Score-Based Routing:** Calculates similarity (L2) scores to decide query processing paths. Highly specific queries access the RAG database, while general knowledge queries fall back to a local bare-metal LLM powered by **Ollama**.

## Setup Instructions

### Prerequisites
Ensure your local environment has the following installed:
- Python 3.12+
- Node.js (v18+)
- PostgreSQL (Server must be running)
- Redis Server (Running on default port `6379`)
- Docker and Docker Compose
- Ollama (Running locally on `127.0.0.1:11434`)

### Running with Docker Compose

The entire application stack (Frontend, Backend, PostgreSQL, and Redis) is containerized and can be started with a single command.

```bash
# Clone the repository and enter the directory
# git clone <repository-url>
cd APilus

# Build and start all designated services
docker compose up --build
```

*Note: Database migrations will run automatically upon starting the backend container depending on your `docker-compose.yml` or entrypoint setup. If you need to run them manually, you can execute `docker compose exec backend python backend/manage.py migrate`.*

## Team Members
- **[Yekta Soytürk]** – 231401007
- **[Özgür Deniz Çelik]** – 231401057
- **[Burak Tekin]** – 221401003


