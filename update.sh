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
echo ".-----------------------."
echo "| Install Archive Agent |"
echo "'-----------------------'"
./install.sh

echo ""
echo ".-------------------------------------."
echo "| Archive Agent: Successfully updated |"
echo "'-------------------------------------'"
echo ""

echo ""
echo ".--------------------------------------------------------------------------------------."
echo "| INFO: It's strongly advised to clear each profile's AI cache — delete these folders: |"
echo "|                                                                                      |"
echo "|       ~/.archive-agent-settings/<your_profile_name>/ai_cache/                        |"
echo "'--------------------------------------------------------------------------------------'"
echo ""
