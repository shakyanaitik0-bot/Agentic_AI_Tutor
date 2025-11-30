# Agentic AI Tutor for Adaptive Learning

An intelligent, adaptive tutoring system using multi-agent AI architecture to provide personalized learning experiences for competitive exam preparation (JEE, SAT, GRE).

## Overview

Traditional e-learning platforms deliver the same content to all learners regardless of their knowledge gaps or learning pace. This system solves that problem using autonomous AI agents that can assess knowledge gaps, retrieve relevant content, generate adaptive quizzes, track progress, and dynamically adjust study plans.

Unlike static chatbots, this agentic tutor can reason about student progress, plan the next learning steps, and autonomously coordinate multiple specialized agents to deliver personalized instruction.

## Key Features

- **Multi-Agent Architecture**: Orchestrator coordinates specialized agents (Planner, Quiz Generator, Feedback, Conversation)
- **Adaptive Learning**: Difficulty adjusts automatically based on student performance (weak: <60%, strong: >80%)
- **RAG-Powered Content**: Retrieval-Augmented Generation from uploaded study materials (PDFs)
- **Student Document Upload**: Upload your own notes and get quizzes based on your content
- **Progress Tracking**: Comprehensive analytics identifying weak/strong topics with trend analysis
- **Personalized Study Plans**: Generate 7-365 day adaptive study schedules with milestones
- **Stateful Sessions**: Maintains conversation context and learning state across interactions
- **Explainable Recommendations**: Transparent reasoning for why topics or questions are assigned
- **100% Free Operation**: Uses Gemini (free tier) + Sentence Transformers (local embeddings)

## Architecture

The system uses a multi-agent workflow where an Orchestrator routes student requests to specialized agents:

**Orchestrator Agent** - Intent classification and agent coordination
- Analyzes student input and routes to appropriate agent
- Coordinates multi-agent workflows (e.g., quiz with feedback)
- Synthesizes responses from multiple agents

**Planner Agent** - Study plan generation
- Analyzes progress to identify weak areas
- Creates adaptive study plans with daily schedules
- Sets milestones and tracks long-term goals

**Quiz Generator Agent** - Adaptive assessment
- Selects difficulty based on student accuracy
- Uses RAG to generate context-based questions from uploaded PDFs
- Provides detailed explanations for answers
- Updates progress records after each quiz

**Feedback Agent** - Progress analysis
- Identifies weak/strong/improving/declining topics
- Generates personalized recommendations
- Creates detailed progress reports
- Triggers replanning when needed

**Conversation Agent** - Natural Q&A
- Retrieves relevant content from knowledge base
- Provides explanations and clarifications
- Maintains conversational context

**RAG Service** - Content retrieval
- Processes uploaded PDF documents
- Semantic search with student-specific filtering
- Lower similarity threshold (0.3) for student documents

## Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Backend Framework | FastAPI | Async API server with automatic OpenAPI docs |
| Package Manager | uv | Fast Python package management |
| Configuration | YAML + Pydantic | Settings management with validation |
| Database | SQLite + SQLAlchemy 2.0 | Student profiles, sessions, progress tracking |
| Vector Database | Pinecone | Document embeddings and semantic search |
| LLM | Gemini 2.5 Flash | Agent reasoning and responses (FREE) |
| Embeddings | Sentence Transformers | Local embeddings - all-MiniLM-L6-v2 (FREE) |
| Frontend | HTML/CSS/JavaScript | Simple web interface |

## Quick Start

### Prerequisites

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) package manager
- Pinecone account (free tier)
- Gemini API key (free tier)

### Installation

1. Clone the repository
   ```bash
   git clone <repository-url>
   cd Agentic_AI_Tutor
   ```

2. Install dependencies
   ```bash
   uv sync
   ```

3. Set up environment variables
   ```bash
   cp .env.example .env
   # Edit .env and add your API keys:
   # PINECONE_API_KEY=your_pinecone_key
   # DEFAULT_GEMINI_API_KEY=your_gemini_key (optional, students can provide their own)
   ```

4. Initialize the database
   ```bash
   uv run python scripts/init_db.py
   ```

5. Run the server
   ```bash
   uv run uvicorn app.main:app --reload
   ```

6. Open your browser
   ```
   http://localhost:8000
   ```

## Usage

### Student Workflow

1. **Register**: Create a student profile with name, email, and exam type (JEE/SAT/GRE)
2. **Upload Documents**: Upload your own study material (PDFs) to the knowledge base
3. **Chat**: Ask questions and get explanations retrieved from your uploaded content
4. **Take Quizzes**: Generate adaptive quizzes based on your uploaded documents
5. **Track Progress**: View detailed progress reports showing weak/strong topics
6. **Generate Study Plans**: Get personalized study schedules (7-365 days)

### Example Interactions

**Question & Answer:**
```
Student: "I don't understand conditional probability"
Tutor: [Retrieves relevant content from uploaded PDFs]
      [Generates explanation with examples]
      [Offers practice quiz on the topic]
```

**Adaptive Quiz:**
```
Student: "Give me a quiz on AI Agents"
Tutor: [Checks student progress on "AI Agents"]
      [Selects appropriate difficulty: easy (<50% accuracy), medium (50-80%), hard (>80%)]
      [Generates questions using content from uploaded PDF]
      [Provides detailed explanations for each answer]
      [Updates progress tracking]
```

**Progress Report:**
```
Student: "Show my progress"
Tutor: [Analyzes all quiz attempts]
      [Identifies weak topics: AI Agents (45% accuracy)]
      [Identifies strong topics: Machine Learning (85% accuracy)]
      [Recommends: "Focus on AI Agents fundamentals"]
```

**Study Plan:**
```
Student: "Create a 30-day study plan"
Tutor: [Analyzes weak areas from progress data]
      [Prioritizes topics by urgency and difficulty]
      [Creates daily schedule with hour allocations]
      [Sets milestones at 25%, 50%, 75%, 100%]
```

## API Documentation

### Student Management

**Register Student**
```http
POST /api/students/register
Content-Type: application/json

{
  "name": "John Doe",
  "email": "john@example.com",
  "exam_type": "JEE",
  "api_key_gemini": "optional_personal_key"
}
```

**Start Session**
```http
POST /api/sessions/start
Content-Type: application/json

{
  "student_id": "student-uuid"
}
```

### Document Upload

**Upload PDF**
```http
POST /api/documents/upload
Content-Type: multipart/form-data

student_id: student-uuid
file: document.pdf
```

### Learning Interactions

**Chat (Orchestrator)**
```http
POST /api/chat
Content-Type: application/json

{
  "student_id": "student-uuid",
  "session_id": "session-uuid",
  "message": "Explain conditional probability"
}
```

**Generate Quiz**
```http
POST /api/quiz/generate
Content-Type: application/json

{
  "student_id": "student-uuid",
  "topic": "AI Agents",
  "num_questions": 5,
  "difficulty": "medium"  // optional, auto-selected if not provided
}
```

**Submit Quiz**
```http
POST /api/quiz/submit
Content-Type: application/json

{
  "student_id": "student-uuid",
  "quiz_id": "quiz-uuid",
  "answers": [0, 2, 1, 3, 0]  // selected option indices
}
```

**Get Progress Report**
```http
GET /api/feedback/{student_id}?report_type=student
```

**Generate Study Plan**
```http
POST /api/plan/generate
Content-Type: application/json

{
  "student_id": "student-uuid",
  "timeline_days": 30,
  "focus_topics": ["Probability", "Calculus"]  // optional
}
```

## Project Structure

```
Agentic_AI_Tutor/
├── app/
│   ├── agents/              # Agent implementations
│   │   ├── base_agent.py    # Abstract base class with RAG integration
│   │   ├── orchestrator.py  # Intent classification and routing
│   │   ├── planner_agent.py # Study plan generation
│   │   ├── quiz_agent.py    # Adaptive quiz generation
│   │   └── feedback_agent.py # Progress analysis
│   ├── api/                 # FastAPI routes
│   │   ├── routes/
│   │   │   ├── students.py  # Student registration
│   │   │   ├── sessions.py  # Session management
│   │   │   ├── chat.py      # Main orchestrator endpoint
│   │   │   ├── quiz.py      # Quiz generation and grading
│   │   │   ├── feedback.py  # Progress reports
│   │   │   ├── plan.py      # Study plans
│   │   │   └── documents.py # PDF upload and processing
│   │   └── dependencies.py  # Shared dependencies
│   ├── core/                # Core configuration
│   │   ├── config.py        # YAML configuration loader
│   │   └── database.py      # SQLite setup
│   ├── models/              # Database models
│   │   ├── student.py       # Student with encrypted API keys
│   │   ├── session.py       # Session and Message models
│   │   └── progress.py      # Performance tracking
│   ├── schemas/             # Pydantic request/response schemas
│   │   ├── common.py
│   │   ├── quiz.py
│   │   ├── plan.py
│   │   └── feedback.py
│   ├── services/            # Business logic
│   │   ├── llm_service.py       # Gemini/OpenAI wrapper
│   │   ├── embedding_service.py # Sentence Transformers
│   │   └── rag_service.py       # Document processing and retrieval
│   └── main.py              # FastAPI application
├── frontend/                # Web interface
│   ├── index.html           # Main UI with tabbed interface
│   ├── style.css            # Styling
│   └── app.js               # API client and interaction logic
├── scripts/                 # Utility scripts
│   ├── init_db.py           # Database initialization
│   └── test_*.py            # Agent and service tests
├── docs/                    # Documentation
│   ├── ARCHITECTURE.md      # System architecture
│   ├── PROJECT_PLAN.md      # 3-day implementation plan
│   └── Problem Statement.pdf # Original requirements
├── data/                    # SQLite database
├── logs/                    # Application logs
├── config.yaml              # YAML configuration
├── pyproject.toml           # Dependencies and build config
└── .env                     # Environment variables (not in git)
```

## Configuration

All non-sensitive settings are in `config.yaml`:

- **LLM Settings**: Temperature, max tokens, model selection
- **RAG Parameters**: Chunk size (500), overlap (50), top_k (5)
- **Quiz Thresholds**: Easy (<50%), medium (50-80%), hard (>80%)
- **Progress Tracking**: Weak (<60%), average (60-80%), strong (>80%), mastery (>85%)
- **Agent-Specific Settings**: Per-agent configuration

Sensitive data goes in `.env`:
- `PINECONE_API_KEY`: Your Pinecone API key (required)
- `DEFAULT_GEMINI_API_KEY`: Default Gemini key (optional, students can provide their own)
- `SECRET_KEY`: Encryption key for student API keys

## Database Schema

**Students**: UUID-based profiles with encrypted API keys, weak/strong areas (JSON)

**Sessions**: Stateful conversations with agent workflow tracking (JSON)

**Messages**: Chat history with role (user/assistant) and metadata

**Progress**: Topic-level performance tracking with accuracy, attempts, strength level, mastery status

## Adaptive Learning Logic

The system automatically adjusts difficulty based on real-time performance:

1. **Initial Assessment**: Starts with medium difficulty
2. **Accuracy Tracking**: Records correct/incorrect answers per topic
3. **Difficulty Selection**:
   - Accuracy < 50% → Easy questions
   - Accuracy 50-80% → Medium questions
   - Accuracy > 80% → Hard questions
4. **Strength Classification**:
   - Weak: <60% accuracy (prioritized in study plans)
   - Average: 60-80% accuracy
   - Strong: >80% accuracy
   - Mastery: >85% accuracy with recent practice
5. **Study Plan Adaptation**: Prioritizes weak areas, allocates more hours to challenging topics

## Evaluation Metrics

Based on the problem statement requirements:

- **Adaptiveness**: Percentage of recommendations aligned with student weak areas
- **Learning Gain**: Pre-test vs post-test improvement on topic accuracy
- **Engagement**: Average session length and retention across sessions
- **Explainability**: Clarity of AI-generated justifications for recommendations

## Development and Testing

### Run Tests
```bash
# Test individual agents
uv run python scripts/test_planner.py
uv run python scripts/test_quiz.py
uv run python scripts/test_feedback.py
uv run python scripts/test_orchestrator.py

# Test services
uv run python scripts/test_services.py
```

### Access API Documentation
```
http://localhost:8000/docs  # Swagger UI
http://localhost:8000/redoc # ReDoc
```

## Known Limitations

- Currently uses SQLite (suitable for single-user/demo, migrate to PostgreSQL for production)
- Session state stored in JSON (works well for current scale)
- No user authentication (uses student_id directly)
- Basic frontend (functional but minimal styling)

## Future Enhancements

- User authentication with JWT tokens
- PostgreSQL migration for production
- Real-time progress charts and analytics dashboard
- Email notifications for study reminders
- Export progress reports as PDF
- Mobile-responsive frontend
- Multi-language support
- Spaced repetition algorithm integration

## License

MIT License

## Acknowledgments

Built as a proof-of-concept for agentic AI in adaptive learning, addressing the problem of one-size-fits-all e-learning platforms. The system demonstrates how autonomous AI agents can provide personalized instruction by reasoning about student progress, planning learning paths, and coordinating specialized capabilities.

## Authors

Aditya Sarade - Initial implementation and research

---

**Status**: Fully Functional MVP (A 3 Day (Night) Run)
