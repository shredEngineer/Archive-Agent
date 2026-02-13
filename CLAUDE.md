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
- `archive_agent/data/ProgressManager.py` - Centralized hierarchical progress management
- `archive_agent/data/loader/pdf.py` - PDF processing with business logic (OCR strategy resolution)
- `archive_agent/data/loader/PdfDocument.py` - Clean PDF abstraction interfaces (PdfDocument, PdfPage, PdfPageContent)
- `archive_agent/data/loader/backend/pdf_pymupdf.py` - PyMuPDF implementation backend (fully isolated)
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

**Conda/Miniconda Compatibility Note**: All scripts (`install.sh`, `audit.sh`, `archive-agent.sh`) automatically unset conda environment variables (`CONDA_DEFAULT_ENV` and `CONDA_PREFIX`) to prevent conflicts with `uv`. When conda is active, `uv` incorrectly resolves to the conda Python environment instead of the project's `.venv`, causing missing dependency errors. The `unset` statements at the beginning of each script resolve this automatically without requiring users to deactivate conda.

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

### Logger Usage Requirements
- **NEVER remove valuable logging information** - use conditional flags instead
- **Use centralized logger hierarchy** - all loggers derive from `ai.cli` system for thread safety
- **Avoid redundant format_file() calls** - prefixed loggers already include file context
- **Appropriate severity levels**: Use `.error()` for processing failures, `.critical()` only for system threats

### Progress Management
- **Use centralized ProgressManager** for all progress operations instead of raw Rich Progress
- **ProgressInfo pattern**: Bundle ProgressManager + phase_key in dataclass for clean API boundaries
- **Hierarchical progress**: Parent progress automatically calculated from weighted child completion
- **Sub-phase support**: Vision phase contains PDF analyzing and Vision AI sub-phases
- **Stable visual ordering**: Tasks appear in creation order (file → phases → sub-phases sequentially)  
- **Weighted phases**: Different processing phases contribute proportionally to overall progress
- **Complete implementation**: No transition period - all components use unified ProgressManager system
- **Progress Symmetry**: All image-containing files (PDF/Binary/Image) show consistent vision progress tracking

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
5. Yields the ProgressManager instance directly for hierarchical progress tracking

**Decoupling Callers**: Callers like `IngestionManager` use the `progress_context` in a simple `with` block. Inside this block, they create task hierarchies using the ProgressManager. This allows the caller to be completely ignorant of the underlying `rich` objects or the multithreaded logging complexity.

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
- **ThreadPoolExecutor Usage**: Use `max_workers=MAX_WORKERS` directly (ThreadPoolExecutor automatically limits workers to task count)
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

Archive Agent uses a hierarchical progress tracking system with smart phase detection:

**Top-Level File Phases**:
- **Smart Phase Detection**: Files with images (PDF/Binary/Image) get 3 phases (Vision+Chunking+Embedding), text-only files get 2 (Chunking+Embedding)
- **File-Level Updates**: File progress advances as phases complete (1/3, 2/3, 3/3) for image files or (1/2, 2/2) for text files
- **Progress Symmetry**: All image processing (PDF pages, binary images, standalone images) shows consistent "AI Vision" subtask

**Image Processing Phase Breakdown** (for PDF/Binary files):

**PDF Processing Sub-tasks**:
- **PDF Analyzing**: Page-by-page analysis and OCR strategy determination
  - Created conditionally when `progress` tracking is enabled
  - Tracks progress per page analyzed (`total=number_of_pages`)
  - Determines OCR strategy (AUTO→STRICT/RELAXED) based on text content thresholds
  - Prepares page layout extraction and image identification
  - Uses separate `analyzing_task_id` for isolated progress tracking
- **AI Vision**: AI-powered image-to-text conversion operations
  - Uses `vision_task_id` parameter for progress coordination
  - Dynamic progress totals set when vision request counts are determined
  - Handles both full-page images (STRICT mode) and embedded images (RELAXED mode)
  - Parallel processing via `VisionProcessor` with proper thread isolation

**Binary Processing Sub-tasks**:
- **Image Processing Only**: Binary documents skip analyzing phase
  - Direct vision processing of extracted images
  - Uses same `vision_task_id` parameter pattern as PDFs

**Standalone Image Processing**:
- **Single Image Vision**: Standalone image files (JPG/PNG/etc.) get direct vision processing
  - Creates "AI Vision" subtask for progress tracking  
  - Preserves original business logic: fails entirely if vision processing fails
  - No parallel processing overhead (single image doesn't need threading)
  - Maintains exact same callback pattern as original implementation

**Progress Architecture Features**:
- **Hierarchical Task Structure**: Vision phase dynamically contains analyzing and/or vision sub-tasks based on file type
- **Dynamic Progress Totals**: Vision tasks created with `total=None`, updated when request counts known
- **Parameter Clarity**: `vision_task_id` clearly indicates vision processing progress tracking
- **Clean Task Management**: All sub-tasks properly removed after completion to prevent UI clutter
- **Thread-Safe Updates**: Progress updates routed through centralized queue system to avoid lock contention

## Parallel Processing Architecture

Archive Agent implements comprehensive parallel processing across major operations using a unified multithreading architecture.

### Parallelized Operations
- **Image Processing**: Cross-page parallel OCR and entity extraction via `VisionProcessor` (in `data/processor/`)
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
  - **Block-Level Error Resilience**: If AI chunking fails for a block (e.g., model token limit exceeded, malformed response after all retries), the block is SKIPPED and the file continues processing. Failed blocks are logged as `BLOCK SKIPPED` errors with sentence counts, and a final `INCOMPLETE INGESTION` summary is logged per file. Carry state is reset so subsequent blocks start fresh. This prevents a single problematic block from losing an entire file's worth of chunks.

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

**PDF Document Processing**:
1. **Document Opening**: PDF backend initialization via clean abstraction layer
2. **PDF Content Extraction**: Page-by-page content extraction via `page.get_content()`
   - Extracts text, image bytes, and block counts through streamlined interface
   - Clean separation: PDF backend handles raw data, main code handles business logic
3. **OCR Strategy Resolution**: Archive Agent business logic determines processing approach
   - Resolves AUTO OCR strategy to STRICT or RELAXED based on text content thresholds
   - For STRICT mode: Uses `page.get_full_page_pixmap()` helper for full-page rendering
   - For RELAXED mode: Uses existing extracted image bytes from layout
4. **Image Processing**: Parallel AI vision operations for image-to-text conversion
5. **Assembly**: Final document construction with processed content and page mapping

**Binary Document Processing**:
1. **Content Extraction**: Pandoc-based text extraction from source document
2. **Image Extraction**: ZIP-based image extraction from document container
3. **Image Processing**: Parallel AI vision operations for embedded images
4. **Assembly**: Final document construction with processed content

This architecture enables surgical integration of parallel processing without breaking existing functionality.

#### Critical Implementation Principles
- **Zero Behavioral Changes**: All parallelization maintains byte-for-byte identical output
- **Preserve Error Handling**: Existing error recovery patterns must be maintained
- **Per-item Error Isolation**: Individual failures don't stop batch processing
- **Order Preservation**: Results maintain original sequence when required using `results_dict` pattern
- **Resource Management**: Appropriate concurrency limits prevent resource exhaustion
- **Surgical Integration**: Only replace core processing loops, preserve all filtering/formatting logic
- **System Brittleness**: The system is verified to work but extremely brittle - extreme caution required

#### PDF Processing Limitations and Surgical Synchronization

**PyMuPDF Threading Constraint**: PyMuPDF (fitz) library does not support multithreading and explicitly warns against concurrent usage:

> "PyMuPDF does not support running on multiple threads - doing so may cause incorrect behaviour or even crash Python itself."

**Architectural Solution: Abstraction Layer + Surgical Synchronization**

Archive Agent implements a two-tier approach that both isolates PyMuPDF dependencies and maximizes parallelism while respecting library constraints:

**PDF Abstraction Architecture**:
- **Interface Definition**: Clean abstract classes in `archive_agent/data/loader/PdfDocument.py`
  - `PdfDocument` - Document-level operations (iteration)
  - `PdfPage` - Page-level operations (text, images, rendering)  
  - `PdfPageContent` - Data container for page content
- **PyMuPDF Backend**: Implementation in `archive_agent/data/loader/backend/pdf_pymupdf.py`
- **Business Logic Layer**: OCR strategy resolution in `archive_agent/data/loader/pdf.py`
- **Clean Separation**: PyMuPDF completely isolated from main code
- **Pluggable Architecture**: Alternative PDF backends (pypdf, pdfplumber) can replace PyMuPDF
- **Streamlined Interface**: Object-oriented design with helper methods

**Synchronized Operations**:
- **PDF Analyzing Phase Only**: `get_pdf_page_contents()` function calls are serialized using `_PDF_ANALYZING_LOCK`
- **All Other Operations**: Vision processing, chunking, and embedding run in full parallel

**Implementation Details**:
- Module-level `threading.Lock()` in `archive_agent/data/loader/pdf.py` (temporary, marked for removal)
- Lock acquired only during PyMuPDF backend operations (page content extraction)
- Lock released immediately after analyzing phase completes
- All subsequent phases (vision, chunking, embedding) execute in parallel across all files
- Verbose logging shows lock acquisition/release for debugging
- **Future**: Lock removal planned when PyMuPDF backend is replaced with thread-safe alternative

**Processing Flow per PDF**:
1. **File Processing**: Fully parallel (`ThreadPoolExecutor` with `MAX_WORKERS=8`)
2. **PDF Analyzing**: Serialized (one at a time due to lock)
3. **Image Processing**: Parallel (within and across files)
4. **Chunking**: Parallel (across files)
5. **Embedding**: Parallel (across files)

**Performance Characteristics**:
- **Maximum Parallelism**: Only the minimal required operation (PDF analyzing) is serialized
- **Optimal Resource Utilization**: Vision/chunking/embedding phases fully utilize available cores
- **Predictable Performance**: Eliminates PyMuPDF lock contention while maintaining concurrency benefits
- **Mixed Workloads**: Non-PDF files maintain full parallelization throughout all phases

**Key Insight**: Surgical synchronization isolates the threading constraint to the smallest possible scope, maximizing overall system throughput by preserving parallelism everywhere else.

#### Streamlined PDF Interface Design

The PDF abstraction layer implements a clean, object-oriented interface that eliminates PyMuPDF-specific structures from the main codebase:

**Interface Principles**:
- **Separation of Concerns**: PDF interfaces handle raw data extraction only, business logic stays in main code
- **Object-Oriented Design**: Pages know how to represent themselves (`page.get_content()` vs external functions)
- **Helper Methods**: Common operations like full-page rendering have dedicated methods
- **Minimal Surface Area**: Only essential operations exposed, unused methods eliminated

**PdfPage Interface** (4 core methods):
- `get_text()` - Extract text content
- `get_image_bytes()` - Extract embedded image bytes  
- `get_counts()` - Block counts for logging statistics
- `get_pixmap(dpi)` - Render page at specified DPI
- `get_content()` - Convenience method combining above operations
- `get_full_page_pixmap(dpi)` - Helper for STRICT OCR mode

**PdfDocument Interface** (minimal):
- `__iter__()` - Iterate over pages (only required operation)
- Eliminated unused methods: `get_page_count()`, `close()` (never called in codebase)

**Benefits**:
- **Pluggable Architecture**: Any PDF library can implement the interface (pypdf, pdfplumber, etc.)
- **Type Safety**: Clean type contracts without PyMuPDF-specific types leaking
- **Maintainability**: PyMuPDF complexity isolated to single backend module
- **Performance**: Interface designed around actual usage patterns, not library capabilities

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

## Retry Logic Architecture

Archive Agent implements a comprehensive multi-layered retry system to handle transient failures across AI operations, database interactions, and network requests.

### RetryManager (Core Retry Infrastructure)

**Location**: `archive_agent/util/RetryManager.py`

The `RetryManager` class provides the foundational retry mechanism with exponential backoff:

**Key Features**:
- **Exponential Backoff**: Configurable delay scaling with `backoff_exponent` multiplier
- **Exception Filtering**: Only retries specific recoverable exception types
- **Pre-delay Support**: Optional fixed delay before first attempt
- **Comprehensive Logging**: Detailed attempt tracking with stack trace capture
- **Graceful Degradation**: Clean exit on non-recoverable exceptions

**Configuration Parameters**:
- `predelay`: Fixed delay before first attempt (seconds)
- `delay_min`: Starting backoff delay (defaults to 1.0s if 0)
- `delay_max`: Maximum backoff cap (seconds)
- `backoff_exponent`: Exponential multiplier for delay scaling
- `retries`: Maximum attempt count

**Supported Exception Types**:
- `AiProviderError` (custom AI provider errors)
- `OpenAIError` (OpenAI API errors)
- `RequestError`, `ResponseError` (Ollama errors)
- `ResponseHandlingException`, `UnexpectedResponse` (Qdrant errors)
- `ReadTimeout`, `TimeoutException` (HTTP timeouts)
- `requests.exceptions.RequestException` (general request errors)

**Usage Pattern**: Create RetryManager instance with configuration parameters, then call retry() method with target function and arguments.

### AiManager Dual Retry Strategy

**Location**: `archive_agent/ai/AiManager.py`

The `AiManager` implements a sophisticated dual-layer retry system by inheriting from `RetryManager`:

**Inheritance Configuration**: AiManager inherits from RetryManager with 10 retries, 60-second max delay, and exponential backoff of 2.

**Dual Retry Architecture**:

1. **Low-Level Network Retries**: Inherited `self.retry()` method handles:
   - Network timeouts and connection failures
   - AI provider API errors (OpenAI, Ollama)
   - Transient service interruptions

2. **High-Level Semantic Retries**: Manual retry loops for business logic failures:
   - Schema parsing validation errors
   - AI response format issues
   - Cache management on failed attempts

**Operations with Dual Retry Logic**:

**Chunking Operations**: Uses dual retry with high-level loop for schema validation failures and inherited low-level retry for network issues. Cache invalidation occurs on parsing failures.

**Reranking Operations**: Same dual-layer pattern as chunking with 10 high-level retries for schema validation and cache invalidation on parsing failures.

**Single-Layer Operations**:
- `embed()`: Only low-level retries (embedding vectors don't need schema validation)
- `query()`: Only low-level retries (query results are always valid)
- `vision()`: Only low-level retries (vision results are pre-validated)

**Critical Design Insight**: The dual retry strategy separates concerns:
- **Network layer**: Handles transient connectivity and API issues
- **Semantic layer**: Handles AI model inconsistencies and response format problems

### QdrantManager Database Retry Integration

**Location**: `archive_agent/db/QdrantManager.py`

All Qdrant database operations use a dedicated `RetryManager` instance:

**Configuration**: Uses class-level QDRANT_RETRY_KWARGS with 10 retries, 1-10 second delay range, and exponential backoff of 2.

**Protected Operations**:
- Collection existence checks and creation
- Vector upsert operations (batch processing)
- Point deletion and counting
- Similarity queries and scrolling
- All database read/write operations

**Usage Pattern**: All Qdrant operations wrapped in retry_manager.retry() calls with function and keyword arguments.

**Database-Specific Considerations**:
- Standardized retry count (10) for consistency across all operations
- Shorter maximum delay (10s) compared to AI operations for better responsiveness
- Focuses on connection and timeout issues rather than semantic failures


### Retry Strategy Guidelines

**When to Use Each Pattern**:

1. **RetryManager Direct**: Simple operations with network/API dependencies
   - Database connections
   - HTTP requests
   - File I/O operations

2. **AiManager Dual Retry**: AI operations requiring response validation
   - Text chunking with schema requirements
   - Reranking with structured output
   - Operations where AI responses need post-processing

3. **Single-Layer Retry**: Operations with guaranteed valid responses
   - Embedding generation (vectors are always valid)
   - Query operations (results don't need validation)

**Retry Configuration Best Practices**:
- **Standardized Retry Count**: All operations use 10 retries for consistency
- **AI Operations**: 60s max delay due to potential model processing time
- **Database Operations**: 10s max delay for better responsiveness
- **Network Operations**: Exponential backoff with operation-appropriate delay caps

**Thread Safety Considerations**:
- Each `AiManager` instance (one per worker thread) has independent retry state
- Retry managers don't share state between parallel operations
- Cache invalidation is thread-safe within individual AI instances

---

## Failure Mode Handling

Archive Agent implements consistent, predictable failure modes across all operations with proper error propagation and resilience guarantees.

### Exception Hierarchy

**`AiProviderError` (retryable)**: Network errors, API errors, transient failures. Caught by `RetryManager._RETRY_EXCEPTIONS` tuple for exponential backoff retry.

**`AiProviderMaxTokensError` (non-retryable)**: Model hit `max_tokens` limit, response truncated. Not in retry tuple — propagates immediately. Detected via `finish_reason='length'` check in all 4 provider operations (chunk/rerank/query/vision). Retrying the same input will always produce the same truncation — skip instantly.

**`typer.Exit` (fatal)**: All retries exhausted, operation cannot continue. Raised by `RetryManager._abort()` after 10 attempts. Must propagate to terminate process. **CRITICAL**: All parallel processors (VisionProcessor, EmbedProcessor, chunking loop) have explicit `except typer.Exit: raise` handlers to prevent swallowing.

### Block-Level Resilience (Chunking Only)

Chunking uses block-level error handling to maximize data recovery:
- **Per-Block Try/Except**: Each block (group of sentences) wrapped in try/except
- **On Failure**: Block skipped, logged as `CRITICAL: BLOCK SKIPPED`, carry state reset
- **File Continues**: Subsequent blocks process normally, partial file ingestion completes
- **Summary Logging**: `CRITICAL: INCOMPLETE INGESTION` logged at end with block count

Vision and embedding do NOT have block-level resilience — failures propagate as `typer.Exit` to ensure data integrity (partial vision results would corrupt document structure).

### Retry Configuration

All operations use consistent retry counts:
- **Network Retries**: 10 attempts via `RetryManager` (AI_RETRY_KWARGS)
- **Schema Retries**: 10 attempts in `AiManager` (SCHEMA_RETRY_ATTEMPTS, reduced from 100 in v18.5.0)
- **MAX_TOKENS**: 0 retries (instant skip via `AiProviderMaxTokensError`)

### Default Worker Counts

- `MAX_WORKERS_INGEST`: 4 (file-level parallelism)
- `MAX_WORKERS_VISION`: 4 (image processing parallelism)
- `MAX_WORKERS_EMBED`: 4 (chunk embedding parallelism)
- spaCy subprocess pool: Auto-scales to CPU count (via `ProcessPoolExecutor()` default)

All configurable via profile settings.

### Logging Severity Conventions

- **`.error()`**: Expected failures (parsing errors, single block failures, per-item errors in parallel loops)
- **`.critical()`**: Data loss events (block skipped, incomplete ingestion, system threats)
- **`.warning()`**: Retry attempts, performance issues, auto-repairs

---

## Progress Management Architecture

Archive Agent uses a hierarchical progress management system that provides true nested progress tracking with automatic cleanup and thread-safe concurrent updates.

### ProgressManager Integration

**Location**: `archive_agent/core/ProgressManager.py`

The `ProgressManager` is a self-contained hierarchical progress system that integrates with Archive Agent's CLI display architecture. It provides a generic interface for any nested progress scenario.

### ProgressInfo Pattern

**Location**: `archive_agent/core/ProgressManager.py`

The `ProgressInfo` dataclass bundles progress parameters to maintain stable function signatures:

```python
@dataclass
class ProgressInfo:
    progress_manager: ProgressManager
    parent_key: str  # Never Optional - progress tracking always enabled
```

**Factory Method**: ProgressManager provides `create_progress_info(parent_key)` to encapsulate all progress creation logic within the progress management system.

**Usage Benefits**:
- **Stable Function Signatures**: Functions accept single `progress_info: ProgressInfo` parameter
- **Clean Parameter Passing**: Single object containing all progress context
- **No Optional Complexity**: Progress tracking is always enabled, eliminating None checks
- **Extensible**: Easy to add new progress-related fields without changing signatures
- **Encapsulated Creation**: Factory method centralizes ProgressInfo creation logic

### Architecture Integration

**ContextManager**: Creates ProgressManager once with console access, passes through component hierarchy to IngestionManager.

**CliManager**: Integrates ProgressManager tree with Live display and AI usage stats in single unified view.

**Component Flow**: ContextManager → CommitManager → IngestionManager → progress_context() 

### Usage in Archive Agent

**File Processing**: ProgressManager provides hierarchical progress (Files → Individual Files → Processing Phases → Sub-phases) with automatic weighted calculations and progressive cleanup.

**ProgressInfo Pattern**: Functions use ProgressInfo dataclass for stable signatures and consistent progress tracking throughout codebase.

---

This guide should be updated whenever significant architectural changes are made to the codebase. Keep it current and comprehensive for future development sessions.
