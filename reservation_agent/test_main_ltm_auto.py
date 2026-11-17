from reservation_agent.agent import graph, store, UserContext

config = {
    "configurable": {
        "thread_id": "auto_ltm_test_thread_2", # New thread
        "user_id": 999  
    }
}

my_context = UserContext(user_id=999)

user_input = "Hi, my name is Neeraj. I'd like to book a table for 17th November 2026 at 8 PM. By the way, for all my future bookings, my usual party size is 4 people, and I always prefer window seating."
print(f"User: {user_input}\n")

print("=" * 50)
print("LIVE AGENT STREAM:")
print("=" * 50)

# Replace graph.invoke() with graph.stream()
# stream_mode="updates" yields a chunk every time a node finishes!
for event in graph.stream({"messages": [("human", user_input)]}, config=config, context=my_context, stream_mode="updates"):
    for node_name, node_state in event.items():
        print(f"\n✅ Finished running node: [{node_name}]")
        
        if node_name == "chatbot":
            last_msg = node_state["messages"][-1]
            if hasattr(last_msg, 'tool_calls') and last_msg.tool_calls:
                 # PRINT WHAT THE AI TRIED TO SEND!
                 print(f"   🤖 AI is calling a tool: {last_msg.tool_calls[0]['name']}")
                 print(f"   📥 Arguments: {last_msg.tool_calls[0]['args']}")
            else:
                 content = last_msg.content
                 text = content if isinstance(content, str) else content[0].get("text", "")
                 print(f"   🤖 AI: {text}")
                 
        # PRINT WHAT THE TOOL REPLIED WITH!
        elif node_name == "tools":
             tool_msg = node_state["messages"][-1]
             print(f"   🔧 Tool Result: {tool_msg.content}")


print("\n" + "=" * 50)
print("VERIFYING THE STORE (DATABASE)")
print("=" * 50)

saved_memory = store.get(("users", "999"), "preferences")
if saved_memory and saved_memory.value:
    print("✅ SUCCESS! Preferences saved:")
    print(saved_memory.value)
else:
    print("❌ FAILED. The store is empty.")