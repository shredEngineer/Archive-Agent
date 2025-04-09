#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

from pydantic import BaseModel


class VisionSchema(BaseModel):
    answer: str
    reject: bool

    class Config:
        extra = "forbid"  # Ensures additionalProperties: false
