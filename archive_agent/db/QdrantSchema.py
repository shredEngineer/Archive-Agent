#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator, ValidationError


class QdrantPayload(BaseModel):
    """
    Pydantic model for Qdrant point payloads, ensuring type safety and validation.
    Mandatory fields are required; optionals default to None for backward compatibility.
    """
    file_path: str = Field(..., description="File path (mandatory).")
    file_mtime: float = Field(..., description="File modification time (mandatory).")
    chunk_index: int = Field(..., description="Chunk index (mandatory).")
    chunks_total: int = Field(..., description="Total chunks (mandatory).")
    chunk_text: str = Field(..., description="Chunk text (mandatory).")
    version: Optional[str] = Field(None, description="Version (optional, added in v7.4.0).")
    page_range: Optional[List[int]] = Field(None, description="Page range (optional, added in v5.0.0).")
    line_range: Optional[List[int]] = Field(None, description="Line range (optional, added in v5.0.0).")

    model_config = {"extra": "forbid"}  # Prevents unknown fields, keeping payloads clean.

    @model_validator(mode='after')
    def validate_ranges(self) -> 'QdrantPayload':
        """
        Custom validator: Ensure at most one of page_range or line_range is set (project-specific rule).
        Also normalizes empty ranges to None for consistency.
        """
        # Normalize empty ranges to None
        if self.page_range is not None and len(self.page_range) == 0:
            self.page_range = None
        if self.line_range is not None and len(self.line_range) == 0:
            self.line_range = None

        # Ensure mutual exclusivity
        if self.page_range is not None and self.line_range is not None:
            raise ValueError("Payload cannot have both 'page_range' and 'line_range' set.")
        return self


def parse_payload(payload_dict: Optional[Dict[str, Any]]) -> QdrantPayload:
    """
    Parse and validate a raw payload dict into the QdrantPayload model.
    Raises ValueError if payload_dict is None, or ValidationError on invalid data (e.g., missing mandatory field).
    This ensures all accesses crash on bad payloads, as required.
    :param payload_dict: Raw dict from Qdrant (or None).
    :return: Validated QdrantPayload instance.
    :raises ValueError: If payload_dict is None.
    :raises ValidationError: If dict is invalid (e.g., missing 'file_path', wrong types).
    """
    if payload_dict is None:
        raise ValueError("Qdrant point payload cannot be None.")
    try:
        return QdrantPayload(**payload_dict)
    except ValidationError as e:
        # Re-raise the original ValidationError (Pydantic errors are already informative)
        raise e
