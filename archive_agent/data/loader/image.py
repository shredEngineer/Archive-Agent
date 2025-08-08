#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

from logging import Logger
from typing import Set, Optional, Callable

from PIL import Image, UnidentifiedImageError

from archive_agent.ai.AiManager import AiManager
from archive_agent.ai.AiManagerFactory import AiManagerFactory
from archive_agent.data.DocumentContent import DocumentContent
from archive_agent.core.ProgressManager import ProgressInfo

from archive_agent.util.format import format_file
from archive_agent.util.text_util import splitlines_exact
from archive_agent.util.PageTextBuilder import PageTextBuilder


ImageToTextCallback = Callable[[AiManager, Image.Image, ProgressInfo], Optional[str]]


def is_image(file_path: str) -> bool:
    """
    Checks if the given file path has a valid image extension.
    :param file_path: File path.
    :return: True if the file path has a valid image extension, False otherwise.
    """
    extensions: Set[str] = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
    return any(file_path.lower().endswith(ext) for ext in extensions)


def load_image(
        ai_factory: AiManagerFactory,
        logger: Logger,
        file_path: str,
        image_to_text_callback: Optional[ImageToTextCallback],
        progress_info: ProgressInfo,
) -> Optional[DocumentContent]:
    """
    Load image as text with progress tracking.
    :param ai_factory: AI manager factory for creating AI instance.
    :param logger: Logger.
    :param file_path: File path.
    :param image_to_text_callback: Optional image-to-text callback.
    :param progress_info: Progress tracking information.
    :return: Document content if successful, None otherwise.
    """
    try:
        image = Image.open(file_path).convert("RGB")
    except (FileNotFoundError, UnidentifiedImageError) as e:
        logger.error(f"Failed to load {format_file(file_path)}: {e}")
        return None

    if image_to_text_callback is None:
        logger.warning(f"Image vision is DISABLED in your current configuration")
        return None

    # Determine progress total based on callback type (1 for single, 2 for combined)
    # For single image files, we need to set the correct total for the callback
    callback_total = 2 if image_to_text_callback.__name__ == 'image_to_text_combined' else 1
    # Create vision AI sub-task for progress tracking
    vision_ai_progress_key = progress_info.progress_manager.start_task(
        "AI Vision", parent=progress_info.parent_key, total=callback_total
    )

    # Original business logic: get AI instance and call callback directly
    ai = ai_factory.get_ai()
    callback_progress_info = progress_info.progress_manager.create_progress_info(vision_ai_progress_key)
    image_text = image_to_text_callback(ai, image, callback_progress_info)

    progress_info.progress_manager.complete_task(vision_ai_progress_key)

    if image_text is None:
        return None
    assert len(splitlines_exact(image_text)) == 1, f"Text from image must be single line:\n'{image_text}'"

    return PageTextBuilder(text=image_text).getDocumentContent()
