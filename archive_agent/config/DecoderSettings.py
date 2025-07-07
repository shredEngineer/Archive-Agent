#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import logging
from enum import Enum

logger = logging.getLogger(__name__)


class OcrStrategy(Enum):
    AUTO = 'auto'
    STRICT = 'strict'
    RELAXED = 'relaxed'


class DecoderSettings:
    """
    Decoder settings.
    """

    def __init__(
            self,
            ocr_strategy: OcrStrategy,
            ocr_auto_threshold: int,
    ):
        """
        Initialize decoder settings.
        :param ocr_strategy: OCR strategy.
        :param ocr_auto_threshold: Minimum number of characters for `auto` OCR strategy
                                   to resolve to `relaxed` instead of `strict`.
        """
        self.ocr_strategy = ocr_strategy
        self.ocr_auto_threshold = ocr_auto_threshold

        logger.info(f"Using OCR strategy: '{self.ocr_strategy}'")
