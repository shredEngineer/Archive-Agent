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
            "You are a semantic chunking agent. Your task is to segment the text into semantically coherent chunks ",
            "for use in Retrieval-Augmented Generation (RAG).",
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
            "Act as a Retrieval-Augmented Generation (RAG) agent.",
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
            "    If `reject` is true, leave ALL other fields blank.",
            "",
            "IMPORTANT GLOBAL CONSTRAINTS:",
            "- DO NOT mention chunk numbers, chunk IDs, or file paths in `answer_list`, `answer_conclusion`, ",
            "  or `further_questions_list`.",
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
            "You are a vision agent for Retrieval-Augmented Generation (RAG).",
            "Your task is to extract and describe all visually relevant information from the input image.",
            "Focus on precision, structure, and semantic relevance.",
            "",
            "You must output only the `answer` and `reject` fields, as described below.",
            "Do not return any other fields or metadata.",
            "",
            "RESPONSE FIELDS:",
            "",
            "- `answer`:",
            "    One or more dense, well-structured paragraphs describing the visual content.",
            "    Extract visible written text verbatim with maximum accuracy.",
            "    Describe relationships only between meaningful visual elements, such as:",
            "    - Diagrams and labels",
            "    - Formulas and annotations",
            "    - UI components and values",
            "    Focus on core content and avoid describing minor artifacts (e.g. grid lines, page edges).",
            "",
            "- `reject`:",
            "    A Boolean flag. Set `reject: true` ONLY if the image is completely unreadable, corrupted, or blank.",
            "    If `reject` is `true`, leave ALL other fields blank.",
            "",
            "VISUAL INPUT TYPES:",
            "- Notes (handwritten or typed)",
            "- Whiteboards and blackboards",
            "- Screenshots (focus on foreground window or video frame)",
            "- Diagrams, forms, and documents",
            "- Photos of scenes, labels, signs, and structured surfaces",
            "",
            "IMPORTANT:",
            "- Be concise but comprehensive. Prioritize semantic structure over pixel-by-pixel detail.",
            "- Extract what matters. Ignore decorative, structural, or irrelevant visual noise.",
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
