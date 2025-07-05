#!/bin/bash

# Exit on any error
set -e

# --- Dependencies ---
echo "Installing Python dependencies with Poetry..."
poetry install

echo "Downloading spaCy model..."
poetry run python -m spacy download xx_sent_ud_sm

echo "Installing system packages (pandoc, python3-tk)..."
sudo apt install -y pandoc python3-tk

# --- Permissions ---
echo "Setting script permissions..."
chmod +x *.sh

# --- Alias Setup ---
ALIAS_DEFINITION="alias archive-agent='$(pwd)/archive-agent.sh'"
if grep -Fxq "$ALIAS_DEFINITION" ~/.bashrc; then
    echo "Alias 'archive-agent' already exists in ~/.bashrc."
else
    echo "Adding 'archive-agent' alias to ~/.bashrc..."
    echo "$ALIAS_DEFINITION" >> ~/.bashrc
    echo "Alias added. Please run 'source ~/.bashrc' or open a new terminal to use it."
fi

echo "Installation script finished."
