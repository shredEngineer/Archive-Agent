# Claude Code Development Guide for Archive Agent

This document captures best practices and essential information for working with the Archive Agent codebase using Claude Code.

## Overview

Archive Agent is an intelligent file indexer with powerful AI search (RAG engine), automatic OCR, and a seamless MCP interface. It processes documents, chunks them semantically, stores embeddings in Qdrant, and provides semantic search capabilities.

## Key Architecture Components

### Core Processing Pipeline
1. **File Tracking**: Pattern-based file selection and change detection
2. **File Processing**: Conversion to text with OCR for images/PDFs  
3. **Semantic Chunking**: AI-powered text chunking with context headers
4. **Embedding**: Vector embeddings stored in Qdrant database
5. **RAG Query**: Retrieval, reranking, expansion, and answer generation

### Important Modules
- `archive_agent/data/FileData.py` - File processing and payload creation
- `archive_agent/db/QdrantManager.py` - Vector database operations  
- `archive_agent/db/QdrantSchema.py` - Qdrant payload schema (Pydantic models)
- `archive_agent/core/ContextManager.py` - Application context initialization
- `archive_agent/core/CommitManager.py` - Commit logic and parallel processing
- `archive_agent/core/CliManager.py` - CLI display and logging with multithreading
- `archive_agent/ai/AiManager.py` - AI API interactions and prompts
- `archive_agent/__main__.py` - CLI command definitions

## Testing and Quality Assurance

### Primary Testing Command
**ALWAYS run the audit script for ANY code changes or testing:**
```bash
./audit.sh
```

**CRITICAL**: Never run individual pytest commands or partial tests. The audit script is the ONLY approved way to run tests as it performs the complete validation suite:
- Unit tests with pytest
- Type checking with mypy  
- Code style checking with ruff
- Import sorting verification

This ensures all code meets project standards and prevents issues from being missed by partial testing.

### Manual Runtime Verification
For multithreaded components, manual testing is required:
```bash
./archive-agent.sh update --verbose --nocache
```

This tests the concurrent processing and live display system.

## Development Best Practices

### Code Quality
- Follow existing code conventions and patterns
- Use type hints consistently
- Maintain clean imports and formatting
- Never introduce security vulnerabilities or malicious code
- **NEVER use automated formatters (ruff format, black, etc.) - fix whitespace manually**
- **CRITICAL: Empty lines must NEVER contain whitespace - they must be completely empty**
- Remove trailing whitespace and ensure proper blank lines
- Files must end with exactly one newline

### Type Safety Requirements
- **ABSOLUTELY FORBIDDEN: `# type: ignore` comments of any kind**
- **NEVER circumvent type checking** - fix the underlying design problem instead
- **If types don't match, the code is wrong** - don't silence the type checker
- **Test validation through proper pathways** - use parsing functions for invalid data tests, not direct constructors
- **Schema violations in tests are unacceptable** - don't create objects that violate your own schema design
- **Type errors indicate design flaws** - address the root cause, never suppress the symptom

### Qdrant Payload Handling
- **ALWAYS** use `QdrantSchema.parse_payload()` for payload access
- Never access `payload['field']` directly - use the schema model
- The schema handles optional fields gracefully (backward compatibility)
- Mandatory fields will raise ValidationError if missing

### Multithreading Architecture
The system uses a sophisticated multithreaded design:
- Worker threads handle I/O-bound tasks concurrently
- All logging goes through a thread-safe queue to a dedicated printer thread
- `CliManager.live_context` orchestrates decoupled logging
- `CliManager.progress_context` provides high-level progress display abstraction

### AI Provider Integration
- Support multiple providers: OpenAI, Ollama, LM Studio
- Configuration is profile-based in `~/.archive-agent-settings/`
- AI operations are cached to avoid redundant processing
- Token usage is tracked and displayed in real-time

## Common Development Tasks

### Adding New File Types
1. Create loader in `archive_agent/data/loader/`
2. Register in `FileData.py` processing logic
3. Update documentation for supported file types

### Modifying Qdrant Schema
1. Update `QdrantSchema.py` with new fields (make optional for backward compatibility)
2. Update all payload creation in `FileData.py`
3. Version field tracks schema changes
4. Test with existing data to ensure compatibility

### Adding CLI Commands  
1. Define command in `archive_agent/__main__.py`
2. Implement logic in appropriate manager class
3. Add to help documentation and README

### AI Model Changes
1. Update provider configurations in `ai_provider/`
2. Modify model specifications in profile config
3. Clear AI cache if embeddings change: `--nocache` flag
4. Update documentation with new model requirements

## Configuration and Profiles

### Profile System
- Profiles stored in `~/.archive-agent-settings/`
- Each profile has independent Qdrant collection
- Contains: config.json, watchlist.json, ai_cache/
- Use `archive-agent switch` to change profiles

### Key Configuration Files
- `config.json` - AI models, chunking parameters, retrieval settings
- `watchlist.json` - File patterns for tracking  
- AI cache prevents redundant processing across sessions

## Database and Storage

### Qdrant Integration
- Local Qdrant instance via Docker
- Collections per profile for isolation
- Vector storage with metadata payloads
- Dashboard at http://localhost:6333/dashboard

### Data Persistence
- Settings: `~/.archive-agent-settings/`
- Database: `~/.archive-agent-qdrant-storage/`
- Separation allows safe code updates without data loss

## Debugging and Troubleshooting

### Verbose Logging
Use `--verbose` flag for detailed operation logs:
- File processing details
- Chunking and embedding information  
- Retrieval and reranking steps
- Token usage statistics

### Cache Management
Use `--nocache` flag to bypass AI cache:
- Forces fresh processing of all operations
- Useful after model changes or debugging
- Does not affect Qdrant database content

### Common Issues
- Check Docker daemon for Qdrant connectivity
- Verify AI provider setup and API keys
- Monitor token usage and costs
- Clear cache if experiencing stale results

## Version Control and Updates

### Update Process
```bash
./update.sh  # Updates code
sudo ./manage-qdrant.sh update  # Updates Qdrant Docker image
```

### Backward Compatibility
- Optional fields in Qdrant payloads maintain compatibility
- AI cache keys change with model updates (automatic handling)
- Profile configs have version numbers for migration

## Security Considerations

- API keys stored in environment variables
- Local processing preserves privacy with Ollama/LM Studio
- No telemetry or external data transmission
- File access controlled by pattern-based permissions

---

This guide should be updated whenever significant architectural changes are made to the codebase. Keep it current and comprehensive for future development sessions.
