# Archive Agent Parallelization Refactoring Plan

## Overview

Currently, CommitManager handles a list of FileData concurrently. However, there are sequential bottlenecks within each FileData that limit true parallelization and create poor progress UX:

- Each FileData first calls the loader for the file type, which in turn may call image-to-text-callbacks for any images.
  These are the binary document loader in text.py, and the PDF loader in pdf.py.
  The loaders currently work sequentially, calling the AI vision function after each other, then joining the image text with the regular document text.
  Split this logic to make a list of AI vision call requests, then parallelize these, too.
  Then join the results with the regular document text.
- Each FileData then iterates over a list of chunks, each requiring a call to ai.embed. Parallelize this, too.
- This approach will fix the issue that, right now, the progress is only updated from the final FileData embedding loop; currently, everything happening before that is showing 0% for most of the runtime.

## Implementation Strategy

Plan to proceed in a multi-step fashion, as outlined below. Reflect deeply on the optimal sequence and use extreme programming with small deltas, verifying the architecture implementation at each step.

## Phase 1: Chunk Embedding Parallelization ✅ COMPLETED

### Objectives
- Parallelize the sequential chunk embedding loop in FileData.process()
- Improve progress tracking to show real-time embedding progress
- Maintain thread safety with isolated AiManager instances per embedding worker
- Preserve all existing behavior while adding parallelization

### Implementation Details

**1.1 FileData.process() is already multithreaded. DONE**

**1.2 Make FileData accept an AiFactory so it can spawn AiManagers for the chunks itself ✅**
- Updated `CommitManager.commit_diff()` to pass `ai_factory` instead of `ai_factory.get_ai()`
- Modified `FileData.__init__()` to accept `AiManagerFactory` parameter
- FileData creates primary `AiManager` for non-embedding operations (vision, chunking, config)
- FileData uses factory to spawn worker `AiManager` instances for embedding operations

**1.3 Parallelize chunking loop ✅**
- Created dedicated `ChunkEmbeddingProcessor` class in `archive_agent/data/ChunkEmbeddingProcessor.py`
- Implemented parallel embedding using `ThreadPoolExecutor` with `MAX_WORKERS = 8` constant
- Each embedding worker gets isolated `AiManager` instance via `ai_factory.get_ai()`
- Results collected and returned in original order using `results_dict` pattern
- Per-chunk error handling that doesn't stop batch processing
- Real-time progress updates during embedding (fixes 0% progress issue)

### Architectural Benefits Achieved
- **Performance**: Parallel embedding instead of sequential processing
- **UX**: Users see progress during embedding phase instead of waiting at 0%
- **Thread Safety**: Each worker has isolated AiManager instance
- **Maintainability**: Clean class separation following unified multithreading style
- **Error Resilience**: Per-chunk failures don't break entire batch
- **Resource Management**: Appropriate concurrency limits prevent resource exhaustion

### Thread Safety Implementation
- Follows unified multithreading style guide in CLAUDE.md
- Uses instance loggers from `ai.cli` hierarchy (never module-level loggers)
- Each parallel worker creates dedicated AiManager via factory pattern
- Progress updates handled safely within worker threads
- Results aggregation maintains original chunk ordering

### Testing Status
- ✅ All unit tests pass (`./audit.sh`)
- ✅ Type checking clean with proper imports
- ✅ Code formatting compliant
- ✅ Manual runtime testing verified working
- ✅ Multithreading architecture preserves all 4 core requirements

## Phase 2: Vision Parallelization

### Architecture Discovery
After deep analysis, we discovered that:
- **PDF Loader already has perfect multi-stage architecture**: `get_pdf_page_contents()` → `extract_image_texts_per_page()` → `build_document_text_from_pages()`
- **Binary Document Loader has inline processing**: Vision happens during document building with immediate injection
- **No complex position mapping needed**: Existing data structures already encode positioning

### Phase 2A: Binary Document Loader Refactoring ✅ COMPLETED

#### Objectives
- Refactor binary document loader to match PDF's multi-stage pattern
- Maintain 100% backward compatibility with existing callback interface
- Prepare foundation for VisionProcessor integration

#### Files Modified
- `archive_agent/data/loader/text.py` ✏️ MODIFIED

#### Implementation Completed
1. **Extracted image processing into `extract_binary_image_texts()` function**:
   - Moved existing inline processing logic into dedicated function
   - Preserves all logging, error handling, and callback behavior
   - Returns list of formatted image texts with brackets and error placeholders
   - Handles disabled vision configuration with appropriate warnings

2. **Created `build_binary_document_with_images()` assembly function**:
   - Handles final document assembly with image texts appended
   - Maintains identical spacing, brackets, and line structure
   - Uses existing `LineTextBuilder.push()` operations exactly as before

3. **Refactored `load_binary_document()` to multi-stage pattern**:
   - **Stage 1**: Text extraction via Pandoc (unchanged)
   - **Stage 2**: Image extraction from ZIP archive (unchanged) 
   - **Stage 3**: Vision processing via new function (same logic)
   - **Stage 4**: Assembly via new function (same result)

#### Critical Requirements Met
- **Zero behavioral changes**: Same input/output, error handling, formatting
- **Same callback interface**: `image_to_text_callback` used exactly as before
- **Identical text assembly**: Same brackets, spacing, line structure
- **Perfect test compatibility**: All 59 tests pass unchanged

#### Testing Status
- ✅ All unit tests pass (`./audit.sh`)
- ✅ Type checking clean
- ✅ Code formatting compliant
- ✅ Identical behavior verified

### Phase 2B: VisionProcessor Implementation ✅ COMPLETED

#### Objectives
- Create unified VisionProcessor for both PDF and Binary loaders
- Implement parallel vision processing with MAX_WORKERS = 8
- Follow unified multithreading style guide
- Support both PDF image bytes and Binary PIL Images

#### Files Added
- `archive_agent/data/VisionProcessor.py` ✅ CREATED

#### VisionProcessor Architecture Implementation
- **VisionRequest dataclass**: Contains image data, callback, formatter lambda, and logging context
  - `image_data: Union[bytes, Image.Image]` - Supports both PDF bytes and PIL Images
  - `callback: ImageToTextCallback` - The actual vision callback to execute
  - `formatter: Callable[[Optional[str]], str]` - Lambda for conditional formatting
  - `log_header: str` - Pre-built log message for progress tracking
  - `image_index: int` - For logging context and error reporting

- **VisionProcessor class**: Handles parallel execution with ThreadPoolExecutor
  - Uses `MAX_WORKERS = 8` constant following unified style
  - Creates dedicated `AiManager` per vision request via `ai_factory.get_ai()`
  - Uses `ai.cli` logger hierarchy for thread-safe logging
  - Maintains original request order using `results_dict` pattern
  - Per-vision error handling that doesn't stop batch processing

#### Critical Architectural Fix
**Problem Discovered**: Initial implementation had architectural flaw where callbacks were bound to FileData's shared AI manager, violating thread safety.

**Solution Implemented**: 
- Updated all `ImageToTextCallback` signatures to accept `AiManager` as first parameter:
  ```python
  ImageToTextCallback = Callable[[AiManager, Image.Image], Optional[str]]
  ```
- Modified all vision callbacks in `FileData.py`:
  - `image_to_text_ocr(self, ai: AiManager, image: Image.Image)`
  - `image_to_text_entity(self, ai: AiManager, image: Image.Image)`
  - `image_to_text_combined(self, ai: AiManager, image: Image.Image)`
- Injected `ai_factory` into PDF and Binary loaders for worker AI creation
- VisionProcessor now properly creates and passes dedicated `ai_worker` to callbacks

#### Implementation Details
- **Thread Safety**: Each parallel worker gets isolated AiManager instance
- **Dual Format Support**: Converts PDF bytes to PIL Images as needed
- **Unified Interface**: Same VisionProcessor handles both loader types
- **Formatter Pattern**: Lambda functions preserve existing conditional formatting logic
- **Progress Tracking**: Real-time logging with pre-built context messages
- **Error Resilience**: Individual vision failures don't break entire batch

#### Testing Status
- ✅ All unit tests pass (`./audit.sh`)
- ✅ Type checking clean with proper imports
- ✅ Code formatting compliant
- ✅ Whitespace issues resolved
- ✅ Thread safety verified with AiManagerFactory pattern

### Phase 2C: PDF Loader Vision Parallelization ✅ COMPLETED

#### Objectives
- Integrate VisionProcessor into PDF loader's existing multi-stage architecture
- Maintain identical output format: `List[List[str]]` (per-page image texts)
- Preserve all existing OCR strategy logic and error handling

#### Files Modified
- `archive_agent/data/loader/pdf.py` ✏️ MODIFIED (internal `extract_image_texts_per_page()` only)
- `archive_agent/data/VisionProcessor.py` ✏️ MODIFIED (added `page_index` field and single-line validation)

#### Implementation Completed
1. **Added `page_index` to VisionRequest**: Eliminated complex mapping arrays by storing page context directly in request
2. **Front-loaded VisionProcessor**: Created at function start, collects ALL requests across ALL pages, processes in parallel
3. **Preserved all original logic**: 
   - Tiny image filtering (unchanged)
   - OCR strategy callback selection (unchanged)
   - Formatter lambdas with exact bracket/error logic (unchanged)
   - Logging calls (restored missing `logger.info()`)
4. **Moved validation to VisionProcessor**: Single-line assertion now validates raw AI result before formatting (matching original flow)
5. **Clean reassembly**: Results mapped back to per-page structure using `request.page_index`

#### Critical Architectural Benefits
- **True cross-page parallelization**: Essential for STRICT mode where each page becomes single full-page image
- **Surgical integration**: Only replaced core AI processing loop, preserved all filtering/formatting logic
- **Identical behavior**: All 59 tests pass, exact equivalence to original modulo parallelization
- **Performance gain**: Parallel vision processing instead of sequential page-by-page processing

#### Key Formatting Logic Preserved
- **STRICT strategy failures**: `"[Unprocessable page]"`
- **RELAXED strategy failures**: `"[Unprocessable image]"`
- **RELAXED strategy success**: `"[{image_text}]"` (brackets added)
- **STRICT strategy success**: `"{image_text}"` (no brackets)

#### Testing Status
- ✅ All unit tests pass (`./audit.sh`)
- ✅ Type checking clean
- ✅ Code formatting compliant
- ✅ Behavior equivalence verified
- ✅ Single-line validation properly implemented in VisionProcessor

### Phase 2D: Binary Loader Vision Parallelization ⏳ NEXT

#### Objectives
- Integrate VisionProcessor into binary loader's new multi-stage architecture
- Maintain identical output format: `List[str]` (formatted image texts)
- Preserve all existing error handling and bracket formatting

#### Files to Modify  
- `archive_agent/data/loader/text.py` ✏️ MODIFY (internal `extract_binary_image_texts()` only)

#### Implementation Plan
1. **Replace sequential loop with VisionProcessor batch processing**
2. **Create formatter lambda with consistent bracket logic**
3. **Handle disabled vision configuration appropriately**
4. **Maintain identical logging and error messages**
5. **Add page_index=0 to VisionRequest** (binary docs are single-page)

#### Key Formatting Logic to Preserve
- **Success cases**: `"[{image_text}]"` (always brackets for binary docs)
- **Failure cases**: `"[Unprocessable Image]"` (consistent placeholder)

### Phase 2E: Chunking Parallelization ⏳ PLANNED

#### Objectives
- Parallelize `get_chunks_with_reference_ranges()` AI chunking operations
- Maintain identical chunk ordering and reference range mapping
- Improve progress tracking during chunking phase
- Follow unified multithreading style guide

#### Current Bottleneck Analysis
The `get_chunks_with_reference_ranges()` function in `archive_agent/data/chunk.py` currently processes chunks sequentially:
```python
for block_index, block_of_sentences in enumerate(blocks_of_sentences):
    chunk_result = chunk_callback(ai_factory.get_ai(), block_of_sentences)
    # Sequential processing creates bottleneck
```

#### Files to Modify
- `archive_agent/data/chunk.py` ✏️ MODIFY (`get_chunks_with_reference_ranges()` function)
- Create `archive_agent/data/ChunkProcessor.py` ➕ NEW (similar to ChunkEmbeddingProcessor)

#### Implementation Plan
1. **Create ChunkProcessor class** with MAX_WORKERS = 8 constant
2. **Extract chunk processing logic** from `get_chunks_with_reference_ranges()`
3. **Batch process all chunk blocks** in parallel via ThreadPoolExecutor
4. **Maintain original chunk ordering** using results_dict pattern
5. **Preserve all reference range mapping** and context logic
6. **Thread-safe progress tracking** if progress callback provided
7. **Per-chunk error handling** that doesn't stop batch processing

#### Critical Requirements
- **Preserve chunk ordering**: Results must maintain exact sequence for reference ranges
- **Maintain reference mapping**: Each chunk's sentence-to-line mapping must be identical
- **Same error handling**: Individual chunk failures should not break entire batch
- **Progress compatibility**: Work with existing progress tracking in FileData.process()

#### Testing Requirements
- All 59 tests must pass unchanged
- Chunk ordering verification
- Reference range mapping verification
- Error handling regression testing

### Phase 2F: README Documentation Update ⏳ PLANNED

#### Objectives
- Document complete parallel processing capabilities
- Highlight performance improvements across all bottlenecks
- Update architecture description with concurrency features
- Provide performance benchmarks and recommendations

#### Files to Modify
- `README.md` ✏️ MODIFY (add concurrency section)

#### Content to Add
1. **Concurrency Architecture Section**
   - Overview of parallel processing across the entire pipeline
   - ThreadPoolExecutor with MAX_WORKERS = 8 across all operations
   - AiManagerFactory pattern for thread isolation

2. **Parallelized Operations**
   - **Chunk Embedding**: Parallel vector embedding with real-time progress
   - **Vision Processing**: Cross-page parallel OCR and entity extraction
   - **AI Chunking**: Parallel semantic chunking operations
   - **File Processing**: Concurrent file processing in CommitManager

3. **Performance Benefits**
   - Strict OCR mode: True cross-page parallelization essential for performance
   - Large document processing: Significant speedup with multiple AI operations
   - Progress UX: Real-time updates instead of 0% for most of runtime
   - Resource utilization: Optimal AI provider usage patterns

4. **Thread Safety Guarantees**
   - Isolated AI manager instances per worker thread
   - Decoupled logging architecture with printer thread
   - Safe progress tracking and UI updates
   - No race conditions or resource contention

5. **Configuration Recommendations**
   - Optimal MAX_WORKERS values for different AI providers
   - Memory usage considerations with parallel processing
   - API rate limiting guidance for external providers

## Phase 3: Future Enhancements (CONCEPTUAL)

### Potential Additional Parallelization
- **Chunking Operations**: Parallelize AI chunking calls if chunking becomes bottleneck
- **Vision Feature Requests**: Parallelize OCR vs Entity extraction if both are enabled
- **Document Preprocessing**: Parallelize sentence extraction and NLP preprocessing

### Architectural Considerations
- Monitor memory usage with increased parallelization
- Consider API rate limiting for external AI providers
- Evaluate optimal MAX_WORKERS values for different operation types
- Maintain balance between parallelization benefit and resource consumption

## Critical Implementation Principles

### EXTREME CAUTION REQUIRED
- **Never break existing functionality** - the current system is verified to work but extremely brittle
- **Preserve all error handling patterns** - existing error recovery must be maintained
- **Maintain identical output formats** - document text assembly must be byte-for-byte identical
- **Respect multithreading architecture** - follow decoupled logging and thread safety requirements

### Unified Multithreading Style Guide
- **Module Constants**: Every parallel processing class must have `MAX_WORKERS = 8` at module top
- **Class Location**: All parallel processing classes belong in `archive_agent/data/` 
- **Logger Hierarchy**: Use instance loggers from `ai.cli` - never module-level loggers
- **Worker Limits**: Always use `min(MAX_WORKERS, len(items))` pattern
- **Variable Naming**: Use `future_to_[item_type]` convention for executor mappings
- **Error Handling**: Per-item exception handling that doesn't stop batch processing
- **Resource Isolation**: Create dedicated AI managers per worker thread
- **Result Collection**: Maintain original order when required using `results_dict` pattern

### Verification Strategy
- Run `./audit.sh` after each change for type checking and formatting
- Manual runtime testing with `./archive-agent.sh update --verbose --nocache`
- Visual verification of multithreading display (progress bars, logging, UI stability)
- Regression testing to ensure identical processing results

### Rollback Strategy
- Git commits after each working milestone
- Maintain ability to revert to working state at any point
- Test suite validation before proceeding to next phase

---

## Current Status Summary

**Phase 1: COMPLETED ✅**
- Chunk embedding parallelization implemented and tested
- ChunkEmbeddingProcessor class created with unified multithreading style
- Real-time progress tracking working
- Thread safety verified with AiManagerFactory pattern

**Phase 2A: COMPLETED ✅**
- Binary document loader successfully refactored to multi-stage pattern
- Foundation prepared for VisionProcessor integration
- Zero behavioral changes achieved, all tests pass
- Architecture now matches PDF loader's multi-stage structure

**Phase 2B: COMPLETED ✅**
- VisionProcessor implementation with unified parallel vision processing
- Support for both PDF bytes and Binary PIL Images
- Unified multithreading style with MAX_WORKERS = 8
- Critical architectural fix: Callbacks now accept AiManager parameter
- Thread safety verified with isolated AI workers per vision request

**Phase 2C: COMPLETED ✅**
- PDF loader vision parallelization with VisionProcessor integration
- True cross-page parallelization essential for STRICT OCR mode
- Surgical integration preserving all original logic and formatting
- Added page_index to VisionRequest for clean reassembly
- Single-line validation moved to VisionProcessor matching original flow

**Phase 2D: NEXT ⏳**
- Binary loader vision parallelization using VisionProcessor
- Simpler than PDF (single-page documents, consistent bracket formatting)
- Complete the vision processing parallelization across all loaders

**Phase 2E: PLANNED ⏳**
- AI chunking parallelization in `get_chunks_with_reference_ranges()`
- Create ChunkProcessor class following unified multithreading style
- Final sequential bottleneck elimination in the processing pipeline

**Phase 2F: PLANNED ⏳**
- README documentation update advertising full parallel capabilities
- Performance benchmarks and architecture documentation
- User-facing concurrency feature highlight

**Next Steps:**
1. ~~Create `VisionProcessor.py` with unified parallel vision processing~~ ✅ COMPLETED
2. ~~Integrate VisionProcessor into PDF loader (`extract_image_texts_per_page()` internals)~~ ✅ COMPLETED
3. Integrate VisionProcessor into Binary loader (`extract_binary_image_texts()` internals) ⏳ NEXT
4. Parallelize AI chunking operations (`get_chunks_with_reference_ranges()`)
5. Create comprehensive README documentation of parallel capabilities
6. Performance benchmarking and optimization recommendations

The architecture is well-designed and Phases 2A, 2B, and 2C are complete! The VisionProcessor provides unified parallel vision processing, with critical thread safety fixes and perfect behavior equivalence. PDF loader now achieves true cross-page parallelization. Ready for Phase 2D: Binary loader integration!

## Key Architectural Insights Gained

### Thread Safety Pattern for AI Callbacks
The most critical discovery was that callbacks requiring AI access must accept the AiManager as a parameter rather than being bound to a shared instance. This pattern ensures:
- **Worker Isolation**: Each parallel worker gets dedicated AI instance
- **No Resource Contention**: Workers don't compete for shared AI state
- **Cache Separation**: Each worker maintains independent AI cache
- **Thread Safety**: No race conditions on AI manager state

### Unified Multithreading Architecture
The refactoring established a consistent pattern across all parallel processing:
1. **Factory Pattern**: AiManagerFactory provides worker AI instances
2. **Callback Injection**: AI-dependent operations receive AiManager as first parameter
3. **Consistent Constants**: All parallel processors use `MAX_WORKERS = 8`
4. **Logger Hierarchy**: Instance loggers from `ai.cli` (never module-level)
5. **Error Isolation**: Per-item failures don't stop batch processing
6. **Order Preservation**: Results maintain original sequence when required

This architecture now scales consistently across chunk embedding, vision processing, and any future parallel operations.