import os
import json
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from google import genai
from google.genai import types

# Import our decoupled DB queries from the LangGraph module
from hotel_assistant.db.room_queries import insert_room_reservation, cancel_room_reservation_db
from hotel_assistant.db.dining_queries import insert_dining_reservation, cancel_dining_reservation_db
from hotel_assistant.db.config import get_pool
from hotel_assistant.security import input_guardrail, output_guardrail
from langgraph.store.postgres import PostgresStore

app = FastAPI()

# Initialize the modern Gemini client (automatically picks up GEMINI_API_KEY from .env)
client = genai.Client(http_options={"api_version": "v1beta"})

def get_user_preferences(user_id: str) -> str:
    """Fetch Long-Term Memory (LTM) from PostgresStore to inject into Gemini."""
    pool = get_pool()
    store = PostgresStore(pool)
    # Note: store.setup() must have been run previously
    namespace = ("users", str(user_id))
    existing_memory = store.get(namespace, "preferences")
    if existing_memory and existing_memory.value:
        return json.dumps(existing_memory.value)
    return "No saved preferences."

# Define the tools we want the Live API to have access to
hotel_tools = [
    types.FunctionDeclaration(
        name="update_draft_details",
        description="Call this whenever the user provides or updates any reservation detail so the inputs are displayed on the user's screen in real time.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "booking_type": types.Schema(type=types.Type.STRING, description="'room' or 'dining'"),
                "guest_name": types.Schema(type=types.Type.STRING, description="Primary guest full name"),
                "guest_email": types.Schema(type=types.Type.STRING, description="Email address for confirmation receipt"),
                "guest_phone": types.Schema(type=types.Type.STRING, description="Phone number"),
                "check_in_date": types.Schema(type=types.Type.STRING, description="Check-in date"),
                "check_out_date": types.Schema(type=types.Type.STRING, description="Check-out date"),
                "room_type": types.Schema(type=types.Type.STRING, description="Type of room"),
                "guests_count": types.Schema(type=types.Type.INTEGER, description="Total number of room guests"),
                "additional_guest_names": types.Schema(type=types.Type.STRING, description="Names of additional guests if guests > 1"),
                "customer_name": types.Schema(type=types.Type.STRING, description="Dining customer name"),
                "customer_phone": types.Schema(type=types.Type.STRING, description="Dining customer phone"),
                "reservation_date": types.Schema(type=types.Type.STRING, description="Dining date"),
                "reservation_time": types.Schema(type=types.Type.STRING, description="Dining time"),
                "party_size": types.Schema(type=types.Type.INTEGER, description="Dining party size"),
                "seating_type": types.Schema(type=types.Type.STRING, description="Seating preference: 'indoor', 'outdoor', 'window', or 'any'")
            }
        )
    ),
    types.FunctionDeclaration(
        name="book_room",
        description="Finalize and book a hotel room after gathering guest name, email, phone, check-in, check-out, room type, guests count, additional guest names (if guests > 1), and receiving verbal confirmation.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "guest_name": types.Schema(type=types.Type.STRING, description="Full name of primary guest"),
                "guest_email": types.Schema(type=types.Type.STRING, description="Email address to receive receipt"),
                "guest_phone": types.Schema(type=types.Type.STRING, description="Contact phone number"),
                "check_in_date": types.Schema(type=types.Type.STRING, description="Check-in date"),
                "check_out_date": types.Schema(type=types.Type.STRING, description="Check-out date"),
                "room_type": types.Schema(type=types.Type.STRING, description="Room category"),
                "guests_count": types.Schema(type=types.Type.INTEGER, description="Total number of guests"),
                "additional_guests": types.Schema(type=types.Type.STRING, description="Names of additional guests if guests > 1, or 'None'"),
            },
            required=["guest_name", "guest_email", "guest_phone", "check_in_date", "check_out_date", "room_type", "guests_count"]
        )
    ),
    types.FunctionDeclaration(
        name="book_table",
        description="Finalize a restaurant dining reservation after gathering customer name, phone number, date, time, party size, and seating type (indoor, outdoor, window, any), and receiving verbal confirmation.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "customer_name": types.Schema(type=types.Type.STRING, description="Name of the customer"),
                "customer_phone": types.Schema(type=types.Type.STRING, description="Customer phone number"),
                "reservation_date": types.Schema(type=types.Type.STRING, description="Date of reservation"),
                "reservation_time": types.Schema(type=types.Type.STRING, description="Reservation time"),
                "party_size": types.Schema(type=types.Type.INTEGER, description="Number of guests in the party"),
                "seating_type": types.Schema(type=types.Type.STRING, description="Seating preference: 'indoor', 'outdoor', 'window', or 'any'"),
            },
            required=["customer_name", "customer_phone", "reservation_date", "reservation_time", "party_size", "seating_type"]
        )
    )
]

@app.websocket("/ws/voice-agent/{user_id}")
async def voice_agent_websocket(websocket: WebSocket, user_id: str):
    """
    The main WebSocket endpoint. The frontend connects here and streams audio.
    We proxy that audio to Gemini, and proxy Gemini's audio back to the frontend.
    """
    await websocket.accept()
    print(f"User {user_id} connected to Voice Agent.")

    # 1. Fetch the user's Long-Term Memory
    preferences = get_user_preferences(user_id)

    # 2. Configure the Live API Session
    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"], # Force Gemini to reply with Voice
        system_instruction=types.Content(parts=[types.Part(
            text=(
                "You are the luxury concierge voice assistant for Grand Luxe Hotel. "
                "Be polite, natural, concise, and helpful.\n\n"

                "=== REAL-TIME FORM SYNCHRONIZATION ===\n"
                "As the user provides any reservation detail (name, email, phone, dates, room type, guests, seating preference), "
                "IMMEDIATELY call the 'update_draft_details' tool. This displays the inputs on the user's screen in real time so they can follow along.\n\n"

                "=== ROOM RESERVATION RULES ===\n"
                "1. Collect the following required details:\n"
                "   - Primary Guest's Full Name\n"
                "   - Guest's Email Address (to send the receipt)\n"
                "   - Guest's Phone Number\n"
                "   - Check-in Date and Check-out Date\n"
                "   - Room Type (e.g., Deluxe King, Executive Suite, Standard Room)\n"
                "   - Number of Guests\n"
                "   - CRITICAL: If number of guests is 2 or more, ask for the names of the other guests.\n"
                "2. When all details are collected, summarize them clearly to the user and ask for their verbal confirmation.\n"
                "3. Once the user confirms, execute 'book_room'.\n"
                "4. Spoken confirmation message: You MUST say: 'Your room has been booked! You will receive the receipt and confirmation shortly at [guest_email]. Your reservation ID is [ID].'\n\n"

                "=== DINING RESERVATION RULES ===\n"
                "1. Collect the following details:\n"
                "   - Customer's Name\n"
                "   - Customer's Phone Number\n"
                "   - Reservation Date and Time\n"
                "   - Party Size (number of guests)\n"
                "   - Seating Preference: Ask whether they prefer 'indoor', 'outdoor', 'window', or 'any'.\n"
                "   - CRITICAL: DO NOT ask for guest names for dinner bookings.\n"
                "2. Summarize the details and ask for verbal confirmation.\n"
                "3. Once confirmed, execute 'book_table'.\n"
                "4. Confirm the table reservation warmly with reservation ID and seating preference.\n\n"

                f"User Profile & Preferences: {preferences}"
            )
        )]),
        tools=[types.Tool(function_declarations=hotel_tools)]
    )

    try:
        # Open connection to Google's Live API
        async with client.aio.live.connect(model="gemini-3.8-live", config=config) as session:
            print("Connected to Gemini Live API.")

            # --- Task A: Receive Audio from Frontend, Send to Gemini ---
            async def receive_from_client():
                try:
                    while True:
                        # Frontend sends raw PCM bytes (16kHz Int16)
                        data = await websocket.receive_bytes()
                        if data:
                            await session.send_realtime_input(
                                audio=types.Blob(
                                    data=data,
                                    mime_type="audio/pcm;rate=16000"
                                )
                            )
                except WebSocketDisconnect:
                    print("Client disconnected.")
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    print(f"Error in receive_from_client: {e}")

            # --- Task B: Receive Data from Gemini, Handle Tools, Send Audio to Frontend ---
            async def receive_from_gemini():
                try:
                    # Keep listening across multiple conversational turns
                    while True:
                        async for response in session.receive():
                            # 1. Handle Interruption by the user
                            if response.server_content and response.server_content.interrupted:
                                print("[Gemini] User interrupted assistant.")
                                await websocket.send_text(json.dumps({"type": "interrupted"}))

                            # 2. Handle Text & Audio output from Gemini
                            if response.server_content and response.server_content.model_turn:
                                for part in response.server_content.model_turn.parts:
                                    if part.text:
                                        # Output Guardrail: Screen model text for prompt leaks or technical credentials
                                        screened = output_guardrail.screen_text(part.text)
                                        if not screened.is_safe:
                                            print(f"[SECURITY ALERT] Output guardrail blocked prompt leak: {screened.reason}")
                                            await websocket.send_text(json.dumps({
                                                "type": "security_alert",
                                                "guardrail": "output",
                                                "attack_type": screened.attack_type,
                                                "reason": screened.reason
                                            }))

                                        await websocket.send_text(json.dumps({
                                            "type": "transcript",
                                            "sender": "ai",
                                            "text": screened.sanitized_text or part.text
                                        }))
                                    if part.inline_data:
                                        # Send the 24kHz audio bytes back to the frontend
                                        await websocket.send_bytes(part.inline_data.data)

                            # 3. Handle Turn Complete
                            if response.server_content and response.server_content.turn_complete:
                                print("[Gemini] Model turn complete.")
                                await websocket.send_text(json.dumps({"type": "turn_complete"}))

                            # 4. Handle Tool Calls from Gemini
                            if response.tool_call:
                                for call in response.tool_call.function_calls:
                                    print(f"Gemini requested tool: {call.name} with args {call.args}")
                                    
                                    result_data = {"error": "Tool not found"}

                                    # Input Guardrail on tool arguments (prevent injection through form fields)
                                    has_injection = False
                                    for arg_key, arg_val in (call.args or {}).items():
                                        if isinstance(arg_val, str):
                                            check_res = input_guardrail.validate(arg_val, use_secondary_model=False)
                                            if not check_res.is_safe:
                                                has_injection = True
                                                print(f"[SECURITY ALERT] Input guardrail blocked tool argument '{arg_key}': {check_res.reason}")
                                                await websocket.send_text(json.dumps({
                                                    "type": "security_alert",
                                                    "guardrail": "input",
                                                    "attack_type": check_res.attack_type,
                                                    "reason": f"Injection blocked in '{arg_key}': {check_res.reason}"
                                                }))
                                                result_data = {
                                                    "status": "error",
                                                    "message": "Security policy violation: Suspicious argument detected."
                                                }
                                                break

                                    if not has_injection:
                                        try:
                                            # Tool A: Live Form Synchronization
                                            if call.name == "update_draft_details":
                                                args = call.args
                                                await websocket.send_text(json.dumps({
                                                    "type": "draft_updated",
                                                    "data": args
                                                }))
                                                result_data = {"status": "success", "message": "Displayed on screen"}

                                            # Tool B: Book Hotel Room
                                            elif call.name == "book_room":
                                                args = call.args
                                                guest_name = str(args.get("guest_name", "Guest"))
                                                guest_email = str(args.get("guest_email", ""))
                                                guest_phone = str(args.get("guest_phone", ""))
                                                check_in = str(args.get("check_in_date", ""))
                                                check_out = str(args.get("check_out_date", ""))
                                                room_type = str(args.get("room_type", "Deluxe Room"))
                                                guests_count = int(args.get("guests_count", args.get("guests", 1)))
                                                additional_guests = str(args.get("additional_guests", args.get("additional_guest_names", "None")))

                                                res_id = insert_room_reservation(
                                                    user_id=user_id,
                                                    check_in=check_in,
                                                    check_out=check_out,
                                                    room_type=room_type,
                                                    guests=guests_count,
                                                    guest_name=guest_name,
                                                    guest_email=guest_email,
                                                    guest_phone=guest_phone,
                                                    additional_guests=additional_guests
                                                )
                                                result_data = {
                                                    "status": "success", 
                                                    "reservation_id": res_id,
                                                    "details": {
                                                        "guest_name": guest_name,
                                                        "guest_email": guest_email,
                                                        "guest_phone": guest_phone,
                                                        "room_type": room_type,
                                                        "check_in": check_in,
                                                        "check_out": check_out,
                                                        "guests": guests_count,
                                                        "additional_guests": additional_guests
                                                    }
                                                }

                                            # Tool C: Book Dining Table
                                            elif call.name == "book_table":
                                                args = call.args
                                                cust_name = str(args.get("customer_name", "Customer"))
                                                cust_phone = str(args.get("customer_phone", ""))
                                                res_date = str(args.get("reservation_date", ""))
                                                res_time = str(args.get("reservation_time", ""))
                                                party_size = int(args.get("party_size", 2))
                                                seating = str(args.get("seating_type", "any"))

                                                res_id = insert_dining_reservation(
                                                    user_id=user_id,
                                                    name=cust_name,
                                                    date=res_date,
                                                    time=res_time,
                                                    party_size=party_size,
                                                    customer_phone=cust_phone,
                                                    seating_type=seating
                                                )
                                                result_data = {
                                                    "status": "success", 
                                                    "reservation_id": res_id,
                                                    "details": {
                                                        "customer_name": cust_name,
                                                        "customer_phone": cust_phone,
                                                        "reservation_date": res_date,
                                                        "reservation_time": res_time,
                                                        "party_size": party_size,
                                                        "seating_type": seating
                                                    }
                                                }
                                        except Exception as db_err:
                                            print(f"DB Error executing {call.name}: {db_err}")
                                            result_data = {"status": "error", "message": str(db_err)}

                                    # Output Guardrail: Screen tool results to prevent data exfiltration
                                    result_data = output_guardrail.screen_tool_output(result_data)

                                    # Inform the frontend about the tool action
                                    await websocket.send_text(json.dumps({
                                        "type": "tool_executed",
                                        "tool": call.name,
                                        "args": call.args,
                                        "result": result_data
                                    }))

                                    # Send the DB result back to Gemini so it speaks confirmation
                                    await session.send_tool_response(
                                        function_responses=[types.FunctionResponse(
                                            name=call.name,
                                            id=call.id,
                                            response=result_data
                                        )]
                                    )
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    print(f"Live API receive loop error: {e}")

            # Run both loops concurrently
            await asyncio.gather(
                receive_from_client(),
                receive_from_gemini()
            )

    except Exception as e:
        print(f"Live API Error: {e}")
    finally:
        await websocket.close()