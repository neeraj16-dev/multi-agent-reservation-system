from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.messages import HumanMessage, SystemMessage, RemoveMessage
from langchain_core.prompts import PromptTemplate
from langchain_core.messages import BaseMessage
from langchain_core.output_parsers import StrOutputParser

from typing import TypedDict, Annotated

from reservation_agent.state import AgentState

KEEP_OLD_MESSAGES = 4

llm = ChatGoogleGenerativeAI(model="gemini-3.1-flash-lite")

def summarizer(state: AgentState):
    parser = StrOutputParser()

    previous_summary = state.get("summary", "")
    messages = state["messages"]

    old_messages = messages[:-KEEP_OLD_MESSAGES]

    def extract_text(msg):
        if isinstance(msg.content, str):
            return msg.content
        elif isinstance(msg.content, list):
            # FIX: If the list is empty, it's a tool call!
            if len(msg.content) == 0:
                return "[Tool Call]"
            # If it has items, safely grab the text
            return msg.content[0].get("text", str(msg.content))
        
        return str(msg.content)

    conversation = "\n".join(
        f"{message.type}: {extract_text(message)}" for message in old_messages
    )

    prompt = PromptTemplate.from_template(f"""
        Summarize the following conversation.

        Previous summary:
        {previous_summary}

        Recent conversation:
        {conversation}

        Preserve important information such as:
        - User preferences
        - Reservation details
        - Decisions made
        - Relevant context for future interactions

        Do not invent information.
    """)

    chain = prompt | llm | parser

    response = chain.invoke({
        "previous_summary": previous_summary,
        "conversation": conversation
    })

    delete_messages = [
        RemoveMessage(id=message.id) for message in old_messages
    ]

    return {
        "summary": response,
        "messages": delete_messages
    }
    

