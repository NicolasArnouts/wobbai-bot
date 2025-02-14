from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    """Schema for query request."""

    dataset_id: str = Field(..., description="ID of the dataset to query")
    question: str = Field(
        ..., description="Natural language question to ask about the data"
    )
    version_id: Optional[str] = Field(
        "latest", description="Version ID of the dataset (defaults to latest)"
    )
    user_id: str = Field(..., description="ID of the user making the query")


class TablePreview(BaseModel):
    """Schema for table preview in query response."""

    columns: List[str]
    rows: List[Dict[str, Any]]
    total_rows: int


class QueryResponse(BaseModel):
    """Schema for query response."""

    answer: str = Field(..., description="LLM-processed summary of the query results")
    raw_answer: Optional[str] = Field(
        None, description="Original count-based answer before LLM processing"
    )
    generated_sql: str = Field(
        ..., description="The SQL query that was generated and executed"
    )
    preview: TablePreview = Field(..., description="Preview of the query results")
    error: Optional[str] = Field(None, description="Error message if query failed")


class QueryLog(BaseModel):
    """Schema for query log entry."""

    dataset_id: str
    version_id: str
    question: str
    generated_sql: str
    row_count: int
    created_at: Optional[str] = None

    class Config:
        from_attributes = True


class QueryHistory(BaseModel):
    """Schema for query history response."""

    queries: List[QueryLog]
    total_count: int
