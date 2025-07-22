#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

from typing import List
from pydantic import BaseModel, ConfigDict


class AnswerItem(BaseModel):
    answer: str
    chunk_ref_list: List[str]
    model_config = ConfigDict(extra='forbid')  # Ensures additionalProperties: false


class QuerySchema(BaseModel):
    question_rephrased: str
    answer_list: List[AnswerItem]
    answer_conclusion: str
    follow_up_questions_list: List[str]
    is_rejected: bool
    rejection_reason: str

    model_config = ConfigDict(extra='forbid')  # Ensures additionalProperties: false
