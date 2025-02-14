import os
import shutil
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from ..db.postgres import get_latest_version, register_dataset_version
from ..schemas.uploads import DatasetVersion, UploadChunkRequest, UploadResponse
from ..tasks.ingestion_tasks import process_csv_task

router = APIRouter()


def get_temp_chunk_dir(user_id: str, dataset_id: str) -> str:
    """Get the temporary directory path for storing chunks."""
    temp_dir = os.path.join("/tmp/uploads", user_id, dataset_id)
    os.makedirs(temp_dir, exist_ok=True)
    return temp_dir


@router.post("/upload-chunk")
async def upload_chunk(
    dataset_id: str,
    user_id: str,
    chunk_index: int,
    total_chunks: int,
    chunk: UploadFile = File(...),
) -> UploadResponse:
    """
    Handle a chunk of a CSV file upload.
    If this is the final chunk, triggers async processing.
    """
    temp_dir = get_temp_chunk_dir(user_id, dataset_id)
    chunk_path = os.path.join(temp_dir, f"chunk_{chunk_index}")

    # Write the chunk to disk
    try:
        with open(chunk_path, "wb") as f:
            shutil.copyfileobj(chunk.file, f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save chunk: {str(e)}")

    # If this is the final chunk, start processing
    if chunk_index == total_chunks - 1:
        # Generate a version ID for this upload
        version_id = str(uuid.uuid4())[:8]

        # Instead of hardcoding "/data", use the DATA_DIR environment variable
        data_dir = os.environ.get("DATA_DIR", "data")
        final_path = os.path.join(data_dir, user_id, f"{dataset_id}-v{version_id}.csv")

        try:
            # Register this version in Postgres
            register_dataset_version(dataset_id, version_id, user_id, final_path)

            # Start async processing
            process_csv_task.delay(
                user_id,
                dataset_id,
                version_id,
                temp_dir,
                total_chunks,
                final_path,
            )

            return UploadResponse(
                status="processing",
                message="Final chunk received. Processing started.",
                dataset_id=dataset_id,
                version_id=version_id,
                is_final_chunk=True,
            )

        except Exception as e:
            # If registration fails, clean up the chunks
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise HTTPException(
                status_code=500, detail=f"Failed to process upload: {str(e)}"
            )

    # Not the final chunk, just acknowledge receipt
    return UploadResponse(
        status="received",
        message=f"Chunk {chunk_index + 1}/{total_chunks} received.",
        dataset_id=dataset_id,
        is_final_chunk=False,
    )


@router.get("/datasets/{dataset_id}/versions/{version_id}")
async def get_dataset_version(
    dataset_id: str, version_id: str, user_id: str
) -> DatasetVersion:
    """Get information about a specific dataset version."""
    latest_version = get_latest_version(dataset_id, user_id)
    if not latest_version:
        raise HTTPException(status_code=404, detail="Dataset not found")

    # TODO: Implement get_dataset_version in postgres.py to return full version info
    # For now, we'll return a mock response
    return DatasetVersion(
        dataset_id=dataset_id,
        version_id=version_id or latest_version,
        user_id=user_id,
        file_path=f"/data/{user_id}/{dataset_id}-v{version_id}.csv",
        created_at="2024-02-14T12:00:00Z",  # Mock timestamp
    )
