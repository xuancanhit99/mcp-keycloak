#!/bin/bash

# Load .env file if it exists
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Run with uv
# Default to stdio mode if not specified
MODE=${1:-stdio}

if [ "$MODE" = "http" ]; then
    echo "Starting server in HTTP mode..."
    TRANSPORT=http PORT=${PORT:-8000} uv run python -m src
else
    echo "Starting server in stdio mode..."
    uv run python -m src
fi