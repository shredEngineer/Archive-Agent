#!/bin/bash

#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

CONTAINER_NAME="archive-agent-qdrant-server"

if docker ps --filter "name=$CONTAINER_NAME" --filter "status=running" --format "{{.Names}}" | grep -q "^$CONTAINER_NAME$"; then
	echo "$(date '+%Y-%m-%d %H:%M:%S') [INFO] Archive Agent: Qdrant server ($CONTAINER_NAME) is running"
else
	if docker ps -a --filter "name=$CONTAINER_NAME" --format "{{.Names}}" | grep -q "^$CONTAINER_NAME$"; then
		echo "$(date '+%Y-%m-%d %H:%M:%S') [INFO] Archive Agent: Qdrant server ($CONTAINER_NAME) is restarting..."
		docker start "$CONTAINER_NAME"
	else
		echo "$(date '+%Y-%m-%d %H:%M:%S') [INFO] Archive Agent: Qdrant server ($CONTAINER_NAME) is starting..."
		docker run -d \
			--name "$CONTAINER_NAME" \
			--restart unless-stopped \
			-p 6333:6333 \
			-v ~/.archive-agent-qdrant-storage:/qdrant/storage \
			qdrant/qdrant
	fi
fi
