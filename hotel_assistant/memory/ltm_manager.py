import time
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.runnables import RunnableConfig
from langgraph.store.base import BaseStore

from hotel_assistant.state import AgentState
from hotel_assistant.memory.schemas import MemoryExtraction

llm = ChatGoogleGenerativeAI(model="gemini-3.5-flash-lite", max_retries=1)
memory_llm = llm.with_structured_output(MemoryExtraction)

def update_ltm(state: AgentState, config: RunnableConfig, store: BaseStore):
    print("\n[DEBUG] 🧠 Routing to LTM Node. Analyzing conversation for preferences...")
    print("Pausing for 4 seconds to clear API rate limits...")
    time.sleep(4)

    # 1. Grab user_id and namespace from the config
    user_id = config["configurable"]["user_id"]
    namespace = ("users", str(user_id))

    # 2. Retrieve existing preferences directly from the injected PostgresStore
    existing_memory = store.get(namespace, "preferences")
    current_preferences = existing_memory.value if existing_memory else {}

    # 3. Safely format messages to avoid the Gemini List/String crash
    def extract_text(msg):
        if isinstance(msg.content, str):
            return msg.content
        elif isinstance(msg.content, list):
            if len(msg.content) == 0:
                return "[Tool Call/Result]"
            return msg.content[0].get("text", str(msg.content))
        return str(msg.content)

    # We only need to check the last few messages for new preferences
    recent_messages = state['messages'][-4:] 
    conversation_text = "\n".join(f"{msg.type}: {extract_text(msg)}" for msg in recent_messages)

    prompt = f"""
    Extract stable, long-term user preferences from this recent conversation.

    Current saved preferences:
    {current_preferences}

    Recent Conversation:
    {conversation_text}

    Rules:
    1. Extract only explicitly expressed long-term preferences (allergies, seating, room types).
    2. Do not treat temporary reservation details (like tomorrow's date) as preferences.
    3. If the user explicitly changes an existing preference, extract the new value.
    4. Do not infer preferences.
    5. If no useful preference is expressed, set should_update=False.
    """

    # 4. Extract data using the structured LLM
    print("\nInvoking LLM for LTM extraction...\n")
    
    try:
        extracted = memory_llm.invoke(prompt)
        print("\nLLM finished")
    except Exception as e:
        print(f"\n[LTM WARNING] Background extraction skipped due to API error: {e}")
        return {}

    if not extracted.should_update:
        return {}

    # 5. Merge new preferences with existing ones
    updated_preferences = current_preferences.copy()
    new_preferences = extracted.preferences.model_dump(exclude_none=True)
    updated_preferences.update(new_preferences)

    # 6. Save back to the Long-Term Store
    store.put(namespace, "preferences", updated_preferences)
    print(f"\n[LTM UPDATED] User {user_id} new preferences saved: {updated_preferences}")

    return {}