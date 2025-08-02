# tests/db/test_QdrantSchema.py
#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

import pytest
from pydantic import ValidationError

from archive_agent.db.QdrantSchema import QdrantPayload, parse_payload


class TestQdrantPayload:
    """Test suite for QdrantPayload Pydantic model."""

    def test_valid_payload_all_fields(self):
        """Test creating a valid payload with all fields."""
        payload = QdrantPayload(
            file_path="/home/user/test.txt",
            file_mtime=1640995200.0,
            chunk_index=5,
            chunks_total=10,
            chunk_text="This is test chunk content.",
            version="v1.0.0",
            page_range=[1, 3],
            line_range=None
        )

        assert payload.file_path == "/home/user/test.txt"
        assert payload.file_mtime == 1640995200.0
        assert payload.chunk_index == 5
        assert payload.chunks_total == 10
        assert payload.chunk_text == "This is test chunk content."
        assert payload.version == "v1.0.0"
        assert payload.page_range == [1, 3]
        assert payload.line_range is None

    def test_valid_payload_mandatory_only(self):
        """Test creating a valid payload with only mandatory fields."""
        payload = QdrantPayload(
            file_path="/home/user/test.txt",
            file_mtime=1640995200.0,
            chunk_index=5,
            chunks_total=10,
            chunk_text="This is test chunk content.",
            version=None,
            page_range=None,
            line_range=None
        )

        assert payload.file_path == "/home/user/test.txt"
        assert payload.file_mtime == 1640995200.0
        assert payload.chunk_index == 5
        assert payload.chunks_total == 10
        assert payload.chunk_text == "This is test chunk content."
        assert payload.version is None
        assert payload.page_range is None
        assert payload.line_range is None

    def test_valid_payload_with_line_range(self):
        """Test creating a valid payload with line_range but no page_range."""
        payload = QdrantPayload(
            file_path="/home/user/test.txt",
            file_mtime=1640995200.0,
            chunk_index=5,
            chunks_total=10,
            chunk_text="This is test chunk content.",
            version="v1.0.0",
            page_range=None,
            line_range=[10, 15]
        )

        assert payload.line_range == [10, 15]
        assert payload.page_range is None

    def test_wrong_type_chunk_index_via_parse_payload(self):
        """Test that wrong type for chunk_index raises ValidationError when parsing."""
        invalid_payload_dict = {
            "file_path": "/home/user/test.txt",
            "file_mtime": 1640995200.0,
            "chunk_index": "not_an_int",  # Wrong type
            "chunks_total": 10,
            "chunk_text": "This is test chunk content."
        }

        with pytest.raises(ValidationError) as exc_info:
            parse_payload(invalid_payload_dict)

        assert "chunk_index" in str(exc_info.value)

    def test_wrong_type_file_mtime_via_parse_payload(self):
        """Test that wrong type for file_mtime raises ValidationError when parsing."""
        invalid_payload_dict = {
            "file_path": "/home/user/test.txt",
            "file_mtime": "not_a_float",  # Wrong type
            "chunk_index": 5,
            "chunks_total": 10,
            "chunk_text": "This is test chunk content."
        }

        with pytest.raises(ValidationError) as exc_info:
            parse_payload(invalid_payload_dict)

        assert "file_mtime" in str(exc_info.value)

    def test_both_ranges_set_validation_error(self):
        """Test that having both page_range and line_range raises ValidationError."""
        with pytest.raises(ValueError) as exc_info:
            QdrantPayload(
                file_path="/home/user/test.txt",
                file_mtime=1640995200.0,
                chunk_index=5,
                chunks_total=10,
                chunk_text="This is test chunk content.",
                version="v1.0.0",
                page_range=[1, 3],  # Both ranges set
                line_range=[10, 15]  # Both ranges set
            )

        assert "cannot have both" in str(exc_info.value).lower()

    def test_extra_field_forbidden_via_parse_payload(self):
        """Test that extra fields are forbidden when parsing."""
        invalid_payload_dict = {
            "file_path": "/home/user/test.txt",
            "file_mtime": 1640995200.0,
            "chunk_index": 5,
            "chunks_total": 10,
            "chunk_text": "This is test chunk content.",
            "extra_field": "should_not_be_allowed"
        }

        with pytest.raises(ValidationError) as exc_info:
            parse_payload(invalid_payload_dict)

        assert "extra_field" in str(exc_info.value) or "Extra inputs are not permitted" in str(exc_info.value)

    def test_model_dump(self):
        """Test that model_dump produces correct dictionary."""
        payload = QdrantPayload(
            file_path="/home/user/test.txt",
            file_mtime=1640995200.0,
            chunk_index=5,
            chunks_total=10,
            chunk_text="This is test chunk content.",
            version="v1.0.0",
            page_range=[1, 3],
            line_range=None
        )
        result = payload.model_dump()
        expected = {
            "file_path": "/home/user/test.txt",
            "file_mtime": 1640995200.0,
            "chunk_index": 5,
            "chunks_total": 10,
            "chunk_text": "This is test chunk content.",
            "version": "v1.0.0",
            "page_range": [1, 3],
            "line_range": None
        }

        assert result == expected

    def test_single_page_range(self):
        """Test payload with single-page range."""
        payload = QdrantPayload(
            file_path="/home/user/test.txt",
            file_mtime=1640995200.0,
            chunk_index=5,
            chunks_total=10,
            chunk_text="This is test chunk content.",
            version="v1.0.0",
            page_range=[5],  # Single page
            line_range=None
        )

        assert payload.page_range == [5]

    def test_single_line_range(self):
        """Test payload with single-line range."""
        payload = QdrantPayload(
            file_path="/home/user/test.txt",
            file_mtime=1640995200.0,
            chunk_index=5,
            chunks_total=10,
            chunk_text="This is test chunk content.",
            version="v1.0.0",
            page_range=None,
            line_range=[42]  # Single line
        )

        assert payload.line_range == [42]


class TestParsePayload:
    """Test suite for parse_payload function."""

    def test_parse_valid_payload_dict(self):
        """Test parsing a valid payload dictionary."""
        payload_dict = {
            "file_path": "/home/user/test.txt",
            "file_mtime": 1640995200.0,
            "chunk_index": 5,
            "chunks_total": 10,
            "chunk_text": "This is test chunk content.",
            "version": "v1.0.0",
            "page_range": [1, 3],
            "line_range": None
        }

        payload = parse_payload(payload_dict)

        assert isinstance(payload, QdrantPayload)
        assert payload.file_path == "/home/user/test.txt"
        assert payload.file_mtime == 1640995200.0
        assert payload.chunk_index == 5
        assert payload.chunks_total == 10
        assert payload.chunk_text == "This is test chunk content."
        assert payload.version == "v1.0.0"
        assert payload.page_range == [1, 3]
        assert payload.line_range is None

    def test_parse_legacy_payload_without_optional_fields(self):
        """Test parsing legacy payload without optional fields (backward compatibility)."""
        legacy_payload_dict = {
            "file_path": "/home/user/test.txt",
            "file_mtime": 1640995200.0,
            "chunk_index": 5,
            "chunks_total": 10,
            "chunk_text": "This is test chunk content."
            # Missing: version, page_range, line_range
        }

        payload = parse_payload(legacy_payload_dict)

        assert isinstance(payload, QdrantPayload)
        assert payload.file_path == "/home/user/test.txt"
        assert payload.file_mtime == 1640995200.0
        assert payload.chunk_index == 5
        assert payload.chunks_total == 10
        assert payload.chunk_text == "This is test chunk content."
        assert payload.version is None  # Should default to None
        assert payload.page_range is None  # Should default to None
        assert payload.line_range is None  # Should default to None

    def test_parse_payload_with_only_page_range(self):
        """Test parsing payload with only page_range (typical pre-v5.0.0 with pages)."""
        payload_dict = {
            "file_path": "/home/user/test.pdf",
            "file_mtime": 1640995200.0,
            "chunk_index": 2,
            "chunks_total": 5,
            "chunk_text": "PDF chunk content.",
            "version": "v5.1.0",
            "page_range": [10, 12]
            # Missing: line_range (should be None)
        }

        payload = parse_payload(payload_dict)

        assert payload.page_range == [10, 12]
        assert payload.line_range is None

    def test_parse_payload_with_only_line_range(self):
        """Test parsing payload with only line_range (typical pre-v5.0.0 with lines)."""
        payload_dict = {
            "file_path": "/home/user/test.txt",
            "file_mtime": 1640995200.0,
            "chunk_index": 2,
            "chunks_total": 5,
            "chunk_text": "Text chunk content.",
            "version": "v5.1.0",
            "line_range": [20, 25]
            # Missing: page_range (should be None)
        }

        payload = parse_payload(payload_dict)

        assert payload.line_range == [20, 25]
        assert payload.page_range is None

    def test_parse_none_payload_raises_value_error(self):
        """Test that parsing None payload raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            parse_payload(None)

        assert "cannot be None" in str(exc_info.value)

    def test_parse_invalid_payload_missing_mandatory_field(self):
        """Test that parsing payload missing mandatory field raises ValidationError."""
        invalid_payload_dict = {
            "file_mtime": 1640995200.0,
            "chunk_index": 5,
            "chunks_total": 10,
            "chunk_text": "This is test chunk content."
            # Missing: file_path (mandatory)
        }

        with pytest.raises(ValidationError) as exc_info:
            parse_payload(invalid_payload_dict)

        assert "file_path" in str(exc_info.value)

    def test_parse_invalid_payload_wrong_type(self):
        """Test that parsing payload with wrong type raises ValidationError."""
        invalid_payload_dict = {
            "file_path": "/home/user/test.txt",
            "file_mtime": 1640995200.0,
            "chunk_index": "not_an_int",  # Wrong type
            "chunks_total": 10,
            "chunk_text": "This is test chunk content."
        }

        with pytest.raises(ValidationError) as exc_info:
            parse_payload(invalid_payload_dict)

        assert "chunk_index" in str(exc_info.value)

    def test_parse_payload_with_both_ranges_raises_error(self):
        """Test that parsing payload with both ranges raises ValidationError."""
        invalid_payload_dict = {
            "file_path": "/home/user/test.txt",
            "file_mtime": 1640995200.0,
            "chunk_index": 5,
            "chunks_total": 10,
            "chunk_text": "This is test chunk content.",
            "version": "v1.0.0",
            "page_range": [1, 3],  # Both ranges set
            "line_range": [10, 15]  # Both ranges set
        }

        with pytest.raises(ValidationError) as exc_info:
            parse_payload(invalid_payload_dict)

        assert "cannot have both" in str(exc_info.value).lower()

    def test_parse_payload_with_extra_field_raises_error(self):
        """Test that parsing payload with extra field raises ValidationError."""
        invalid_payload_dict = {
            "file_path": "/home/user/test.txt",
            "file_mtime": 1640995200.0,
            "chunk_index": 5,
            "chunks_total": 10,
            "chunk_text": "This is test chunk content.",
            "extra_field": "should_not_be_allowed"
        }

        with pytest.raises(ValidationError) as exc_info:
            parse_payload(invalid_payload_dict)
        # The error message might vary between Pydantic versions
        assert "extra_field" in str(exc_info.value) or "Extra inputs are not permitted" in str(exc_info.value)

    def test_parse_payload_roundtrip(self):
        """Test that parsing a model_dump produces equivalent model."""
        original_payload = QdrantPayload(
            file_path="/home/user/test.txt",
            file_mtime=1640995200.0,
            chunk_index=5,
            chunks_total=10,
            chunk_text="This is test chunk content.",
            version="v1.0.0",
            page_range=[1, 3],
            line_range=None
        )

        payload_dict = original_payload.model_dump()
        parsed_payload = parse_payload(payload_dict)

        assert parsed_payload == original_payload
        assert parsed_payload.file_path == original_payload.file_path
        assert parsed_payload.file_mtime == original_payload.file_mtime
        assert parsed_payload.chunk_index == original_payload.chunk_index
        assert parsed_payload.chunks_total == original_payload.chunks_total
        assert parsed_payload.chunk_text == original_payload.chunk_text
        assert parsed_payload.version == original_payload.version
        assert parsed_payload.page_range == original_payload.page_range
        assert parsed_payload.line_range == original_payload.line_range
