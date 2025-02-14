# CSV Query Bot

A Discord bot that allows users to upload CSV files and query them using natural language. Built with FastAPI, DuckDB, Celery, and discord.py.

## Features

- Upload CSV files through Discord slash commands
- Query data using natural language questions
- Secure multi-tenant data isolation
- Asynchronous file processing
- Versioning support for datasets
- Tabular results displayed in Discord

## Architecture

- **FastAPI**: Main backend API handling file uploads and queries
- **DuckDB**: Per-user database for efficient CSV querying
- **Celery**: Async task processing for file ingestion
- **PostgreSQL**: Metadata storage (users, datasets, versions)
- **Redis**: Task queue for Celery
- **discord.py**: Discord bot interface using slash commands

## Prerequisites

- Docker and Docker Compose
- A Discord bot token
- Python 3.10+
- pip (Python package installer)

## Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd wobby-new
```

2. Create a virtual environment and install dependencies:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows, use: venv\Scripts\activate
pip install -r requirements.txt
```

3. Create a `.env` file:
```bash
DISCORD_TOKEN=your_discord_bot_token_here
```

4. Build and start the services:
```bash
docker compose up --build
```

## Discord Commands

### Upload a CSV
```
/dataset upload [dataset_id] <attach CSV file>
```
- `dataset_id` is optional; if not provided, one will be generated
- Attach your CSV file to the command

### Query Data
```
/dataset query <dataset_id> <question>
```
- `dataset_id`: The ID of your dataset
- `question`: Your natural language question about the data

## Development

1. Set up the development environment:
```bash
# Make the setup script executable
chmod +x dev-setup.sh
# Run the setup script
./dev-setup.sh
```

2. Run services locally:
```bash
# Terminal 1: FastAPI
source venv/bin/activate
uvicorn app.main:app --reload

# Terminal 2: Celery Worker
source venv/bin/activate
celery -A app.celery_app worker --loglevel=info

# Terminal 3: Discord Bot
source venv/bin/activate
python discord_bot/bot.py
```

## Project Structure

```
.
├── app/
│   ├── routers/          # FastAPI route handlers
│   ├── schemas/          # Pydantic models
│   ├── db/              # Database connections
│   ├── tasks/           # Celery tasks
│   ├── main.py          # FastAPI entry point
│   └── celery_app.py    # Celery configuration
├── discord_bot/         # Discord bot code
├── data/               # Mounted volume for user data
└── tests/             # Test files
```

## Data Storage

- CSV files are stored in `/data/<user_id>/`
- Each user gets their own DuckDB file at `/data/<user_id>/db.duckdb`
- Metadata (versions, query logs) stored in PostgreSQL

## Security

- Each user's data is isolated in separate directories and DuckDB files
- File access is controlled through user authentication
- All Discord interactions are ephemeral (private to the user)

## Testing

Run the test suite:
```bash
source venv/bin/activate
pytest
```

## Limitations

- Currently supports CSV files up to Discord's file size limit
- Basic text-to-SQL conversion (can be enhanced with LLMs)
- Single-node deployment (can be scaled with modifications)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

MIT License - See LICENSE file for details