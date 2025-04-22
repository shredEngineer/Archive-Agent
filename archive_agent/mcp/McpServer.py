#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import logging
from http.server import HTTPServer, BaseHTTPRequestHandler

logger = logging.getLogger(__name__)


class McpRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        """Handle GET requests."""
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Archive Agent: MCP server is running.")


class McpServer:
    """
    MCP server.
    """

    def __init__(self, port=5000):
        """Initialize the MCP server."""
        self.port = port
        self.server = HTTPServer(("", self.port), McpRequestHandler)

    def start(self) -> None:
        """
        Start the MCP server.
        """
        logger.info(f"MCP server running on http://localhost:{self.port}/")
        logger.info("Press CTRL+C to stop the MCP server.")
        try:
            self.server.serve_forever()
        except KeyboardInterrupt:
            logger.info("Shutting down MCP server...")
            self.stop()

    def stop(self) -> None:
        """
        Stop the MCP server.
        """
        self.server.shutdown()
        self.server.server_close()
        logger.info("MCP server stopped.")
