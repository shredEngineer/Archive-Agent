#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

from logging import Logger
import os
from typing import Set, Optional, List

import io
from PIL import Image
import zipfile
import pypandoc
from charset_normalizer import from_path

from archive_agent.ai.AiManagerFactory import AiManagerFactory
from archive_agent.util.format import format_file
from archive_agent.data.loader.image import ImageToTextCallback
from archive_agent.data.processor.VisionProcessor import VisionProcessor, VisionRequest
from archive_agent.data.loader.image import is_image
from archive_agent.util.text_util import utf8_tempfile
from archive_agent.util.LineTextBuilder import LineTextBuilder
from archive_agent.core.ProgressManager import ProgressInfo

from archive_agent.data.DocumentContent import DocumentContent


def is_plaintext(file_path: str) -> bool:
    """
    Check for valid plaintext extension.
    :param file_path: File path.
    :return: True if valid plaintext extension, False otherwise.
    """
    extensions: Set[str] = {".txt", ".md", ".markdown"}
    return any(file_path.lower().endswith(ext) for ext in extensions)


def load_plaintext(
        logger: Logger,
        file_path: str,
) -> Optional[DocumentContent]:
    """
    Load plaintext.
    :param logger: Logger.
    :param file_path: File path.
    :return: Document content if successful, None otherwise.
    """
    try:
        matches = from_path(file_path)
    except IOError as e:
        logger.error(f"Failed to read {format_file(file_path)}: {e}")
        return None

    best_match = matches.best()
    if best_match is None:
        logger.error(f"Failed to decode {format_file(file_path)}: Best match is None")
        return None

    text = str(best_match)

    return LineTextBuilder(text=text).getDocumentContent()


def is_ascii_document(file_path: str) -> bool:
    """
    Check for valid ASCII document extension.
    :param file_path: File path.
    :return: True if valid ASCII document extension, False otherwise.
    """
    extensions: Set[str] = {".html", ".htm"}
    return any(file_path.lower().endswith(ext) for ext in extensions)


def load_ascii_document(
        logger: Logger,
        file_path: str,
) -> Optional[DocumentContent]:
    """
    Load ASCII document (using Pandoc).
    :param logger: Logger.
    :param file_path: File path.
    :return: Document content if successful, None otherwise.
    """
    file_ext = os.path.splitext(file_path)[1].lower()

    raw_text_doc = load_plaintext(logger=logger, file_path=file_path)
    if raw_text_doc is None:
        return None

    raw_text = raw_text_doc.text  # Only text, not lines, as Pandoc will re-wrap lines

    # Pandoc refuses `.htm` extension, so make it `.html`.
    if file_ext == ".htm":
        file_ext = ".html"

    tmp_path = utf8_tempfile(raw_text, suffix=file_ext)

    try:
        text = pypandoc.convert_file(tmp_path, to="plain", format=file_ext.lstrip("."), extra_args=["--wrap=preserve"])
        text = text.encode("utf-8", errors="replace").decode("utf-8")

        return LineTextBuilder(text=text).getDocumentContent()

    except Exception as e:
        logger.error(f"Failed to convert {format_file(file_path)} via Pandoc: {e}")
        return None

    finally:
        try:
            if tmp_path is not None:
                os.remove(tmp_path)
        except Exception as e:
            logger.error(f"Failed to delete temporary file {tmp_path}: {e}")


def is_binary_document(file_path: str) -> bool:
    """
    Check for valid binary document extension.
    :param file_path: File path.
    :return: True if valid binary document extension, False otherwise.
    """
    extensions: Set[str] = {".odt", ".docx"}
    return any(file_path.lower().endswith(ext) for ext in extensions)


def load_binary_document(
        ai_factory: AiManagerFactory,
        logger: Logger,
        verbose: bool,
        file_path: str,
        max_workers_vision: int,
        image_to_text_callback: Optional[ImageToTextCallback],
        progress_info: ProgressInfo,
) -> Optional[DocumentContent]:
    """
    Load binary document (using Pandoc).
    :param ai_factory: AI manager factory.
    :param logger: Logger.
    :param verbose: Enable verbose output.
    :param file_path: File path.
    :param max_workers_vision: Max. workers for vision.
    :param image_to_text_callback: Optional image-to-text callback.
    :param progress_info: Progress tracking information
    :return: Document content if successful, None otherwise.
    """
    file_ext = os.path.splitext(file_path)[1].lower()

    try:
        text = pypandoc.convert_file(file_path, to="plain", format=file_ext.lstrip("."), extra_args=["--wrap=preserve"])
        text = text.encode("utf-8", errors="replace").decode("utf-8")
    except Exception as e:
        logger.error(f"Failed to convert {format_file(file_path)} via Pandoc: {e}")
        return None

    # Stage 1: Text extraction (unchanged)
    builder = LineTextBuilder(text=text)

    # Stage 2: Image extraction (unchanged)
    images = load_binary_document_images(logger=logger, file_path=file_path)

    # Stage 3: Vision processing (new function, same logic)
    image_texts = extract_binary_image_texts(
        ai_factory,
        logger,
        verbose,
        file_path,
        max_workers_vision,
        images,
        image_to_text_callback,
        progress_info,
    )

    # Stage 4: Assembly (new function)
    return build_binary_document_with_images(builder, image_texts)


def extract_binary_image_texts(
        ai_factory: AiManagerFactory,
        logger: Logger,
        verbose: bool,
        file_path: str,
        max_workers_vision: int,
        images: List[Image.Image],
        image_to_text_callback: Optional[ImageToTextCallback],
        progress_info: ProgressInfo,
) -> List[str]:
    """
    Extract text from binary document images with parallel processing.
    :param ai_factory: AI manager factory.
    :param logger: Logger.
    :param verbose: Enable verbose output.
    :param file_path: File path.
    :param max_workers_vision: Max. workers for vision.
    :param images: List of PIL Images.
    :param image_to_text_callback: Optional image-to-text callback.
    :param progress_info: Progress tracking information.
    :return: List of formatted image texts.
    """
    image_texts = []

    if not images:
        return image_texts

    if image_to_text_callback is None:
        logger.warning(f"Image vision is DISABLED in your current configuration")
        logger.warning(f"IGNORING ({len(images)}) document image(s)")
        return image_texts

    # Create VisionProcessor for batch processing
    vision_processor = VisionProcessor(ai_factory, logger, verbose, file_path, max_workers_vision)
    vision_requests = []

    # Collect all vision requests
    for image_index, image in enumerate(images):
        log_header = f"Image ({image_index + 1}) / ({len(images)})"

        if verbose:
            logger.info(f"{log_header}: Queueing")

        # Formatter lambda with consistent bracket logic for binary docs
        formatter = lambda vision_result: f"[{vision_result}]" if vision_result is not None else "[Unprocessable Image]"

        vision_request = VisionRequest(
            image_data=image,
            callback=image_to_text_callback,
            formatter=formatter,
            log_header=f"{log_header}: Converting to text",
            image_index=image_index,
            page_index=0  # Binary docs are single-page
        )
        vision_requests.append(vision_request)

    if not vision_requests:
        return image_texts

    # Update progress total now that we know the number of vision requests
    progress_info.progress_manager.set_total(progress_info.parent_key, len(vision_requests))

    # Process all requests in parallel
    vision_results = vision_processor.process_vision_requests_parallel(
        vision_requests, progress_info
    )

    return vision_results


def build_binary_document_with_images(
        base_builder: LineTextBuilder,
        image_texts: List[str]
) -> Optional[DocumentContent]:
    """
    Assemble final document with image texts appended.
    :param base_builder: Base document builder with text content.
    :param image_texts: List of formatted image texts.
    :return: Document content.
    """
    # Append image texts to builder
    for image_text in image_texts:
        base_builder.push()
        base_builder.push(image_text)  # Already formatted
        base_builder.push()

    return base_builder.getDocumentContent()


def load_binary_document_images(
        logger: Logger,
        file_path: str,
) -> List[Image.Image]:
    """
    Extract images from binary document.
    :param logger: Logger.
    :param file_path: File path.
    :return: Images.
    """
    images = []
    try:
        with zipfile.ZipFile(file_path, "r") as archive:
            for zip_file_path in archive.namelist():
                if is_image(zip_file_path):
                    # noinspection PyUnresolvedReferences
                    with archive.open(zip_file_path) as image_stream:
                        image = Image.open(io.BytesIO(image_stream.read()))
                        image.load()  # Prevent lazy I/O; load into memory NOW.
                        images.append(image)
    except Exception as e:
        logger.error(f"Failed to extract image(s) from {format_file(file_path)}: {e}")

    return images
