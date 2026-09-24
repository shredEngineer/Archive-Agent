#!/bin/bash

# Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
# This file is part of Archive Agent. See LICENSE for details.

# Exit on any error
set -e

CONTAINER_NAME="archive-agent-qdrant-server"

# Qdrant's API key is the workstation password LOCAL_AUTH_PASSWORD.
# sudo strips the environment, so pass it through explicitly:
#   sudo --preserve-env=LOCAL_AUTH_PASSWORD ./manage-qdrant.sh start

# Function to display help message
show_help() {
    echo "Usage: sudo --preserve-env=LOCAL_AUTH_PASSWORD $0 [start|stop|update|recreate]"
    echo "  start:    Ensures the Qdrant server container is running."
    echo "  stop:     Stops the Qdrant server container."
    echo "  update:   Pulls the latest Qdrant Docker image and recreates the container on it (storage is kept)."
    echo "  recreate: Removes and recreates the container (applies a new API key or image; storage is kept)."
    exit 1
}

# Function to fail closed if the API key is missing
require_api_key() {
    if [ -z "${LOCAL_AUTH_PASSWORD:-}" ]; then
        echo "Archive Agent: Qdrant server: ERROR: LOCAL_AUTH_PASSWORD is not set; refusing to run Qdrant without an API key."
        echo "Archive Agent: Qdrant server: Run: sudo --preserve-env=LOCAL_AUTH_PASSWORD $0 $1"
        exit 1
    fi
}

# Function to check if the existing container was created with an API key
container_has_api_key() {
    docker inspect --format '{{range .Config.Env}}{{println .}}{{end}}' "$CONTAINER_NAME" | grep -q '^QDRANT__SERVICE__API_KEY=.'
}

# Function to refuse (re)starting a container that was created without an API key
require_container_api_key() {
    if ! container_has_api_key; then
        echo "Archive Agent: Qdrant server: ERROR: Container was created without an API key."
        echo "Archive Agent: Qdrant server: Run: sudo --preserve-env=LOCAL_AUTH_PASSWORD $0 recreate"
        exit 1
    fi
}

# Function to create and start a new container
run_qdrant() {
    require_api_key "$1"
    # `-e VAR` without a value takes it from docker's environment, keeping the key off the command line.
    if ! QDRANT__SERVICE__API_KEY="$LOCAL_AUTH_PASSWORD" docker run -d \
        --name "$CONTAINER_NAME" \
        --restart unless-stopped \
        -p 127.0.0.1:6333:6333 \
        -e QDRANT__SERVICE__API_KEY \
        -v ~/.archive-agent-qdrant-storage:/qdrant/storage \
        qdrant/qdrant; then
        echo "Archive Agent: Qdrant server: ERROR: Failed to start."
        exit 1
    fi
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
        require_container_api_key
        echo "Archive Agent: Qdrant server: Already running."
    else
        if container_exists; then
            require_container_api_key
            echo "Archive Agent: Qdrant server: Restarting..."
            if ! docker start "$CONTAINER_NAME"; then
                echo "Archive Agent: Qdrant server: ERROR: Failed to restart."
                exit 1
            fi
            echo "Archive Agent: Qdrant server: Restarted successfully."
        else
            echo "Archive Agent: Qdrant server: Starting for the first time..."
            run_qdrant start
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
# `docker start` reuses the image a container was created from, so a pulled image
# only takes effect once the container is recreated. The pull runs first, while
# Qdrant keeps serving; the container is only touched once the new image is there.
update_qdrant() {
    require_api_key update
    if container_exists; then
        require_container_api_key
    fi

    echo "Archive Agent: Qdrant server: Pulling latest Qdrant Docker image (qdrant/qdrant)..."
    if ! docker pull qdrant/qdrant; then
        echo "Archive Agent: Qdrant server: ERROR: Failed to pull latest Qdrant Docker image. Container left as it was."
        exit 1
    fi

    if ! container_exists; then
        echo "Archive Agent: Qdrant server: No container yet. Run start to create it."
        return
    fi

    if [ "$(docker inspect --format '{{.Image}}' "$CONTAINER_NAME")" = "$(docker image inspect --format '{{.Id}}' qdrant/qdrant)" ]; then
        echo "Archive Agent: Qdrant server: Already on the latest image. No action needed."
        return
    fi

    local was_running=false
    if container_is_running; then
        was_running=true
    fi

    echo "Archive Agent: Qdrant server: Recreating container on the new image (storage is kept)..."
    if ! docker rm -f "$CONTAINER_NAME"; then
        echo "Archive Agent: Qdrant server: ERROR: Failed to remove container."
        exit 1
    fi
    run_qdrant update

    if $was_running; then
        echo "Archive Agent: Qdrant server: Updated and running."
    else
        docker stop "$CONTAINER_NAME" >/dev/null
        echo "Archive Agent: Qdrant server: Updated; left stopped as it was."
    fi
}

# Function to recreate the Qdrant server container
recreate_qdrant() {
    # Check before removing anything, so a missing key never leaves Qdrant down.
    require_api_key recreate
    if container_exists; then
        echo "Archive Agent: Qdrant server: Removing container (storage is kept)..."
        if ! docker rm -f "$CONTAINER_NAME"; then
            echo "Archive Agent: Qdrant server: ERROR: Failed to remove container."
            exit 1
        fi
    fi
    echo "Archive Agent: Qdrant server: Creating container..."
    run_qdrant recreate
    echo "Archive Agent: Qdrant server: Recreated successfully."
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
    recreate)
        recreate_qdrant
        ;;
    *)
        echo "Archive Agent: Qdrant server: ERROR: Invalid command: $1"
        show_help
        ;;
esac
