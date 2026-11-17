from langgraph.types import interrupt
from hotel_assistant.state import AgentState

def approval_node(state: AgentState):
    """Interrupts the graph if a destructive action (cancellation) is called."""
    last_message = state["messages"][-1]
    tool_calls = getattr(last_message, "tool_calls", [])

    if not tool_calls:
        return {}

    # Look for ANY cancellation call (room or table)
    cancellation = next(
        (call for call in tool_calls if call["name"] in ["cancel_table", "cancel_room"]),
        None
    )

    if not cancellation:
        return {}

    reservation_id = cancellation["args"]["reservation_id"]
    domain = "hotel room" if cancellation["name"] == "cancel_room" else "dining table"

    # Pause the graph and ask for approval
    decision = interrupt({
        "message": f"Do you approve the cancellation of this {domain}?",
        "reservation_id": reservation_id,
        "tool_name": cancellation["name"]
    })

    return {"approved": decision}