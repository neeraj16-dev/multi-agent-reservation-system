import os
from psycopg_pool import ConnectionPool
from dotenv import load_dotenv

load_dotenv()

# Default to a local Postgres URI for testing
DB_URI = os.getenv("DB_URL")

# Create a global connection pool
# max_size determines how many concurrent connections are allowed
connection_pool = ConnectionPool(
    conninfo=DB_URI,
    max_size=20,
    kwargs={"autocommit": True} # Required by LangGraph Postgres modules
)

def get_pool():
    """Returns the active Postgres connection pool."""
    return connection_pool