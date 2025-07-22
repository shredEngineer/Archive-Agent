#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import json
import hashlib


class AiProviderParams:
    """
    AI provider parameters.
    """

    def __init__(
            self,
            model_chunk: str,
            model_embed: str,
            model_rerank: str,
            model_query: str,
            model_vision: str,
            temperature_query: float,
    ):
        """
        Initialize AI provider parameters.
        :param model_chunk: Model for chunking.
        :param model_embed: Model for embeddings.
        :param model_rerank: Model for reranking.
        :param model_query: Model for queries.
        :param model_vision: Model for vision (leave empty to disable vision support).
        :param temperature_query: Temperature of query model.
        """
        self.model_chunk = model_chunk
        self.model_embed = model_embed
        self.model_rerank = model_rerank
        self.model_query = model_query
        self.model_vision = model_vision
        self.temperature_query = temperature_query

    def get_static_cache_key(self) -> str:
        """
        Get static cache key.
        :return: Deterministic SHA-256 hash over AI provider parameters.
        """
        params = {
            'model_chunk': self.model_chunk,
            'model_embed': self.model_embed,
            'model_rerank': self.model_rerank,
            'model_vision': self.model_vision,

            # NOTE: Do NOT include query-related parameters, as queries are NOT cached anyway.
            # 'model_query': self.model_query,
            # 'temperature_query': self.temperature_query,
        }

        key_str = json.dumps(params, sort_keys=True)

        # noinspection PyTypeChecker
        return hashlib.sha256(key_str.encode('utf-8')).hexdigest()
