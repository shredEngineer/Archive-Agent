from typing import List

from pydantic import BaseModel, ConfigDict


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
    model_config = ConfigDict(extra='forbid')  # Ensures additionalProperties: false — DO NOT REMOVE THIS

    is_rejected: bool
    rejection_reason: str

    entities: List[Entity]
    relations: List[Relation]

    answer: str
