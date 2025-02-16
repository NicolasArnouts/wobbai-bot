#!/bin/bash
set -e

# Create directories if they don't exist
mkdir -p /var/run/celery /var/log/celery /data /tmp/uploads

# Set proper permissions for celery directories
chown -R appuser:appuser /var/run/celery /var/log/celery /data /tmp/uploads
chmod -R 755 /var/run/celery /var/log/celery /data /tmp/uploads

echo "Starting supervisord..."
exec supervisord -c /app/supervisord.conf