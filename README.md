# 🎓 Agentic AI Tutor for Adaptive Learning

An intelligent, adaptive tutoring system that uses multi-agent AI architecture to provide personalized learning experiences for competitive exam preparation (JEE, SAT, GRE).

## 🌟 Features

- **Multi-Agent Architecture**: Planner, Retriever, Quiz Generator, and Progress Tracker agents working together
- **RAG-Powered Responses**: Retrieval-Augmented Generation for accurate, context-aware answers
- **Adaptive Learning**: Dynamic difficulty adjustment based on student performance
- **Progress Tracking**: Comprehensive analytics on strengths, weaknesses, and learning patterns
- **Stateful Sessions**: Maintains conversation context across multiple interactions
- **User-Provided API Keys**: Students use their own LLM API keys for privacy and cost control

## 🏗️ Architecture

```
┌─────────────┐
│   Student   │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────┐
│         FastAPI Backend             │
│  ┌───────────────────────────────┐  │
│  │     Planner Agent             │  │
│  │   (Orchestrator)              │  │
│  └────┬──────┬─────────┬─────────┘  │
│       │      │         │             │
│   ┌───▼──┐ ┌─▼─────┐ ┌─▼────────┐   │
│   │Retrie│ │ Quiz  │ │ Progress │   │
│   │ver   │ │Gener- │ │ Tracker  │   │
│   │Agent │ │ ator  │ │ Agent    │   │
│   └───┬──┘ └───┬───┘ └─┬────────┘   │
└───────┼────────┼───────┼────────────┘
        │        │       │
   ┌────▼───┐   │   ┌───▼─────┐
   │Pinecone│   │   │ SQLite  │
   │(Vector │   │   │ (State) │
   │  DB)   │   │   └─────────┘
   └────────┘   │
                │
           ┌────▼─────┐
           │ OpenAI/  │
           │ Gemini   │
           └──────────┘
```

## 📦 Tech Stack

| Component | Technology |
|-----------|-----------|
| **Backend** | FastAPI |
| **Package Manager** | uv |
| **Database** | SQLite |
| **Vector DB** | Pinecone |
| **LLMs** | OpenAI GPT-4o-mini, Gemini 2.5 Flash |
| **Embeddings** | OpenAI text-embedding-3-small |
| **Frontend** | HTML/CSS/JavaScript |
| **Deployment** | Railway |

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) package manager
- Pinecone account (free tier)
- OpenAI API key (optional, for testing)

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd agentic-tutor
   ```

2. **Install dependencies**
   ```bash
   uv sync
   ```

3. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env and add your Pinecone API key
   ```

4. **Initialize the database**
   ```bash
   uv run python scripts/init_db.py
   ```

5. **Ingest study material** (optional)
   ```bash
   # Place PDFs in knowledge_base/ directory
   uv run python scripts/ingest_docs.py
   ```

6. **Run the server**
   ```bash
   uv run uvicorn app.main:app --reload
   ```

7. **Open your browser**
   ```
   http://localhost:8000
   ```

## 📚 API Documentation

### Student Management

#### Register New Student
```http
POST /api/student/register
Content-Type: application/json

{
  "name": "John Doe",
  "email": "john@example.com",
  "exam_type": "JEE",
  "api_key_openai": "sk-...",  // Optional
  "api_key_gemini": "AIza..."  // Optional
}
```

#### Start Learning Session
```http
POST /api/session/start
Content-Type: application/json

{
  "student_id": "uuid-here"
}
```

### Learning Interactions

#### Ask a Question
```http
POST /api/ask
Content-Type: application/json

{
  "student_id": "uuid-here",
  "session_id": "session-uuid",
  "message": "I don't understand conditional probability"
}
```

**Response:**
```json
{
  "response": "I noticed you're struggling with Probability. Let's review...",
  "retrieved_content": "Conditional probability is...",
  "quiz": [
    {
      "id": 1,
      "question": "A coin is tossed twice...",
      "options": ["A", "B", "C", "D"]
    }
  ],
  "plan_executed": ["Retrieved notes", "Generated quiz"]
}
```

#### Generate Adaptive Quiz
```http
POST /api/quiz
Content-Type: application/json

{
  "student_id": "uuid-here",
  "topic": "Probability",  // Optional
  "num_questions": 5       // Optional
}
```

#### Get Progress Report
```http
GET /api/progress/{student_id}
```

**Response:**
```json
{
  "progress": {
    "Probability": {"accuracy": 50, "strength": "weak"},
    "Algebra": {"accuracy": 90, "strength": "strong"}
  },
  "recommendation": "Focus next on Conditional Probability",
  "summary": "You're strong in Algebra but need practice in Probability"
}
```

## 🧪 Testing

Run tests with:
```bash
uv run pytest
```

## 🗂️ Project Structure

```
Agentic_AI_Tutor/
├── app/
│   ├── agents/              # Agent implementations
│   │   ├── base_agent.py    # Abstract base class
│   │   ├── planner.py       # Orchestrator agent
│   │   ├── retriever.py     # RAG retrieval agent
│   │   ├── quiz_generator.py
│   │   └── progress_tracker.py
│   ├── api/                 # FastAPI routes
│   │   └── routes.py
│   ├── core/                # Core configuration
│   │   ├── config.py        # Settings
│   │   └── database.py      # SQLite setup
│   ├── models/              # Database models
│   │   ├── student.py
│   │   ├── session.py
│   │   └── progress.py
│   ├── schemas/             # Pydantic schemas
│   │   ├── requests.py
│   │   └── responses.py
│   ├── services/            # Business logic
│   │   ├── llm_service.py   # LLM wrapper
│   │   ├── rag_service.py   # RAG implementation
│   │   └── embedding_service.py
│   └── main.py              # FastAPI app
├── frontend/                # Web interface
│   ├── index.html
│   ├── style.css
│   └── app.js
├── scripts/                 # Utility scripts
│   ├── init_db.py
│   └── ingest_docs.py
├── tests/
├── pyproject.toml
├── .env.example
└── README.md
```

## 🎯 Agent Workflow

1. **Student sends message** → FastAPI endpoint
2. **Planner Agent** analyzes intent
3. **Agents execute tasks**:
   - **Retriever**: Fetches relevant content from Pinecone
   - **Quiz Generator**: Creates adaptive questions
   - **Progress Tracker**: Updates performance metrics
4. **Planner** synthesizes responses
5. **Response sent** to student with natural language + structured data

## 🔒 Security & Privacy

- User API keys are stored securely (encrypted in database)
- No conversation data is shared across students
- Sessions expire after inactivity
- All interactions are logged for progress tracking only

## 🚢 Deployment

### Railway Deployment

1. **Create new project on Railway**
2. **Connect repository**
3. **Set environment variables**:
   ```
   PINECONE_API_KEY=your_key
   DATABASE_URL=sqlite:///./data/agentic_tutor.db
   ```
4. **Deploy**
   ```bash
   railway up
   ```

### Alternative Platforms
- **Render**: Similar to Railway
- **Fly.io**: For more control
- **Vercel**: Only for frontend (API may timeout)

## 📊 Evaluation Metrics

- **Adaptiveness**: % of recommendations aligned with weak areas
- **Learning Gain**: Pre-test vs post-test improvement
- **Engagement**: Average session length and retention
- **Explainability**: Clarity of AI justifications

## 🤝 Contributing

This is a research project for educational purposes. Feedback and suggestions are welcome!

## 📄 License

MIT License

## 🙏 Acknowledgments

- Built with FastAPI, OpenAI, and Pinecone
- Inspired by modern agentic AI architectures
- Designed for competitive exam preparation

---

**Status**: 🚧 In Development (3-day sprint)  
**Last Updated**: 2024-11-27