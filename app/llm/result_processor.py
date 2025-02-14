import os
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from langfuse.decorators import observe
from langfuse.openai import openai

# Load environment variables from .env file
load_dotenv()

# Initialize Langfuse configuration
os.environ.setdefault("LANGFUSE_HOST", "https://cloud.langfuse.com")


@observe()
async def process_query_results(
    results: List[Dict[str, Any]], question: str, sql: str, preview: Dict[str, Any]
) -> str:
    """
    Process query results using LLM to generate a concise, insightful summary.

    Args:
        results: The full query results
        question: Original user question
        sql: Generated SQL query
        preview: Preview data including column names and sample rows

    Returns:
        str: A concise summary (guaranteed < 1500 chars to allow for formatting)
    """
    try:
        # Build system prompt
        system_prompt = """You are an expert data analyst helping users understand query results. Given a user's question and the query results:

1. Provide a clear, concise answer (max 1500 characters)
2. Focus on insights relevant to the original question
3. Include key statistics or aggregates if relevant
4. Format numbers for readability
5. If the data has time series, note any trends
6. If results are empty, explain possible reasons why

Remember:
- Be concise but informative
- Highlight the most important findings
- Use natural language
- Stay under the character limit"""

        # Build user prompt with context and data
        user_prompt = f"""Question: {question}

SQL Query Used:
{sql}

Data Preview:
Columns: {", ".join(preview["columns"])}
Total Rows: {preview["total_rows"]}

Sample Data:
{format_sample_data(preview["rows"])}

Please provide a clear, concise analysis of these results."""

        # Call OpenAI with Langfuse tracing
        response = openai.chat.completions.create(
            model="gpt-4o-mini",  # Using GPT-4 for better analysis
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,  # Allow none creativity in analysis
            # max_tokens=750,  # ~1500 characters
            presence_penalty=0.2,  # Encourage diverse insights
            frequency_penalty=0.2,
        )

        # Extract the summary
        summary = response.choices[0].message.content.strip()

        # Ensure we're under the length limit
        if len(summary) > 1500:
            summary = summary[:1497] + "..."

        return summary

    except Exception as e:
        # If LLM processing fails, fall back to a basic summary
        return generate_fallback_summary(results, question)


def format_sample_data(rows: List[Dict[str, Any]], max_rows: int = 5) -> str:
    """Format sample data rows for LLM prompt."""
    if not rows:
        return "No data available"

    # Take up to max_rows
    sample_rows = rows[:max_rows]

    # Format each row
    formatted_rows = []
    for row in sample_rows:
        formatted_row = ", ".join(f"{k}: {v}" for k, v in row.items())
        formatted_rows.append(f"- {formatted_row}")

    return "\n".join(formatted_rows)


def generate_fallback_summary(results: List[Dict[str, Any]], question: str) -> str:
    """Generate a basic summary when LLM processing fails."""
    try:
        if not results:
            return "No results found for your query."

        num_results = len(results)
        summary = f"Found {num_results} {'result' if num_results == 1 else 'results'}."

        # If it's an aggregation query with a single row, make it more readable
        if num_results == 1 and len(results[0]) == 1:
            col_name = list(results[0].keys())[0]
            value = list(results[0].values())[0]
            summary = f"{col_name}: {value}"

        return summary

    except Exception:
        # Ultimate fallback
        return "Unable to process query results. Please try a different question."
