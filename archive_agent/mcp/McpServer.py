#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import logging
import json
import asyncio
from typing import Dict, Any, List, cast

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
import uvicorn

from archive_agent.core.ContextManager import ContextManager
from archive_agent.ai_schema.QuerySchema import QuerySchema
from qdrant_client.models import ScoredPoint

logger = logging.getLogger(__name__)


class McpServer:
    """
    JSON-RPC MCP server with SSE keep-alive.
    """

    def __init__(self, context: ContextManager, port: int):
        """
        Initialize MCP server.
        :param context: Context manager.
        :param port: Port.
        """
        self.context = context
        self.port = port
        self.app = FastAPI()
        self._setup_routes()

    def start(self) -> None:
        """
        Start MCP server.
        """
        logger.info(f"MCP server running on http://localhost:{self.port}/")
        uvicorn.run(self.app, host="0.0.0.0", port=self.port, log_level="info")

    def _setup_routes(self) -> None:
        """
        Setup HTTP routes for JSON-RPC and streaming GET.
        """
        @self.app.get("/")
        async def sse_keepalive():
            logger.info("[MCP] GET (SSE keep-alive)")
            async def stream():
                while True:
                    await asyncio.sleep(30)
                    yield ": keep-alive\r\n\r\n"
            return StreamingResponse(stream(), media_type="text/event-stream")

        @self.app.post("/")
        async def mcp_handler(request: Request):
            req_json = await request.json()
            logger.info(f"[MCP] Request: {json.dumps(req_json)}")

            method = req_json.get("method")
            jsonrpc_id = req_json.get("id")
            params = req_json.get("params", {})
            is_jsonrpc = req_json.get("jsonrpc") == "2.0"

            if not is_jsonrpc or not method:
                return self._error_response(jsonrpc_id, -32600, "Invalid JSON-RPC request")

            try:
                match method:
                    case "initialize":
                        return {
                            "jsonrpc": "2.0",
                            "id": jsonrpc_id,
                            "result": {
                                "capabilities": {
                                    "chat": False,
                                    "completion": False,
                                    "tools": True,
                                    "tools/list": True,
                                    "invoke": True
                                },
                                "model": {
                                    "id": "archive-agent",
                                    "name": "Archive Agent",
                                    "description": "Archive Agent",
                                },
                            },
                        }

                    case "notifications/initialized":
                        return {"jsonrpc": "2.0", "id": jsonrpc_id, "result": {}}

                    case "tools/list":
                        return {
                            "jsonrpc": "2.0",
                            "id": jsonrpc_id,
                            "result": {"tools": self._list_tools()}
                        }

                    case "tools/call":
                        tool_name = params.get("name")
                        tool_args = params.get("arguments", {})

                        if not hasattr(self, f"_tool_{tool_name}"):
                            return self._error_response(jsonrpc_id, -32601, f"Tool not found: {tool_name}")

                        tool_method = getattr(self, f"_tool_{tool_name}")

                        result = await tool_method(**tool_args)
                        response = {
                            "jsonrpc": "2.0",
                            "id": jsonrpc_id,
                            "result": result,
                        }
                        logger.info(f"[MCP] Response: {json.dumps(response)}")
                        return response

                    case _:
                        return self._error_response(jsonrpc_id, -32601, f"Unsupported method: {method}")

            except Exception as e:
                logger.exception("[MCP] Tool execution error")
                return self._error_response(jsonrpc_id, -32603, str(e))

    def _error_response(self, id_: Any, code: int, message: str) -> Dict[str, Any]:
        """
        Format a JSON-RPC error response.
        :param id_: JSON-RPC request ID.
        :param code: Error code.
        :param message: Error message.
        :return: JSON-RPC error response.
        """
        return {
            "jsonrpc": "2.0",
            "id": id_,
            "error": {
                "code": code,
                "message": message
            }
        }

    def _list_tools(self) -> List[Dict[str, Any]]:
        """
        List all available MCP tools.
        :return: JSON.
        """
        return [
            {
                "name": "patterns",
                "description": "Get the list of included / excluded patterns.",
                "parameters": {"type": "object"},
            },
            {
                "name": "list",
                "description": "Get the list of tracked files.",
                "parameters": {"type": "object"},
            },
            {
                "name": "diff",
                "description": "Get the list of changed files.",
                "parameters": {"type": "object"},
            },
            {
                "name": "search",
                "description": "Get files matching the question.",
                "parameters": {
                    "type": "object",
                    "properties": {"question": {"type": "string"}},
                    "required": ["question"],
                },
            },
            {
                "name": "query",
                "description": "Get answer using RAG.",
                "parameters": {
                    "type": "object",
                    "properties": {"question": {"type": "string"}},
                    "required": ["question"],
                },
            },
        ]

    async def _tool_patterns(self) -> Dict[str, Any]:
        """
        Get the list of included / excluded patterns.
        :return: JSON.
        """
        result = {
            "included": self.context.watchlist.get_included_patterns(),
            "excluded": self.context.watchlist.get_excluded_patterns()
        }
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(result, indent=2),
                },
            ],
        }

    async def _tool_list(self) -> Dict[str, Any]:
        """
        Get the list of tracked files.
        :return: JSON.
        """
        result = {
            "tracked": list(self.context.watchlist.get_tracked_files()),
        }
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(result, indent=2),
                },
            ],
        }

    async def _tool_diff(self) -> Dict[str, Any]:
        """
        Get the list of changed files.
        :return: JSON.
        """
        result = {
            "added": list(self.context.watchlist.get_diff_files(self.context.watchlist.DIFF_ADDED).keys()),
            "changed": list(self.context.watchlist.get_diff_files(self.context.watchlist.DIFF_CHANGED).keys()),
            "removed": list(self.context.watchlist.get_diff_files(self.context.watchlist.DIFF_REMOVED).keys()),
        }
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(result, indent=2),
                },
            ],
        }

    async def _tool_search(self, question: str) -> Dict[str, Any]:
        """
        Get files matching the question.
        :param question: Question.
        :return: JSON.
        """
        points: List[ScoredPoint] = self.context.qdrant.search(question)
        result = [
            {
                "filepath": point.payload["file_path"],
                "relevance": point.score,
                "last_modified": point.payload["file_mtime"],
            }
            for point in points if point.payload
        ]
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(result, indent=2),
                },
            ],
        }

    async def _tool_query(self, question: str) -> Dict[str, Any]:
        """
        Get answer using RAG.
        :param question: Question.
        :return: JSON.
        """
        query_result, _answer = self.context.qdrant.query(question)
        query_result = cast(QuerySchema, query_result)
        result = {
            "answer_conclusion": query_result.answer_conclusion,
            "answer_list": query_result.answer_list,
            "chunk_ref_list": query_result.chunk_ref_list,
            "further_questions_list": query_result.further_questions_list,
            "reject": query_result.reject,
            "rejection_reason": query_result.rejection_reason,
        }
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(result, indent=2)
                },
            ],
        }
