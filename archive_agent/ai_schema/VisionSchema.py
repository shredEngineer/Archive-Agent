#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

from pydantic import BaseModel, ConfigDict


class VisionSchema(BaseModel):
    answer: str
    is_rejected: bool
    rejection_reason: str

    model_config = ConfigDict(extra='forbid')  # Ensures additionalProperties: false
