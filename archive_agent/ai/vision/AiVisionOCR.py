#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

from archive_agent.ai.vision.AiVisionSchema import VisionSchema
from archive_agent.util.text_util import splitlines_exact


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
            "    Examples: 'image is blank', 'image is too blurred to read', 'image file is corrupted',",
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
    def get_prompt_vision_standalone() -> str:
        """
        OCR prompt for the standalone-ocr-strict command ONLY.

        Unlike `get_prompt_vision()` (used by the RAG ingestion pipeline, which collapses
        the result into a single line), this prompt asks for structured Markdown so the
        standalone output file carries the document's hierarchy. It also explicitly
        suppresses page numbers, headers, and footers. This prompt MUST NOT be used by
        the regular ingestion pipeline.
        """
        return "\n".join([
            "Act as an OCR agent that transcribes a single document page into clean, structured Markdown.",
            "Your task is to faithfully reproduce all readable text together with the visual structure of the page.",
            "You must output structured information using the exact response fields described below.",
            "Do not return any explanations, commentary, or additional fields.",
            "",
            "RESPONSE FIELDS:",
            "",
            "- `answer`:",
            "    The page content transcribed as Markdown (see MARKDOWN TRANSCRIPTION RULES below).",
            "",
            "- `is_rejected`:",
            "    A Boolean flag. Set `is_rejected: true` ONLY if the image is unreadable or corrupted",
            "    and cannot be meaningfully processed.",
            "    If `is_rejected` is true, leave `answer` blank and populate `rejection_reason`.",
            "",
            "- `rejection_reason`:",
            "    A short, factual reason for rejection.",
            "    Required ONLY if `is_rejected` is `true`. Leave this field blank if `is_rejected` is `false`.",
            "    Examples: 'image is blank', 'image is too blurred to read', 'image file is corrupted'",
            "",
            "ADDITIONAL REQUIRED BLANK FIELDS:",
            "- `entities`: Empty list.",
            "- `relations`: Empty list.",
            "",
            "MARKDOWN TRANSCRIPTION RULES:",
            "    - Transcribe the body text of the page exactly as shown",
            "      (see CONTENT TO EXCLUDE below for what must be omitted).",
            "    - Reproduce the document's structure using Markdown:",
            "        - Use Markdown headings (`#`, `##`, `###`, ...) for titles and section headings,",
            "          reflecting the visual heading hierarchy.",
            "        - Separate distinct paragraphs with a single blank line.",
            "        - Use Markdown list syntax (`-` or `1.`) for itemized or enumerated content.",
            "    - Preserve line breaks ONLY at structurally significant boundaries (between headings,",
            "      paragraphs, list items, and displayed equations).",
            "    - Join lines that belong to the same paragraph or sentence into a single line —",
            "      do NOT preserve mid-paragraph visual line wrapping.",
            "    - Join words that are hyphenated across a line break into a single word (remove the hyphen).",
            "    - Ignore purely visual layout artifacts such as columns, borders, and pagination.",
            "    - All mathematical formulas MUST be in LaTeX: inline math enclosed in $...$,",
            "      and displayed or numbered equations on their own line.",
            "    - In LaTeX every command uses exactly ONE backslash: write \\sim, \\mu, \\mu_B,",
            "      \\vec{E} — NOT \\\\sim or \\\\mu. Never double a backslash or escape it,",
            "      not even inside Markdown list items.",
            "",
            "CONTENT TO EXCLUDE (this is NOT body text — OMIT it completely from `answer`):",
            "    - Page numbers. A page number is an isolated number (usually 1-3 digits) printed",
            "      alone in the top or bottom margin, separated from the body text. When you see",
            "      such an isolated marginal number, DROP it entirely: do not place it on its own",
            "      line, and do not attach it to the preceding or following text.",
            "    - Running headers and running footers: repeated page titles, author names,",
            "      journal names, DOIs, or arXiv identifiers printed in the top or bottom margin.",
            "    - Note: numbers that are part of a sentence, a citation, a list, or an equation",
            "      label such as (12) ARE body text — keep those. Only marginal page numbers and",
            "      running headers/footers are excluded.",
            "",
            "FIGURE AND DIAGRAM RULES:",
            "    - For embedded figures, labeled diagrams, charts, or illustrations:",
            "        - Output a concise, sentence-level description of what is visually present,",
            "          focusing on labels, arrows, flow, structure, and spatial relationships.",
            "    - DO NOT describe decorative elements, shadows, backgrounds, or textures.",
            "",
            "IMPORTANT GLOBAL CONSTRAINTS:",
            "- The `answer` field MUST contain ONLY the transcribed Markdown — no commentary, no code fences.",
            "- Be faithful to the image; do not invent, summarize, translate, or reorder content.",
            "- Only set `is_rejected: true` if the image is technically unreadable or corrupted",
            "  (e.g. blurred, distorted, broken file).",
            "- ALWAYS include the additional required blank `entities` and `relations` fields.",
            "",
            "Image input is provided separately.",
        ])

    @staticmethod
    def format_vision_answer(vision_result: VisionSchema) -> str:
        """
        Format vision result as single line (without linebreaks — required for downstream logic).
        """
        return " ".join(splitlines_exact(vision_result.answer)).strip()

    @staticmethod
    def format_vision_answer_multiline(vision_result: VisionSchema) -> str:
        r"""
        Format vision result preserving line breaks (for standalone OCR Markdown output).

        Unlike `format_vision_answer`, this does NOT collapse lines into a single line.
        Line endings are normalized to '\n' and surrounding whitespace is stripped.
        Used ONLY by the standalone-ocr-strict command, so the Markdown carries structure.
        """
        return "\n".join(splitlines_exact(vision_result.answer)).strip()
