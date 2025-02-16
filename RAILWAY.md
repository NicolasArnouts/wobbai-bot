# Railway Deployment Guide

## Volume Setup

1. Create a new volume named `csv_data` in Railway through the Command Palette (⌘K) or by right-clicking the project canvas
2. Connect the volume to your service
3. Configure the volume mount path as `/data`

This ensures that your application's data persists between deployments and restarts.

## Environment Variables

Make sure to set the following environment variables in your Railway project:

1. Database URLs (will be provided by Railway):
   - `POSTGRES_URL` - PostgreSQL connection string
   - `REDIS_URL` - Redis connection string

2. Other Required Variables:
   - The service automatically sets `RAILWAY_VOLUME_NAME` and `RAILWAY_VOLUME_MOUNT_PATH`
   - `RAILWAY_RUN_UID=0` is already set in the Dockerfile for proper volume permissions

## Services

The application runs three services managed by supervisord:

1. FastAPI Application (Main web service)
2. Celery Worker (Background task processing)
3. Discord Bot

All services are automatically managed and will restart if they crash. Logs are available through the Railway dashboard.

## Data Persistence

- All persistent data should be written to `/app/data`
- The volume is mounted at runtime, not during build time
- Data written during build time will not persist
- All services have proper permissions to read/write to the volume

## Service Management

Supervisord manages all services and ensures they:
- Start automatically
- Restart on failure
- Forward logs properly to Railway's log collection