from langgraph.types import interrupt
from reservation_agent.state import AgentState

def approval_node(state: AgentState):
    last_message = state["messages"][-1]

    tool_calls = getattr(last_message, "tool_calls", [])

    if not tool_calls:
        return {}

    cancellation = next(
        (
            call for call in tool_calls if call["name"] == "cancel_reservation"
        ),
        None
    )

    if not cancellation:
        return {}

    reservation_id = cancellation["args"]["reservation_id"]

    decision = interrupt({
        "message": "Do you approve this cancellation?",
        "reservation_id": reservation_id
    })

    return {
        "approved": decision
    }

