#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

from typing import List
from pydantic import BaseModel, ConfigDict


class QuerySchema(BaseModel):
    question_rephrased: str
    answer_list: List[str]
    answer_conclusion: str
    chunk_ref_list: List[str]
    follow_up_list: List[str]
    reject: bool
    rejection_reason: str

    model_config = ConfigDict(extra='forbid')  # Ensures additionalProperties: false
