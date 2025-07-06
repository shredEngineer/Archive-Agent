#!/bin/bash

# Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
# This file is part of Archive Agent. See LICENSE for details.

# Exit on any error
set -e

# 1. Ensure the virtual environment is synced (installs dependencies including dev extras).
#    IMPORTANT: uv sync will remove any packages not declared in pyproject.toml, including spacy data models downloaded separately.

# 2. Download Spacy model. This MUST be done *after* uv sync, as uv sync would have uninstalled it if it was present.
#    The uv run here ensures it's run within the project's environment.
uv run python -m spacy download xx_sent_ud_sm

# 3. Run pytest with code coverage
uv run pytest

# 4. Run pyright
uv run pyright

# 5. Run pycodestyle
uv run pycodestyle archive_agent tests
