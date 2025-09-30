#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

from typing import List

from pydantic import BaseModel, ConfigDict, field_validator


class Entity(BaseModel):
    name: str
    description: str

    model_config = ConfigDict(extra='forbid')  # Ensures additionalProperties: false — DO NOT REMOVE THIS

    @field_validator('name', 'description')
    @classmethod
    def strip_newlines(cls, v: str) -> str:
        """Strip newlines from entity fields to ensure single-line output."""
        return ' '.join(v.splitlines()).strip()


class Relation(BaseModel):
    subject: str
    predicate: str
    object: str

    model_config = ConfigDict(extra='forbid')  # Ensures additionalProperties: false — DO NOT REMOVE THIS

    @field_validator('subject', 'predicate', 'object')
    @classmethod
    def strip_newlines(cls, v: str) -> str:
        """Strip newlines from relation fields to ensure single-line output."""
        return ' '.join(v.splitlines()).strip()


class VisionSchema(BaseModel):
    model_config = ConfigDict(extra='forbid')  # Ensures additionalProperties: false — DO NOT REMOVE THIS

    is_rejected: bool
    rejection_reason: str

    entities: List[Entity]
    relations: List[Relation]

    answer: str

    @field_validator('answer')
    @classmethod
    def strip_newlines(cls, v: str) -> str:
        """Strip newlines from answer field to ensure single-line output."""
        return ' '.join(v.splitlines()).strip()
