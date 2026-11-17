from hotel_assistant.db.config import get_pool

def insert_room_reservation(
    user_id: str,
    check_in: str,
    check_out: str,
    room_type: str,
    guests: int,
    guest_name: str = "Guest",
    guest_email: str = "",
    guest_phone: str = "",
    additional_guests: str = ""
) -> int:
    with get_pool().connection() as conn:
        with conn.cursor() as cursor:
            # Ensure columns exist if not already migrated
            cursor.execute("""
                ALTER TABLE room_reservations 
                ADD COLUMN IF NOT EXISTS guest_name VARCHAR(255),
                ADD COLUMN IF NOT EXISTS guest_email VARCHAR(255),
                ADD COLUMN IF NOT EXISTS guest_phone VARCHAR(50),
                ADD COLUMN IF NOT EXISTS additional_guests TEXT;
            """)
            cursor.execute("""
                INSERT INTO room_reservations (
                    user_id, check_in_date, check_out_date, room_type, guests,
                    guest_name, guest_email, guest_phone, additional_guests
                ) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
            """, (
                user_id, check_in, check_out, room_type, guests,
                guest_name, guest_email, guest_phone, additional_guests
            ))
            return cursor.fetchone()[0]

def fetch_user_room_reservations(user_id: str):
    with get_pool().connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, guest_name, guest_email, guest_phone, check_in_date, check_out_date, room_type, guests, additional_guests, status 
                FROM room_reservations WHERE user_id = %s ORDER BY check_in_date
            """, (user_id,))
            return cursor.fetchall()

def cancel_room_reservation_db(reservation_id: int, user_id: str) -> bool:
    with get_pool().connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE room_reservations SET status = 'CANCELLED' 
                WHERE id = %s AND user_id = %s AND status='CONFIRMED'
            """, (reservation_id, user_id))
            return cursor.rowcount > 0