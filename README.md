# 🏨 AI-Powered Real-Time Hotel Concierge

An ultra-low latency, real-time voice AI assistant for hospitality, built with the **Gemini Multimodal Live API**, **FastAPI WebSockets**, and **LangGraph**.

This system moves beyond traditional turn-based chatbots by maintaining a continuous, bidirectional audio stream. It uses a **Hierarchical Multi-Agent (Supervisor)** architecture to seamlessly handle context switching between hotel room bookings and dining reservations, executing secure transactions against a PostgreSQL database.

## ✨ Key Features

- **Real-Time Voice Streaming:** Bidirectional WebSocket integration with `gemini-3.8-live` (`v1beta` endpoint) for instant voice-to-voice interaction.
- **Multi-Agent Supervisor Routing:** A central LangGraph Supervisor intelligently routes conversational state between specialized worker agents (Room Agent & Dining Agent) based on user intent.
- **Decoupled Tool Execution (Security):** The LLM has zero direct database access. It emits JSON tool proposals (`book_room`, `cancel_table`) which are intercepted, validated, and executed natively by the FastAPI backend.
- **Audio Queueing Engine:** Custom React Web Audio API implementation that converts browser `Float32` audio to Gemini's required `Int16 PCM`, featuring a time-based scheduling queue to eliminate audio overlap ("gibberish").
- **Human-in-the-Loop (HITL):** High-risk actions (like reservation cancellations) trigger LangGraph state interrupts, physically pausing the execution graph until manual terminal approval is received.
- **Long-Term Memory (LTM):** Uses LangGraph's `PostgresStore` to extract and inject user preferences (e.g., "prefers a King bed") across multiple sessions.
- **Prompt Injection Defense:** Protected by strict behavioral system boundaries and native Google GenAI safety threshold guardrails.

## 🛠 Tech Stack

- **AI & Orchestration:** Google GenAI SDK (`v1beta`), LangGraph, LangChain
- **Backend:** FastAPI, Python, Uvicorn, WebSockets
- **Frontend:** React.js, Vite, Web Audio API
- **Database & State:** PostgreSQL (`psycopg_pool`)

## 🏗 System Architecture

1. **Client (React):** Captures microphone audio, down-samples to 16kHz Int16 PCM, and streams over WebSockets.
2. **Gateway (FastAPI):** Proxies audio to Google's Live API and intercepts `ToolCall` events.
3. **Orchestration (LangGraph):** Manages conversational state, Long-Term Memory, and routes the user to the correct domain agent.
4. **Execution (Postgres):** FastAPI safely runs the decoupled database queries and returns the `reservation_id` to Gemini for voice confirmation.

---

## 🚀 Local Setup & Installation

### Prerequisites

- Python 3.10+
- Node.js & npm
- PostgreSQL installed and running locally
- Google Gemini API Key

### 1. Database Setup

Create a PostgreSQL database named `hotel_db` and run your schema creation scripts to set up the `reservations` and `dining` tables.

### 2. Backend Setup

Navigate to the project root and install the Python dependencies:

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux / macOS
source .venv/bin/activate

pip install fastapi uvicorn websockets google-genai langgraph psycopg_pool
```

Create a `.env` file in the root directory:

```ini
GEMINI_API_KEY="your_google_api_key_here"
DATABASE_URL="postgresql://postgres:password123@localhost:5432/hotel_db"
```

Start the FastAPI server:

```bash
python -m uvicorn backend.main:app --reload --port 8000
```

### 3. Frontend Setup

Open a new terminal, navigate to the frontend directory, and install dependencies:

```bash
cd frontend
npm install
```

Start the Vite development server:

```bash
npm run dev
```

## 🎙️ Usage

1. Open `http://localhost:5173` in your browser.
2. Click **Start Voice Conversation** and grant microphone permissions.
3. Try speaking these scenarios naturally:

   - *"Hi, I'd like to book a room for this weekend for two people. I need a King bed."* (Tests Room Agent & LTM)
   - *"Actually, can you also book a dinner table for tonight at 8 PM?"* (Tests Supervisor Context Switch)
   - *"Cancel that dinner table."* (Tests HITL terminal interrupt in the backend)

## 🔒 Roadmap / Future Enhancements

- [ ] Implement JWT Authentication on the WebSocket connection.
- [ ] Add Role-Based Access Control (RBAC) to restrict cancellations to Admin users.
- [ ] Build an Admin Dashboard for managing HITL approvals visually.

---

**Designed and built by Neeraj Mayekar.**
