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
# en_core_web_md is now a direct dependency (URL spec in pyproject.toml), so
# `uv sync` installs it idempotently — no separate `spacy download` step needed.
uv sync --extra dev

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
