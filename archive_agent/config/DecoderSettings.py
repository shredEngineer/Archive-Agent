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
            image_ocr: bool,
            image_entity_extract: bool,
    ):
        """
        Initialize decoder settings.
        :param ocr_strategy: OCR strategy.
        :param ocr_auto_threshold: Minimum number of characters for `auto` OCR strategy
                                   to resolve to `relaxed` instead of `strict`.
        :param image_entity_extract: Enables OCR.
        :param image_entity_extract: Enables entity extraction.
        """
        self.ocr_strategy = ocr_strategy
        self.ocr_auto_threshold = ocr_auto_threshold
        self.image_ocr = image_ocr
        self.image_entity_extract = image_entity_extract

        logger.info(f"Using OCR strategy: '{self.ocr_strategy.value}'")

        vision_features = []

        if self.image_ocr:
            vision_features.append('OCR')

        if self.image_entity_extract:
            vision_features.append('Entity Extraction')

        vision_features_str = ", ".join(vision_features)

        logger.info(f"Enabled vision feature(s): {vision_features_str}")
