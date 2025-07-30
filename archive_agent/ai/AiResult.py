#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

from typing import Optional, List
from dataclasses import dataclass, field

from archive_agent.ai.chunk.AiChunk import ChunkSchema
from archive_agent.ai.rerank.AiRerank import RerankSchema
from archive_agent.ai.query.AiQuery import QuerySchema
from archive_agent.ai.vision.AiVisionSchema import VisionSchema


@dataclass
class AiResult:
    """
    AI result.

    💀 💀 💀 DO NOT TOUCH THIS FILE — INSTANCES OF THIS CLASS MAY ALREADY BE CACHED — REFACTORING WOULD BREAK COMPATIBILITY 💀 💀 💀
    """

    total_tokens: int = field(default=0)

    output_text: str = field(default="")

    parsed_schema: Optional[ChunkSchema | RerankSchema | QuerySchema | VisionSchema] = field(default=None)

    embedding: List[float] = field(default_factory=list)
