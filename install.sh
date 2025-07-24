#!/bin/bash

# Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
# This file is part of Archive Agent. See LICENSE for details.

# Exit on any error
set -e

# Script permissions
chmod +x archive-agent.sh
chmod +x audit.sh
chmod +x manage-qdrant.sh

echo ""
echo ".------------."
echo "| Install uv |"
echo "'------------'"
# https://docs.astral.sh/uv/getting-started/installation/#standalone-installer
curl -LsSf https://astral.sh/uv/install.sh | sh

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
echo ".-----------------------."
echo "| (sudo) Install pandoc |"
echo "'-----------------------'"
sudo apt update && sudo apt install -y pandoc

echo ""
echo ".------------------------------."
echo "| (sudo) Install Qdrant server |"
echo "'------------------------------'"
sudo ./manage-qdrant.sh start

echo ""
echo ".-----------------------."
echo "| Install command alias |"
echo "'-----------------------'"
ALIAS_DEFINITION="alias archive-agent='$(pwd)/archive-agent.sh'"
if grep -Fxq "$ALIAS_DEFINITION" ~/.bashrc; then
    echo "Alias 'archive-agent' already exists in ~/.bashrc."
else
    echo "Adding 'archive-agent' alias to ~/.bashrc..."
    echo "$ALIAS_DEFINITION" >> ~/.bashrc
    echo "Alias added. Please run 'source ~/.bashrc' or open a new terminal to use it."
fi

echo ""
echo ".---------------------------------------."
echo "| Archive Agent: Successfully installed |"
echo "'---------------------------------------'"
echo ""
