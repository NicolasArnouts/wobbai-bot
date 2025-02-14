import logging
import os
import shutil
from typing import Optional

from celery import shared_task

from ..db.duckdb import create_or_replace_table

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def process_csv_task(
    self,
    user_id: str,
    dataset_id: str,
    version_id: str,
    temp_dir: str,
    total_chunks: int,
    final_path: str,
) -> Optional[str]:
    """
    Process uploaded CSV chunks:
    1. Merge chunks into final CSV
    2. Basic sanitization
    3. Create DuckDB table
    4. Clean up temporary files

    Returns error message if failed, None if successful.
    """
    try:
        # Ensure the user's data directory exists
        os.makedirs(os.path.dirname(final_path), exist_ok=True)

        # Merge chunks into final CSV
        with open(final_path, "wb") as outfile:
            # Read and write chunks in order
            for i in range(total_chunks):
                chunk_path = os.path.join(temp_dir, f"chunk_{i}")
                if not os.path.exists(chunk_path):
                    raise FileNotFoundError(f"Missing chunk {i}")

                with open(chunk_path, "rb") as infile:
                    shutil.copyfileobj(infile, outfile)

        # Optional: Basic sanitization could go here
        # For MVP, we'll trust DuckDB's CSV reader to handle basic cleanup

        # Create DuckDB table from the CSV
        error = create_or_replace_table(
            user_id=user_id,
            dataset_id=dataset_id,
            version_id=version_id,
            csv_path=final_path,
        )

        if error:
            raise Exception(f"Failed to create DuckDB table: {error}")

        # Only clean up temporary chunks directory, but keep the final CSV file
        shutil.rmtree(temp_dir, ignore_errors=True)

        # Verify both the CSV and DuckDB files exist
        if not os.path.exists(final_path):
            raise Exception(f"CSV file not found at {final_path}")

        duckdb_path = os.path.join(
            os.environ.get("DUCKDB_DB_ROOT", "data"), user_id, "db.duckdb"
        )
        if not os.path.exists(duckdb_path):
            raise Exception(f"DuckDB database not found at {duckdb_path}")

        logger.info(
            f"Successfully processed CSV for user {user_id}, "
            f"dataset {dataset_id}, version {version_id}"
        )
        return None

    except Exception as e:
        logger.error(
            f"Error processing CSV for user {user_id}, "
            f"dataset {dataset_id}, version {version_id}: {str(e)}"
        )

        # Clean up temporary files on error
        shutil.rmtree(temp_dir, ignore_errors=True)

        # Also try to remove the incomplete final file
        try:
            os.remove(final_path)
        except:
            pass

        # Retry up to 3 times (configured in decorator)
        try:
            self.retry(countdown=60)  # Wait 60 seconds before retry
        except self.MaxRetriesExceededError:
            return f"Failed to process CSV after 3 retries: {str(e)}"

        return str(e)


@shared_task
def cleanup_stale_uploads():
    """
    Periodic task to clean up stale upload chunks.
    This could be scheduled to run daily or hourly.
    """
    try:
        base_temp_dir = "/tmp/uploads"
        if not os.path.exists(base_temp_dir):
            return

        # Walk through all user directories
        for user_id in os.listdir(base_temp_dir):
            user_dir = os.path.join(base_temp_dir, user_id)
            if not os.path.isdir(user_dir):
                continue

            # Check each dataset directory
            for dataset_id in os.listdir(user_dir):
                dataset_dir = os.path.join(user_dir, dataset_id)
                if not os.path.isdir(dataset_dir):
                    continue

                # If directory is older than 24 hours, remove it
                import time

                dir_age = time.time() - os.path.getctime(dataset_dir)
                if dir_age > 86400:  # 24 hours in seconds
                    shutil.rmtree(dataset_dir, ignore_errors=True)
                    logger.info(f"Cleaned up stale upload: {dataset_dir}")

    except Exception as e:
        logger.error(f"Error cleaning up stale uploads: {str(e)}")
        return str(e)
