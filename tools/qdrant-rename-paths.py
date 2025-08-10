#!/usr/bin/env -S uv run python
"""
Qdrant Path Renaming Tool
"""

import sys
import logging
from typing import List, Tuple, Optional

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


def step1_get_source_prefix_and_find_points(qdrant) -> Tuple[str, List, List[str]]:
    """Step 1: Get source path prefix and find matching points."""
    matching_points = []
    sorted_paths = []

    while True:
        # Get source path prefix
        print(colored_text("Step 1: Source Path Prefix", Colors.BOLD))
        source_prefix = input("Enter the path prefix to find (e.g., '/old/path'): ").strip()
        
        if not source_prefix:
            print("Path prefix cannot be empty. Please try again.\n")
            continue
            
        print(f"Searching for files with prefix: {colored_text(source_prefix, Colors.BLUE)}")
        
        # Find matching points
        try:
            scroll_result = qdrant.qdrant.scroll(
                collection_name=qdrant.collection,
                scroll_filter=Filter(must=[]),  # Get all points
                limit=1_000_000_000,  # Large limit to get all points
                with_payload=True,
            )
            
            all_points = scroll_result[0]
            matching_points = []
            
            for point in all_points:
                try:
                    payload = parse_payload(point.payload)
                    if payload.file_path.startswith(source_prefix):
                        matching_points.append(point)
                except Exception as e:
                    print(f"Warning: Could not parse payload for point {point.id}: {e}")
                    continue
                    
        except UnexpectedResponse as e:
            print(f"Error querying Qdrant: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"Error during point retrieval: {e}")
            retry = get_user_input("Try another prefix? (retry/abort): ", ["retry", "r", "abort", "a"])
            if retry in ["abort", "a"]:
                print("Aborting.")
                sys.exit(0)
            print()
            continue
        
        print(f"\nFound {colored_text(str(len(matching_points)), Colors.YELLOW)} points with matching prefix.")
        
        if len(matching_points) == 0:
            print("No points found with this prefix.")
            retry = get_user_input("Try another prefix? (retry/abort): ", ["retry", "r", "abort", "a"])
            if retry in ["abort", "a"]:
                print("Aborting.")
                sys.exit(0)
            print()
            continue
        
        # Show unique file paths
        unique_paths = set()
        for point in matching_points:
            try:
                payload = parse_payload(point.payload)
                unique_paths.add(payload.file_path)
            except Exception as e:
                print(f"Warning: Could not parse payload for point {point.id}: {e}")
                continue
        
        print(f"\nUnique file paths ({len(unique_paths)}):")
        sorted_paths = sorted(unique_paths)
        for i, path in enumerate(sorted_paths[:10], 1):  # Show first 10
            print(f"  {i:2d}. {path}")
        
        if len(sorted_paths) > 10:
            print(f"  ... and {len(sorted_paths) - 10} more")
        
        # Confirm this is the right prefix
        confirm = get_user_input(f"\nIs this the correct prefix to rename? (continue/retry/abort): ", 
                                 ["continue", "c", "retry", "r", "abort", "a"])
        
        if confirm in ["abort", "a"]:
            print("Aborting.")
            sys.exit(0)
        elif confirm in ["retry", "r"]:
            print()
            continue
        else:
            break  # Continue to next step
    
    return source_prefix, matching_points, sorted_paths


def step2_get_target_prefix(source_prefix: str, retry: bool = False) -> str:
    """Step 2: Get target path prefix from user."""
    step_title = "Step 2: Target Path Prefix (Retry)" if retry else "Step 2: Target Path Prefix"
    print(f"\n{colored_text(step_title, Colors.BOLD)}")
    while True:
        target_prefix = input(f"Enter the replacement prefix (current: '{source_prefix}'): ").strip()
        
        if not target_prefix:
            print("Replacement prefix cannot be empty. Please try again.")
            continue
        
        if target_prefix == source_prefix:
            print("Replacement prefix is the same as source prefix. Please enter a different prefix.")
            continue
            
        return target_prefix

    return ""  # make the type checker happy; unreachable since the loop won't break


def step3_show_preview_and_confirm(source_prefix: str, target_prefix: str, sorted_paths: List[str], matching_points: List) -> str:
    """Step 3: Show preview of changes and get confirmation."""
    print(f"\n{colored_text('Step 3: Preview Changes', Colors.BOLD)}")
    
    # Show preview of path changes
    path_changes = {}
    
    for path in sorted_paths:
        new_path = target_prefix + path[len(source_prefix):]
        path_changes[path] = new_path
    
    print(f"Preview of path changes (first 10):")
    for i, (old_path, new_path) in enumerate(list(path_changes.items())[:10], 1):
        print(f"  {i:2d}. {old_path}")
        print(f"      → {new_path}")
    
    if len(path_changes) > 10:
        print(f"  ... and {len(path_changes) - 10} more")
    
    print(f"\nSummary:")
    print(f"  Total files: {len(path_changes)}")
    print(f"  Total points: {len(matching_points)}")
    
    # Final confirmation
    print(f"\n{colored_text('Step 4: Final Confirmation', Colors.BOLD)}")
    return get_user_input("Proceed with renaming these paths? (continue/retry/abort): ", 
                         ["continue", "c", "retry", "r", "abort", "a"])


def step4_update_paths(qdrant, source_prefix: str, target_prefix: str, matching_points: List, sorted_paths: List[str]):
    """Step 4: Update the paths in Qdrant collection."""
    print(f"\n{colored_text('Step 5: Updating Paths', Colors.BOLD)}")
    print("Updating file paths in Qdrant collection...")
    
    try:
        # Update each point
        updated_count = 0
        for point in matching_points:
            payload = parse_payload(point.payload)
            old_path = payload.file_path
            new_path = target_prefix + old_path[len(source_prefix):]
            
            # Create updated payload
            updated_payload = payload.model_dump()
            updated_payload['file_path'] = new_path
            
            # Update the point payload only
            qdrant.qdrant.set_payload(
                collection_name=qdrant.collection,
                payload=updated_payload,
                points=[point.id]
            )
            updated_count += 1
            
            if updated_count % 100 == 0:  # Progress indicator
                print(f"  Updated {updated_count}/{len(matching_points)} points...")
        
        print(f"\n{colored_text('✅ Success!', Colors.GREEN)}")
        print(f"Updated {updated_count} points across {len(sorted_paths)} unique files.")
        print(f"Changed prefix '{source_prefix}' → '{target_prefix}'")
        
    except Exception as e:
        print(f"\n{colored_text('❌ Error updating paths:', Colors.RED)} {e}")
        sys.exit(1)


def main():
    """Main function for the path renaming tool."""
    print(colored_text("🔧 Qdrant Path Renaming Tool", Colors.BOLD))
    print("This tool will rename file path prefixes in your Qdrant collection.\n")

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

    # Step 1: Get source prefix and find points
    source_prefix, matching_points, sorted_paths = step1_get_source_prefix_and_find_points(qdrant)
    
    # Steps 2 & 3: Get target prefix and confirm (with retry loop)
    retry = False
    while True:
        target_prefix = step2_get_target_prefix(source_prefix, retry)
        proceed = step3_show_preview_and_confirm(source_prefix, target_prefix, sorted_paths, matching_points)
        
        if proceed in ["abort", "a"]:
            print("Aborting without making changes.")
            sys.exit(0)
        elif proceed in ["continue", "c"]:
            break
        # If retry, loop continues to get new target prefix
        retry = True
    
    # Step 4: Update the paths
    step4_update_paths(qdrant, source_prefix, target_prefix, matching_points, sorted_paths)


if __name__ == "__main__":
    main()
