# archive_agent/mcp_server/McpServer.py
#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import logging
from typing import Dict, Any, List, cast, Optional

from archive_agent.core.ContextManager import ContextManager

from archive_agent.ai.query.AiQuery import QuerySchema

from qdrant_client.models import ScoredPoint
from archive_agent.db.QdrantSchema import parse_payload

logger = logging.getLogger(__name__)


# Server stuff...
from mcp.server.fastmcp import FastMCP
from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.routing import Mount, Route
import uvicorn


mcp = FastMCP("Archive-Agent")


@mcp.tool()
async def get_patterns() -> Dict[str, Any]:
    """
    Get the list of included / excluded patterns.
    :return: {"included": [filename], "excluded": [filename]}.
    """
    global _context
    assert _context is not None  # makes pyright happy
    return {
        "included": _context.watchlist.get_included_patterns(),
        "excluded": _context.watchlist.get_excluded_patterns()
    }


@mcp.tool()
async def get_files_tracked() -> Dict[str, Any]:
    """
    Get the list of tracked files.
    :return: {"tracked": [filename]}.
    """
    global _context
    assert _context is not None  # makes pyright happy
    _context.watchlist.track()
    return {
        "tracked": list(_context.watchlist.get_tracked_files()),
    }


@mcp.tool()
async def get_files_changed() -> Dict[str, Any]:
    """
    Get the list of changed files.
    :return: {"added": [filename], "changed": [filename], "removed": [filename]}.
    """
    global _context
    assert _context is not None  # makes pyright happy
    _context.watchlist.track()
    return {
        "added": list(_context.watchlist.get_diff_files(_context.watchlist.DIFF_ADDED).keys()),
        "changed": list(_context.watchlist.get_diff_files(_context.watchlist.DIFF_CHANGED).keys()),
        "removed": list(_context.watchlist.get_diff_files(_context.watchlist.DIFF_REMOVED).keys()),
    }


@mcp.tool()
async def get_search_result(question: str) -> Dict[str, Any]:
    """
    Get the list of files relevant to the question.
    :param question: Question.
    :return: {file_path: relevance_score, ...}.
    """
    global _context
    assert _context is not None  # makes pyright happy
    points: List[ScoredPoint] = await _context.qdrant.search(question)
    return {
        parse_payload(point.payload).file_path: point.score
        for point in points
    }


@mcp.tool()
async def get_answer_rag(question: str) -> Dict[str, Any]:
    """
    Get answer to question using RAG.
    :param question: Question.
    :return: {
        "question_rephrased": str,
        "answer_list": [{"answer": str, "chunk_ref_list": List[str]}],
        "answer_conclusion": str,
        "follow_up_questions_list": List[str],
        "is_rejected": bool,
        "rejection_reason": Optional[str]
    }.
    """
    global _context
    assert _context is not None  # makes pyright happy
    query_result, _answer = await _context.qdrant.query(question)
    query_result = cast(QuerySchema, query_result)

    return {
        "question_rephrased":       query_result.question_rephrased,
        "answer_list":              [{"answer": item.answer, "chunk_ref_list": item.chunk_ref_list} for item in query_result.answer_list],
        "answer_conclusion":        query_result.answer_conclusion,
        "follow_up_questions_list": query_result.follow_up_questions_list,
        "is_rejected":              query_result.is_rejected,
        "rejection_reason":         query_result.rejection_reason,
    }


_context: Optional[ContextManager] = None


class McpServer:
    """
    MCP server.
    """

    def __init__(self, context: ContextManager, host: str, port: int):
        """
        Initialize MCP server.
        :param context: Context manager.
        :param host: Host.
        :param port: Port.
        """
        global _context
        _context = context

        self.host = host
        self.port = port

        # noinspection PyProtectedMember
        mcp_server = mcp._mcp_server
        sse = SseServerTransport("/messages/")

        async def handle_sse(request: Request) -> None:
            # noinspection PyProtectedMember
            async with sse.connect_sse(
                    request.scope,
                    request.receive,
                    request._send,
            ) as (read_stream, write_stream):
                await mcp_server.run(
                    read_stream,
                    write_stream,
                    mcp_server.create_initialization_options(),
                )

        self.app = Starlette(
            debug=True,
            routes=[
                Route("/sse", endpoint=handle_sse),
                Mount("/messages/", app=sse.handle_post_message),
            ],
        )

        logger.info(f"MCP server running on http://{self.host}:{self.port}/")

    def start(self):
        """
        Start MCP server.
        """
        uvicorn.run(self.app, host=self.host, port=self.port)
