import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row
import os

load_dotenv()

db_url = os.getenv("DB_URL")

def get_connection():
    return psycopg.connect(
        db_url,
        row_factory=dict_row
    )
