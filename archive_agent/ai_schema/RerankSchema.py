#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

from typing import List
from pydantic import BaseModel, ConfigDict


class ChunkSchema(BaseModel):
    chunk_start_lines: List[int]

    model_config = ConfigDict(extra='forbid')  # Ensures additionalProperties: false
