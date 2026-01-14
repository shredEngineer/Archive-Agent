#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import asyncio
from types import SimpleNamespace
from unittest.mock import Mock

from qdrant_client.models import ScoredPoint

from archive_agent.ai.query.AiQuery import AnswerItem, QuerySchema
from archive_agent.ai.AiManagerFactory import AiManagerFactory
from archive_agent.core.CliManager import CliManager
from archive_agent.db.QdrantManager import QdrantManager
import archive_agent.db.QdrantManager as qdrant_module
from archive_agent.util.knee_detection import find_score_cutoff_index


class FakeAi:
    def __init__(self, rerank_indices, query_schema=None):
        self._rerank_indices = rerank_indices
        self._query_schema = query_schema
        self.rerank_calls = []
        self.query_calls = []

    def embed(self, question):
        return [0.0]

    def rerank(self, question, indexed_chunks):
        self.rerank_calls.append(indexed_chunks)
        return SimpleNamespace(is_rejected=False, reranked_indices=self._rerank_indices)

    def query(self, question, points):
        self.query_calls.append((question, points))
        return self._query_schema


class FakeAiFactory(AiManagerFactory):
    def __init__(self, ai):
        self._ai = ai

    def get_ai(self):
        return self._ai


class FakeQdrantClient:
    def __init__(self, points):
        self._points = points

    async def collection_exists(self, collection_name):
        return True

    async def query_points(self, **kwargs):
        return SimpleNamespace(points=self._points)


def _make_payload(chunk_index, chunk_text):
    return {
        "file_path": "/tmp/test.txt",
        "file_mtime": 0.0,
        "chunk_index": chunk_index,
        "chunks_total": 4,
        "chunk_text": chunk_text,
        "page_range": [1],
        "line_range": None,
    }


def _make_point(score, chunk_index, chunk_text):
    point = Mock(spec=ScoredPoint)
    point.payload = _make_payload(chunk_index, chunk_text)
    point.score = score
    return point


def _make_manager(monkeypatch, points, ai):
    fake_qdrant = FakeQdrantClient(points)
    monkeypatch.setattr(qdrant_module, "AsyncQdrantClient", lambda *args, **kwargs: fake_qdrant)

    cli = CliManager(verbose=False)
    ai_factory = FakeAiFactory(ai)
    return QdrantManager(
        cli=cli,
        ai_factory=ai_factory,
        server_url="http://qdrant.test",
        collection="test",
        vector_size=1,
        retrieve_score_min=0.1,
        retrieve_chunks_max=10,
        retrieve_knee_enable=True,
        retrieve_knee_sensitivity=1.0,
        retrieve_knee_min_chunks=1,
        rerank_chunks_max=10,
        expand_chunks_radius=0,
    )


def _make_query_schema():
    return QuerySchema(
        question_rephrased="What is in scope?",
        answer_list=[
            AnswerItem(
                answer="Answer about retrieval.",
                chunk_ref_list=["<<< 0123456789ABCDEF >>>"]
            )
        ],
        answer_conclusion="Conclusion.",
        follow_up_questions_list=["What else?"],
        is_rejected=False,
        rejection_reason=""
    )


def test_search_applies_knee_cutoff_before_rerank(monkeypatch):
    points = [
        _make_point(0.95, 0, "chunk-0"),
        _make_point(0.94, 1, "chunk-1"),
        _make_point(0.93, 2, "chunk-2"),
        _make_point(0.10, 3, "chunk-3"),
        _make_point(0.09, 4, "chunk-4"),
        _make_point(0.08, 5, "chunk-5"),
    ]
    knee_cutoff = find_score_cutoff_index([p.score for p in points], min_chunks=1)
    assert knee_cutoff is not None
    assert knee_cutoff < len(points)

    rerank_indices = list(range(knee_cutoff - 1, -1, -1))
    ai = FakeAi(rerank_indices=rerank_indices)
    manager = _make_manager(monkeypatch, points, ai)

    result = asyncio.run(manager.search("what is tested"))

    assert result == [points[i] for i in rerank_indices]
    assert ai.rerank_calls == [
        {index: points[index].payload["chunk_text"] for index in range(knee_cutoff)}
    ]


def test_search_without_knee_cutoff_keeps_points(monkeypatch):
    points = [
        _make_point(0.9, 0, "chunk-0"),
        _make_point(0.85, 1, "chunk-1"),
        _make_point(0.8, 2, "chunk-2"),
        _make_point(0.75, 3, "chunk-3"),
        _make_point(0.7, 4, "chunk-4"),
        _make_point(0.65, 5, "chunk-5"),
    ]
    knee_cutoff = find_score_cutoff_index([p.score for p in points], min_chunks=1)
    assert knee_cutoff is None

    rerank_indices = list(range(len(points)))
    ai = FakeAi(rerank_indices=rerank_indices)
    manager = _make_manager(monkeypatch, points, ai)

    result = asyncio.run(manager.search("what is tested"))

    assert result == [points[i] for i in rerank_indices]
    assert ai.rerank_calls == [
        {i: points[i].payload["chunk_text"] for i in range(len(points))}
    ]


def test_expand_points_fetches_neighbors(monkeypatch):
    center_point = _make_point(0.9, 1, "center")
    prev_point = _make_point(0.8, 0, "prev")
    next_point = _make_point(0.7, 2, "next")
    ai = FakeAi(rerank_indices=[])
    manager = _make_manager(monkeypatch, [center_point], ai)
    manager.expand_chunks_radius = 1

    async def fake_get_points(file_path, chunk_indices):
        if chunk_indices == [0]:
            return [prev_point]
        if chunk_indices == [2]:
            return [next_point]
        return []

    monkeypatch.setattr(manager, "_get_points", fake_get_points)

    result = asyncio.run(manager._expand_points([center_point]))

    assert result == [prev_point, center_point, next_point]


def test_dedup_points_keeps_first_occurrence(monkeypatch):
    point_a = _make_point(0.9, 1, "dup-a")
    point_b = _make_point(0.8, 1, "dup-b")
    ai = FakeAi(rerank_indices=[])
    manager = _make_manager(monkeypatch, [], ai)

    result = manager._dedup_points([point_a, point_b])

    assert result == [point_a]


def test_query_uses_search_results_and_formats_answer(monkeypatch):
    points = [
        _make_point(0.9, 0, "chunk-0"),
        _make_point(0.8, 1, "chunk-1"),
    ]
    query_schema = _make_query_schema()
    ai = FakeAi(rerank_indices=[], query_schema=query_schema)
    manager = _make_manager(monkeypatch, points, ai)
    manager.expand_chunks_radius = 0

    async def fake_search(question):
        return points

    monkeypatch.setattr(manager, "search", fake_search)

    result_schema, answer_text = asyncio.run(manager.query("question"))

    assert result_schema == query_schema
    assert "Answer about retrieval." in answer_text
    assert ai.query_calls == [("question", points)]
