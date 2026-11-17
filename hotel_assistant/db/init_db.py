from hotel_assistant.db.config import get_pool

def create_tables():
    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor() as cursor:
            # Dining Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS dining_reservations (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(255) NOT NULL,
                    customer_name VARCHAR(255) NOT NULL,
                    customer_phone VARCHAR(50),
                    reservation_date DATE NOT NULL,
                    reservation_time TIME NOT NULL,
                    party_size INT NOT NULL,
                    seating_type VARCHAR(50) DEFAULT 'any',
                    status VARCHAR(50) DEFAULT 'CONFIRMED'
                );
            """)

            # Room Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS room_reservations (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(255) NOT NULL,
                    guest_name VARCHAR(255),
                    guest_email VARCHAR(255),
                    guest_phone VARCHAR(50),
                    check_in_date DATE NOT NULL,
                    check_out_date DATE NOT NULL,
                    room_type VARCHAR(100) NOT NULL,
                    guests INT NOT NULL,
                    additional_guests TEXT,
                    status VARCHAR(50) DEFAULT 'CONFIRMED'
                );
            """)

            # Migrations for existing tables
            cursor.execute("""
                ALTER TABLE room_reservations 
                ADD COLUMN IF NOT EXISTS guest_name VARCHAR(255),
                ADD COLUMN IF NOT EXISTS guest_email VARCHAR(255),
                ADD COLUMN IF NOT EXISTS guest_phone VARCHAR(50),
                ADD COLUMN IF NOT EXISTS additional_guests TEXT;

                ALTER TABLE dining_reservations 
                ADD COLUMN IF NOT EXISTS customer_phone VARCHAR(50),
                ADD COLUMN IF NOT EXISTS seating_type VARCHAR(50) DEFAULT 'any';
            """)
            print("Business tables and columns verified/updated successfully.")

    pool.close()

if __name__ == "__main__":
    create_tables()