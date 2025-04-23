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
logging.basicConfig(level=logging.INFO)


class McpServer:
    """
    JSON-RPC MCP server with SSE keep-alive.
    """

    def __init__(self, context: ContextManager, port: int):
        """
        Initialize the MCP server.
        :param context: Application context manager.
        :param port: Port to listen on.
        """
        self.context = context
        self.port = port
        self.app = FastAPI()
        self._setup_routes()

    def start(self) -> None:
        """
        Start the Uvicorn server to serve MCP endpoints.
        """
        logger.info(f"MCP server running on http://localhost:{self.port}/")
        uvicorn.run(self.app, host="0.0.0.0", port=self.port, log_level="info")

    def _setup_routes(self) -> None:
        """
        Define the HTTP routes for JSON-RPC and streaming GET.
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
            logger.info(f"[MCP] POST body: {json.dumps(req_json)}")

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
                                    "chat": True,
                                    "completion": True,
                                    "tools": True,
                                    "tools/list": True,
                                    "invoke": True
                                },
                                "model": {
                                    "id": "archive-agent-gpt4",
                                    "name": "Archive Agent GPT-4.1",
                                    "description": "Archive Agent powered by GPT-4.1"
                                }
                            }
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
                        logger.info(f"[MCP] Tool '{tool_name}' response: {json.dumps(response)}")
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
        """
        return [
            {
                "name": "patterns",
                "description": "Get the list of included / excluded patterns.",
                "parameters": {"type": "object"}
            },
            {
                "name": "list",
                "description": "Get the list of tracked files.",
                "parameters": {"type": "object"}
            },
            {
                "name": "diff",
                "description": "Get the list of changed files.",
                "parameters": {"type": "object"}
            },
            {
                "name": "search",
                "description": "Lists files matching the question.",
                "parameters": {
                    "type": "object",
                    "properties": {"question": {"type": "string"}},
                    "required": ["question"]
                }
            },
            {
                "name": "query",
                "description": "Answers your question using RAG.",
                "parameters": {
                    "type": "object",
                    "properties": {"question": {"type": "string"}},
                    "required": ["question"]
                }
            },
            {
                "name": "test",
                "description": "Returns the string 'Test'.",
                "parameters": {"type": "object"}
            }
        ]

    async def _tool_test(self) -> Dict[str, Any]:
        """
        Return a fixed test string inside a proper JSON-RPC result structure.
        """
        return {
            "content": [
                {"type": "text", "text": "Test"}
            ]
        }

    async def _tool_patterns(self) -> Dict[str, Any]:
        """
        Get the list of included / excluded patterns.
        """
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps({
                        "included": self.context.watchlist.get_included_patterns(),
                        "excluded": self.context.watchlist.get_excluded_patterns()
                    }, indent=2)
                }
            ]
        }

    async def _tool_list(self) -> Dict[str, Any]:
        """
        Get the list of tracked files.
        """
        tracked = self.context.watchlist.get_tracked_files() or {}
        result = [
            {
                "filepath": path,
                "size": meta.get("size", 0),
                "mtime": meta.get("mtime", 0)
            }
            for path, meta in tracked.items()
        ]
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(result, indent=2)
                }
            ]
        }

    async def _tool_diff(self) -> Dict[str, Any]:
        """
        Get the list of changed files.
        """
        diff = {
            "added": list(self.context.watchlist.get_diff_files(self.context.watchlist.DIFF_ADDED).keys()),
            "changed": list(self.context.watchlist.get_diff_files(self.context.watchlist.DIFF_CHANGED).keys()),
            "removed": list(self.context.watchlist.get_diff_files(self.context.watchlist.DIFF_REMOVED).keys())
        }
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(diff, indent=2)
                }
            ]
        }

    async def _tool_search(self, question: str) -> Dict[str, Any]:
        """
        Lists files matching the question.
        """
        points: List[ScoredPoint] = self.context.qdrant.search(question)
        result = [
            {
                "filepath": point.payload["file_path"],
                "relevance": point.score,
                "last_modified": point.payload["file_mtime"]
            }
            for point in points if point.payload
        ]
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(result, indent=2)
                }
            ]
        }

    async def _tool_query(self, question: str) -> Dict[str, Any]:
        """
        Answers your question using RAG.
        """
        query_result, _ = self.context.qdrant.query(question)
        query_result = cast(QuerySchema, query_result)
        result = {
            "answer": query_result.answer_conclusion,
            "details": query_result.answer_list,
            "sources": query_result.chunk_ref_list,
            "follow_ups": query_result.further_questions_list,
            "rejected": query_result.reject,
            "rejection_reason": query_result.rejection_reason
        }
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(result, indent=2)
                }
            ]
        }
