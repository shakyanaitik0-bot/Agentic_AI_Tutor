# Agentic AI Tutor - Multi-Agent Adaptive Learning Platform

<p align="center">
  <strong>Production-ready AI tutoring system with multi-agent orchestration, hybrid RAG, and adaptive learning</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-0.109+-green.svg" alt="FastAPI">
  <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License">
  <img src="https://img.shields.io/badge/Cost-$0%2Fmonth-brightgreen.svg" alt="Cost">
</p>

---

## What Is This?

An intelligent tutoring system that uses **6 specialized AI agents** to deliver personalized learning for **any topic**. Unlike static chatbots, this system autonomously reasons about student progress, plans learning paths, generates flashcards with spaced repetition, and coordinates specialized capabilities.

### Key Differentiators

- **Multi-Agent Architecture**: Orchestrator coordinates Planner, Quiz Generator, Feedback, Flashcard, and Conversation agents
- **Hybrid RAG Pipeline**: Vector search + BM25 keyword matching + Knowledge Graph with citations
- **Web Search Fallback**: Automatically searches the web when documents aren't uploaded
- **Spaced Repetition**: SM-2 algorithm for optimal flashcard scheduling
- **Citation Support**: All AI responses include source citations (documents, web, knowledge graph)
- **Zero-Cost Operation**: Runs entirely on free tiers (Gemini + Pinecone + local embeddings)
- **Production-Ready**: JWT auth, rate limiting, Prometheus metrics, Docker deployment

---

## Architecture Overview

```
                         +-------------------+
                         |    Frontend UI    |
                         +--------+----------+
                                  |
                                  v
+------------------------------------------------------------------+
|                        FastAPI Backend                            |
|  +------------------------------------------------------------+  |
|  |                    Orchestrator Agent                      |  |
|  |    - Intent Classification (Pattern + LLM)                 |  |
|  |    - Agent Routing & Coordination                          |  |
|  +------+----------+----------+----------+----------+---------+  |
|         |          |          |          |          |            |
|    +----v----+ +---v----+ +---v----+ +---v----+ +---v--------+   |
|    | Planner | |  Quiz  | |Feedback| |Flashcard| |Conversation|  |
|    |  Agent  | |Generator| | Agent | |  Agent  | |   Agent    |  |
|    +---------+ +---------+ +--------+ +---------+ +------------+ |
|         |          |          |          |          |            |
|  +------v----------v----------v----------v----------v--------+   |
|  |              Unified Retrieval Service                    |   |
|  |  +----------+  +-------+  +-----------+  +------------+   |   |
|  |  |  Hybrid  |  | Web   |  | Knowledge |  |  Citation  |   |   |
|  |  |   RAG    |  |Search |  |   Graph   |  |  Tracking  |   |   |
|  |  +----------+  +-------+  +-----------+  +------------+   |   |
|  +-----------------------------------------------------------+   |
+------------------------------------------------------------------+
         |                    |                    |
    +----v----+         +-----v-----+        +-----v-----+
    | Pinecone|         |  Gemini   |        |  SQLite   |
    | Vectors |         |    LLM    |        | Database  |
    +---------+         +-----------+        +-----------+
```

---

## Features

### For Students
- **Universal Topic Support**: Learn any subject - not restricted to specific exams
- **Adaptive Quizzes**: AI-generated quizzes that adjust to your skill level
- **Flashcard Generation**: Create flashcards with SM-2 spaced repetition algorithm
- **Study Plans**: AI-generated plans (7-365 days) prioritizing weak areas
- **Document Upload**: Upload your own study materials for context-aware help
- **Web Search Fallback**: Get accurate information even without uploaded documents
- **Source Citations**: See where information comes from (documents, web, knowledge graph)
- **Progress Tracking**: Comprehensive performance analytics with trend analysis
- **Natural Conversation**: Chat interface for explanations and questions

### For Recruiters/Engineers
- **Multi-Agent Orchestration**: Intent classification, agent routing, workflow coordination
- **Hybrid RAG**: Dense + sparse retrieval with knowledge graph enhancement
- **Unified Retrieval**: Combines documents, knowledge graph, and web search with citations
- **Spaced Repetition**: Full SM-2 algorithm implementation for flashcards
- **Production Patterns**: JWT auth, rate limiting, metrics, health checks
- **Clean Architecture**: Service layer, dependency injection, comprehensive tests (51 passing)
- **Docker Ready**: Multi-stage builds, docker-compose, monitoring stack

---

## Tech Stack

| Component | Technology | Why |
|-----------|-----------|-----|
| **Backend** | FastAPI | Async, auto-docs, type safety |
| **Database** | SQLite + SQLAlchemy 2.0 | Zero-config, production patterns |
| **Vector DB** | Pinecone | Managed, free tier |
| **LLM** | Google Gemini 2.5 Flash | Free tier, fast |
| **Embeddings** | Sentence Transformers | Free, local, no API calls |
| **Sparse Search** | BM25 (rank_bm25) | Keyword matching |
| **Knowledge Graph** | NetworkX | Topic relationships |
| **Web Search** | DuckDuckGo + Wikipedia | Free, no API key required |
| **Flashcards** | SM-2 Algorithm | Spaced repetition scheduling |
| **Auth** | JWT + bcrypt | Industry standard |
| **Monitoring** | Prometheus + Grafana | Metrics & dashboards |
| **Deployment** | Docker + Railway | Container-ready |

---

## Quick Start

### Prerequisites
- Python 3.10+
- [uv](https://github.com/astral-sh/uv) package manager
- Free accounts: [Pinecone](https://www.pinecone.io/), [Google AI Studio](https://aistudio.google.com/)

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/Agentic_AI_Tutor.git
cd Agentic_AI_Tutor

# Install dependencies
uv sync

# Configure environment
cp .env.example .env
# Edit .env with your API keys

# Initialize database
uv run python scripts/init_db.py

# Start the server
uv run uvicorn app.main:app --reload

# Open browser
# http://localhost:8000 (API)
# http://localhost:8000/docs (Swagger UI)
# frontend/index.html (Web UI)
```

### Docker Deployment

```bash
# Build and run
docker-compose up -d

# With monitoring stack
docker-compose --profile monitoring up -d

# View logs
docker-compose logs -f app
```

---

## Adaptive Learning Algorithm

```
Student Performance Analysis
         |
         v
+------------------+
| Accuracy < 50%   | --> EASY questions
+------------------+
| Accuracy 50-80%  | --> MEDIUM questions  (Optimal Learning Zone)
+------------------+
| Accuracy > 80%   | --> HARD questions
+------------------+
         |
         v
Strength Classification:
- Weak: < 60% (prioritized in plans)
- Average: 60-80%
- Strong: > 80%
- Mastery: > 85% + recent practice
```

### Spaced Repetition (SM-2 Algorithm)

```
Quality Rating (0-5):
  0: Complete blackout
  1: Incorrect, remembered upon seeing answer
  2: Incorrect, but answer was easy to recall
  3: Correct with difficulty
  4: Correct with minor hesitation
  5: Perfect response

Interval Calculation:
  - Quality < 3: Reset to 1 day
  - Quality >= 3: interval = interval * easiness_factor

Easiness Factor Adjustment:
  EF' = EF + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
  Minimum EF: 1.3
```

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/students/register` | POST | Create student account |
| `/api/students/login` | POST | Authenticate and get JWT |
| `/api/sessions/start` | POST | Start learning session |
| `/api/chat` | POST | Main orchestrator endpoint |
| `/api/quiz/generate` | POST | Generate adaptive quiz |
| `/api/quiz/submit` | POST | Submit quiz answers |
| `/api/feedback/{id}` | GET | Get progress report |
| `/api/plan/generate` | POST | Generate study plan |
| `/api/documents/upload` | POST | Upload study materials |
| `/api/flashcards/generate/{id}` | POST | Generate flashcard deck |
| `/api/flashcards/decks/{id}` | GET | Get student's flashcard decks |
| `/api/flashcards/study/{deck_id}` | GET | Get cards for study session |
| `/api/flashcards/review` | POST | Submit flashcard review (SM-2) |
| `/api/flashcards/stats/{id}` | GET | Get flashcard statistics |
| `/health` | GET | Health check |
| `/metrics` | GET | Prometheus metrics |

Full API documentation available at `/docs` when running.

---

## Project Structure

```
Agentic_AI_Tutor/
├── app/
│   ├── agents/                    # AI Agents (6 total)
│   │   ├── orchestrator.py        # Intent routing & coordination
│   │   ├── planner_agent.py       # Study plan generation
│   │   ├── quiz_agent.py          # Adaptive quiz generation
│   │   ├── feedback_agent.py      # Progress analysis
│   │   ├── flashcard_agent.py     # Flashcard generation with SM-2
│   │   └── base_agent.py          # Agent base class
│   ├── services/                  # Business Logic
│   │   ├── unified_retrieval_service.py  # Combined retrieval with citations
│   │   ├── hybrid_rag_service.py  # Vector + BM25 + KG
│   │   ├── web_search_service.py  # DuckDuckGo + Wikipedia search
│   │   ├── rag_service.py         # Core document retrieval
│   │   ├── llm_service.py         # Gemini/OpenAI wrapper
│   │   └── embedding_service.py   # Sentence Transformers
│   ├── models/                    # Database Models
│   │   ├── student.py             # Student profiles
│   │   ├── session.py             # Stateful sessions
│   │   ├── progress.py            # Performance tracking
│   │   ├── quiz.py                # Persistent quizzes
│   │   └── flashcard.py           # Flashcards with SM-2
│   ├── core/                      # Core Infrastructure
│   │   ├── security.py            # JWT, bcrypt, encryption
│   │   ├── middleware.py          # Rate limiting, metrics
│   │   └── config.py              # YAML configuration
│   └── api/                       # REST Endpoints
│       └── routes/
│           ├── flashcards.py      # Flashcard endpoints
│           └── ...
├── frontend/                      # Web UI (HTML/CSS/JS)
├── tests/                         # Pytest tests (51 passing)
├── docs/                          # Documentation
│   ├── PROJECT_OVERVIEW.md        # Executive summary
│   ├── CHALLENGES_AND_DECISIONS.md  # Technical deep-dive
│   ├── SHOWCASE.md                # Interview prep
│   └── ACCOUNTS_NEEDED.md         # Setup guide
├── monitoring/                    # Prometheus/Grafana configs
├── Dockerfile                     # Multi-stage build
├── docker-compose.yml             # Full stack deployment
└── config.yaml                    # Application config
```

---

## Documentation

| Document | Purpose |
|----------|---------|
| [PROJECT_OVERVIEW.md](docs/PROJECT_OVERVIEW.md) | Executive summary, architecture diagrams |
| [CHALLENGES_AND_DECISIONS.md](docs/CHALLENGES_AND_DECISIONS.md) | Technical decisions, trade-offs, interview prep |
| [SHOWCASE.md](docs/SHOWCASE.md) | LinkedIn post templates, demo script, talking points |
| [ACCOUNTS_NEEDED.md](docs/ACCOUNTS_NEEDED.md) | Free account setup guide |

---

## Running Tests

```bash
# Run all tests (51 passing)
uv run pytest

# Run with coverage
uv run pytest --cov=app --cov-report=html

# Run specific test file
uv run pytest tests/test_models.py -v
```

---

## Cost Breakdown

| Service | Monthly Cost |
|---------|-------------|
| Google Gemini API | $0 (free tier) |
| Pinecone Vector DB | $0 (free tier) |
| Sentence Transformers | $0 (local) |
| DuckDuckGo/Wikipedia | $0 (free) |
| Railway Hosting | $0 (free tier) |
| **Total** | **$0** |

---

## Feature Highlights

### Flashcards with Spaced Repetition
- Generate AI-powered flashcards from any topic
- Uses uploaded documents for context when available
- SM-2 algorithm schedules optimal review times
- Track mastery progress across decks
- Multiple card types: Basic, Cloze, Definition, Concept, Formula, Example

### Unified Retrieval with Citations
- Combines document search, knowledge graph, and web search
- All responses include source citations
- Automatic fallback to web when documents unavailable
- Relevance scoring for all sources

### Web Search Fallback
- No API key required (uses DuckDuckGo + Wikipedia)
- Educational domain prioritization
- Caching for faster responses
- Seamless integration with document retrieval

---

## Future Roadmap

- [x] Spaced repetition algorithm (SM-2)
- [x] Web search fallback
- [x] Citation support
- [x] Flashcard generation
- [ ] WebSocket real-time chat
- [ ] Mobile responsive design
- [ ] PostgreSQL for scale
- [ ] Redis caching layer
- [ ] Email notifications
- [ ] Analytics dashboard
- [ ] Voice interaction (Whisper)

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## License

MIT License - see [LICENSE](LICENSE) for details.

---

## Author

**Aditya Sarade**

Built as a production-ready demonstration of multi-agent AI systems for adaptive learning.

---

<p align="center">
  <strong>If you found this useful, please star the repository!</strong>
</p>
