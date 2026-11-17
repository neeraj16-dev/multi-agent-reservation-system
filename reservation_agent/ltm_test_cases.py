from reservation_agent.agent import graph, store

print("\n" + "=" * 50)
print("TESTING LONG-TERM MEMORY BEHAVIOR")
print("=" * 50)

# We use the same user (105) for all tests to see the memory evolve
config = {
    "configurable": {
        "thread_id": "ltm_test_thread",
        "user_id": 105  
    }
}
namespace = ("users", "105")

# First, let's manually seed the database with the starting state (Test 1 assumes we had window seating)
store.put(namespace, "preferences", {"preferred_seating": "window"})
print(f"🏁 STARTING MEMORY: {store.get(namespace, 'preferences').value}\n")

tests = [
    {
        "name": "Test 1: Update window -> outdoor",
        "input": "Actually, I prefer outdoor seating now.",
    },
    {
        "name": "Test 2: Update seating, preserve party size",
        "input": "I prefer outdoor seating. I usually book for 4.",
    },
    {
        "name": "Test 3: Don't save 8 as a permanent preference",
        "input": "Book a table for 8 tonight. (My name is Neeraj, tonight's date is Nov 13, 2026)", 
    }
]

for i, test in enumerate(tests):
    print("-" * 50)
    print(f"▶️ {test['name']}")
    print(f"User: {test['input']}")
    
    # Run the graph
    graph.invoke({"messages": [("human", test['input'])]}, config=config)
    
    # Fetch the updated memory from the store immediately after the graph finishes
    saved_memory = store.get(namespace, "preferences")
    current_prefs = saved_memory.value if saved_memory else {}
    
    print(f"🧠 LTM STATE AFTER TEST: {current_prefs}")
    
print("\n" + "=" * 50)
print("TEST RUN COMPLETE!")