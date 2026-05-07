#!/bin/bash

# Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
# This file is part of Archive Agent. See LICENSE for details.

# Exit on any error
set -e

echo ""
echo ".---------------------."
echo "| Pull latest changes |"
echo "'---------------------'"
git pull

echo ""
echo ".---------------------."
echo "| Install environment |"
echo "'---------------------'"
uv sync --extra dev

echo ""
echo ".---------------------."
echo "| Install spaCy model |"
echo "'---------------------'"
# Idempotent: only download if the model isn't already importable. spacy's `download`
# always uninstall+reinstalls (~33 MB) — skipping when present saves bandwidth and time.
if uv run python -c "import en_core_web_md" >/dev/null 2>&1; then
    echo "en_core_web_md already installed, skipping download"
else
    uv run python -m spacy download en_core_web_md
fi

echo ""
echo ".-------------------------------------."
echo "| Archive Agent: Successfully updated |"
echo "'-------------------------------------'"
echo ""

echo ""
echo ".---------------------------------------------------------------."
echo "| INFO: It's advised to clear AI cache — delete these folders:  |"
echo "|                                                               |"
echo "|       ~/.archive-agent-settings/<your_profile_name>/ai_cache/ |"
echo "'---------------------------------------------------------------'"
echo ""
