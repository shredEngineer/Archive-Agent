#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import logging
from typing import List

from openai import OpenAI, OpenAIError

from archive_agent.schema.ChunkSchema import ChunkSchema
from archive_agent.schema.QuerySchema import QuerySchema
from archive_agent.schema.VisionSchema import VisionSchema
from archive_agent.util.text import prepend_line_numbers
from archive_agent.util import CliManager
from archive_agent.util import RetryManager

logger = logging.getLogger(__name__)


class OpenAiManager(RetryManager):
    """
    OpenAI manager.
    """

    @staticmethod
    def get_prompt_chunk(line_numbered_text: str):
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
            "- Avoid small chunks: Do NOT create chunks smaller than 3 lines unless strictly necessary.",
            "- Only create a new chunk if there is a clear semantic shift or topic boundary.",
            "- Review the entire text before selecting chunk boundaries. Do NOT chunk line by line.",
            "",
            "Text with line numbers:\n\"\"\"\n" + line_numbered_text + "\n\"\"\""
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
            "- `further_questions_list`:",
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
            "    or `further_questions_list`.",
            "- DO NOT cite, explain, or hint at which chunk supports which answer.",
            "- The only valid place to refer to chunks is the `chunk_ref_list` field.",
            "- Every field must follow its format exactly. No extra commentary, no schema deviations.",
            "",
            "Context:\n\"\"\"\n" + context + "\n\"\"\"\n\n",
            "Question:\n\"\"\"\n" + question + "\n\"\"\"\n\n",
            "Answer:"
        ])

    @staticmethod
    def get_prompt_vision():
        return "\n".join([
            "Act as a vision agent for a semantic retrieval system (Retrieval-Augmented Generation / RAG).",
            "Your output will be used in embedding-based search, chunk-level indexing, and precision ranking.",
            "Do NOT summarize or interpret beyond what is visible in the image.",
            "Your goal is to extract clean, modular, maximally relevant units of visual information.",
            "You must output only the `answer`, `reject`, and `rejection_reason` fields, as described below.",
            "Do NOT return any explanations, commentary, or extra metadata.",
            "",
            "RESPONSE FIELDS:",
            "",
            "- `answer`:",
            "    Output format and content depend on the type of visual input (see rules below).",
            "    If the image is visually empty, the `answer` field must contain the exact string: 'Empty image'.",
            "",
            "- `reject`:",
            "    A Boolean flag. Set to `true` ONLY if the image is unreadable or corrupted",
            "    and cannot be meaningfully processed.",
            "    If `reject` is `true`, `answer` must be left blank",
            "    and `rejection_reason` must contain the explanation.",
            "",
            "- `rejection_reason`:",
            "    A short, factual reason for rejection.",
            "    Required ONLY if `reject` is `true`. Leave this field blank if `reject` is `false`.",
            "    Examples: 'image is too blurred to read', 'image file is corrupted',",
            "    'image contains unreadable or distorted text'",
            "",
            "INPUT-TYPE RULES:",
            "",
            "1. Scanned documents, printed articles, books, or typewritten pages:",
            "    - Treat the task as OCR.",
            "    - Output a single plain-text block containing all visible text.",
            "    - Preserve line breaks and reading order exactly as shown.",
            "    - Do NOT add formatting, interpretation, or description.",
            "    - Do NOT segment into sentences or restructure the text.",
            "",
            "2. Handwritten notes, whiteboards, blackboards, or labeled sketches:",
            "    - Output a list of short, discrete sentences describing the content.",
            "    - Transcribe all visible text exactly as shown.",
            "    - Describe diagrams, labels, arrows, formulas, and spatial relationships.",
            "    - All mathematical formulas MUST be in LaTeX and enclosed in inline $...$ delimiters.",
            "    - Do NOT use any other markdown formatting.",
            "",
            "3. Diagrams, charts, figures, technical illustrations, or UI elements:",
            "    - Output a list of atomic sentences describing all semantically relevant visual content.",
            "    - Transcribe visible text exactly as shown.",
            "    - Describe structure, relationships, flow, geometry, and annotations.",
            "    - All formulas MUST be in LaTeX and enclosed in inline $...$ delimiters.",
            "    - Do NOT describe decorative elements, shadows, backgrounds, or textures.",
            "",
            "IMPORTANT GLOBAL CONSTRAINTS:",
            "- Select the correct output behavior based solely on the visual characteristics of the image.",
            "- The `answer` field must strictly follow the rules above — no hybrids, no markdown, no commentary.",
            "- Every output unit must be clean, faithful to the image, and suitable for downstream semantic indexing.",
            "- If `reject` is `true`, `answer` must be blank",
            "    and `rejection_reason` must contain a short, factual reason.",
            "- If the image is visually empty, set `reject` to false and set `answer` to 'Empty image'.",
        ])

    def __init__(
            self,
            cli: CliManager,
            model_chunk: str,
            model_embed: str,
            model_query: str,
            model_vision: str,
            temp_query: float,
            chunk_lines_block: int,
    ):
        """
        Initialize OpenAI manager.
        :param cli: CLI manager.
        :param model_chunk: Model for chunking.
        :param model_embed: Model for embeddings.
        :param model_query: Model for queries.
        :param model_vision: Model for vision.
        :param temp_query: Temperature of query model.
        :param chunk_lines_block: Number of lines per block for chunking.
        """
        self.cli = cli
        self.model_chunk = model_chunk
        self.model_embed = model_embed
        self.model_query = model_query
        self.model_vision = model_vision
        self.temp_query = temp_query
        self.chunk_lines_block = chunk_lines_block

        self.client = OpenAI()

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

    def usage(self) -> None:
        """
        Show usage.
        """
        if any([x > 0 for x in [
            self.total_tokens_chunk, self.total_tokens_embed, self.total_tokens_query, self.total_tokens_vision
        ]]):
            logger.info(
                f"Used OpenAI API token(s): "
                f"({self.total_tokens_chunk}) chunking, "
                f"({self.total_tokens_embed}) embedding, "
                f"({self.total_tokens_query}) query, "
                f"({self.total_tokens_vision}) vision"
            )
        else:
            logger.info(f"No OpenAI API tokens used")

    def chunk(self, sentences: List[str]) -> ChunkSchema:
        """
        Get chunks of sentences.
        :param sentences: Sentences.
        :return: ChunkSchema.
        """
        line_numbered_text = "\n".join(prepend_line_numbers(sentences))

        prompt = self.get_prompt_chunk(line_numbered_text)

        def callback():
            return self.client.responses.create(
                model=self.model_chunk,
                temperature=0,
                input=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_text",
                                "text": prompt,
                            },
                        ],
                    },
                ],
                text={
                    "format": {
                        "type": "json_schema",
                        "name": ChunkSchema.__name__,
                        "schema": ChunkSchema.model_json_schema(),
                        "strict": True,
                    },
                },
            )

        response = self.cli.format_openai_chunk(lambda: self.retry(callback), line_numbered_text)
        if response.usage is not None:  # makes pyright happy
            self.total_tokens_chunk += response.usage.total_tokens

        if hasattr(response, "refusal") and response.refusal:
            raise OpenAIError(response.refusal)

        chunk_result = ChunkSchema.model_validate_json(response.output[0].content[0].text)

        if len(chunk_result.chunk_start_lines) == 0 or chunk_result.chunk_start_lines[0] != 1:
            raise RuntimeError(f"Invalid chunk start lines: {chunk_result.chunk_start_lines}")

        return chunk_result

    def embed(self, text: str) -> List[float]:
        """
        Embed text.
        :param text: Text.
        :return: Embedding vector.
        """
        def callback():
            return self.client.embeddings.create(
                input=text,
                model=self.model_embed,
            )

        response = self.cli.format_openai_embed(lambda: self.retry(callback), text)
        if response.usage is not None:  # makes pyright happy
            self.total_tokens_embed += response.usage.total_tokens
        return response.data[0].embedding

    def query(self, question: str, context: str) -> QuerySchema:
        """
        Get answer to question using RAG.
        :param question: Question.
        :param context: RAG context.
        :return: QuerySchema.
        """
        prompt = self.get_prompt_query(question, context)

        def callback():
            return self.client.responses.create(
                model=self.model_query,
                temperature=self.temp_query,
                input=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_text",
                                "text": prompt,
                            },
                        ],
                    },
                ],
                text={
                    "format": {
                        "type": "json_schema",
                        "name": QuerySchema.__name__,
                        "schema": QuerySchema.model_json_schema(),
                        "strict": True,
                    },
                },
            )

        response = self.cli.format_openai_query(lambda: self.retry(callback), prompt)
        if response.usage is not None:  # makes pyright happy
            self.total_tokens_query += response.usage.total_tokens

        if hasattr(response, "refusal") and response.refusal:
            raise OpenAIError(response.refusal)

        query_result = QuerySchema.model_validate_json(response.output[0].content[0].text)

        return query_result

    def vision(self, image_base64: str) -> VisionSchema:
        """
        Convert image to text.
        :param image_base64: Image as UTF-8 encoded Base64 string.
        :return: VisionSchema.
        """

        def callback():
            return self.client.responses.create(
                model=self.model_vision,
                input=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_text",
                                "text": self.get_prompt_vision()
                            },
                            {
                                "type": "input_image",
                                "image_url": f"data:image/jpeg;base64,{image_base64}",
                            },
                        ],
                    },
                ],
                text={
                    "format": {
                        "type": "json_schema",
                        "name": VisionSchema.__name__,
                        "schema": VisionSchema.model_json_schema(),
                        "strict": True,
                    },
                },
            )

        response = self.cli.format_openai_vision(lambda: self.retry(callback))
        if response.usage is not None:  # makes pyright happy
            self.total_tokens_vision += response.usage.total_tokens

        if response.status == 'incomplete':
            raise OpenAIError("Vision response incomplete, probably due to token limits")

        if hasattr(response, "refusal") and response.refusal:
            raise OpenAIError(response.refusal)

        vision_result = VisionSchema.model_validate_json(response.output[0].content[0].text)

        return vision_result
