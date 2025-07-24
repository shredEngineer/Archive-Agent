#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import logging
from enum import Enum

logger = logging.getLogger(__name__)


class OcrStrategy(Enum):
    # first value is used as default for new profiles
    STRICT = 'strict'
    RELAXED = 'relaxed'
    AUTO = 'auto'


class DecoderSettings:
    """
    Decoder settings.
    """

    def __init__(
            self,
            ocr_strategy: OcrStrategy,
            ocr_auto_threshold: int,
            image_entity_extract: bool,
    ):
        """
        Initialize decoder settings.
        :param ocr_strategy: OCR strategy.
        :param ocr_auto_threshold: Minimum number of characters for `auto` OCR strategy
                                   to resolve to `relaxed` instead of `strict`.
        :param image_entity_extract: True for entity extraction, False for OCR.
        """
        self.ocr_strategy = ocr_strategy
        self.ocr_auto_threshold = ocr_auto_threshold
        self.image_entity_extract = image_entity_extract

        logger.info(f"Using OCR strategy: '{self.ocr_strategy.value}'")

        if self.image_entity_extract:
            logger.info(f"Vision uses entity extraction for image files")
        else:
            logger.info(f"Vision uses OCR for image files")
