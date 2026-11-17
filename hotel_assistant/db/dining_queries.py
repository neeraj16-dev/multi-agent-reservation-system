from hotel_assistant.db.config import get_pool

def insert_dining_reservation(
    user_id: str,
    name: str,
    date: str,
    time: str,
    party_size: int,
    customer_phone: str = "",
    seating_type: str = "any"
) -> int:
    with get_pool().connection() as conn:
        with conn.cursor() as cursor:
            # Ensure columns exist if not already migrated
            cursor.execute("""
                ALTER TABLE dining_reservations 
                ADD COLUMN IF NOT EXISTS customer_phone VARCHAR(50),
                ADD COLUMN IF NOT EXISTS seating_type VARCHAR(50) DEFAULT 'any';
            """)
            cursor.execute("""
                INSERT INTO dining_reservations (
                    user_id, customer_name, customer_phone, reservation_date, reservation_time, party_size, seating_type
                ) 
                VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id
            """, (user_id, name, customer_phone, date, time, party_size, seating_type))
            return cursor.fetchone()[0]

def fetch_user_dining_reservations(user_id: str):
    with get_pool().connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, customer_name, customer_phone, reservation_date, reservation_time, party_size, seating_type, status 
                FROM dining_reservations WHERE user_id = %s ORDER BY reservation_date
            """, (user_id,))
            return cursor.fetchall()

def update_dining_reservation_db(reservation_id: int, user_id: str, date: str, time: str, party_size: int) -> bool:
    with get_pool().connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE dining_reservations SET reservation_date = %s, reservation_time = %s, party_size = %s 
                WHERE id = %s AND user_id = %s AND status = 'CONFIRMED'
            """, (date, time, party_size, reservation_id, user_id))
            return cursor.rowcount > 0

def cancel_dining_reservation_db(reservation_id: int, user_id: str) -> bool:
    with get_pool().connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE dining_reservations SET status = 'CANCELLED' 
                WHERE id = %s AND user_id = %s AND status='CONFIRMED'
            """, (reservation_id, user_id))
            return cursor.rowcount > 0