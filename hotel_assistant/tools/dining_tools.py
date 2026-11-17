from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from hotel_assistant.db.dining_queries import (
    insert_dining_reservation,
    fetch_user_dining_reservations,
    update_dining_reservation_db,
    cancel_dining_reservation_db
)

@tool
def book_table(
    customer_name: str,
    customer_phone: str,
    reservation_date: str,
    reservation_time: str,
    party_size: int,
    seating_type: str = "any",
    config: RunnableConfig = None
) -> str:
    """Create a restaurant table reservation for the user with seating preference."""
    user_id = config["configurable"]["user_id"] if config else "default_user"

    if not customer_name.strip():
        return "Customer name cannot be empty"
    if not 1 <= party_size <= 20:
        return "Party size must be between 1 to 20"

    reservation_id = insert_dining_reservation(
        user_id, customer_name, reservation_date, reservation_time, party_size,
        customer_phone=customer_phone, seating_type=seating_type
    )
    return f"Table reservation created successfully, ID: {reservation_id} with {seating_type} seating."

@tool
def get_dining_reservations(config: RunnableConfig) -> str:
    """Retrieve all dining reservations belonging to the user."""
    user_id = config["configurable"]["user_id"]
    reservations = fetch_user_dining_reservations(user_id)
    
    if not reservations:
        return "No dining reservations found"
    return str(reservations)

@tool
def update_table_reservation(
    reservation_id: int,
    reservation_date: str,
    reservation_time: str,
    party_size: int,
    config: RunnableConfig
) -> str:
    """Update the date, time and party size of the user's dining reservation."""
    user_id = config["configurable"]["user_id"]

    if not 1 <= party_size <= 20:
        return "Party size must be between 1 and 20."

    success = update_dining_reservation_db(reservation_id, user_id, reservation_date, reservation_time, party_size)
    if not success:
        return "Error occurred while updating the table reservation. Ensure ID is correct."
    return "Table reservation updated."

@tool
def cancel_table(reservation_id: int, config: RunnableConfig) -> str:
    """Cancel a dining reservation belonging to the user."""
    user_id = config["configurable"]["user_id"]
    
    success = cancel_dining_reservation_db(reservation_id, user_id)
    if not success:
        return "Dining reservation not found or already cancelled."
    return "Table reservation cancelled successfully."