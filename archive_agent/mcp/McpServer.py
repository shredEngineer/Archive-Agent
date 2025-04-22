#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import logging
import json
import asyncio
from typing import Dict, Any, List, cast

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
import uvicorn
from qdrant_client.models import ScoredPoint

from archive_agent.core.ContextManager import ContextManager
from archive_agent.ai_schema.QuerySchema import QuerySchema

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class McpServer:
    """
    Model Context Protocol (MCP) server using HTTP SSE transport.
    Compatible with VS Code and Roo Code Agent Mode.
    """
    def __init__(self, context: ContextManager, port: int):
        """
        Initialize the MCP server.
        :param context: Application context manager.
        :param port: Port for the HTTP server.
        """
        self.context = context
        self.port = port
        self.app = FastAPI()
        self._setup_routes()

    def start(self) -> None:
        """
        Start the MCP server using Uvicorn.
        """
        logger.info(f"MCP server running on http://localhost:{self.port}/")
        uvicorn.run(self.app, host="0.0.0.0", port=self.port, log_level="info")

    def _setup_routes(self) -> None:
        """
        Set up the root endpoint for both GET and POST to handle MCP protocol.
        """
        @self.app.api_route("/", methods=["GET", "POST"])
        async def mcp_handler(request: Request):
            logger.info(f"[MCP] {request.method} {request.url.path} from {request.client.host}:{request.client.port}")
            if request.method == "POST":
                try:
                    req_json = await request.json()
                    logger.info(f"[MCP] POST body: {json.dumps(req_json)}")
                    # Support both classic MCP and JSON-RPC 2.0 (VS Code)
                    msg_type = req_json.get("type")
                    jsonrpc_method = req_json.get("method")
                    jsonrpc_id = req_json.get("id")
                    is_jsonrpc = "jsonrpc" in req_json and jsonrpc_method is not None
                    logger.info(f"[MCP] Handling message type: {msg_type or jsonrpc_method}")

                    # Handle JSON-RPC initialize
                    if is_jsonrpc and jsonrpc_method == "initialize":
                        logger.info("[MCP] Responding to JSON-RPC initialize handshake")
                        result = {
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
                        return {
                            "jsonrpc": req_json["jsonrpc"],
                            "id": jsonrpc_id,
                            "result": result
                        }
                    
                    # Handle notifications/initialized
                    if is_jsonrpc and jsonrpc_method == "notifications/initialized":
                        logger.info("[MCP] Client initialization completed")
                        return {}  # Return empty response for notifications as per JSON-RPC spec
                    
                    # Handle JSON-RPC tools/list
                    if is_jsonrpc and jsonrpc_method == "tools/list":
                        logger.info("[MCP] Responding to JSON-RPC tools/list request")
                        return {
                            "jsonrpc": req_json["jsonrpc"],
                            "id": jsonrpc_id,
                            "result": {"tools": self._list_tools()}
                        }

                    # Handle classic MCP initialize
                    if msg_type == "initialize":
                        logger.info("[MCP] Responding to classic MCP initialize handshake")
                        return {
                            "type": "initialize",
                            "capabilities": {
                                "chat": True,
                                "completion": True
                            },
                            "model": {
                                "id": "archive-agent-gpt4",
                                "name": "Archive Agent GPT-4.1",
                                "description": "Archive Agent powered by GPT-4.1"
                            }
                        }
                    # For other message types, stream SSE events
                    async def stream():
                        try:
                            # JSON-RPC tool invoke
                            if is_jsonrpc and jsonrpc_method == "invoke":
                                tool = req_json.get("params", {}).get("tool")
                                args = req_json.get("params", {}).get("input", {})
                                logger.info(f"[MCP] Invoking tool (JSON-RPC): {tool} with args: {args}")
                                result = self._invoke(tool, args)
                                payload = {
                                    "jsonrpc": req_json["jsonrpc"],
                                    "id": jsonrpc_id,
                                    "result": {"tool": tool, "output": result}
                                }
                                yield f"data: {json.dumps(payload)}\r\n\r\n"
                            # Classic MCP list
                            elif msg_type == "list":
                                logger.info("[MCP] Handling 'list' tools request")
                                payload = {
                                    "type": "list",
                                    "tools": self._list_tools()
                                }
                                yield f"data: {json.dumps(payload)}\r\n\r\n"
                            # Classic MCP invoke
                            elif msg_type == "invoke":
                                tool = req_json.get("tool")
                                args = req_json.get("input", {})
                                logger.info(f"[MCP] Invoking tool: {tool} with args: {args}")
                                result = self._invoke(tool, args)
                                payload = {
                                    "type": "invoke_result",
                                    "tool": tool,
                                    "output": result
                                }
                                yield f"data: {json.dumps(payload)}\r\n\r\n"
                            else:
                                logger.info(f"[MCP] Unsupported message type: {msg_type or jsonrpc_method}")
                                error_payload = {"error": "Unsupported message type"}
                                if is_jsonrpc:
                                    error_payload = {
                                        "jsonrpc": req_json["jsonrpc"],
                                        "id": jsonrpc_id,
                                        "error": {"code": -32601, "message": "Unsupported method"}
                                    }
                                yield f"data: {json.dumps(error_payload)}\r\n\r\n"
                        except Exception as e:
                            logger.exception("[MCP] Error handling MCP request")
                            yield f"data: {json.dumps({'error': str(e)})}\r\n\r\n"
                        # Keep connection open for SSE clients
                        while True:
                            await asyncio.sleep(30)
                            yield ": keep-alive\r\n\r\n"
                    return StreamingResponse(stream(), media_type="text/event-stream")
                except Exception as e:
                    logger.exception("[MCP] Invalid JSON in MCP POST")
                    async def error_stream():
                        yield f"data: {json.dumps({'error': 'Invalid JSON'})}\r\n\r\n"
                        while True:
                            await asyncio.sleep(30)
                            yield ": keep-alive\r\n\r\n"
                    return StreamingResponse(error_stream(), media_type="text/event-stream")
            # GET: keep SSE connection alive
            logger.info("[MCP] GET (SSE keep-alive)")
            async def noop_stream():
                while True:
                    await asyncio.sleep(30)
                    yield ": keep-alive\r\n\r\n"
            return StreamingResponse(noop_stream(), media_type="text/event-stream")

    def _list_tools(self) -> List[Dict[str, Any]]:
        """
        Return the list of available MCP tools.
        """
        return [
            {
                "name": "query",
                "description": "Ask a question via RAG",
                "parameters": {
                    "type": "object",
                    "properties": {"question": {"type": "string"}},
                    "required": ["question"],
                },
            },
            {
                "name": "search",
                "description": "Search semantic files",
                "parameters": {
                    "type": "object",
                    "properties": {"term": {"type": "string"}},
                    "required": ["term"],
                },
            },
            {"name": "list", "description": "List tracked files", "parameters": {"type": "object"}},
            {"name": "diff", "description": "Show changed files", "parameters": {"type": "object"}},
            {"name": "patterns", "description": "List include/exclude patterns", "parameters": {"type": "object"}},
        ]

    def _invoke(self, tool: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Invoke the specified tool with arguments and return the result.
        """
        match tool:
            case "query":
                return self.query(args.get("question", ""))
            case "search":
                return self.search(args.get("term", ""))
            case "list":
                return self.list()
            case "diff":
                return self.diff()
            case "patterns":
                return self.patterns()
            case _:
                return {"error": f"Unknown tool: {tool}"}

    def query(self, question: str) -> Dict[str, Any]:
        """
        Handle the 'query' tool: answer a question using RAG.
        """
        query_result, _ = self.context.qdrant.query(question)
        query_result = cast(QuerySchema, query_result)
        return {
            "answer": query_result.answer_conclusion,
            "details": query_result.answer_list,
            "sources": query_result.chunk_ref_list,
            "follow_ups": query_result.further_questions_list,
            "rejected": query_result.reject,
            "rejection_reason": query_result.rejection_reason,
        }

    def search(self, term: str) -> Dict[str, Any]:
        """
        Handle the 'search' tool: search for files semantically.
        """
        points: List[ScoredPoint] = self.context.qdrant.search(term)
        return {
            "matches": [
                {
                    "filepath": point.payload["file_path"],
                    "relevance": point.score,
                    "last_modified": point.payload["file_mtime"],
                }
                for point in points
                if point.payload is not None
            ]
        }

    def list(self) -> Dict[str, Any]:
        """
        Handle the 'list' tool: list tracked files.
        """
        files = self.context.watchlist.list()
        return {
            "files": [
                {
                    "filepath": file_data.file_path,
                    "size": file_data.size,
                    "mtime": file_data.mtime,
                    "tracked": True,
                }
                for file_data in files
            ]
        }

    def diff(self) -> Dict[str, Any]:
        """
        Handle the 'diff' tool: show changed files.
        """
        result = self.context.watchlist.diff()
        return {
            "added": [str(p) for p in result.added],
            "modified": [str(p) for p in result.modified],
            "deleted": [str(p) for p in result.deleted],
        }

    def patterns(self) -> Dict[str, Any]:
        """
        Handle the 'patterns' tool: list include/exclude patterns.
        """
        return {
            "included": self.context.watchlist.get_included_patterns(),
            "excluded": self.context.watchlist.get_excluded_patterns(),
        }
