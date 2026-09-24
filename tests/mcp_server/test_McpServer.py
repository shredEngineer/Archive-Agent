#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

from archive_agent.mcp_server.McpServer import _extract_header_from_chunk_text


class TestExtractHeaderFromChunkText:
    """Test suite for _extract_header_from_chunk_text helper function."""

    def test_extracts_header_from_standard_format(self):
        """Test extracting header from standard chunk format."""
        chunk_text = "# Introduction to Machine Learning\n\nThis is the body of the chunk."
        result = _extract_header_from_chunk_text(chunk_text)
        assert result == "Introduction to Machine Learning"

    def test_extracts_header_with_special_characters(self):
        """Test extracting header with special characters."""
        chunk_text = "# Section 1.2: Data Analysis & Processing\n\nBody text here."
        result = _extract_header_from_chunk_text(chunk_text)
        assert result == "Section 1.2: Data Analysis & Processing"

    def test_returns_empty_string_for_no_header(self):
        """Test returns empty string when no header prefix found."""
        chunk_text = "This chunk has no header prefix."
        result = _extract_header_from_chunk_text(chunk_text)
        assert result == ""

    def test_returns_empty_string_for_empty_text(self):
        """Test returns empty string for empty chunk text."""
        chunk_text = ""
        result = _extract_header_from_chunk_text(chunk_text)
        assert result == ""

    def test_handles_header_only_chunk(self):
        """Test handles chunk that is only a header."""
        chunk_text = "# Only Header"
        result = _extract_header_from_chunk_text(chunk_text)
        assert result == "Only Header"

    def test_does_not_extract_non_first_line_headers(self):
        """Test that headers not on the first line are not extracted."""
        chunk_text = "Some intro text\n# This is not extracted\n\nBody."
        result = _extract_header_from_chunk_text(chunk_text)
        assert result == ""

    def test_handles_multiple_hashes(self):
        """Test handles lines starting with multiple hashes (markdown subheaders)."""
        chunk_text = "## Subheader\n\nBody text."
        result = _extract_header_from_chunk_text(chunk_text)
        # This starts with "##" not "# " so should return empty
        assert result == ""

    def test_requires_space_after_hash(self):
        """Test that a space is required after the hash."""
        chunk_text = "#NoSpaceAfterHash\n\nBody."
        result = _extract_header_from_chunk_text(chunk_text)
        assert result == ""

    def test_preserves_leading_whitespace_in_header(self):
        """Test that leading whitespace in header is preserved."""
        chunk_text = "#  Header with leading space\n\nBody."
        result = _extract_header_from_chunk_text(chunk_text)
        assert result == " Header with leading space"

    def test_handles_unicode_header(self):
        """Test handles Unicode characters in header."""
        chunk_text = "# Données d'analyse: 日本語テスト\n\nBody with unicode."
        result = _extract_header_from_chunk_text(chunk_text)
        assert result == "Données d'analyse: 日本語テスト"


class TestMcpServerAuth:
    """Test suite for the MCP server's LOCAL_AUTH_PASSWORD guard."""

    PASSWORD = "test-pw"

    @staticmethod
    def _client(monkeypatch, password):
        from unittest.mock import Mock
        from starlette.testclient import TestClient
        from archive_agent.mcp_server.McpServer import McpServer

        if password is None:
            monkeypatch.delenv("LOCAL_AUTH_PASSWORD", raising=False)
        else:
            monkeypatch.setenv("LOCAL_AUTH_PASSWORD", password)
        server = McpServer(context=Mock(), host="127.0.0.1", port=0)
        return TestClient(server.app)

    def test_refuses_to_start_without_password(self, monkeypatch):
        """Test that the server fails closed if LOCAL_AUTH_PASSWORD is unset."""
        import pytest
        with pytest.raises(SystemExit):
            self._client(monkeypatch, None)

    def test_sse_without_credentials_is_401(self, monkeypatch):
        """Test that /sse asks for Basic auth when no credentials are sent."""
        client = self._client(monkeypatch, self.PASSWORD)
        response = client.get("/sse")
        assert response.status_code == 401
        assert response.headers["www-authenticate"] == 'Basic realm="Archive-Agent MCP"'

    def test_messages_with_wrong_credentials_is_401(self, monkeypatch):
        """Test that /messages/ rejects a wrong password."""
        client = self._client(monkeypatch, self.PASSWORD)
        assert client.post("/messages/", headers={"Authorization": "Bearer wrong"}).status_code == 401
        assert client.post("/messages/", auth=("x", "wrong")).status_code == 401

    def test_messages_with_bearer_passes(self, monkeypatch):
        """Test that a Bearer password reaches the MCP transport (400: no session_id)."""
        client = self._client(monkeypatch, self.PASSWORD)
        response = client.post("/messages/", headers={"Authorization": f"Bearer {self.PASSWORD}"})
        assert response.status_code == 400

    def test_messages_with_basic_passes(self, monkeypatch):
        """Test that Basic auth with any username reaches the MCP transport (400: no session_id)."""
        client = self._client(monkeypatch, self.PASSWORD)
        response = client.post("/messages/", auth=("anyone", self.PASSWORD))
        assert response.status_code == 400
