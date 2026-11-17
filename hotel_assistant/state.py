from typing import Annotated, Sequence, TypedDict, Optional
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    # add_messages ensures new messages are appended, not overwritten
    messages: Annotated[Sequence[BaseMessage], add_messages]
    
    # Tracks active agent: "supervisor", "room_agent", "dining_agent"
    current_agent: str
    
    # Short-term memory summary for long context management
    summary: str

    # Tracks HITL approval decision for destructive actions
    approved: Optional[bool]

    # Security Guardrail flags
    blocked: Optional[bool]
    security_reason: Optional[str]

# This maps to the config["configurable"] payload passed from your FastAPI/Next.js backend
class UserContext(TypedDict):
    user_id: str
    role: str  # e.g., "guest", "admin"