#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import logging
from enum import Enum

logger = logging.getLogger(__name__)


class OcrStrategy(Enum):
    RELAXED = 'relaxed'
    STRICT = 'strict'


class DecoderSettings:
    """
    Decoder settings.
    """

    def __init__(self, ocr_strategy: OcrStrategy):
        """
        Initialize decoder settings.
        :param ocr_strategy: OCR strategy.
        """
        self.ocr_strategy = ocr_strategy

        logger.info(f"Using OCR strategy: '{self.ocr_strategy}'")
