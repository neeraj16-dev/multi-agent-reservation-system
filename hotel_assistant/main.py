import uuid
import os
from dotenv import load_dotenv
from langgraph.types import Command

# Ensure environment variables (like DATABASE_URL, GEMINI_API_KEY) are loaded
load_dotenv()

# Import the compiled graph
from hotel_assistant.graph import graph

def main():
    print("🏨 Welcome to the Multi-Agent Hotel Assistant (Local Test)")
    print("Type 'q' or 'quit' to exit.\n")
    
    # Generate a static thread ID for this session to test Short-Term Memory
    thread_id = str(uuid.uuid4())
    # Hardcode a mock user ID to test Long-Term Memory (BaseStore)
    user_id = "test_user_001" 
    
    config = {
        "configurable": {
            "thread_id": thread_id,
            "user_id": user_id,
            "role": "guest"
        }
    }
    
    while True:
        try:
            user_input = input("\nYou: ").strip()
            if user_input.lower() in ['q', 'quit', 'exit']:
                print("Ending session...")
                break
                
            if not user_input:
                continue

            # 1. Stream the graph with the new user input
            # stream_mode="updates" lets us see which node is generating the output
            for event in graph.stream({"messages": [("user", user_input)]}, config, stream_mode="updates"):
                for node_name, state_update in event.items():
                    # Only print text responses from the AI agents, skip hidden nodes
                    if node_name in ["room_agent", "dining_agent"]:
                        messages = state_update.get("messages", [])
                        if messages and messages[-1].content:
                            agent_title = node_name.replace('_', ' ').title()
                            print(f"\n🤖 [{agent_title}]: {messages[-1].content}")

            # 2. Check if the graph paused for Human-in-the-Loop (HITL) approval
            state = graph.get_state(config)
            
            # state.next contains the name of the next node if paused
            if state.next: 
                # Retrieve the payload we passed into interrupt() in hitl_logic.py
                interrupt_data = state.tasks[0].interrupts[0].value
                
                print("\n⚠️ [SYSTEM ALERT: ADMIN APPROVAL REQUIRED]")
                print(f"Message: {interrupt_data['message']}")
                print(f"Action: {interrupt_data['tool_name']}")
                print(f"Target ID: {interrupt_data['reservation_id']}")
                
                # Ask the user for terminal input to approve/reject
                decision = input("\nApprove this action? (y/n): ").strip().lower()
                is_approved = decision == 'y'
                
                print(f"\nResuming graph... (Approved: {is_approved})")
                
                # 3. Resume the graph using Command, passing the decision back to the state
                for event in graph.stream(Command(resume=is_approved), config, stream_mode="updates"):
                    for node_name, state_update in event.items():
                        # The reject_action node or active agent might have a follow-up message
                        if node_name in ["room_agent", "dining_agent", "reject_action"]:
                            messages = state_update.get("messages", [])
                            if messages and messages[-1].content:
                                agent_title = node_name.replace('_', ' ').title()
                                print(f"\n🤖 [{agent_title}]: {messages[-1].content}")

        except Exception as e:
            print(f"\n❌ An error occurred: {e}")

if __name__ == "__main__":
    main()