#!/bin/bash

#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

LOCKFILE="/tmp/archive-agent.lock"

# Acquire exclusive lock, or exit if already locked
exec 200>"$LOCKFILE"
flock -n 200 || {
    echo "[archive-agent.sh] is already running. Exiting."
    exit 1
}

# Get the script's directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cd "$SCRIPT_DIR"
./ensure-qdrant.sh
poetry run archive-agent "$@"
