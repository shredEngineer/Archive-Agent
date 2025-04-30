#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import logging
from typing import cast, List

from archive_agent.ai.AiResult import AiResult
from archive_agent.ai_provider.AiProvider import AiProvider

from archive_agent.ai_schema.ChunkSchema import ChunkSchema
from archive_agent.ai_schema.QuerySchema import QuerySchema
from archive_agent.ai_schema.VisionSchema import VisionSchema

from archive_agent.util.CliManager import CliManager
from archive_agent.util.RetryManager import RetryManager
from archive_agent.util.text_util import prepend_line_numbers

logger = logging.getLogger(__name__)


class AiManager(RetryManager):
    """
    AI manager.
    """

    @staticmethod
    def get_prompt_chunk(line_numbered_text: str) -> str:
        return "\n".join([
            "Act as a chunking agent for a semantic retrieval system (Retrieval-Augmented Generation / RAG).",
            "Your task is to segment the text into semantically coherent chunks.",
            "You must output only the `chunk_start_lines` field, as described below.",
            "Do not return any explanations or additional fields.",
            "",
            "RESPONSE FIELD:",
            "",
            "- `chunk_start_lines`:",
            "    A list of line numbers marking the start of each chunk.",
            "    The first element MUST be 1, since the first chunk always starts at line 1.",
            "    The list must be unique and monotonically increasing.",
            "",
            "CHUNKING GUIDELINES:",
            "- Consider both well-structured text and unordered note dumps.",
            "- Group content based on semantic relatedness, not formatting or superficial structure.",
            "- Each chunk must contain a coherent, self-contained unit of meaning.",
            "- Avoid small chunks: Do NOT create chunks smaller than 10 lines unless strictly necessary.",
            "- Only create a new chunk if there is a clear semantic shift or topic boundary.",
            "- Review the entire text before selecting chunk boundaries. Do NOT chunk line by line.",
            "",
            "Text with line numbers:\n\"\"\"\n" + line_numbered_text + "\n\"\"\"",
        ])

    @staticmethod
    def get_prompt_query(question: str, context: str):
        return "\n".join([
            "Act as a RAG query agent for a semantic retrieval system (Retrieval-Augmented Generation / RAG).",
            "Your only source of truth is the provided context. Do NOT use any other knowledge.",
            "You must output structured information using the exact response fields described below.",
            "",
            "RESPONSE FIELDS:",
            "",
            "- `question_rephrased`:",
            "    Rephrase the original question using context-aware language.",
            "    Preserve the original intent while clarifying ambiguity if needed.",
            "",
            "- `answer_list`:",
            "    A list of detailed, complete answers directly based on the provided context.",
            "    Each answer must explain a distinct point clearly and thoroughly.",
            "    DO NOT mention, reference, or allude to any chunk numbers, chunk IDs, file paths, or metadata.",
            "    DO NOT indicate which chunk the answer is from.",
            "    DO NOT include citations or provenance of any kind.",
            "    Each entry must stand on its own as an informative, self-contained response.",
            "",
            "- `answer_conclusion`:",
            "    A short, precise summary of the main ideas expressed in `answer_list`.",
            "    DO NOT introduce new information.",
            "",
            "- `chunk_ref_list`:",
            "    A list of reference designators indicating which chunks informed the answers.",
            "    These MUST follow the exact format: `<<< Chunk (X) / (Y) of file://... @ YYYY-MM-DD HH:MM:SS >>>`.",
            "    DO NOT shorten or omit any part of the file URI.",
            "    DO NOT include any chunk references anywhere else except in this list.",
            "",
            "- `follow_up_list`:",
            "    A list of specific, well-formed follow-up questions that build on the material.",
            "    Each question must be self-contained;",
            "    do NOT reference 'the answer', 'the context', or prior responses.",
            "",
            "- `reject`:",
            "    A Boolean flag. Set `reject: true` ONLY if the context contains no relevant information whatsoever.",
            "    If `reject` is true, leave ALL other fields blank except `rejection_reason`.",
            "",
            "- `rejection_reason`:",
            "    A short, factual reason for rejection.",
            "    Required ONLY if `reject` is `true`. Leave this field blank if `reject` is `false`.",
            "    Examples: 'context is entirely unrelated', 'context is empty',",
            "    'context contains no answerable material'",
            "",
            "IMPORTANT GLOBAL CONSTRAINTS:",
            "- DO NOT mention chunk numbers, chunk IDs, or file paths in `answer_list`, `answer_conclusion`,",
            "    or `follow_up_list`.",
            "- DO NOT cite, explain, or hint at which chunk supports which answer.",
            "- The only valid place to refer to chunks is the `chunk_ref_list` field.",
            "- Every field must follow its format exactly. No extra commentary, no schema deviations.",
            "",
            "Context:\n\"\"\"\n" + context + "\n\"\"\"\n\n",
            "Question:\n\"\"\"\n" + question + "\n\"\"\"\n\n",
            "Answer:",
        ])

    @staticmethod
    def get_prompt_vision():
        return "\n".join([
            "Act as a vision agent for a semantic retrieval system (Retrieval-Augmented Generation / RAG).",
            "Your task is to extract clean, modular, maximally relevant units of visual information from an image.",
            "You must output structured information using the exact response fields described below.",
            "DO NOT return any explanations, commentary, or extra metadata.",
            "",
            "RESPONSE FIELDS:",
            "",
            "- `answer`:",
            "    Output format and content depend on the type of visual input (see input-type rules below).",
            "    If the image contains no legible text, figures, or meaningful visual content, the `answer` field MUST",
            "    contain the exact string: 'Empty image'.",
            "",
            "- `reject`:",
            "    A Boolean flag. Set `reject: true` ONLY if the image is unreadable or corrupted",
            "    and cannot be meaningfully processed.",
            "    If `reject` is true, leave `answer` blank and populate `rejection_reason`.",
            "",
            "- `rejection_reason`:",
            "    A short, factual reason for rejection.",
            "    Required ONLY if `reject` is `true`. Leave this field blank if `reject` is `false`.",
            "    Examples: 'image is too blurred to read', 'image file is corrupted',",
            "    'image contains unreadable or distorted text'",
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
            "- If the image has no legible text or meaningful visual content (e.g. a blank page, unlabeled form,",
            "  empty whiteboard), set `reject: false` and set `answer` to 'Empty image'.",
            "- Only set `reject: true` if the image is technically unreadable or corrupted, and cannot be interpreted",
            "  meaningfully (e.g. blurred, distorted, broken file).",
            "",
            "Image input is provided separately.",
        ])

    def __init__(
            self,
            ai_provider: AiProvider,
            cli: CliManager,
            chunk_lines_block: int,
    ):
        """
        Initialize AI manager.
        :param ai_provider: AI provider.
        :param cli: CLI manager.
        :param chunk_lines_block: Number of lines per block for chunking.
        """
        self.ai_provider = ai_provider

        self.cli = cli

        self.chunk_lines_block = chunk_lines_block

        self.total_tokens_chunk = 0
        self.total_tokens_embed = 0
        self.total_tokens_query = 0
        self.total_tokens_vision = 0

        RetryManager.__init__(
            self,
            predelay=0,
            delay_min=0,
            delay_max=60,
            backoff_exponent=2,
            retries=10,
        )

        if not self.ai_provider.supports_vision:
            logger.warning(f"Image vision is DISABLED in your current configuration")

    def usage(self) -> None:
        """
        Show usage.
        """
        if any([x > 0 for x in [
            self.total_tokens_chunk, self.total_tokens_embed, self.total_tokens_query, self.total_tokens_vision
        ]]):
            logger.info(
                f"Used AI API token(s): "
                f"({self.total_tokens_chunk}) chunking, "
                f"({self.total_tokens_embed}) embedding, "
                f"({self.total_tokens_query}) query, "
                f"({self.total_tokens_vision}) vision"
            )
        else:
            logger.info(f"No AI API tokens used")

    def chunk(self, sentences: List[str]) -> ChunkSchema:
        """
        Get chunks of sentences.
        :param sentences: Sentences.
        :return: ChunkSchema.
        """
        line_numbered_text = "\n".join(prepend_line_numbers(sentences))
        prompt = self.get_prompt_chunk(line_numbered_text)
        callback = lambda: self.ai_provider.chunk_callback(prompt)

        result: AiResult = self.cli.format_openai_chunk(lambda: self.retry(callback), line_numbered_text)
        self.total_tokens_chunk += result.total_tokens

        assert result.parsed_schema is not None
        result.parsed_schema = cast(ChunkSchema, result.parsed_schema)
        if len(result.parsed_schema.chunk_start_lines) == 0 or result.parsed_schema.chunk_start_lines[0] != 1:
            raise RuntimeError(f"Invalid chunk start lines: {result.parsed_schema.chunk_start_lines}")

        return result.parsed_schema

    def embed(self, text: str) -> List[float]:
        """
        Embed text.
        :param text: Text.
        :return: Embedding vector.
        """
        callback = lambda: self.ai_provider.embed_callback(text)

        result: AiResult = self.cli.format_openai_embed(lambda: self.retry(callback), text)
        self.total_tokens_embed += result.total_tokens
        assert result.embedding is not None
        return result.embedding

    def query(self, question: str, context: str) -> QuerySchema:
        """
        Get answer to question using RAG.
        :param question: Question.
        :param context: RAG context.
        :return: QuerySchema.
        """
        prompt = self.get_prompt_query(question, context)
        callback = lambda: self.ai_provider.query_callback(prompt)

        result: AiResult = self.cli.format_openai_query(lambda: self.retry(callback), prompt)
        self.total_tokens_query += result.total_tokens
        assert result.parsed_schema is not None
        result.parsed_schema = cast(QuerySchema, result.parsed_schema)
        return result.parsed_schema

    def vision(self, image_base64: str) -> VisionSchema:
        """
        Convert image to text.
        :param image_base64: Image as UTF-8 encoded Base64 string.
        :return: VisionSchema.
        """
        prompt = self.get_prompt_vision()
        callback = lambda: self.ai_provider.vision_callback(prompt, image_base64)

        result: AiResult = self.cli.format_openai_vision(lambda: self.retry(callback))
        self.total_tokens_vision += result.total_tokens
        assert result.parsed_schema is not None
        result.parsed_schema = cast(VisionSchema, result.parsed_schema)
        return result.parsed_schema
