#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import logging

logger = logging.getLogger(__name__)


class DecoderSettings:
    """
    Decoder settings.
    """

    def __init__(self, ocr_mode_strict: str):
        """
        Initialize decoder settings.
        """
        self.ocr_mode_strict: bool = ocr_mode_strict.strip().lower() == "true"

        if self.ocr_mode_strict:
            logger.warning(f"Strict OCR mode is ENABLED in your current configuration")
