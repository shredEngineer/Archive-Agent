#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

from pydantic import BaseModel, ConfigDict
from typing import List


class Entity(BaseModel):
    name: str
    description: str

    model_config = ConfigDict(extra='forbid')  # Ensures additionalProperties: false


class Relation(BaseModel):
    subject: str
    predicate: str
    object: str

    model_config = ConfigDict(extra='forbid')  # Ensures additionalProperties: false


class VisionSchema(BaseModel):
    entities: List[Entity]
    relations: List[Relation]
    is_rejected: bool
    rejection_reason: str

    model_config = ConfigDict(extra='forbid')  # Ensures additionalProperties: false
