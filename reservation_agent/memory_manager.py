from reservation_agent.state import AgentState
from reservation_agent.memory_schema import MemoryExtraction

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig

from langgraph.store.base import BaseStore

import time

llm = ChatGoogleGenerativeAI(model="gemini-3.5-flash-lite", max_retries=1)
memory_llm = llm.with_structured_output(MemoryExtraction)

MAX_TOKENS = 2000

def check_memory(state: AgentState):
    messages = state['messages']

    token_count = llm.get_num_tokens_from_messages(messages)

    print(f"Current conversation tokens: {token_count}")

    return {
        "needs_summary": token_count > MAX_TOKENS
    }

def route_memory(state: AgentState):
    if state["needs_summary"]:
        return "summarize"

    return "continue"

def update_ltm(state: AgentState, config: RunnableConfig, store: BaseStore):
    print("\n[DEBUG] 🧠 Routing to LTM Node. Analyzing conversation for preferences...")

    print("Pausing for 4 seconds to clear API rate limits...")
    time.sleep(4)

    # 1. Grab user_id and namespace from the modern config
    user_id = config["configurable"]["user_id"]
    namespace = ("users", str(user_id))

    # 2. Retrieve existing preferences directly from the injected store
    existing_memory = store.get(namespace, "preferences")
    current_preferences = existing_memory.value if existing_memory else {}

    # 3. CRITICAL FIX: Safely format messages to avoid the Gemini List/String crash!
    def extract_text(msg):
        if isinstance(msg.content, str):
            return msg.content
        elif isinstance(msg.content, list):
            if len(msg.content) == 0:
                return "[Tool Call/Result]"
            return msg.content[0].get("text", str(msg.content))
        return str(msg.content)

    # We only need to check the last few messages for new preferences (saves tokens!)
    recent_messages = state['messages'][-4:] 
    conversation_text = "\n".join(f"{msg.type}: {extract_text(msg)}" for msg in recent_messages)

    prompt = f"""
    Extract stable, long-term user preferences from this recent conversation.

    Current saved preferences:
    {current_preferences}

    Recent Conversation:
    {conversation_text}

    Rules:
    1. Extract only explicitly expressed long-term preferences (allergies, seating, favorite foods).
    2. Do not treat temporary reservation details (like tomorrow's date or a specific time) as preferences.
    3. If the user explicitly changes an existing preference, extract the new value.
    4. Do not infer preferences.
    5. If no useful preference is expressed, set should_update=False.
    """

    # 4. Extract data using the structured LLM
    print("\nInvoking LLM\n")
    extracted = memory_llm.invoke(prompt)
    print("\nLLM finished")

    if not extracted.should_update:
        return {}

    # 5. Merge new preferences with existing ones
    updated_preferences = current_preferences.copy()
    
    # Exclude None values so we don't overwrite existing preferences with empty data
    new_preferences = extracted.preferences.model_dump(exclude_none=True)
    updated_preferences.update(new_preferences)

    # 6. Save back to the Long-Term Store
    store.put(
        namespace,
        "preferences",
        updated_preferences
    )

    print(f"\n[LTM UPDATED] User {user_id} new preferences saved: {updated_preferences}")

    # We don't return anything to the state here, we just silently update the store
    return {}