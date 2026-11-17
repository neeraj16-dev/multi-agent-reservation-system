from langchain_core.messages import SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.runnables import RunnableConfig
from langgraph.store.base import BaseStore

from hotel_assistant.state import AgentState
from hotel_assistant.tools.room_tools import book_room, get_room_reservations, cancel_room

llm = ChatGoogleGenerativeAI(model="gemini-3.5-flash-lite")
room_tools = [book_room, get_room_reservations, cancel_room]
room_agent_llm = llm.bind_tools(room_tools)

def room_agent_node(state: AgentState, config: RunnableConfig, store: BaseStore):
    """Handles hotel accommodation requests."""
    user_id = config["configurable"]["user_id"]
    namespace = ("users", str(user_id))
    
    # Retrieve LTM from the injected store
    existing_memory = store.get(namespace, "preferences")
    preferences = existing_memory.value if existing_memory else {}
    summary = state.get("summary", "")

    system_prompt = (
        "You are the Hotel Accommodation Specialist. "
        "Help the user book, check, or cancel room reservations. "
        "Always check available context before asking the user for details.\n\n"
    )
    
    if summary:
        system_prompt += f"Conversation Summary:\n{summary}\n\n"
    if preferences:
        system_prompt += f"Saved User Preferences (apply these when booking):\n{preferences}\n"

    response = room_agent_llm.invoke([SystemMessage(content=system_prompt)] + state["messages"])
    
    return {"messages": [response]}