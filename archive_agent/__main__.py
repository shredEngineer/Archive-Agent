# Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
# This file is part of Archive Agent. See LICENSE for details.

import typer

app = typer.Typer(
    no_args_is_help=True,
    help="Archive Agent: Track files, sync changes, and query with RAG.",
)

@app.command()
def init():
    """Initialize settings: Creates config.json and watchlist.json."""
    print(" ⚙️ Initializing settings in ~/.archive-agent/settings/...")
    print(" ✅ Created config.json and watchlist.json.")

@app.command()
def watch(path: str, additional_paths: list[str] = typer.Argument(None)):
    """Watch files and folders: Add paths to watchlist."""
    all_paths = [path] + (additional_paths or [])
    print(f" 👀 Watching paths: {', '.join(all_paths)}")
    print(" 📥 Added to watchlist and synced to Qdrant.")

@app.command()
def unwatch(path: str, additional_paths: list[str] = typer.Argument(None)):
    """Unwatch files and folders: Remove paths from watchlist."""
    all_paths = [path] + (additional_paths or [])
    print(f" 🙈 Unwatching paths: {', '.join(all_paths)}")
    print(" 🗑️ Removed from watchlist and Qdrant.")

@app.command()
def list():
    """List watched files and folders."""
    print(" 📋 Listing watched paths:")
    print(" ℹ️ (Mock output - replace with actual watchlist data)")

@app.command()
def commit():
    """Commit changes: Sync watchlist and Qdrant database."""
    print(" 🔍 Scanning for changes...")
    print(" 🔄 Updated watchlist and synced Qdrant (added, updated, removed entries).")

@app.command()
def query(question: str):
    """Query files with RAG: Search for specific content."""
    print(f" ❓ Querying: '{question}'")
    print(" 📤 (Mock output - replace with RAG results)")

if __name__ == "__main__":
    app()