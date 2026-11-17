from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from hotel_assistant.db.room_queries import (
    insert_room_reservation,
    fetch_user_room_reservations,
    cancel_room_reservation_db
)

@tool
def book_room(
    check_in_date: str,
    check_out_date: str,
    room_type: str,
    guests: int,
    guest_name: str,
    guest_email: str,
    guest_phone: str,
    additional_guests: str = "None",
    config: RunnableConfig = None
) -> str:
    """Book a hotel room accommodation for the user after gathering contact and guest details."""
    user_id = config["configurable"]["user_id"] if config else "default_user"

    if guests < 1:
        return "Number of guests must be at least 1."

    reservation_id = insert_room_reservation(
        user_id, check_in_date, check_out_date, room_type, guests,
        guest_name=guest_name, guest_email=guest_email, guest_phone=guest_phone,
        additional_guests=additional_guests
    )
    return f"Room booked successfully. Reservation ID: {reservation_id}. A confirmation receipt has been issued for {guest_name} at {guest_email}."

@tool
def get_room_reservations(config: RunnableConfig) -> str:
    """Retrieve all hotel room reservations belonging to the user."""
    user_id = config["configurable"]["user_id"]
    reservations = fetch_user_room_reservations(user_id)
    
    if not reservations:
        return "No room reservations found."
    return str(reservations)

@tool
def cancel_room(reservation_id: int, config: RunnableConfig) -> str:
    """Cancel a hotel room reservation belonging to the user."""
    user_id = config["configurable"]["user_id"]
    
    success = cancel_room_reservation_db(reservation_id, user_id)
    if not success:
        return "Room reservation not found or already cancelled."
    return "Room reservation cancelled successfully."