import pytest
from fastapi import HTTPException


def test_basic_query(client, mock_user):
    """Test a basic query against a dataset."""
    # Prepare query request
    query_data = {
        "dataset_id": mock_user["dataset_id"],
        "user_id": mock_user["user_id"],
        "question": "What is the average age?",
    }

    response = client.post("/query/ask", json=query_data)

    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert "generated_sql" in data
    assert "preview" in data

    # Check if SQL was generated correctly
    assert "SELECT" in data["generated_sql"]
    assert "AVG" in data["generated_sql"]  # Since we asked for average

    # Check preview structure
    preview = data["preview"]
    assert "columns" in preview
    assert "rows" in preview
    assert "total_rows" in preview


def test_query_nonexistent_dataset(client, mock_user):
    """Test querying a dataset that doesn't exist."""
    query_data = {
        "dataset_id": "nonexistent_dataset",
        "user_id": mock_user["user_id"],
        "question": "What is the total count?",
    }

    response = client.post("/query/ask", json=query_data)
    assert response.status_code == 404


def test_query_with_grouping(client, mock_user):
    """Test a query that involves grouping."""
    query_data = {
        "dataset_id": mock_user["dataset_id"],
        "user_id": mock_user["user_id"],
        "question": "What is the average age by city?",
    }

    response = client.post("/query/ask", json=query_data)

    assert response.status_code == 200
    data = response.json()

    # Check if SQL has GROUP BY
    assert "GROUP BY" in data["generated_sql"]

    # Verify preview structure for grouped data
    preview = data["preview"]
    assert len(preview["columns"]) >= 2  # Should have at least city and avg_age


def test_query_history(client, mock_user):
    """Test retrieving query history for a dataset."""
    response = client.get(
        f"/query/history/{mock_user['dataset_id']}",
        params={"user_id": mock_user["user_id"]},
    )

    assert response.status_code == 200
    data = response.json()
    assert "queries" in data
    assert "total_count" in data
    assert isinstance(data["queries"], list)


def test_malformed_query(client, mock_user):
    """Test handling of malformed queries."""
    query_data = {
        "dataset_id": mock_user["dataset_id"],
        "user_id": mock_user["user_id"],
        "question": "",  # Empty question
    }

    response = client.post("/query/ask", json=query_data)
    assert response.status_code == 422  # Validation error


def test_complex_query(client, mock_user):
    """Test a more complex query with multiple operations."""
    query_data = {
        "dataset_id": mock_user["dataset_id"],
        "user_id": mock_user["user_id"],
        "question": "What is the average age and total count by city, sorted by average age?",
    }

    response = client.post("/query/ask", json=query_data)

    assert response.status_code == 200
    data = response.json()

    # Check SQL complexity
    sql = data["generated_sql"]
    assert "GROUP BY" in sql
    assert "ORDER BY" in sql
    assert "AVG" in sql
    assert "COUNT" in sql


def test_query_specific_version(client, mock_user):
    """Test querying a specific version of a dataset."""
    query_data = {
        "dataset_id": mock_user["dataset_id"],
        "user_id": mock_user["user_id"],
        "question": "What is the total count?",
        "version_id": "specific_version",  # Should be a real version ID in practice
    }

    response = client.post("/query/ask", json=query_data)

    # Either 200 (if version exists) or 404 (if it doesn't)
    assert response.status_code in [200, 404]

    if response.status_code == 200:
        data = response.json()
        assert "answer" in data
        assert "generated_sql" in data
        assert "preview" in data
