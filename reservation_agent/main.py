from reservation_agent.agent import graph, UserContext

config = {
    "configurable": {
        "thread_id": "usr101",
    }
}

context = UserContext(user_id=101)

result = graph.invoke({
    "messages": [
        ("human", "I want to update my reservation time. I have a reservation on November 15, 2026 at 7:00pm, can you update the timing to 9:00pm.")
    ]
}, config=config, context=context)

print(result["messages"][-1].content[0]["text"])

history = graph.get_state_history(config=config)

for snapshot in history:
    print("\nValues: ", snapshot.values)
    print("Next: ", snapshot.next)
    print("Create at: ", snapshot.created_at)
    print("-" * 10)