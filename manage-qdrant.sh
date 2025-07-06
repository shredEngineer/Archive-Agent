#!/bin/bash

# Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
# This file is part of Archive Agent. See LICENSE for details.

# Exit on any error
set -e

CONTAINER_NAME="archive-agent-qdrant-server"

# Function to display help message
show_help() {
    echo "Usage: $0 [start|stop|update]"
    echo "  start:  Ensures the Qdrant server container is running."
    echo "  stop:   Stops the Qdrant server container."
    echo "  update: Pulls the latest Qdrant Docker image and restarts the container if it was running."
    exit 1
}

# Function to check if the container exists (running or stopped)
container_exists() {
    docker ps -a --filter "name=$CONTAINER_NAME" --format "{{.Names}}" | grep -q "^$CONTAINER_NAME$"
}

# Function to check if the container is running
container_is_running() {
    docker ps --filter "name=$CONTAINER_NAME" --filter "status=running" --format "{{.Names}}" | grep -q "^$CONTAINER_NAME$"
}

# Function to start the Qdrant server
start_qdrant() {
    if container_is_running; then
        echo "Archive Agent: Qdrant server: Already running."
    else
        if container_exists; then
            echo "Archive Agent: Qdrant server: Restarting..."
            if ! docker start "$CONTAINER_NAME"; then
                echo "Archive Agent: Qdrant server: ERROR: Failed to restart."
                exit 1
            fi
            echo "Archive Agent: Qdrant server: Restarted successfully."
        else
            echo "Archive Agent: Qdrant server: Starting for the first time..."
            if ! docker run -d \
                --name "$CONTAINER_NAME" \
                --restart unless-stopped \
                -p 6333:6333 \
                -v ~/.archive-agent-qdrant-storage:/qdrant/storage \
                qdrant/qdrant; then
                echo "Archive Agent: Qdrant server: ERROR: Failed to start."
                exit 1
            fi
            echo "Archive Agent: Qdrant server: Started successfully."
        fi
    fi
}

# Function to stop the Qdrant server
stop_qdrant() {
    if container_is_running; then
        echo "Archive Agent: Qdrant server: Stopping..."
        if ! docker stop "$CONTAINER_NAME"; then
            echo "Archive Agent: Qdrant server: ERROR: Failed to stop."
            exit 1
        fi
        echo "Archive Agent: Qdrant server: Stopped successfully."
    elif container_exists; then
        echo "Archive Agent: Qdrant server: Not running but exists. No action needed."
    else
        echo "Archive Agent: Qdrant server: Does not exist. No action needed."
    fi
}

# Function to update the Qdrant Docker image
update_qdrant() {
    local was_running=false
    if container_is_running; then
        was_running=true
        echo "Archive Agent: Qdrant server: Running. Stopping it before update..."
        if ! docker stop "$CONTAINER_NAME"; then
            echo "Archive Agent: Qdrant server: ERROR: Failed to stop for update. Aborting."
            exit 1
        fi
    fi

    echo "Archive Agent: Qdrant server: Pulling latest Qdrant Docker image (qdrant/qdrant)..."
    if ! docker pull qdrant/qdrant; then
        echo "Archive Agent: Qdrant server: ERROR: Failed to pull latest Qdrant Docker image."
        # Attempt to restart if it was running, even if pull failed
        if $was_running; then
            echo "Archive Agent: Qdrant server: Attempting to restart after failed pull."
            docker start "$CONTAINER_NAME" || echo "Archive Agent: Qdrant server: ERROR: Failed to restart."
        fi
        exit 1
    fi
    echo "Archive Agent: Qdrant server: Qdrant Docker image updated successfully."

    if $was_running; then
        echo "Archive Agent: Qdrant server: Restarting after update..."
        if ! docker start "$CONTAINER_NAME"; then
            echo "Archive Agent: Qdrant server: ERROR: Failed to restart after update."
            exit 1
        fi
        echo "Archive Agent: Qdrant server: Restarted successfully after update."
    else
        echo "Archive Agent: Qdrant server: Was not running, so not restarting."
    fi
}

# Main script logic
if [ "$#" -ne 1 ]; then
    show_help
fi

case "$1" in
    start)
        start_qdrant
        ;;
    stop)
        stop_qdrant
        ;;
    update)
        update_qdrant
        ;;
    *)
        echo "Archive Agent: Qdrant server: ERROR: Invalid command: $1"
        show_help
        ;;
esac
