"""Tests for knee detection utility."""

import pytest
from archive_agent.util.knee_detection import find_score_cutoff_index


class TestFindScoreCutoffIndex:
    """Test knee detection with various score distributions."""

    def test_sharp_knee_cuts_before_drop(self) -> None:
        """Sharp dropoff should trigger cutoff before low scores."""
        # Requirements Shot 1: [0.92, 0.91, 0.89, 0.71, 0.69, 0.30, 0.28]
        # Expected cutoff: after 0.69 (index 4), so result=5
        scores = [0.92, 0.91, 0.89, 0.71, 0.69, 0.30, 0.28]
        result = find_score_cutoff_index(scores)
        assert result is not None
        # Should cut after 0.69 (index 4). Cutoff is 5.
        assert result <= 5
        assert result >= 1

    def test_flat_distribution_returns_none(self) -> None:
        """Flat scores should return None, not arbitrary cutoff."""
        scores = [0.81, 0.80, 0.79, 0.78]
        result = find_score_cutoff_index(scores)
        assert result is None

    def test_gradual_decay_returns_none_or_all(self) -> None:
        """Gradual decay should fallback (None) or keep all."""
        scores = [0.95, 0.93, 0.92, 0.91, 0.90, 0.89]
        result = find_score_cutoff_index(scores)
        # Fallback or keep all 6
        assert result is None or result == len(scores)

    def test_insufficient_points_returns_none(self) -> None:
        """< 3 points must return None."""
        assert find_score_cutoff_index([0.9, 0.8]) is None
        assert find_score_cutoff_index([0.9]) is None
        assert find_score_cutoff_index([]) is None

    def test_min_chunks_floor_enforced(self) -> None:
        """min_chunks must be respected even with early knee."""
        scores = [0.95, 0.10, 0.09, 0.08]
        result = find_score_cutoff_index(scores, min_chunks=3)
        assert result is None or result >= 3

    def test_extreme_drop_after_first(self) -> None:
        """Single high score followed by low should detect correctly."""
        scores = [0.95, 0.40, 0.35, 0.30]
        result = find_score_cutoff_index(scores)
        # Should detect drop after first, cutoff at 1 or 2
        assert result is not None
        assert 1 <= result <= 2
