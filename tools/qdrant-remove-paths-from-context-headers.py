#!/usr/bin/env -S uv run python
"""
Remove legacy file path header lines from pre-v11.0.0 chunks.

- Iterates all points in the Qdrant collection.
- Selects points with payload.version < v11.0.0 (robust semantic compare).
- If the first line of the chunk starts with '# file://', remove that line.
- If not present, warn and skip that point.
- Shows a preview and asks for confirmation before updating.
"""

import sys
import logging
from typing import List, Tuple, Optional, Dict, Any
import asyncio
import re

# Set up minimal logging to avoid spam
logging.basicConfig(level=logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("qdrant_client").setLevel(logging.WARNING)

from archive_agent.core.ContextManager import ContextManager
from archive_agent.db.QdrantSchema import parse_payload
from qdrant_client.models import Filter
from qdrant_client.http.exceptions import UnexpectedResponse


class Colors:
    """ANSI color codes for terminal output."""
    GREEN = '\033[92m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    YELLOW = '\033[93m'
    BOLD = '\033[1m'
    END = '\033[0m'


def colored_text(text: str, color: str) -> str:
    """Return colored text for terminal output."""
    return f"{color}{text}{Colors.END}"


def get_user_input(prompt: str, valid_responses: Optional[List[str]] = None) -> str:
    """Get user input with optional validation."""
    while True:
        response = input(prompt).strip().lower()
        if valid_responses is None or response in valid_responses:
            return response
        print(f"Invalid response. Please enter one of: {', '.join(valid_responses)}")


def semver_tuple(v: str) -> Tuple[int, int, int]:
    """Convert 'vMAJOR.MINOR.PATCH' or 'MAJOR.MINOR.PATCH' to a tuple of ints."""
    if not isinstance(v, str) or not v:
        return 0, 0, 0
    v = v.strip()
    if v.startswith("v") or v.startswith("V"):
        v = v[1:]
    parts = re.split(r"[.\-+]", v)
    nums: List[int] = []
    for p in parts[:3]:
        # noinspection PyBroadException
        try:
            nums.append(int(p))
        except Exception:
            nums.append(0)
    while len(nums) < 3:
        nums.append(0)
    return tuple(nums[:3])  # type: ignore[return-value]


def is_version_lt(version: Optional[str], ref: str = "v11.0.0") -> bool:
    """Return True if version < ref with semantic comparison."""
    return semver_tuple(version or "0.0.0") < semver_tuple(ref)


def resolve_text_field(payload_dict: Dict[str, Any]) -> Optional[str]:
    """Find the text-bearing field in the payload dict."""
    candidates = [
        "cpntext",          # legacy?
        "chunk_text",       # common
        "text",             # fallback
        "content",          # fallback
        "body",             # fallback
    ]
    for k in candidates:
        if k in payload_dict and isinstance(payload_dict[k], str):
            return k
    # Try to guess: first str field with multiple lines
    for k, v in payload_dict.items():
        if isinstance(v, str) and ("\n" in v or v.startswith("# ")):
            return k
    return None


def has_file_header(first_line: str) -> bool:
    """Check whether the first line is a 'file://' header comment."""
    return first_line.strip().lower().startswith("# file://")


def step1_collect_candidates(qdrant) -> Tuple[List, List[str], List[str]]:
    """Step 1: Scan all points and collect candidates to modify and to skip."""
    print(colored_text("Step 1: Scan All Points", Colors.BOLD))
    print("Reading entire collection (this may take a moment)...")

    try:
        scroll_result = asyncio.run(
            qdrant.qdrant.scroll(
                collection_name=qdrant.collection,
                scroll_filter=Filter(must=[]),  # Get all points
                limit=1_000_000_000,            # Large limit to get all points
                with_payload=True,
            )
        )
    except UnexpectedResponse as e:
        print(f"Error querying Qdrant: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error during point retrieval: {e}")
        sys.exit(1)

    all_points = scroll_result[0]
    print(f"Total points in collection: {colored_text(str(len(all_points)), Colors.YELLOW)}")

    candidates = []
    skip_reasons: List[str] = []
    errors: List[str] = []

    for point in all_points:
        try:
            payload_model = parse_payload(point.payload)
            payload = payload_model.model_dump()
            version = payload.get("version") or payload.get("schema_version") or payload.get("meta_version")

            # Only pre-v11.0.0 are candidates
            if not is_version_lt(version, "v11.0.0"):
                continue

            text_field = resolve_text_field(payload)
            if not text_field:
                skip_reasons.append(f"point {point.id}: no recognizable text field")
                continue

            text_value = payload[text_field]
            lines = text_value.splitlines()
            if not lines:
                skip_reasons.append(f"point {point.id}: empty text")
                continue

            if has_file_header(lines[0]):
                candidates.append((point, text_field, text_value))
            else:
                skip_reasons.append(f"point {point.id}: first line is not a file header; will skip")

        except Exception as e:
            errors.append(f"point {getattr(point, 'id', '?')}: {e}")
            continue

    print(f"\nPre-v11.0.0 points with removable header: {colored_text(str(len(candidates)), Colors.GREEN)}")
    print(f"Pre-v11.0.0 points without header (skipped): {colored_text(str(len(skip_reasons)), Colors.YELLOW)}")
    if errors:
        print(f"Points with parse errors: {colored_text(str(len(errors)), Colors.RED)}")

    return candidates, skip_reasons, errors


def step2_preview(candidates: List[Tuple[Any, str, str]], skip_reasons: List[str], errors: List[str]) -> str:
    """Step 2: Show a preview of changes and gather confirmation."""
    print(f"\n{colored_text('Step 2: Preview Changes', Colors.BOLD)}")

    show_n = min(10, len(candidates))
    if show_n == 0:
        print("No eligible points found. Nothing to change.")
        return get_user_input("\nAbort? (abort): ", ["abort", "a"])

    print(f"Showing first {show_n} diffs:")
    for i in range(show_n):
        point, text_field, text_value = candidates[i]
        lines = text_value.splitlines()
        old_first = lines[0] if lines else ""
        new_text = "\n".join(lines[1:]) if len(lines) > 1 else ""
        print(f"\n  {i+1:2d}. point {point.id}  field '{text_field}'")
        print(f"      - old first line: {colored_text(old_first, Colors.RED)}")
        preview_new_first = new_text.splitlines()[0] if new_text else "<empty after removal>"
        print(f"      + new first line: {colored_text(preview_new_first, Colors.GREEN)}")

    print("\nSummary:")
    print(f"  Will modify: {colored_text(str(len(candidates)), Colors.GREEN)} points")
    print(f"  Will skip : {colored_text(str(len(skip_reasons)), Colors.YELLOW)} points (no header on first line)")
    if errors:
        print(f"  Errors    : {colored_text(str(len(errors)), Colors.RED)} points (parse failures)")

    if skip_reasons[:5]:
        print("\nExamples of skipped reasons (up to 5):")
        for s in skip_reasons[:5]:
            print(f"  - {s}")

    if errors[:3]:
        print("\nExamples of errors (up to 3):")
        for e in errors[:3]:
            print(f"  - {e}")

    print(f"\n{colored_text('Step 3: Final Confirmation', Colors.BOLD)}")
    return get_user_input("Proceed with removing header lines? (continue/retry/abort): ",
                          ["continue", "c", "retry", "r", "abort", "a"])


def step3_apply(qdrant, candidates: List[Tuple[Any, str, str]]):
    """Step 3: Apply the changes to Qdrant."""
    print(f"\n{colored_text('Step 4: Applying Changes', Colors.BOLD)}")
    updated = 0
    try:
        for idx, (point, text_field, text_value) in enumerate(candidates, 1):
            lines = text_value.splitlines()
            # Safety: re-check header presence right before write
            if not lines or not has_file_header(lines[0]):
                # This should be rare; skip if it changed between preview and apply
                print(f"  Skipping point {point.id}: header no longer present.")
                continue

            new_text = "\n".join(lines[1:])

            # Prepare updated payload
            payload_model = parse_payload(point.payload)
            updated_payload = payload_model.model_dump()
            updated_payload[text_field] = new_text

            asyncio.run(
                qdrant.qdrant.set_payload(
                    collection_name=qdrant.collection,
                    payload=updated_payload,
                    points=[point.id],
                )
            )
            updated += 1

            if idx % 100 == 0:
                print(f"  Updated {updated}/{len(candidates)} points...")

        print(f"\n{colored_text('✅ Success!', Colors.GREEN)}")
        print(f"Updated {updated} points (removed leading '# file://…' line).")

    except Exception as e:
        print(f"\n{colored_text('❌ Error while updating:', Colors.RED)} {e}")
        sys.exit(1)


def main():
    """Main entry point for the header removal tool."""
    print(colored_text("🔧 Qdrant Pre-v11 Header Cleanup", Colors.BOLD))
    print("This tool removes leading '# file://…' lines from pre-v11.0.0 chunks.\n")

    # Initialize context manager (uses current profile)
    try:
        print("Connecting to Archive Agent...")
        context = ContextManager(verbose=False)
        qdrant = context.qdrant
        print(f"Connected to profile: {colored_text(context.profile_manager.get_profile_name(), Colors.BLUE)}")
        print(f"Collection: {colored_text(qdrant.collection, Colors.BLUE)}\n")
    except Exception as e:
        print(f"Error connecting to Archive Agent: {e}")
        print("Make sure Qdrant is running and your profile is configured.")
        sys.exit(1)

    # Step 1: Collect candidates
    candidates, skip_reasons, errors = step1_collect_candidates(qdrant)

    # Step 2: Preview & confirm (with retry option, which simply rescans)
    while True:
        decision = step2_preview(candidates, skip_reasons, errors)
        if decision in ["abort", "a"]:
            print("Aborting without making changes.")
            sys.exit(0)
        if decision in ["continue", "c"]:
            break
        # retry path: rescan
        candidates, skip_reasons, errors = step1_collect_candidates(qdrant)

    # Step 3: Apply
    step3_apply(qdrant, candidates)


if __name__ == "__main__":
    main()
