from langchain.tools import ToolRuntime, tool
from reservation_agent.database import get_connection

@tool
def create_reservation(
    customer_name: str,
    reservation_date: str,
    reservation_time: str,
    party_size: int,
    runtime: ToolRuntime
) -> str:
    """Create a restaurant reservation for the authenticated user."""

    user_id = runtime.context.user_id

    if not customer_name.strip():
        return "Customer name cannot be empty"

    if not 1 <= party_size <= 20:
        return "Party size must be between 1 to 20"

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO reservations (user_id, customer_name, reservation_date, reservation_time, party_size) 
                VALUES (%s, %s, %s, %s, %s) RETURNING id
            """, (user_id, customer_name, reservation_date, reservation_time, party_size))

            reservation_id = cursor.fetchone()["id"]


    return f"Reservation created successfully, ID: {reservation_id}"

@tool
def get_reservations(runtime: ToolRuntime) -> str:
    """Retrieve all the reservations belonging to the authenticated user"""

    user_id = runtime.context.user_id

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT * FROM reservations WHERE user_id = %s ORDER BY reservation_date, reservation_time
            """, (user_id,))

            reservations = cursor.fetchall()

    if not reservations:
        return "No reservations found"

    return str(reservations)

@tool
def update_reservation(
    reservation_id: int,
    customer_name: str,
    reservation_date: str,
    reservation_time: str,
    party_size: int,
    runtime: ToolRuntime
) -> str:
    """Update the date, time and party size of the user's reservation."""
    user_id = runtime.context.user_id

    if not 1 <= party_size <= 20:
        return "Party size must be between 1 and 20."

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE reservations SET reservation_date = %s, reservation_time = %s, party_size = %s 
                WHERE id = %s AND user_id = %s AND status = 'CONFIRMED'
            """, (reservation_date, reservation_time, party_size, reservation_id, user_id))

            if cursor.rowcount == 0:
                return "Error occurred while updating the reservation."

    return "Reservation updated."

@tool
def cancel_reservation(
    reservation_id: int,
    runtime: ToolRuntime
) -> str:
    """Cancel a reservation belonging to the authenticated user."""
    user_id = runtime.context.user_id

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE reservations SET status = 'CANCELLED' 
                WHERE id = %s AND user_id = %s AND status='CONFIRMED'
            """, (reservation_id, user_id,))

            if cursor.rowcount == 0:
                return "Reservation not found."


    return "Reservation cancelled."