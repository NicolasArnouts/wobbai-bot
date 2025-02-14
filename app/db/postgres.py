import os
from contextlib import contextmanager
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import psycopg2
from psycopg2.pool import SimpleConnectionPool

# Global connection pool
DB_POOL = None


def sanitize_db_url(db_url: str) -> str:
    parsed = urlparse(db_url)
    query_params = dict(parse_qsl(parsed.query))
    if "pgbouncer" in query_params:
        del query_params["pgbouncer"]
    new_query = urlencode(query_params)
    return urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            new_query,
            parsed.fragment,
        )
    )


def init_postgres_db():
    """Initialize PostgreSQL connection pool and create tables if they don't exist."""
    global DB_POOL
    if DB_POOL is None:
        db_url = os.environ.get("DATABASE_URL")
        db_url = sanitize_db_url(db_url)
        DB_POOL = SimpleConnectionPool(minconn=1, maxconn=10, dsn=db_url)

        # Create tables if they don't exist
        with get_conn() as conn:
            with conn.cursor() as cur:
                # Dataset versions table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS dataset_versions (
                        id SERIAL PRIMARY KEY,
                        dataset_id VARCHAR(128) NOT NULL,
                        version_id VARCHAR(128) NOT NULL,
                        user_id VARCHAR(128) NOT NULL,
                        file_path TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT NOW(),
                        UNIQUE (dataset_id, version_id, user_id)
                    );
                """)

                # Query logs table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS query_logs (
                        id SERIAL PRIMARY KEY,
                        dataset_id VARCHAR(128) NOT NULL,
                        version_id VARCHAR(128) NOT NULL,
                        question TEXT NOT NULL,
                        generated_sql TEXT,
                        row_count INT,
                        created_at TIMESTAMP DEFAULT NOW()
                    );
                """)
                conn.commit()


@contextmanager
def get_conn():
    """Context manager for getting a connection from the pool."""
    global DB_POOL
    if DB_POOL is None:
        init_postgres_db()

    conn = DB_POOL.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        DB_POOL.putconn(conn)


def get_latest_version(dataset_id: str, user_id: str):
    """Get the latest version ID for a dataset."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT version_id 
                FROM dataset_versions 
                WHERE dataset_id = %s AND user_id = %s 
                ORDER BY created_at DESC 
                LIMIT 1
            """,
                (dataset_id, user_id),
            )
            result = cur.fetchone()
            return result[0] if result else None


def log_query(
    dataset_id: str, version_id: str, question: str, generated_sql: str, row_count: int
):
    """Log a query execution."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO query_logs 
                (dataset_id, version_id, question, generated_sql, row_count)
                VALUES (%s, %s, %s, %s, %s)
            """,
                (dataset_id, version_id, question, generated_sql, row_count),
            )


def register_dataset_version(
    dataset_id: str, version_id: str, user_id: str, file_path: str
):
    """Register a new dataset version."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO dataset_versions 
                (dataset_id, version_id, user_id, file_path)
                VALUES (%s, %s, %s, %s)
            """,
                (dataset_id, version_id, user_id, file_path),
            )
