from reservation_agent.agent import graph, UserContext

config = {
    "configurable": {
        "thread_id": "test_summary_user_99", # Changed thread_id for a fresh state
    }
}

context = UserContext(user_id=101)

# Generate a massive block of text (~1500 tokens) to instantly fill the agent's memory
token_bomb = "Also, I have a very long story about my dietary restrictions. " + ("I cannot eat peanuts, walnuts, or shellfish. " * 160)

# 1. Simulate the conversation
chat_script = [
    "Hi, my name is Neeraj.",
    "I'd like to make a reservation for 4 people tomorrow at 7:00 PM.",
    # This message pushes the memory over the 2000 limit
    token_bomb, 
    # This next message will trigger the memory check, route to the summarizer, 
    # generate the summary, clear the old memory, and THEN update the reservation!
    "Actually, can you change the time to 9:00 PM?",
    "Perfect, thank you!"
]

print("Starting conversation simulation...\n")

for user_input in chat_script:
    # Print a truncated version of the user input so it doesn't flood your terminal
    display_input = user_input if len(user_input) < 100 else user_input[:100] + "... [MASSIVE TEXT HIDDEN]"
    print(f"User: {display_input}")
    
    result = graph.invoke({
        "messages": [
            ("human", user_input)
        ]
    }, config=config, context=context)
    
    ai_content = result["messages"][-1].content
    if isinstance(ai_content, list):
        print(f"AI: {ai_content[0].get('text', '[Tool Call]')}\n")
    else:
        print(f"AI: {ai_content}\n")

print("=" * 40)
print("TESTING SUMMARY RESULTS")
print("=" * 40)

# 3. Fetch the final state of the graph
final_state = graph.get_state(config)
summary = final_state.values.get("summary")

if summary:
    print("\n✅ SUMMARIZER TRIGGERED SUCCESSFULLY!")
    print("Summary Content:\n")
    print(summary)
else:
    print("\n❌ No summary found. The conversation still didn't reach the token limit.")