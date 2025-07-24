#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import logging

from archive_agent.ai.vision.AiVisionSchema import VisionSchema

logger = logging.getLogger(__name__)


class AiVisionOCR:

    @staticmethod
    def get_prompt_vision() -> str:
        return "\n".join([
            "Act as a vision agent for a semantic retrieval system (Retrieval-Augmented Generation / RAG).",
            "Your task is to extract clean, modular, maximally relevant units of visual information from an image.",
            "You must output structured information using the exact response fields described below.",
            "Do not return any explanations, commentary, or additional fields.",
            "",
            "RESPONSE FIELDS:",
            "",
            "- `answer`:",
            "    Output format and content depend on the type of visual input (see input-type rules below).",
            "",
            "- `is_rejected`:",
            "    A Boolean flag. Set `is_rejected: true` ONLY if the image is unreadable or corrupted",
            "    and cannot be meaningfully processed.",
            "    If `is_rejected` is true, leave `answer` blank and populate `rejection_reason`.",
            "",
            "- `rejection_reason`:",
            "    A short, factual reason for rejection.",
            "    Required ONLY if `is_rejected` is `true`. Leave this field blank if `is_rejected` is `false`.",
            "    Examples: 'image is too blurred to read', 'image file is corrupted',",
            "    'image contains unreadable or distorted text'",
            "",
            "ADDITIONAL REQUIRED BLANK FIELDS:"
            "",
            "- `entities`: Empty list."
            "- `relations`: Empty list."
            "",
            "EXTRACTION RULE SETS:",
            "",
            "- TEXT EXTRACTION RULES:",
            "    - Transcribe all visible text exactly as shown.",
            "    - Preserve natural reading order and line breaks.",
            "    - Retain structural hierarchy when meaningful, but ignore visual layout artifacts such as columns,",
            "      pagination, or borders.",
            "    - DO NOT use any formatting, interpretation, or commentary.",
            "    - All output must be optimized for downstream semantic indexing in RAG systems.",
            "",
            "- VISUAL DESCRIPTION RULES:",
            "    - For any embedded figures, labeled diagrams, UI elements, or illustrations:",
            "        - Output a concise, sentence-level description of what is visually present.",
            "        - Focus on semantic content such as labels, arrows, flow, structure, and spatial relationships.",
            "    - All mathematical formulas MUST be in LaTeX and enclosed in inline $...$ delimiters.",
            "    - DO NOT describe decorative elements, shadows, backgrounds, or textures.",
            "    - DO NOT add interpretation, commentary, or markdown formatting.",
            "",
            "INPUT-TYPE RULES:",
            "",
            "1. Scanned documents, printed articles, books, or typewritten pages:",
            "    - Apply TEXT EXTRACTION RULES to capture all readable text.",
            "    - Apply VISUAL DESCRIPTION RULES to any embedded figures or labeled diagrams.",
            "",
            "2. Handwritten notes, whiteboards, blackboards, labeled sketches, diagrams, charts, figures,",
            "    technical illustrations, or UI elements:",
            "    - Apply both TEXT EXTRACTION RULES and VISUAL DESCRIPTION RULES.",
            "    - Output a sequence of concise, discrete sentences in plain paragraph form.",
            "",
            "IMPORTANT GLOBAL CONSTRAINTS:",
            "- Select the correct output behavior based solely on the visual characteristics of the image.",
            "- The `answer` field MUST strictly follow the rules above — no hybrids, no markdown, no commentary.",
            "- Every output unit MUST be clean, faithful to the image, and suitable for downstream semantic indexing.",
            "- Only set `is_rejected: true` if the image is technically unreadable or corrupted, and cannot be interpreted",
            "  meaningfully (e.g. blurred, distorted, broken file).",
            "- ALWAYS include the additional required blank `entities` and `relations` fields.",
            "",
            "Image input is provided separately.",
        ])

    @staticmethod
    def format_vision_answer(vision_result: VisionSchema) -> str:
        """
        Format vision result as single line (without linebreaks — required for downstream logic).
        """
        return " ".join(vision_result.answer.splitlines())
