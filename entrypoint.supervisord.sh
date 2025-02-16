#!/bin/bash
set -e

# Fix permissions on /data in case the attached volume is owned by root
chown -R appuser:appuser /data

# Start supervisord (which will run your services as defined in supervisord.conf)
exec supervisord -c /app/supervisord.conf
