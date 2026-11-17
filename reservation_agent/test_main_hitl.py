from langgraph.types import Command
from reservation_agent.agent import graph, UserContext

print("\n" + "=" * 50)
print("TESTING HUMAN-IN-THE-LOOP (HITL) CANCELLATION")
print("=" * 50)

config = {
    "configurable": {
        "thread_id": "hitl_test_thread_1",
        "user_id": 999  
    }
}
my_context = UserContext(user_id=999)

# 1. Ask the AI to do something destructive
user_input = "Hi, can you please cancel my reservation ID 11?"
print(f"User: {user_input}\n")

print("--- 1. INITIATING GRAPH ---")
# We run the graph normally. It should run chatbot, realize it needs to cancel, and hit the interrupt!
for event in graph.stream(
    {"messages": [("human", user_input)]}, 
    config=config, 
    context=my_context,
    stream_mode="updates"
):
    for node_name, node_state in event.items():
        print(f"✅ Finished node: [{node_name}]")

print("\n--- 2. CHECKING GRAPH STATE ---")
state = graph.get_state(config)

# Check if the graph is waiting at our approval node
if state.next and state.next[0] == "approval":
    # Extract the payload we passed into the interrupt() function
    interrupt_data = state.tasks[0].interrupts[0].value
    print(f"🛑 GRAPH PAUSED BY HITL!")
    print(f"   Message: {interrupt_data['message']}")
    print(f"   Target ID: {interrupt_data['reservation_id']}")
    
    # ---------------------------------------------------------
    # SIMULATING THE HUMAN UI CLICK
    # Let's set this to False to test your new reject node!
    # ---------------------------------------------------------
    human_decision = False  
    
    print(f"\n👤 Human clicks: {'APPROVE (Proceed)' if human_decision else 'REJECT (Block Action)'}\n")
    
    print("--- 3. RESUMING GRAPH ---")
    # We resume the graph by passing Command(resume=False) instead of a new user message
    for event in graph.stream(
        Command(resume=human_decision), 
        config=config, 
        context=my_context,
        stream_mode="updates"
    ):
        for node_name, node_state in event.items():
            print(f"✅ Finished node: [{node_name}]")
            
            # Print the AI's final reaction to being blocked!
            if node_name == "chatbot":
                last_msg = node_state["messages"][-1]
                content = last_msg.content
                text = content if isinstance(content, str) else content[0].get("text", "")
                if text:
                    print(f"   🤖 AI: {text}")

else:
    print("\n❌ Graph did not pause. It either finished completely or routed incorrectly.")