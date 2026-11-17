from typing import TypedDict, Annotated

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.messages import SystemMessage, trim_messages, ToolMessage
from langchain_core.runnables import RunnableConfig

from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore
from langgraph.store.base import BaseStore

from reservation_agent.reservation_tools import (
    create_reservation,
    update_reservation,
    get_reservations,
    cancel_reservation
)

from reservation_agent.state import AgentState
from reservation_agent.summarizer import summarizer
from reservation_agent.memory_manager import route_memory, check_memory, update_ltm
from reservation_agent.approval import approval_node

from dataclasses import dataclass

@dataclass
class UserContext:
    user_id: int

tools = [
    create_reservation,
    update_reservation,
    get_reservations,
    cancel_reservation
]

llm = ChatGoogleGenerativeAI(model="gemini-3.5-flash-lite")
llm_with_tools = llm.bind_tools(tools)

def chatbot(state: AgentState, config: RunnableConfig, store: BaseStore):
    summary = state.get("summary", "")

    user_id = config["configurable"]["user_id"]
    namespace = ("users", str(user_id))

    memory = store.get(namespace, "preferences") if store else None
    preferences = memory.value if memory else {}

    print(f"\n[SYSTEM DETECTED LTM] User {user_id} Preferences: {preferences}")

    system_prompt = """
        You are a helpful reservation assistant.
        Help users create, view, update and cancel reservations.
    """

    if summary:
        system_prompt += f"""
            Previous Conversation Summary:
            {summary}

            Use this information when responding to the user.
        """

    if preferences:
        system_prompt += f"""

        User's saved preferences:
        {preferences}

        Consider these preferences when assisting the user.
        Do not assume a preference is mandatory if the user requests otherwise.
        """

    # --- THE FIX: Safely trim the message history ---
    # This guarantees tool calls and their results are never separated!
    safe_messages = trim_messages(
        state["messages"],
        max_tokens=2000,             # Keep this at your token limit
        token_counter=llm,          # Uses your Gemini instance to count
        strategy="last",            # Keep the most recent messages
        start_on="human",           # CRITICAL: Always starts history on a human message
        include_system=False,       # We are injecting our own SystemMessage below
        allow_partial=False
    )

    # Pass the SystemMessage + the safely trimmed messages to Gemini
    response = llm_with_tools.invoke(
        [SystemMessage(content=system_prompt)] + safe_messages    
    )

    return {
        "messages": [response]
    }

def route_tools(state: AgentState):
    last_message = state["messages"][-1]
    tool_calls = getattr(last_message, "tool_calls", [])

    if not tool_calls:
        return "end"

    if any(call["name"] == "cancel_reservation" for call in tool_calls):
        return "approval"

    return "tools"

def route_after_approval(state: AgentState):
    if state.get("approved"):
        return "execute"

    return "reject"

def reject_cancellation(state: AgentState):
    """If the user rejects the action, tell the LLM it was blocked."""
    last_message = state["messages"][-1]
    tool_calls = getattr(last_message, "tool_calls", [])
    
    # Find the ID of the tool call that was blocked
    cancellation_call = next(call for call in tool_calls if call["name"] == "cancel_reservation")
    
    # Send a ToolMessage back to the LLM so it doesn't crash waiting for a response
    return {
        "messages": [
            ToolMessage(
                tool_call_id=cancellation_call["id"], 
                content="Action blocked: The user rejected the cancellation."
            )
        ]
    }

tool_node = ToolNode(tools, handle_tool_errors=True)
checkpointer = InMemorySaver()
store = InMemoryStore()

builder = StateGraph(AgentState, context_schema=UserContext)

builder.add_node("chatbot", chatbot)
builder.add_node("tools", tool_node)
builder.add_node("summarizer", summarizer)
builder.add_node("check_memory", check_memory)
builder.add_node("update_ltm", update_ltm)
builder.add_node("approval", approval_node)
builder.add_node("reject_action", reject_cancellation)

builder.add_edge(START, "check_memory")
builder.add_conditional_edges(
    "check_memory",
    route_memory, 
    {
        "summarize": "summarizer",
        "continue": "chatbot"
    }
)
builder.add_edge("summarizer", "chatbot")
builder.add_conditional_edges(
    "chatbot",
    route_tools, 
    {
        "tools":"tools",
        "approval": "approval",
        "end": "update_ltm"
    }
)
builder.add_conditional_edges(
    "approval",
    route_after_approval,
    {
        "execute": "tools",       # If approved, run the tool
        "reject": "reject_action" # If rejected, send the rejection message
    }
)
builder.add_edge("tools", "chatbot")
builder.add_edge("reject_action", "chatbot")
builder.add_edge("update_ltm", END)

graph = builder.compile(
    checkpointer=checkpointer,
    store=store
)