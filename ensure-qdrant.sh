#!/bin/bash

#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

CONTAINER_NAME="archive-agent-qdrant-server"

if docker ps --filter "name=$CONTAINER_NAME" --filter "status=running" --format "{{.Names}}" | grep -q "^$CONTAINER_NAME$"; then
	echo " ✅ Archive Agent Qdrant server is running."
else
	echo " ❌ Archive Agent Qdrant server is NOT running."

	if docker ps -a --filter "name=$CONTAINER_NAME" --format "{{.Names}}" | grep -q "^$CONTAINER_NAME$"; then
		echo " 🔁 Restarting existing container '$CONTAINER_NAME'..."
		docker start "$CONTAINER_NAME"
	else
		echo " 🚀 Starting new container '$CONTAINER_NAME'..."
		docker run -d \
			--name "$CONTAINER_NAME" \
			--restart unless-stopped \
			-p 6333:6333 \
			-v ~/.archive-agent/qdrant_storage:/qdrant/storage \
			qdrant/qdrant
	fi
fi
