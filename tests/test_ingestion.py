import os
from pathlib import Path

import pytest
from fastapi import UploadFile


def test_upload_chunk_success(client, mock_user, sample_csv):
    """Test successful upload of a single chunk."""
    # Read sample CSV content
    with open(sample_csv, "rb") as f:
        content = f.read()

    # Create upload parameters
    params = {
        "dataset_id": mock_user["dataset_id"],
        "user_id": mock_user["user_id"],
        "chunk_index": 0,
        "total_chunks": 1,
    }

    # Create file data
    files = {"chunk": ("sample.csv", content, "text/csv")}

    # Make the request
    response = client.post("/ingestion/upload-chunk", params=params, files=files)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["received", "processing"]
    assert data["dataset_id"] == mock_user["dataset_id"]

    if data["is_final_chunk"]:
        assert "version_id" in data


def test_upload_chunk_missing_file(client, mock_user):
    """Test upload without a file attached."""
    params = {
        "dataset_id": mock_user["dataset_id"],
        "user_id": mock_user["user_id"],
        "chunk_index": 0,
        "total_chunks": 1,
    }

    response = client.post("/ingestion/upload-chunk", params=params)
    assert response.status_code == 422  # Validation error


def test_chunked_upload(client, mock_user, sample_csv):
    """Test uploading a file in multiple chunks."""
    # Read sample CSV content
    with open(sample_csv, "rb") as f:
        content = f.read()

    # Split content into chunks
    chunk_size = 1024  # 1KB chunks for testing
    chunks = [content[i : i + chunk_size] for i in range(0, len(content), chunk_size)]
    total_chunks = len(chunks)

    # Upload each chunk
    for i, chunk in enumerate(chunks):
        params = {
            "dataset_id": mock_user["dataset_id"],
            "user_id": mock_user["user_id"],
            "chunk_index": i,
            "total_chunks": total_chunks,
        }

        files = {"chunk": (f"chunk_{i}.csv", chunk, "text/csv")}

        response = client.post("/ingestion/upload-chunk", params=params, files=files)

        assert response.status_code == 200
        data = response.json()

        if i < total_chunks - 1:
            assert not data["is_final_chunk"]
        else:
            assert data["is_final_chunk"]
            assert "version_id" in data


def test_get_dataset_version(client, mock_user):
    """Test retrieving dataset version information."""
    response = client.get(
        f"/ingestion/datasets/{mock_user['dataset_id']}/versions/latest",
        params={"user_id": mock_user["user_id"]},
    )

    assert response.status_code in [200, 404]  # 404 is acceptable if no versions exist

    if response.status_code == 200:
        data = response.json()
        assert data["dataset_id"] == mock_user["dataset_id"]
        assert data["user_id"] == mock_user["user_id"]
        assert "version_id" in data
        assert "file_path" in data
        assert "created_at" in data
