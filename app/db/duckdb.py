import os
import threading
from contextlib import contextmanager
from typing import Optional

import duckdb

# Thread-local storage for DuckDB connections
_local = threading.local()


def get_user_db_path(user_id: str) -> str:
    """Get the path to a user's DuckDB database file."""
    db_root = os.environ.get("DUCKDB_DB_ROOT", "data")
    user_dir = os.path.join(db_root, user_id)
    os.makedirs(user_dir, exist_ok=True)
    return os.path.join(user_dir, "db.duckdb")


@contextmanager
def get_duckdb_connection(user_id: str):
    """
    Get a DuckDB connection for a specific user.
    Uses thread-local storage to cache connections per thread.
    """
    if not hasattr(_local, "connections"):
        _local.connections = {}

    db_path = get_user_db_path(user_id)

    # Check if we already have a connection for this user in this thread
    if user_id not in _local.connections:
        _local.connections[user_id] = duckdb.connect(db_path)

    try:
        yield _local.connections[user_id]
    except Exception:
        # If there's an error, close and remove the connection
        if user_id in _local.connections:
            _local.connections[user_id].close()
            del _local.connections[user_id]
        raise


def create_or_replace_table(
    user_id: str, dataset_id: str, version_id: str, csv_path: str
) -> Optional[str]:
    """
    Create or replace a table in DuckDB from a CSV file.
    Returns an error message if something goes wrong, None on success.
    """
    table_name = f"{dataset_id}_v{version_id}"

    try:
        with get_duckdb_connection(user_id) as conn:
            # First try to read the CSV to infer schema
            conn.execute(f"""
                CREATE TABLE IF NOT EXISTS "{table_name}" AS 
                SELECT * FROM read_csv_auto('{csv_path}')
            """)
            return None
    except Exception as e:
        return f"Error creating table from CSV: {str(e)}"


def execute_query(user_id: str, sql: str) -> tuple[list, Optional[str]]:
    """
    Execute a SQL query for a user.
    Returns (results, error_message).
    If error_message is not None, results will be empty.
    """
    try:
        with get_duckdb_connection(user_id) as conn:
            result = conn.execute(sql).fetchall()
            columns = [desc[0] for desc in conn.description]

            # Convert to list of dicts for easier JSON serialization
            results = [dict(zip(columns, row)) for row in result]
            return results, None
    except Exception as e:
        return [], f"Error executing query: {str(e)}"


def list_user_tables(user_id: str) -> list[str]:
    """List all tables in a user's DuckDB database."""
    with get_duckdb_connection(user_id) as conn:
        result = conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
        ).fetchall()
        return [row[0] for row in result]


def get_table_schema(user_id: str, table_name: str) -> list[tuple[str, str]]:
    """
    Get the schema (column names and types) for a specific table.
    Returns list of (column_name, column_type) tuples.
    """
    with get_duckdb_connection(user_id) as conn:
        result = conn.execute(f"""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = '{table_name}'
            AND table_schema = 'main'
        """).fetchall()
        return [(row[0], row[1]) for row in result]
