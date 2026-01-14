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
uv run python -m spacy download en_core_web_md

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
