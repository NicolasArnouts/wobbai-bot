import os
import shutil
import tempfile

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    """Create a test client for FastAPI app."""
    return TestClient(app)


@pytest.fixture
def test_data_dir():
    """Create a temporary directory for test data."""
    test_dir = tempfile.mkdtemp()
    os.environ["DATA_DIR"] = test_dir
    yield test_dir
    shutil.rmtree(test_dir)


@pytest.fixture
def sample_csv(test_data_dir):
    """Create a sample CSV file for testing."""
    csv_content = """name,age,city
Alice,25,New York
Bob,30,London
Charlie,35,Paris"""

    file_path = os.path.join(test_data_dir, "sample.csv")
    with open(file_path, "w") as f:
        f.write(csv_content)

    return file_path


@pytest.fixture
def mock_user():
    """Mock user data for testing."""
    return {"user_id": "test_user_123", "dataset_id": "test_dataset_456"}
