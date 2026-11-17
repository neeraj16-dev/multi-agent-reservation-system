from reservation_agent.agent import graph, store

# ==========================================
# 1. SEED THE LONG-TERM MEMORY (STORE)
# ==========================================
store.put(
    ("users", "101"),
    "preferences",
    {
        "name": "Neeraj",
        "preferred_seating": "window",
        "preferred_party_size": 4
    }
)

print("\n" + "=" * 50)
print("TEST CASE 1: USER 101 (Should remember preferences)")
print("=" * 50)

# --- FIX: Add user_id directly to the configurable dictionary ---
config_101 = {
    "configurable": {
        "thread_id": "customer_101_new",
        "user_id": 101  
    }
}

# Notice we don't even need the context= UserContext() anymore!
result_101 = graph.invoke(
    {
        "messages": [
            ("human", "I'd like to book a restaurant for tomorrow. Do you know my usual preferences?")
        ]
    },
    config=config_101 
)

ai_content_101 = result_101["messages"][-1].content
text_101 = ai_content_101 if isinstance(ai_content_101, str) else ai_content_101[0]["text"]
print(f"AI: {text_101}\n")


print("\n" + "=" * 50)
print("TEST CASE 2: USER 102 (Should NOT know User 101's preferences)")
print("=" * 50)

# --- FIX: Add user_id 102 here ---
config_102 = {
    "configurable": {
        "thread_id": "customer_102_new",
        "user_id": 102
    }
}

result_102 = graph.invoke(
    {
        "messages": [
            ("human", "I'd like to book a restaurant for tomorrow. Do you know my usual preferences?")
        ]
    },
    config=config_102
)

ai_content_102 = result_102["messages"][-1].content
text_102 = ai_content_102 if isinstance(ai_content_102, str) else ai_content_102[0]["text"]
print(f"AI: {text_102}\n")