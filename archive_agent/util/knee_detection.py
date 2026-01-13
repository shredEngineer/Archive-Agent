#  Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
#  This file is part of Archive Agent. See LICENSE for details.

"""
Knee point detection for score-based cutoff.

Uses the Kneedle algorithm to find the point of maximum curvature
in a sorted score distribution, enabling adaptive retrieval cutoff.
"""

from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

# Internal safety toggle; not user-facing.
# Set to False to disable knee detection globally without code changes.
_INTERNAL_ENABLE_KNEE_CUTOFF = True


def find_score_cutoff_index(
    scores: List[float],
    min_chunks: int = 1,
    sensitivity: float = 1.0,
) -> Optional[int]:
    """
    Find optimal cutoff index using knee detection.

    Knee detection identifies where scores drop off significantly,
    indicating transition from relevant to irrelevant results.

    :param scores: Similarity scores in DESCENDING order.
    :param min_chunks: Minimum chunks to retain (floor).
    :param sensitivity: Kneedle S parameter (default 1.0).
    :return: Cutoff index (exclusive) or None if no knee found.

    Sensitivity parameter guidance:
    - S=1.0: Default, conservative. Detects only prominent knees.
    - S<1.0: Aggressive. Risks false positives on noisy curves.
    - S>1.0: Very conservative. May miss valid knees.

    Empirically, S=1.0 works well for cosine similarity distributions
    where scores are normalized to [-1, 1] range. The Kneedle algorithm
    expects monotonic data; cosine similarity retrieval results from
    Qdrant are returned in descending order, satisfying this requirement.
    """
    if not _INTERNAL_ENABLE_KNEE_CUTOFF:
        return None

    if len(scores) < 3:
        # Too few points for meaningful knee detection
        return None

    try:
        from kneed import KneeLocator
    except ImportError:
        logger.warning("kneed library not available, skipping knee detection")
        return None

    # X-axis: indices, Y-axis: scores (descending)
    x = list(range(len(scores)))
    y = scores

    try:
        # Use Kneedle with polynomial interpolation for smoother curvature
        # calculation on small retrieval sets.
        kneedle = KneeLocator(
            x=x,
            y=y,
            curve="convex",
            direction="decreasing",
            S=sensitivity,
            online=True,         # Correct for later knees in multi-drop curves
            interp_method="polynomial",
        )

        if kneedle.knee is None:
            # Fallback to standard interpolation if polynomial fails
            kneedle = KneeLocator(
                x=x,
                y=y,
                curve="convex",
                direction="decreasing",
                S=sensitivity,
                online=True,
            )

        if kneedle.knee is None:
            return None

        # Knee index is the LAST point before significant drop-off.
        # We want to keep chunks UP TO AND INCLUDING the knee.
        cutoff_index = kneedle.knee + 1

        # Enforce minimum floor
        cutoff_index = max(cutoff_index, min_chunks)

        logger.debug(f"Knee detected at index {kneedle.knee}, cutoff at {cutoff_index}")
        return cutoff_index

    except Exception as e:
        # Any failure in knee detection → graceful fallback
        logger.debug(f"Knee detection failed: {e}")
        return None
