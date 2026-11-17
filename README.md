# Multi-Agent Hotel Reservation System (LangGraph)

An intelligent, multi-agent hotel management system built with LangGraph and Google Gemini. This system handles both room accommodations and dining reservations using specialized sub-agents, backed by a robust dual-memory architecture and Postgres for persistent state.

## 🎯 Phase 1 Strategy
- **Core Focus:** Build and debug the state graph, multi-agent routing, and Pydantic schemas using **text-based models** first.
- **Deferred:** Real-time voice APIs (e.g., Gemini Multimodal Live API) and UI development will be integrated only after the core state machine is bulletproof.
- **Decoupled Architecture:** The LangGraph "brain" remains completely isolated from HTTP requests and authentication headers.

## 🧠 Multi-Agent Architecture
The system utilizes a hierarchical agent structure to route intents and manage domain-specific tools:

1. **Supervisor Agent (Router):** Analyzes initial user intent and routes the conversation to the appropriate specialized sub-agent. Does not execute tools directly.
2. **Room Agent:** Manages accommodation requests. Bound to tools: `check_room_availability`, `book_room`, `cancel_room`, `get_room_details`.
3. **Dining Agent:** Manages restaurant and table reservations. Bound to tools: `check_table_availability`, `book_table`, `cancel_table`.
4. **Concierge Agent (Future):** A RAG-powered agent to deflect general FAQ queries (pool hours, pet policies) to save tool-calling costs on transactional agents.

## 💾 State & Memory Management
The system tracks conversations and user preferences using a dual-memory approach, migrating from local in-memory storage to production-ready PostgreSQL.

- **Short-Term Memory (STM):** Uses `langgraph-checkpoint-postgres` (`PostgresSaver`) to persist the conversational state and message history. The `AgentState` schema tracks the `current_agent` to ensure multi-turn follow-ups bypass the supervisor. 
- **Long-Term Memory (LTM):** Uses a Postgres-backed `BaseStore` to secretly extract and persist explicit user preferences (e.g., bed sizes, dietary restrictions, preferred dining times) across multiple sessions.
- **Human-in-the-Loop (HITL):** Destructive actions (like `cancel_room` or `cancel_table`) trigger an `interrupt()`, pausing the graph execution until explicit user/admin approval is provided.

## 🔐 Authentication & Access Control
- JWT authentication and role-based access control (RBAC) are handled entirely at the API layer (FastAPI/Next.js).
- LangGraph remains agnostic to tokens. The backend decodes the JWT and passes the `user_id` and `role` (e.g., "guest" vs. "admin") into the graph via LangGraph's `RunnableConfig`.
- Tools check `config["configurable"]["role"]` to authorize specific administrative actions.

## 📁 Directory Structure
```text
multi-agent-reservation-system/
├── frontend/                   # Next.js frontend (Admin dashboard & User UI)
├── backend/                    # FastAPI/Django backend (JWT Auth & API layer)
├── hotel_assistant/            # LangGraph Multi-Agent Service (Formerly reservation_agent)
│   ├── .env
│   ├── requirements.txt
│   ├── main.py                 # CLI entry point for local graph testing
│   ├── state.py                # Defines AgentState (tracks 'current_agent' & 'messages')
│   ├── graph.py                # Main graph builder, PostgresSaver checkpointer, and routing
│   ├── __init__.py
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── supervisor.py       # Analyzes intent and routes to sub-agents
│   │   ├── room_agent.py       # Handles accommodation logic and prompts
│   │   └── dining_agent.py     # Handles restaurant/table logic and prompts
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── room_tools.py       # check_rooms, book_room, cancel_room
│   │   ├── dining_tools.py     # check_tables, book_table, cancel_table
│   │   └── hitl_logic.py       # Human-in-the-loop interrupt nodes for cancellations
│   ├── memory/
│   │   ├── __init__.py
│   │   ├── ltm_manager.py      # BaseStore extraction, update_ltm node
│   │   ├── stm_summarizer.py   # Token trimming and summarization nodes
│   │   └── schemas.py          # Pydantic models (UserPreferences, ExtractionSchemas)
│   ├── db/
│   │   ├── __init__.py
│   │   ├── config.py           # Postgres connection pooling (psycopg/asyncpg)
│   │   ├── room_queries.py     # Business data CRUD operations for rooms
│   │   └── dining_queries.py   # Business data CRUD operations for tables
│   └── tests/
│       ├── test_supervisor.py
│       ├── test_room_agent.py
│       ├── test_dining_agent.py
│       └── test_memory.py
├── .gitignore
└── README.md