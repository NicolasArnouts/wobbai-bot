from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class UploadChunkRequest(BaseModel):
    """Schema for upload chunk request parameters."""

    dataset_id: str = Field(..., description="Unique identifier for the dataset")
    user_id: str = Field(..., description="ID of the user uploading the file")
    chunk_index: int = Field(..., ge=0, description="Index of the current chunk")
    total_chunks: int = Field(..., gt=0, description="Total number of chunks expected")


class UploadResponse(BaseModel):
    """Schema for upload response."""

    status: str
    message: str
    dataset_id: str
    version_id: Optional[str] = None
    is_final_chunk: bool = False


class DatasetVersion(BaseModel):
    """Schema for dataset version information."""

    dataset_id: str
    version_id: str
    user_id: str
    file_path: str
    created_at: datetime

    class Config:
        from_attributes = True


class DatasetsList(BaseModel):
    """Schema for listing datasets response."""

    datasets: List[DatasetVersion]
