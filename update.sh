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
