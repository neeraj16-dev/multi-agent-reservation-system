from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import RemoveMessage
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

from hotel_assistant.state import AgentState

KEEP_OLD_MESSAGES = 4
MAX_TOKENS = 2000

llm = ChatGoogleGenerativeAI(model="gemini-3.5-flash-lite")

def check_memory(state: AgentState):
    """Checks if the conversation exceeds the token limit."""
    messages = state['messages']
    token_count = llm.get_num_tokens_from_messages(messages)
    print(f"[STM] Current conversation tokens: {token_count}")
    
    # We return needs_summary but do not mutate state directly here
    return {"needs_summary": token_count > MAX_TOKENS}

def route_memory(state: dict) -> str:
    """Conditional edge router for token management."""
    # Note: route_memory takes a dict containing needs_summary from check_memory
    if state.get("needs_summary", False):
        return "summarize"
    return "continue"

def summarizer(state: AgentState):
    """Summarizes old messages and trims the state history."""
    parser = StrOutputParser()
    previous_summary = state.get("summary", "")
    messages = state["messages"]

    # Grab the oldest messages that we will summarize and delete
    old_messages = messages[:-KEEP_OLD_MESSAGES]

    def extract_text(msg):
        if isinstance(msg.content, str):
            return msg.content
        elif isinstance(msg.content, list):
            if len(msg.content) == 0:
                return "[Tool Call]"
            return msg.content[0].get("text", str(msg.content))
        return str(msg.content)

    conversation = "\n".join(
        f"{message.type}: {extract_text(message)}" for message in old_messages
    )

    prompt = PromptTemplate.from_template(f"""
        Summarize the following conversation for a hotel assistant.

        Previous summary:
        {previous_summary}

        Recent conversation:
        {conversation}

        Preserve important information such as:
        - User preferences
        - Active reservations (rooms and dining)
        - Decisions made
        - Relevant context for future interactions

        Do not invent information.
    """)

    chain = prompt | llm | parser
    response = chain.invoke({
        "previous_summary": previous_summary,
        "conversation": conversation
    })

    delete_messages = [RemoveMessage(id=message.id) for message in old_messages]

    return {
        "summary": response,
        "messages": delete_messages
    }