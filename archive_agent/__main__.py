# Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
# This file is part of Archive Agent. See LICENSE for details.

import typer

app = typer.Typer(
    no_args_is_help=True,
    help="Archive Agent: Track files, sync changes, and power smart queries.",
)

@app.command()
def init():
    """Initialize settings: Creates default config.json and watchlist.json."""
    print(" ⚙️ Initializing settings in ~/.archive-agent/settings/...")
    print(" ✅ Created config.json and watchlist.json.")

@app.command()
def watch(pattern: str, additional_patterns: list[str] = typer.Argument(None)):
    """Watch files and folders: Add patterns or paths to watchlist."""
    all_patterns = [pattern] + (additional_patterns or [])
    print(f" 👀 Watching patterns: {', '.join(all_patterns)}")
    print(" 📥 Added to watchlist.")

@app.command()
def unwatch(pattern: str, additional_patterns: list[str] = typer.Argument(None)):
    """Unwatch files and folders: Remove patterns or paths from watchlist."""
    all_patterns = [pattern] + (additional_patterns or [])
    print(f" 🙈 Unwatching patterns: {', '.join(all_patterns)}")
    print(" 🗑️ Removed from watchlist.")

@app.command()
def list():
    """List watched files and folders: Display current watchlist."""
    print(" 📋 Listing watched paths:")
    print(" ℹ️ (Mock output - replace with actual watchlist data)")

@app.command()
def commit():
    """Commit changes: Detect updates and sync Qdrant database."""
    print(" 🔍 Scanning for changes...")
    print(" 🔄 Updated watchlist and synced Qdrant (added, updated, removed entries).")

@app.command()
def search(question: str):
    """Search files and folders: List paths matching the question."""
    print(f" ❓ Searching: '{question}'")
    print(" 📋 (Mock output - replace with matching paths)")

@app.command()
def query(question: str):
    """Query files and folders: Answer your question using RAG."""
    print(f" ❓ Querying: '{question}'")
    print(" 📤 (Mock output - replace with RAG results)")

if __name__ == "__main__":
    app()
