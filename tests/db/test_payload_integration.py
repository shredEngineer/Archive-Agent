# tests/db/test_payload_integration.py
#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import logging

from unittest.mock import Mock
from qdrant_client.models import ScoredPoint

from archive_agent.db.QdrantSchema import QdrantPayload, parse_payload
from archive_agent.util.format import get_point_page_line_info, get_point_reference_info
from archive_agent.ai.query.AiQuery import AiQuery

logger = logging.getLogger(__name__)


class TestPayloadIntegrationFormatUtils:
    """Test payload integration with format utilities."""

    @staticmethod
    def create_mock_point(payload_dict: dict) -> Mock:
        """Helper to create a mock ScoredPoint with payload."""
        point = Mock(spec=ScoredPoint)
        point.payload = payload_dict
        point.score = 0.85
        return point

    def test_get_point_page_line_info_with_page_range(self):
        """Test get_point_page_line_info with page_range payload."""
        payload_dict = {
            "file_path": "/home/user/document.pdf",
            "file_mtime": 1640995200.0,
            "chunk_index": 0,
            "chunks_total": 5,
            "chunk_text": "PDF content from pages 2-4.",
            "version": "v5.1.0",
            "page_range": [2, 4],
            "line_range": None
        }
        point = self.create_mock_point(payload_dict)
        result = get_point_page_line_info(point)

        assert result == "pages 2–4"

    def test_get_point_page_line_info_with_single_page(self):
        """Test get_point_page_line_info with single page."""
        payload_dict = {
            "file_path": "/home/user/document.pdf",
            "file_mtime": 1640995200.0,
            "chunk_index": 0,
            "chunks_total": 5,
            "chunk_text": "PDF content from page 7.",
            "version": "v5.1.0",
            "page_range": [7],
            "line_range": None
        }
        point = self.create_mock_point(payload_dict)
        result = get_point_page_line_info(point)

        assert result == "page 7"

    def test_get_point_page_line_info_with_line_range(self):
        """Test get_point_page_line_info with line_range payload."""
        payload_dict = {
            "file_path": "/home/user/document.txt",
            "file_mtime": 1640995200.0,
            "chunk_index": 2,
            "chunks_total": 8,
            "chunk_text": "Text content from lines 15-20.",
            "version": "v5.1.0",
            "page_range": None,
            "line_range": [15, 20]
        }
        point = self.create_mock_point(payload_dict)
        result = get_point_page_line_info(point)

        assert result == "lines 15–20"

    def test_get_point_page_line_info_with_single_line(self):
        """Test get_point_page_line_info with single line."""
        payload_dict = {
            "file_path": "/home/user/document.txt",
            "file_mtime": 1640995200.0,
            "chunk_index": 2,
            "chunks_total": 8,
            "chunk_text": "Text content from line 42.",
            "version": "v5.1.0",
            "page_range": None,
            "line_range": [42]
        }
        point = self.create_mock_point(payload_dict)
        result = get_point_page_line_info(point)

        assert result == "line 42"

    def test_get_point_page_line_info_no_ranges(self):
        """Test get_point_page_line_info with no ranges (legacy payload)."""
        legacy_payload_dict = {
            "file_path": "/home/user/document.txt",
            "file_mtime": 1640995200.0,
            "chunk_index": 2,
            "chunks_total": 8,
            "chunk_text": "Legacy chunk content.",
            # No version, page_range, line_range fields
        }
        point = self.create_mock_point(legacy_payload_dict)
        result = get_point_page_line_info(point)

        assert result is None

    def test_get_point_page_line_info_empty_ranges(self):
        """Test get_point_page_line_info with empty ranges."""
        payload_dict = {
            "file_path": "/home/user/document.txt",
            "file_mtime": 1640995200.0,
            "chunk_index": 2,
            "chunks_total": 8,
            "chunk_text": "Chunk with empty ranges.",
            "version": "v5.1.0",
            "page_range": [],  # Empty
            "line_range": None
        }
        point = self.create_mock_point(payload_dict)
        result = get_point_page_line_info(point)

        assert result is None

    def test_get_point_reference_info_with_pages(self):
        """Test get_point_reference_info with page-based document."""
        payload_dict = {
            "file_path": "/home/user/My Document.pdf",
            "file_mtime": 1640995200.0,
            "chunk_index": 3,
            "chunks_total": 10,
            "chunk_text": "Chunk from PDF pages.",
            "version": "v5.1.0",
            "page_range": [5, 7],
            "line_range": None
        }
        point = self.create_mock_point(payload_dict)
        result = get_point_reference_info(logger=logger, point=point, verbose=True)

        # Should contain escaped file path and page info
        assert "file:///home/user/My%20Document.pdf" in result
        assert "pages 5–7" in result

    def test_get_point_reference_info_with_lines(self):
        """Test get_point_reference_info with line-based document."""
        payload_dict = {
            "file_path": "/home/user/notes.txt",
            "file_mtime": 1640995200.0,
            "chunk_index": 1,
            "chunks_total": 4,
            "chunk_text": "Chunk from text lines.",
            "version": "v5.1.0",
            "page_range": None,
            "line_range": [10, 15]
        }
        point = self.create_mock_point(payload_dict)
        result = get_point_reference_info(logger=logger, point=point, verbose=True)

        assert "file:///home/user/notes.txt" in result
        assert "lines 10–15" in result

    def test_get_point_reference_info_verbose_mode(self):
        """Test get_point_reference_info with verbose=True."""
        payload_dict = {
            "file_path": "/home/user/document.pdf",
            "file_mtime": 1640995200.0,
            "chunk_index": 2,
            "chunks_total": 10,
            "chunk_text": "Test chunk content.",
            "version": "v5.1.0",
            "page_range": [3, 5],
            "line_range": None
        }
        point = self.create_mock_point(payload_dict)
        result = get_point_reference_info(logger=logger, point=point, verbose=True)

        # Verbose mode should include chunk info and timestamp
        assert "chunk 3/10" in result
        assert "pages 3–5" in result
        assert "2022-01-01" in result  # Formatted timestamp

    def test_get_point_reference_info_legacy_payload(self):
        """Test get_point_reference_info with legacy payload (no ranges)."""
        legacy_payload_dict = {
            "file_path": "/home/user/old_document.txt",
            "file_mtime": 1640995200.0,
            "chunk_index": 0,
            "chunks_total": 3,
            "chunk_text": "Legacy chunk without ranges.",
        }
        point = self.create_mock_point(legacy_payload_dict)
        result = get_point_reference_info(logger=logger, point=point, verbose=True)

        # Should fall back to chunk info only
        assert "file:///home/user/old_document.txt" in result
        assert "chunk 1/3" in result


class TestPayloadIntegrationAiQuery:
    """Test payload integration with AiQuery utilities."""

    @staticmethod
    def create_mock_point(payload_dict: dict) -> Mock:
        """Helper to create a mock ScoredPoint with payload."""
        point = Mock(spec=ScoredPoint)
        point.payload = payload_dict
        point.score = 0.85
        return point

    def test_get_point_hash_with_all_fields(self):
        """Test AiQuery.get_point_hash with complete payload."""
        payload_dict = {
            "file_path": "/home/user/test.pdf",
            "file_mtime": 1640995200.0,
            "chunk_index": 5,
            "chunks_total": 10,
            "chunk_text": "Test chunk content for hashing.",
            "version": "v5.1.0",
            "page_range": [2, 4],
            "line_range": None
        }
        point = self.create_mock_point(payload_dict)
        hash_result = AiQuery.get_point_hash(point)

        # Should be 16-character hex string
        assert isinstance(hash_result, str)
        assert len(hash_result) == 16
        assert all(c in '0123456789abcdef' for c in hash_result)

    def test_get_point_hash_with_legacy_payload(self):
        """Test AiQuery.get_point_hash with legacy payload (no optional fields)."""
        legacy_payload_dict = {
            "file_path": "/home/user/legacy.txt",
            "file_mtime": 1609459200.0,  # Different timestamp
            "chunk_index": 2,
            "chunks_total": 6,
            "chunk_text": "Legacy chunk content.",
            # No version, page_range, line_range
        }
        point = self.create_mock_point(legacy_payload_dict)
        hash_result = AiQuery.get_point_hash(point)

        # Should still work and produce valid hash
        assert isinstance(hash_result, str)
        assert len(hash_result) == 16
        assert all(c in '0123456789abcdef' for c in hash_result)

    def test_get_point_hash_consistency(self):
        """Test that identical payloads produce identical hashes."""
        payload_dict = {
            "file_path": "/home/user/consistent.txt",
            "file_mtime": 1640995200.0,
            "chunk_index": 3,
            "chunks_total": 7,
            "chunk_text": "Consistent content.",
            "version": "v1.0.0",
            "page_range": None,
            "line_range": [10, 15]
        }
        point1 = self.create_mock_point(payload_dict.copy())
        point2 = self.create_mock_point(payload_dict.copy())

        hash1 = AiQuery.get_point_hash(point1)
        hash2 = AiQuery.get_point_hash(point2)

        assert hash1 == hash2

    def test_get_point_hash_different_for_different_payloads(self):
        """Test that different payloads produce different hashes."""
        payload_dict1 = {
            "file_path": "/home/user/file1.txt",
            "file_mtime": 1640995200.0,
            "chunk_index": 1,
            "chunks_total": 5,
            "chunk_text": "Content 1.",
            "version": "v1.0.0",
            "page_range": None,
            "line_range": [5, 10]
        }

        payload_dict2 = {
            "file_path": "/home/user/file2.txt",  # Different file
            "file_mtime": 1640995200.0,
            "chunk_index": 1,
            "chunks_total": 5,
            "chunk_text": "Content 1.",
            "version": "v1.0.0",
            "page_range": None,
            "line_range": [5, 10]
        }
        point1 = self.create_mock_point(payload_dict1)
        point2 = self.create_mock_point(payload_dict2)

        hash1 = AiQuery.get_point_hash(point1)
        hash2 = AiQuery.get_point_hash(point2)

        assert hash1 != hash2

    def test_get_context_from_points(self):
        """Test AiQuery.get_context_from_points with multiple points."""
        payload1 = {
            "file_path": "/home/user/doc1.txt",
            "file_mtime": 1640995200.0,
            "chunk_index": 0,
            "chunks_total": 2,
            "chunk_text": "First chunk content.",
            "version": "v1.0.0",
            "page_range": None,
            "line_range": [1, 5]
        }

        payload2 = {
            "file_path": "/home/user/doc2.txt",
            "file_mtime": 1640995200.0,
            "chunk_index": 1,
            "chunks_total": 3,
            "chunk_text": "Second chunk content.",
            "version": "v1.0.0",
            "page_range": [2, 3],
            "line_range": None
        }
        point1 = self.create_mock_point(payload1)
        point2 = self.create_mock_point(payload2)
        points = [point1, point2]  # type: ignore[list-item] # Mock objects for testing
        context = AiQuery.get_context_from_points(points)  # type: ignore[arg-type] # Mock objects for testing

        # Should contain both chunks with hash separators
        assert "First chunk content." in context
        assert "Second chunk content." in context
        assert "<<<" in context  # Hash separator format
        assert ">>>" in context


class TestPayloadIntegrationBackwardCompatibility:
    """Test backward compatibility with legacy payloads across the system."""

    def test_legacy_payload_missing_version_field(self):
        """Test that legacy payloads without version field work correctly."""
        legacy_payload = {
            "file_path": "/home/user/legacy.txt",
            "file_mtime": 1609459200.0,
            "chunk_index": 0,
            "chunks_total": 1,
            "chunk_text": "Legacy content without version."
            # Missing: version, page_range, line_range
        }

        # Should parse successfully
        parsed = parse_payload(legacy_payload)
        assert parsed.version is None
        assert parsed.page_range is None
        assert parsed.line_range is None

        # Should work with format utilities
        mock_point = Mock(spec=ScoredPoint)
        mock_point.payload = legacy_payload
        mock_point.score = 0.9

        reference_info = get_point_reference_info(logger=logger, point=mock_point, verbose=True)
        assert "chunk 1/1" in reference_info
        assert "file:///home/user/legacy.txt" in reference_info

    def test_legacy_payload_missing_range_fields(self):
        """Test legacy payloads without range fields (pre-v5.0.0)."""
        pre_v5_payload = {
            "file_path": "/home/user/pre_v5.txt",
            "file_mtime": 1577836800.0,  # 2020-01-01
            "chunk_index": 2,
            "chunks_total": 5,
            "chunk_text": "Pre-v5.0.0 chunk content.",
            "version": "v4.9.0"
            # Missing: page_range, line_range (added in v5.0.0)
        }

        # Should parse successfully with defaults
        parsed = parse_payload(pre_v5_payload)
        assert parsed.version == "v4.9.0"
        assert parsed.page_range is None
        assert parsed.line_range is None

        # Should work with all utilities
        mock_point = Mock(spec=ScoredPoint)
        mock_point.payload = pre_v5_payload
        mock_point.score = 0.8

        # Format utilities should handle gracefully
        page_line_info = get_point_page_line_info(mock_point)
        assert page_line_info is None  # No ranges available

        reference_info = get_point_reference_info(logger=logger, point=mock_point, verbose=True)
        assert "chunk 3/5" in reference_info  # Falls back to chunk info

        # AiQuery should work
        hash_result = AiQuery.get_point_hash(mock_point)
        assert isinstance(hash_result, str)
        assert len(hash_result) == 16

    def test_payload_evolution_compatibility(self):
        """Test that payloads can evolve while maintaining compatibility."""
        # Simulate different payload versions
        payloads = [
            # Very old payload (minimal fields)
            {
                "file_path": "/home/user/v1.txt",
                "file_mtime": 1546300800.0,  # 2019-01-01
                "chunk_index": 0,
                "chunks_total": 1,
                "chunk_text": "Very old chunk."
            },
            # Pre-v5.0.0 payload (has version but no ranges)
            {
                "file_path": "/home/user/v4.txt",
                "file_mtime": 1577836800.0,  # 2020-01-01
                "chunk_index": 0,
                "chunks_total": 1,
                "chunk_text": "Pre-v5 chunk.",
                "version": "v4.9.0"
            },
            # v5.0.0+ payload (has ranges)
            {
                "file_path": "/home/user/v5.txt",
                "file_mtime": 1609459200.0,  # 2021-01-01
                "chunk_index": 0,
                "chunks_total": 1,
                "chunk_text": "v5+ chunk with ranges.",
                "version": "v5.1.0",
                "page_range": None,
                "line_range": [1, 10]
            },
            # Current payload (all fields)
            {
                "file_path": "/home/user/current.txt",
                "file_mtime": 1640995200.0,  # 2022-01-01
                "chunk_index": 0,
                "chunks_total": 1,
                "chunk_text": "Current chunk with all fields.",
                "version": "v7.4.0",
                "page_range": None,
                "line_range": [1, 15]
            }
        ]

        # All payloads should parse successfully
        for i, payload_dict in enumerate(payloads):
            parsed = parse_payload(payload_dict)
            assert isinstance(parsed, QdrantPayload)
            # Verify the payload has the expected file path pattern
            if i == 0:
                assert "v1" in parsed.file_path
            elif i == 1:
                assert "v4" in parsed.file_path  # This is the v4.txt file
            elif i == 2:
                assert "v5" in parsed.file_path
            else:
                assert "current" in parsed.file_path

            # All should work with format utilities
            mock_point = Mock(spec=ScoredPoint)
            mock_point.payload = payload_dict
            mock_point.score = 0.7

            reference_info = get_point_reference_info(logger=logger, point=mock_point, verbose=True)
            assert isinstance(reference_info, str)
            assert len(reference_info) > 0

            hash_result = AiQuery.get_point_hash(mock_point)
            assert isinstance(hash_result, str)
            assert len(hash_result) == 16
