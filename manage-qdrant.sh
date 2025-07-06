#!/bin/bash

# Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
# This file is part of Archive Agent. See LICENSE for details.

CONTAINER_NAME="archive-agent-qdrant-server"
LOG_PREFIX="$(date '+%Y-%m-%d %H:%M:%S')"

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
        echo "$LOG_PREFIX INFO     Archive Agent: Qdrant server ($CONTAINER_NAME) is already running."
    else
        if container_exists; then
            echo "$LOG_PREFIX INFO     Archive Agent: Qdrant server ($CONTAINER_NAME) is restarting..."
            if ! docker start "$CONTAINER_NAME"; then
                echo "$LOG_PREFIX ERROR    Archive Agent: Failed to restart Qdrant server ($CONTAINER_NAME)."
                exit 1
            fi
            echo "$LOG_PREFIX INFO     Archive Agent: Qdrant server ($CONTAINER_NAME) restarted successfully."
        else
            echo "$LOG_PREFIX INFO     Archive Agent: Qdrant server ($CONTAINER_NAME) is starting for the first time..."
            if ! docker run -d \
                --name "$CONTAINER_NAME" \
                --restart unless-stopped \
                -p 6333:6333 \
                -v ~/.archive-agent-qdrant-storage:/qdrant/storage \
                qdrant/qdrant; then
                echo "$LOG_PREFIX ERROR    Archive Agent: Failed to start Qdrant server ($CONTAINER_NAME)."
                exit 1
            fi
            echo "$LOG_PREFIX INFO     Archive Agent: Qdrant server ($CONTAINER_NAME) started successfully."
        fi
    fi
}

# Function to stop the Qdrant server
stop_qdrant() {
    if container_is_running; then
        echo "$LOG_PREFIX INFO     Archive Agent: Stopping Qdrant server ($CONTAINER_NAME)..."
        if ! docker stop "$CONTAINER_NAME"; then
            echo "$LOG_PREFIX ERROR    Archive Agent: Failed to stop Qdrant server ($CONTAINER_NAME)."
            exit 1
        fi
        echo "$LOG_PREFIX INFO     Archive Agent: Qdrant server ($CONTAINER_NAME) stopped successfully."
    elif container_exists; then
        echo "$LOG_PREFIX INFO     Archive Agent: Qdrant server ($CONTAINER_NAME) is not running but exists. No action needed."
    else
        echo "$LOG_PREFIX INFO     Archive Agent: Qdrant server ($CONTAINER_NAME) does not exist. No action needed."
    fi
}

# Function to update the Qdrant Docker image
update_qdrant() {
    local was_running=false
    if container_is_running; then
        was_running=true
        echo "$LOG_PREFIX INFO     Archive Agent: Qdrant server ($CONTAINER_NAME) is running. Stopping it before update..."
        if ! docker stop "$CONTAINER_NAME"; then
            echo "$LOG_PREFIX ERROR    Archive Agent: Failed to stop Qdrant server ($CONTAINER_NAME) for update. Aborting."
            exit 1
        fi
    fi

    echo "$LOG_PREFIX INFO     Archive Agent: Pulling latest Qdrant Docker image (qdrant/qdrant)..."
    if ! docker pull qdrant/qdrant; then
        echo "$LOG_PREFIX ERROR    Archive Agent: Failed to pull latest Qdrant Docker image."
        # Attempt to restart if it was running, even if pull failed
        if $was_running; then
            echo "$LOG_PREFIX INFO     Archive Agent: Attempting to restart Qdrant server ($CONTAINER_NAME) after failed pull."
            docker start "$CONTAINER_NAME" || echo "$LOG_PREFIX ERROR    Archive Agent: Failed to restart Qdrant server ($CONTAINER_NAME)."
        fi
        exit 1
    fi
    echo "$LOG_PREFIX INFO     Archive Agent: Qdrant Docker image updated successfully."

    if $was_running; then
        echo "$LOG_PREFIX INFO     Archive Agent: Restarting Qdrant server ($CONTAINER_NAME)..."
        if ! docker start "$CONTAINER_NAME"; then
            echo "$LOG_PREFIX ERROR    Archive Agent: Failed to restart Qdrant server ($CONTAINER_NAME) after update."
            exit 1
        fi
        echo "$LOG_PREFIX INFO     Archive Agent: Qdrant server ($CONTAINER_NAME) restarted successfully after update."
    else
        echo "$LOG_PREFIX INFO     Archive Agent: Qdrant server ($CONTAINER_NAME) was not running, so not restarting."
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
        echo "$LOG_PREFIX ERROR    Archive Agent: Invalid command: $1"
        show_help
        ;;
esac
