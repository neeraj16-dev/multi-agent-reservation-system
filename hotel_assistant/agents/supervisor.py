from typing import Literal
from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from hotel_assistant.state import AgentState

class RouterDecision(BaseModel):
    next_agent: Literal["room_agent", "dining_agent", "FINISH"] = Field(
        description="The agent to route to. Use FINISH for general greetings or when a task is completed."
    )

llm = ChatGoogleGenerativeAI(model="gemini-3.5-flash-lite")
supervisor_llm = llm.with_structured_output(RouterDecision)

def supervisor_node(state: AgentState):
    """Analyzes the conversation and sets the current_agent in the state."""
    
    # Find out who was handling the conversation last
    current = state.get("current_agent", "None")
    
    system_prompt = SystemMessage(content=(
        "You are the routing supervisor for a luxury hotel AI assistant. "
        f"The active agent currently handling the conversation is: {current}.\n\n"
        "Analyze the user's latest input and route to the correct specialist:\n"
        "- 'room_agent': User wants to book, check, or cancel a hotel room/accommodation.\n"
        "- 'dining_agent': User wants to book, check, or cancel a restaurant table/dining.\n"
        "- 'FINISH': User is just saying hello/thanks, or the task is already fully complete.\n\n"
        "CRITICAL: If the user is simply answering a follow-up question (like providing a date, time, or name) "
        f"route them back to the active agent ({current}). Only change agents if they explicitly change the topic."
    ))
    
    # We only need the last few messages to determine intent
    messages_to_analyze = [system_prompt] + state["messages"][-3:]
    
    decision = supervisor_llm.invoke(messages_to_analyze)
    
    return {"current_agent": decision.next_agent}