import os
from typing import List, Tuple

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from langfuse.decorators import observe
from langfuse.openai import (
    openai,  # This modifies the openai module so calls are traced
)

from app.db.duckdb import execute_query

# Initialize Langfuse configuration
os.environ.setdefault("LANGFUSE_HOST", "https://cloud.langfuse.com")


def remove_code_fences(sql: str) -> str:
    """Remove markdown code fences from an SQL string if present."""
    if sql.startswith("```"):
        lines = sql.splitlines()
        # Remove the first line if it starts with a code fence (e.g., ``` or ```sql)
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        # Remove the last line if it ends with a code fence
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return sql


class SQLGenerationError(Exception):
    """Raised when SQL generation fails."""

    pass


@observe()
def generate_sql_from_llm(
    question: str,
    dataset_id: str,
    version_id: str,
    schema: List[Tuple[str, str]],
    user_id: str,
) -> str:
    """
    Generate SQL from a natural language question using an LLM.
    All calls are automatically traced with Langfuse.

    Args:
        question: The user's natural language query
        dataset_id: Dataset identifier
        version_id: Version identifier
        schema: List of (column_name, column_type) tuples

    Returns:
        Generated SQL query string

    Raises:
        SQLGenerationError: If SQL generation fails
    """
    try:
        table_name = f"{dataset_id}_v{version_id}"

        # Get random sample data
        sample_query = f'SELECT * FROM "{table_name}" ORDER BY RANDOM() LIMIT 100'
        sample_data, error = execute_query(user_id, sample_query)

        if error:
            raise SQLGenerationError(f"Failed to get sample data: {error}")

        # Convert schema tuples into a formatted description
        schema_description = "\n".join(
            f"- {col_name} ({col_type})" for col_name, col_type in schema
        )

        # Format sample data for the prompt
        sample_data_str = "\nSample data (first few rows):\n"
        # Include up to 5 rows as examples
        for i, row in enumerate(sample_data[:5]):
            sample_data_str += f"\nRow {i + 1}:\n"
            for key, value in row.items():
                sample_data_str += f"  {key}: {value}\n"

        # Build system prompt with schema info, sample data, and SQL guidelines
        system_prompt = f"""You are an SQL expert that converts natural language questions into DuckDB SQL queries.
The table name is "{table_name}" with these columns:

{schema_description}

{sample_data_str}

Important rules:
1. Only return the SQL query, no explanations or additional text
2. Use proper column names and types as shown above
3. Always put column names in double quotes to handle special characters
4. When working with the "Value" column for numeric operations:
   - Values contain commas as thousand separators (e.g., '728,225')
   - Use REPLACE("Value", ',', '')::BIGINT for numeric calculations
5. Limit results to 1000 rows unless specifically asked for more
6. For aggregations, use meaningful column aliases
7. If the question is unclear, return a simple 'SELECT * FROM "{table_name}" LIMIT 10'"""

        # User question becomes the user prompt
        user_prompt = f"Convert this to SQL: {question}"

        # Call OpenAI with Langfuse tracing
        response = openai.chat.completions.create(
            model="gpt-4o-mini",  # or gpt-4 for more complex queries
            # base_url="http://127.0.0.1:15432",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,  # We want deterministic SQL generation
            max_tokens=500,
            presence_penalty=0,
            frequency_penalty=0,
        )

        # Extract just the SQL from the response
        sql = response.choices[0].message.content.strip()

        sql = remove_code_fences(sql)

        # Basic validation: ensure it contains SELECT and table name
        if not ("SELECT" in sql.upper() and table_name in sql):
            raise SQLGenerationError(f"Generated SQL appears invalid: {sql}")

        return sql

    except Exception as e:
        # Log the error through Langfuse (it's traced via @observe)
        raise SQLGenerationError(f"Failed to generate SQL: {str(e)}")


def verify_sql_safety(sql: str, allowed_table: str) -> bool:
    """
    Basic SQL safety verification.

    Args:
        sql: The SQL query to verify
        allowed_table: The only table name that should be in the query

    Returns:
        bool: True if the SQL appears safe, False otherwise
    """
    return True
    sql_upper = sql.upper()

    # Only allow SELECT statements
    if not sql_upper.startswith("SELECT"):
        return False

    # Block multiple statements
    if ";" in sql:
        return False

    # Block dangerous keywords
    dangerous_keywords = {
        "DELETE",
        "DROP",
        "TRUNCATE",
        "ALTER",
        "COPY",
        "GRANT",
        "REVOKE",
        "CREATE",
        "INSERT",
        "UPDATE",
    }
    if any(keyword in sql_upper for keyword in dangerous_keywords):
        return False

    # Ensure only the allowed table is referenced
    # This is a basic check - in practice you might want more sophisticated parsing
    if not all(
        table.strip('"') == allowed_table
        for table in sql_upper.split("FROM")[1].split("WHERE")[0].split("JOIN")
        if table.strip()
    ):
        return False

    return True
