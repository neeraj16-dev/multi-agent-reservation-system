from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import ToolMessage, AIMessage
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.store.postgres import PostgresStore

from hotel_assistant.state import AgentState, UserContext
from hotel_assistant.db.config import get_pool
from hotel_assistant.security import input_guardrail, output_guardrail

# Import Nodes
from hotel_assistant.memory.stm_summarizer import check_memory, summarizer
from hotel_assistant.memory.ltm_manager import update_ltm
from hotel_assistant.agents.supervisor import supervisor_node
from hotel_assistant.agents.room_agent import room_agent_node
from hotel_assistant.agents.dining_agent import dining_agent_node
from hotel_assistant.tools.hitl_logic import approval_node

# Import Tools
from hotel_assistant.tools.room_tools import book_room, get_room_reservations, cancel_room
from hotel_assistant.tools.dining_tools import book_table, get_dining_reservations, update_table_reservation, cancel_table

# Combine all tools for the executor node
all_tools = [
    book_room, get_room_reservations, cancel_room, 
    book_table, get_dining_reservations, update_table_reservation, cancel_table
]
tool_node = ToolNode(all_tools)


# --- SECURITY GUARDRAIL NODES ---

def input_guardrail_node(state: AgentState):
    """Screens the incoming user message for prompt injection, jailbreaks, and leaks."""
    messages = state.get("messages", [])
    if not messages:
        return {"blocked": False}

    last_msg = messages[-1]
    text = ""
    if hasattr(last_msg, "content"):
        if isinstance(last_msg.content, str):
            text = last_msg.content
        elif isinstance(last_msg.content, list) and len(last_msg.content) > 0:
            text = last_msg.content[0].get("text", "")

    result = input_guardrail.validate(text)
    if not result.is_safe:
        warning_msg = (
            "I cannot fulfill this request. I am only authorized to assist with "
            "hotel room accommodations and restaurant dining reservations."
        )
        return {
            "messages": [AIMessage(content=warning_msg)],
            "blocked": True,
            "security_reason": result.reason
        }

    return {"blocked": False}

def route_after_input_guardrail(state: AgentState):
    """If blocked by security guardrails, terminate immediately."""
    if state.get("blocked"):
        return END
    return "check_memory"

def output_guardrail_node(state: AgentState):
    """Screens assistant output to prevent system prompt leakage or data exfiltration."""
    messages = state.get("messages", [])
    if not messages:
        return {}

    last_msg = messages[-1]
    if hasattr(last_msg, "content") and isinstance(last_msg.content, str):
        screen_res = output_guardrail.screen_text(last_msg.content)
        if not screen_res.is_safe:
            last_msg.content = screen_res.sanitized_text
            return {"messages": [last_msg], "security_reason": screen_res.reason}

    return {}


# --- ROUTING LOGIC ---

def route_after_memory(state: AgentState):
    """Checks if we need to summarize first, otherwise routes straight to Supervisor."""
    if state.get("needs_summary"):
        return "summarizer"
    return "supervisor"

def route_agent_output(state: AgentState):
    """Checks if the agent invoked a tool, requires HITL approval, or is done."""
    last_message = state["messages"][-1]
    tool_calls = getattr(last_message, "tool_calls", [])
    
    if not tool_calls:
        # No tools called -> agent has responded to the user. Screen output before LTM update.
        return "output_guardrail"
    
    if any(call["name"] in ["cancel_room", "cancel_table"] for call in tool_calls):
        return "approval"
    
    return "tools"

def route_after_approval(state: AgentState):
    """Routes based on the HITL interrupt decision."""
    if state.get("approved"):
        return "tools"
    return "reject_action"

def reject_action_node(state: AgentState):
    """Generates a mock ToolMessage so the LLM knows the user blocked the action."""
    last_message = state["messages"][-1]
    tool_calls = getattr(last_message, "tool_calls", [])
    cancellation_call = next(call for call in tool_calls if call["name"] in ["cancel_room", "cancel_table"])
    
    return {
        "messages": [ToolMessage(tool_call_id=cancellation_call["id"], content="Action blocked: The user or admin rejected the cancellation.")]
    }

def route_after_tools(state: AgentState):
    """Returns the tool output back to whoever called it."""
    return state.get("current_agent", "supervisor")


# --- GRAPH CONSTRUCTION ---

def build_graph():
    builder = StateGraph(AgentState, context_schema=UserContext)
    
    # 1. Add Nodes
    builder.add_node("input_guardrail", input_guardrail_node)
    builder.add_node("output_guardrail", output_guardrail_node)
    builder.add_node("check_memory", check_memory)
    builder.add_node("summarizer", summarizer)
    builder.add_node("supervisor", supervisor_node)
    builder.add_node("room_agent", room_agent_node)
    builder.add_node("dining_agent", dining_agent_node)
    builder.add_node("tools", tool_node)
    builder.add_node("approval", approval_node)
    builder.add_node("reject_action", reject_action_node)
    builder.add_node("update_ltm", update_ltm)
    
    # 2. Add Edges
    builder.add_edge(START, "input_guardrail")
    builder.add_conditional_edges(
        "input_guardrail",
        route_after_input_guardrail,
        {"check_memory": "check_memory", END: END}
    )
    
    # Check token limits, then proceed
    builder.add_conditional_edges(
        "check_memory", 
        route_after_memory, 
        {"summarizer": "summarizer", "supervisor": "supervisor"}
    )
    
    # Summarizer flows straight to the supervisor
    builder.add_edge("summarizer", "supervisor")
    
    # Supervisor evaluates intent and sets current_agent
    builder.add_conditional_edges(
        "supervisor",
        lambda s: s.get("current_agent"),
        {"room_agent": "room_agent", "dining_agent": "dining_agent", "FINISH": "output_guardrail"}
    )
    
    # Agents route to tools, approval, or output guardrail
    builder.add_conditional_edges("room_agent", route_agent_output, {"tools": "tools", "approval": "approval", "output_guardrail": "output_guardrail"})
    builder.add_conditional_edges("dining_agent", route_agent_output, {"tools": "tools", "approval": "approval", "output_guardrail": "output_guardrail"})
    
    # Approval conditional routing
    builder.add_conditional_edges("approval", route_after_approval, {"tools": "tools", "reject_action": "reject_action"})
    
    # Tools/Rejections flow back to the active agent to interpret the result
    builder.add_conditional_edges("tools", route_after_tools, {"room_agent": "room_agent", "dining_agent": "dining_agent", "supervisor": "supervisor"})
    builder.add_conditional_edges("reject_action", route_after_tools, {"room_agent": "room_agent", "dining_agent": "dining_agent", "supervisor": "supervisor"})
    
    # Output guardrail flows to LTM update then ends turn
    builder.add_edge("output_guardrail", "update_ltm")
    builder.add_edge("update_ltm", END)
    
    # 3. Compile with Postgres Persistence
    pool = get_pool()
    checkpointer = PostgresSaver(pool)
    checkpointer.setup()
    
    store = PostgresStore(pool)
    store.setup()
    
    return builder.compile(checkpointer=checkpointer, store=store)

# Export the compiled graph
graph = build_graph()