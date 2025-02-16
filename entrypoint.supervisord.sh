#!/bin/bash
set -e

echo "Starting supervisord..."
supervisord -c /app/supervisord.conf

# Keep the script running
exec "$@"