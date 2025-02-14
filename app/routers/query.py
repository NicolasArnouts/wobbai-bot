import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request

from ..db.duckdb import execute_query, get_table_schema
from ..db.postgres import get_latest_version, log_query
from ..llm.result_processor import process_query_results
from ..llm.text_to_sql import (
    SQLGenerationError,
    generate_sql_from_llm,
    verify_sql_safety,
)
from ..schemas.queries import QueryHistory, QueryRequest, QueryResponse, TablePreview

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/ask", response_model=QueryResponse)
async def ask_question(req: QueryRequest, request: Request) -> QueryResponse:
    """
    Handle a natural language query about a dataset using LLM-powered SQL generation.
    All LLM interactions are traced with Langfuse.
    """
    # Log incoming request
    logger.info(f"Received query request: {await request.json()}")

    try:
        # Get the correct version (latest if not specified)
        version_id = req.version_id
        if version_id == "latest":
            version_id = get_latest_version(req.dataset_id, req.user_id)
            if not version_id:
                logger.error(f"Dataset not found: {req.dataset_id}")
                raise HTTPException(status_code=404, detail="Dataset not found")

        # Get table schema for the query
        table_name = f"{req.dataset_id}_v{version_id}"
        schema = get_table_schema(req.user_id, table_name)

        if not schema:
            logger.error(f"Table not found: {table_name}")
            raise HTTPException(
                status_code=404,
                detail=f"Table {table_name} not found in user's database",
            )

        logger.info(f"Found schema for table {table_name}: {schema}")

        try:
            # Generate SQL using LLM (traced by Langfuse)
            generated_sql = generate_sql_from_llm(
                question=req.question,
                dataset_id=req.dataset_id,
                version_id=version_id,
                schema=schema,
            )

            logger.info(f"Generated SQL: {generated_sql}")

            # Verify SQL safety
            if not verify_sql_safety(generated_sql, table_name):
                logger.error(f"SQL failed safety checks: {generated_sql}")
                raise SQLGenerationError("Generated SQL failed safety checks")

            # Execute the query
            results, error = execute_query(req.user_id, generated_sql)

            if error:
                logger.error(f"Query execution error: {error}")
                raise HTTPException(status_code=500, detail=error)

            # Create a preview of the results
            preview = TablePreview(
                columns=list(results[0].keys()) if results else [],
                rows=results[:10],  # Only return first 10 rows in preview
                total_rows=len(results),
            )

            # Generate basic answer first (as a fallback)
            if len(results) == 0:
                raw_answer = "No results found."
            else:
                # Basic answer based on result count
                raw_answer = f"Found {len(results)} results."

                # If it's an aggregation query with a single row, make it more readable
                if len(results) == 1 and len(results[0]) == 1:
                    # Get the single column name and value
                    col_name = list(results[0].keys())[0]
                    value = list(results[0].values())[0]
                    raw_answer = f"{col_name}: {value}"

            try:
                # Process results with LLM to generate insights
                processed_answer = await process_query_results(
                    results=results,
                    question=req.question,
                    sql=generated_sql,
                    preview=preview.dict(),
                )
            except Exception as e:
                logger.error(f"Error processing results with LLM: {e}")
                # Fall back to raw answer if LLM processing fails
                processed_answer = raw_answer

            # Log the query
            log_query(
                req.dataset_id, version_id, req.question, generated_sql, len(results)
            )

            logger.info(f"Query successful: {processed_answer}")

            return QueryResponse(
                answer=processed_answer,
                raw_answer=raw_answer,
                generated_sql=generated_sql,
                preview=preview,
            )

        except SQLGenerationError as e:
            logger.error(f"SQL generation error: {str(e)}")
            raise HTTPException(
                status_code=400, detail=f"Failed to generate SQL query: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error processing query: {str(e)}"
            )

    except Exception as e:
        logger.error(f"Top-level error: {str(e)}")
        raise


@router.get("/history/{dataset_id}", response_model=QueryHistory)
async def get_query_history(dataset_id: str, user_id: str) -> QueryHistory:
    """Get the query history for a dataset."""
    # TODO: Implement get_query_history in postgres.py
    # For now, return an empty list
    return QueryHistory(queries=[], total_count=0)
