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
- `archive_agent/data/processor/VisionProcessor.py` - Parallel vision processing
- `archive_agent/data/processor/EmbedProcessor.py` - Parallel chunk embedding
- `archive_agent/db/QdrantManager.py` - Vector database operations  
- `archive_agent/db/QdrantSchema.py` - Qdrant payload schema (Pydantic models)
- `archive_agent/core/ContextManager.py` - Application context initialization
- `archive_agent/core/CommitManager.py` - Commit orchestration and database operations
- `archive_agent/core/IngestionManager.py` - Parallel file processing and progress tracking
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

**CRITICAL**: The audit script **cannot** validate multithreaded runtime behavior. **Manual verification is required** by running the application and visually confirming that all four core multithreading requirements are met:
1. True parallel processing without serialization
2. Styled logging with custom `RichHandler` formatting
3. Clean live display with stable status and scrolling history
4. Real-time updates without glitches

**Note**: If there are files that have been removed from the watchlist, the script will pause for a confirmation prompt. This is expected behavior. The core concurrency and logging test is successful if the live display runs without errors up to that point.

### Parallel Processing Verification Strategy
When developing or modifying parallel processing components:

**Development Workflow**:
1. Run `./audit.sh` after each change for type checking and formatting
2. Manual runtime testing with `./archive-agent.sh update --verbose --nocache`
3. Visual verification of multithreading display (progress bars, logging, UI stability)
4. Regression testing to ensure identical processing results

**Rollback Strategy**:
- Git commits after each working milestone
- Maintain ability to revert to working state at any point
- Test suite validation before proceeding to next phase

**Critical Testing Requirements**:
- All parallel operations must pass identical behavior tests
- Progress tracking must work without serializing worker threads
- Error isolation must not break entire batch processing

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

### Multithreading & Live Display Architecture

#### Core Requirements
The implementation must satisfy these four critical requirements:
1. **True Parallel Processing**: Worker threads must execute I/O-bound tasks concurrently without being serialized by logging or UI updates
2. **Styled Logging**: All log output, even during concurrent operations, must use the single, custom-styled `RichHandler` defined in `__init__.py`
3. **Clean Live Display**: The live display must show a stable status block, with verbose logs appearing as a persistent, scrolling history above it without interleaving or glitching
4. **Real-time Updates**: The status block (progress bars, tables) must update smoothly

#### CRITICAL: Logger Thread Safety Requirements
**ABSOLUTELY FORBIDDEN**: Module-level loggers (`logger = logging.getLogger(__name__)`)

**REQUIRED**: All loggers must derive from `ai.cli.logger` hierarchy to ensure thread safety:
- **Correct**: `self.logger = ai.cli.get_prefixed_logger(prefix=...)`
- **Correct**: `self.logger = self.ai.cli.logger` 
- **FORBIDDEN**: `logger = logging.getLogger(__name__)`
- **FORBIDDEN**: `import logging; logging.getLogger(...)`

**Rationale**: The decoupled logging architecture requires all log messages to flow through the centralized `ai.cli` logger system. Module-level loggers bypass this system and will cause:
- Thread serialization (defeating parallelization)
- Log message loss during live display
- UI corruption and race conditions

#### Core Problem: Concurrency vs. `rich.Live`
The fundamental challenge is that `rich.Live` uses an internal lock to manage screen updates. If multiple worker threads attempt to log or print directly to the console, they will contend for this lock. This forces the threads to execute one by one, serializing their execution and defeating the purpose of multithreading for concurrent tasks.

#### Architectural Solution: Decoupled Logging
The architecture decouples worker threads from the console to ensure true parallel processing. All logging and printing is funneled through a single, dedicated "printer thread" that is the sole manager of the `Live` display.

The pattern is:
1. Worker threads place log records onto a thread-safe `queue.Queue` instead of writing to the console
2. The printer thread is the only consumer of this queue. It safely handles each message and updates the `Live` display without lock contention

#### Implementation Layers

**Low-Level Orchestration: `live_context`**
The `live_context` manager is the core orchestrator of the decoupled logging system:

1. **Find and Redirect the Global `RichHandler`**: It finds the single, globally-configured `RichHandler` instance from the root logger. It then temporarily redirects the handler's output to the `Live` object's internal console.
   - **CRITICAL DESIGN CONSTRAINT**: The system **must not** create a new `RichHandler`. Doing so would bypass the central styling configuration (e.g., timestamps, custom highlighters) defined in `__init__.py`, leading to incorrectly formatted log output
2. **Funnel All Logs to the Queue**: It replaces the root logger's handlers with a single `QueueHandler`, ensuring every log message from anywhere in the application is captured and put onto the queue
3. **Manage the Printer Thread**: It starts the dedicated printer thread to process the queue and guarantees that it is safely shut down when the context is exited
4. **Guaranteed Restoration**: In a `finally` block, it restores the original logger handlers and, most importantly, restores the original console to the `RichHandler`, ensuring normal logging continues after the `Live` display is closed

**High-Level Abstraction: `progress_context`**
The `progress_context` manager provides a simple, high-level abstraction for components like `CommitManager` that need to display progress. This centralizes UI logic in `CliManager` and decouples other components from UI implementation details.

Responsibilities:
1. Acts as the single entry point for creating live progress displays
2. Constructs all necessary `rich` components (`Progress`, `Group`, `Live`, etc.) for a consistent look and feel
3. Automatically includes shared UI elements, like the AI token usage table
4. Internally wraps the entire operation within the `live_context` manager, so that safe, concurrent logging is handled automatically
5. Yields the necessary `rich.Progress` handles back to the caller

**Decoupling Callers**: Callers like `IngestionManager` use the `progress_context` in a simple `with` block. Inside this block, they use the yielded handles to report progress. This allows the caller to be completely ignorant of the underlying `rich` objects or the multithreaded logging complexity.

#### Challenge: Dynamic UI Updates
A challenge is ensuring dynamic UI elements, like the AI token usage table, update in real-time. While worker threads correctly update the underlying statistics (protected by a `threading.Lock`), the `Live` object, if initialized with static content, will not reflect these changes.

**CRITICAL SAFETY CONCERN**: Any solution must be implemented with extreme care, ensuring it does **not** compromise the core architecture. Specifically, it must not:
1. Interfere with the decoupled logging mechanism
2. Introduce new race conditions or thread-safety issues
3. Degrade the concurrency of the worker threads

**The Safe Solution**: The solution is to make the `Live` object's content dynamic without violating the architectural principles:

1. **Timed Queue Read**: The printer thread's `queue.get()` call uses a short timeout (`0.1s`) instead of being fully blocking
2. **Periodic Refresh**: When the timeout occurs (i.e., during brief idle periods with no new log messages), the printer thread's loop continues. At the end of every loop iteration (whether a log was processed or not), it calls `live.update()`
3. **Dynamic Renderable**: To provide the `live.update()` method with fresh content, a `get_renderable` function is passed down from `progress_context` to the printer thread. This function, when called, generates a new `rich.Group` containing the progress bars and a **newly-rendered table** with the latest, thread-safely read statistics

This solution is surgically precise. It confines all UI update logic to the single printer thread, fully respecting the existing locks and queues. It ensures the display is dynamic while upholding the system's foundational guarantees of safety and concurrency.

#### Challenge: Accurate Real-time Statistics
Providing accurate, real-time updates for cumulative statistics like AI token usage is a significant challenge. The system solves this with a dual-mechanism architecture that balances liveness with correctness. Understanding the separation of concerns is critical.

1. **Authoritative Accounting in `AiManager`**: For each file being processed, a worker thread uses a dedicated `AiManager` instance. This instance is the **source of truth** for usage statistics, meticulously tracking detailed data like `prompt_tokens`, `completion_tokens`, and `cost`. At the end of a file's processing, `IngestionManager` returns the results to `CommitManager` which aggregates this detailed, accurate data. This final aggregation ensures the final numbers are always correct.

2. **Live UI Updates in `CliManager`**: The `CliManager` is responsible for the live display. The core challenge is that the `CliManager`'s formatting callbacks (e.g., `format_ai_chunk`) are only passed an `AiResult` object.
   - **CRITICAL DESIGN CONSTRAINT**: The `AiResult` class is effectively immutable due to its instances being cached. It cannot be changed. It only provides a `total_tokens` field for a given operation and lacks the detailed breakdown.

**The Safe Architectural Pattern for Live Updates**: The solution is to use the `CliManager` to provide live updates to the UI without interfering with the authoritative accounting happening in `AiManager`.

- **Leverage Existing Methods**: The `CliManager` already has a thread-safe `update_ai_usage(stats: Dict[str, int])` method, which uses a lock to safely update the `ai_usage_stats` dictionary that backs the UI table
- **Use Context for Categorization**: The implementation adds a single line inside each `format_ai_*` method (e.g., `format_ai_chunk`). This line calls `self.update_ai_usage()`. Because the call is made from within a specific formatting method, the category is known (e.g., `'chunk'`). The `result.total_tokens` is passed for that category
- **Embrace the Dual System**: This approach provides immediate, real-time feedback in the UI. It does not attempt to replicate the detailed accounting of `AiManager`, which would be complex and error-prone. The live stats are for user feedback, and the final, authoritative stats from `CommitManager` ensure ultimate correctness. This avoids over-engineering and respects the system's established separation of concerns

#### Deadlock Prevention
**CRITICAL**: After the `progress_context` exits, the printer thread may still be active. Be extremely cautious when implementing methods that are called *after* the live display is finished. If such a method acquires a lock that is *also* used by the printer thread's `get_renderable` function (like the `ai_usage_stats` lock), it **must not** attempt to send output to the printer thread's queue (e.g., via `_print`). Doing so will cause a deadlock: the main thread will hold the lock and wait for the queue, while the printer thread holds the queue and waits for the lock. In these specific cases, print directly to the console (e.g., `self.console.print(...)`) to bypass the printer thread entirely.

#### Unified Multithreading Style Guide

**Key Requirements**:
- **Module Constants**: Every parallel processing class must have `MAX_WORKERS = 8` at module top
- **Class Location**: All parallel processing classes belong in `archive_agent/data/processor/` 
- **Logger Hierarchy**: Use instance loggers from `ai.cli` - never module-level loggers
- **Worker Limits**: Always use `min(MAX_WORKERS, len(items))` pattern
- **Variable Naming**: Use `future_to_[item_type]` convention for executor mappings
- **Error Handling**: Per-item exception handling that doesn't stop batch processing
- **Resource Isolation**: Create dedicated AI managers per worker thread
- **Result Collection**: Maintain original order when required using `results_dict` pattern

#### Thread Safety Pattern for AI Callbacks

**CRITICAL**: Callbacks requiring AI access must accept the AiManager as a parameter rather than being bound to a shared instance. This pattern ensures:
- **Worker Isolation**: Each parallel worker gets dedicated AI instance
- **No Resource Contention**: Workers don't compete for shared AI state
- **Cache Separation**: Each worker maintains independent AI cache
- **Thread Safety**: No race conditions on AI manager state

**Implementation Pattern**:
```python
# Correct: AI-dependent callback accepts AiManager parameter
def process_item(ai: AiManager, item_data) -> Result:
    return ai.some_operation(item_data)

# In parallel processor:
ai_worker = self.ai_factory.get_ai()  # Dedicated instance
result = callback(ai_worker, item)
```

#### Nested Progress Architecture

Archive Agent uses a three-level progress tracking system with smart phase detection:

**Key Features**:
- **Smart Phase Detection**: PDF/Binary files get 3 phases (Vision+Chunking+Embedding), others get 2 (Chunking+Embedding)
- **Dynamic Progress Totals**: Sub-tasks set `total=len(requests)` when request counts are known (not when created)
- **File-Level Updates**: File progress advances as phases complete (1/3, 2/3, 3/3)
- **Meaningful Progress**: Shows actual work completed (sentences/images/chunks processed)
- **Real-time Updates**: Progress tracking works correctly with parallel processing without serializing worker threads
- **Clean Task Management**: Sub-tasks are removed after completion, preventing UI clutter

## Parallel Processing Architecture

Archive Agent implements comprehensive parallel processing across major operations using a unified multithreading architecture.

### Parallelized Operations
- **Vision Processing**: Cross-page parallel OCR and entity extraction via `VisionProcessor` (in `data/processor/`)
  - Essential for STRICT OCR mode where each PDF page becomes a full-page image
  - Processes multiple images simultaneously across different documents
  - Supports both PDF image bytes and Binary PIL Images with unified interface
- **Chunk Embedding**: Parallel vector embedding via `EmbedProcessor` (in `data/processor/`)
  - Processes multiple text chunks simultaneously using ThreadPoolExecutor
  - Real-time progress updates instead of waiting at 0% for most of runtime
  - Each worker gets isolated AiManager instance for thread safety
- **File Processing**: Concurrent file processing across multiple documents in `IngestionManager` (in `core/`)

### Sequential Operations with Progress Tracking
- **Smart Chunking**: Sequential processing due to "carry" mechanism dependencies
  - Text chunks can overflow from one block to the next, creating strict sequential dependencies
  - Block N+1 depends on results of Block N for proper chunk boundaries
  - Comprehensive progress tracking based on sentences processed (not blocks processed)
  - Maintains semantic coherence and prevents chunk fragmentation
  - Infrastructure exists for future parallelization opportunities (ChunkProcessor pattern ready)

### Key Architectural Insights

#### Factory Pattern for Thread Safety
All parallel operations use `AiManagerFactory` to provide worker AI instances:
- Each parallel worker gets dedicated AI instance via `ai_factory.get_ai()`
- Workers don't compete for shared AI state or cache
- No race conditions on AI manager state
- Cache separation maintains independence between workers

#### Callback Injection Pattern
**CRITICAL**: AI-dependent operations must receive AiManager as first parameter:
```python
# Correct pattern for thread-safe callbacks
def image_to_text_callback(ai: AiManager, image: Image.Image) -> Optional[str]:
    return ai.vision_operation(image)

# In parallel processor:
ai_worker = self.ai_factory.get_ai()  # Dedicated instance per worker
result = callback(ai_worker, item_data)
```

This pattern ensures worker isolation and prevents shared state corruption.

#### Multi-Stage Loader Architecture
Both PDF and Binary document loaders use consistent multi-stage patterns:
1. **Content Extraction**: Text/image extraction from source
2. **Vision Processing**: Parallel AI vision operations (if applicable)
3. **Assembly**: Final document construction with processed content

This architecture enables surgical integration of parallel processing without breaking existing functionality.

#### Critical Implementation Principles
- **Zero Behavioral Changes**: All parallelization maintains byte-for-byte identical output
- **Preserve Error Handling**: Existing error recovery patterns must be maintained
- **Per-item Error Isolation**: Individual failures don't stop batch processing
- **Order Preservation**: Results maintain original sequence when required using `results_dict` pattern
- **Resource Management**: Appropriate concurrency limits prevent resource exhaustion
- **Surgical Integration**: Only replace core processing loops, preserve all filtering/formatting logic
- **System Brittleness**: The system is verified to work but extremely brittle - extreme caution required

#### VisionProcessor Architecture Details
The `VisionProcessor` implements a sophisticated parallel vision processing system:

**VisionRequest dataclass components**:
- `image_data: Union[bytes, Image.Image]` - Supports both PDF bytes and PIL Images
- `callback: ImageToTextCallback` - The actual vision callback to execute
- `formatter: Callable[[Optional[str]], str]` - Lambda for conditional formatting
- `log_header: str` - Pre-built log message for progress tracking
- `image_index: int` - For logging context and error reporting
- `page_index: int` - Page context for clean reassembly (PDF only)

**Key Design Patterns**:
- **Front-loaded Processing**: Collects ALL requests across ALL pages/images before parallel execution
- **Formatter Pattern**: Lambda functions preserve existing conditional formatting logic
- **Dual Format Support**: Automatically converts PDF bytes to PIL Images as needed
- **Clean Reassembly**: Results mapped back to original structure using context indices

#### OCR Strategy Formatting Preservation
VisionProcessor maintains exact formatting behavior for different OCR strategies:
- **STRICT strategy failures**: `"[Unprocessable page]"`
- **RELAXED strategy failures**: `"[Unprocessable image]"`  
- **RELAXED strategy success**: `"[{image_text}]"` (brackets added)
- **STRICT strategy success**: `"{image_text}"` (no brackets)
- **Binary documents**: `"[{image_text}]"` (always brackets) or `"[Unprocessable Image]"`

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
