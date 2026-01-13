#!/bin/bash

#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

# Unset conda environment variables to prevent uv conflicts
unset CONDA_DEFAULT_ENV CONDA_PREFIX

# Get the script's directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cd "$SCRIPT_DIR"
uv run archive-agent "$@"
