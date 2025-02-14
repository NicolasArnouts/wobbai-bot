import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.celery_app import create_celery
from app.db.postgres import init_postgres_db
from app.routers import ingestion, query

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Initialize FastAPI application."""
    app = FastAPI(title="CSV Query MVP")

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # In production, replace with specific origins
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Initialize DB if needed
    init_postgres_db()

    # Include Routers
    app.include_router(ingestion.router, prefix="/ingestion", tags=["Ingestion"])
    app.include_router(query.router, prefix="/query", tags=["Query"])

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        # Log the incoming request
        logger.info(f"Incoming request: {request.method} {request.url}")

        # Log request body for POST requests
        if request.method == "POST":
            body = await request.body()
            if body:
                logger.info(f"Request body: {body.decode()}")

        start_time = time.time()
        response = await call_next(request)
        process_time = (time.time() - start_time) * 1000

        # Log the completion with timing
        logger.info(
            f"Completed {request.method} {request.url} "
            f"in {process_time:.2f}ms with status {response.status_code}"
        )
        return response

    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {"status": "healthy"}

    return app


app = create_app()

# Create Celery instance
celery = create_celery()

if __name__ == "__main__":
    import uvicorn

    logger.info("Starting server...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
