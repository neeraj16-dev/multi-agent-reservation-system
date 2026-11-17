from langchain_core.messages import SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.runnables import RunnableConfig
from langgraph.store.base import BaseStore

from hotel_assistant.state import AgentState
from hotel_assistant.tools.dining_tools import book_table, get_dining_reservations, update_table_reservation, cancel_table

llm = ChatGoogleGenerativeAI(model="gemini-3.5-flash-lite")
dining_tools = [book_table, get_dining_reservations, update_table_reservation, cancel_table]
dining_agent_llm = llm.bind_tools(dining_tools)

def dining_agent_node(state: AgentState, config: RunnableConfig, store: BaseStore):
    """Handles restaurant table requests."""
    user_id = config["configurable"]["user_id"]
    namespace = ("users", str(user_id))
    
    existing_memory = store.get(namespace, "preferences")
    preferences = existing_memory.value if existing_memory else {}
    summary = state.get("summary", "")

    system_prompt = (
        "You are the Hotel Dining Specialist. "
        "Help the user book, update, check, or cancel restaurant tables. "
        "Pay attention to dietary restrictions.\n\n"
    )
    
    if summary:
        system_prompt += f"Conversation Summary:\n{summary}\n\n"
    if preferences:
        system_prompt += f"Saved User Preferences (apply these when booking):\n{preferences}\n"

    response = dining_agent_llm.invoke([SystemMessage(content=system_prompt)] + state["messages"])
    
    return {"messages": [response]}