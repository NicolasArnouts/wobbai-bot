#!/bin/bash

# Ensure script exits on any error
set -e

# Check if python3 and pip are available
if ! command -v python3 &> /dev/null; then
    echo "Python 3 is required but not found. Please install Python 3."
    exit 1
fi

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Create necessary directories
echo "Creating data directories..."
mkdir -p data
mkdir -p tmp/uploads

# Install dependencies
echo "Installing project dependencies..."
pip install -r requirements.txt

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "Creating .env file from .env.example..."
    if [ -f .env.example ]; then
        cp .env.example .env
        echo "Created .env file from template. Please update it with your credentials:"
        echo "1. Discord bot token (from Discord Developer Portal)"
        echo "2. OpenAI API key (from platform.openai.com)"
        echo "3. Langfuse credentials (from cloud.langfuse.com)"
    else
        echo "Warning: .env.example not found. Creating basic .env file..."
        cat > .env << EOL
# Discord Bot Configuration
DISCORD_TOKEN=your_discord_bot_token_here

# Database Configuration
DATABASE_URL=postgresql://postgres:secret@postgres:5432/postgres
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here

# Langfuse Configuration
LANGFUSE_PUBLIC_KEY=your_langfuse_public_key_here
LANGFUSE_SECRET_KEY=your_langfuse_secret_key_here
LANGFUSE_HOST=https://cloud.langfuse.com
EOL
    fi
fi

# Make sure scripts are executable
chmod +x dev-setup.sh

echo "Setup complete! Next steps:"
echo ""
echo "1. Update your .env file with the following credentials:"
echo "   - Discord bot token (from Discord Developer Portal)"
echo "   - OpenAI API key (from platform.openai.com)"
echo "   - Langfuse credentials (from cloud.langfuse.com)"
echo ""
echo "2. Start the services using either:"
echo "   a) Docker Compose (recommended):"
echo "      docker compose up --build"
echo ""
echo "   b) Local development:"
echo "      Terminal 1: source venv/bin/activate && uvicorn app.main:app --reload"
echo "      Terminal 2: source venv/bin/activate && celery -A app.celery_app worker --loglevel=info"
echo "      Terminal 3: source venv/bin/activate && python discord_bot/bot.py"
echo ""
echo "3. Test the setup by:"
echo "   a) Using the /dataset upload command in Discord with a CSV file"
echo "   b) Using the /dataset query command to ask questions about your data"
echo ""
echo "For more information, see the README.md file."