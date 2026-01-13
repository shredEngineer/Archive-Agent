#!/bin/bash

# Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
# This file is part of Archive Agent. See LICENSE for details.

# Exit on any error
set -e

# Unset conda environment variables to prevent uv conflicts
unset CONDA_DEFAULT_ENV CONDA_PREFIX

uv run pytest --cov=archive_agent --cov-report=term-missing

PYRIGHT_PYTHON_FORCE_VERSION=latest uv run pyright

uv run pycodestyle archive_agent tests
