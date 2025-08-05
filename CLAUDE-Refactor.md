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

### Phase 2B: VisionProcessor Implementation ⏳ NEXT

#### Objectives
- Create unified VisionProcessor for both PDF and Binary loaders
- Implement parallel vision processing with MAX_WORKERS = 8
- Follow unified multithreading style guide
- Support both PDF image bytes and Binary PIL Images

#### Files to Add
- `archive_agent/data/VisionProcessor.py` ➕ NEW

#### VisionProcessor Architecture Design
- **VisionRequest class**: Contains image data, callback, formatter lambda, and context
- **VisionProcessor class**: Handles parallel execution with ThreadPoolExecutor
- **Thread Safety**: Uses AiManagerFactory for worker isolation, ai.cli logger hierarchy
- **Unified Interface**: Supports both PDF bytes and Binary PIL Images
- **Formatter Pattern**: Lambda functions preserve existing conditional formatting logic
- **Error Handling**: Per-vision failures don't stop batch processing
- **Ordered Results**: Maintains request order for deterministic reassembly

#### Integration Strategy
- **PDF Loader**: Replace internals of `extract_image_texts_per_page()` with VisionProcessor
- **Binary Loader**: Replace internals of `extract_binary_image_texts()` with VisionProcessor  
- **Callback Selection**: PDF chooses based on `ocr_strategy`, Binary uses provided callback
- **Formatting Logic**: Preserve existing conditional formatting via lambda formatters

### Phase 2C: PDF Loader Vision Parallelization ⏳ PLANNED

#### Objectives
- Integrate VisionProcessor into PDF loader's existing multi-stage architecture
- Maintain identical output format: `List[List[str]]` (per-page image texts)
- Preserve all existing OCR strategy logic and error handling

#### Files to Modify
- `archive_agent/data/loader/pdf.py` ✏️ MODIFY (internal `extract_image_texts_per_page()` only)

#### Implementation Plan
1. **Collect vision requests with context from page contents**
2. **Choose callbacks based on existing `ocr_strategy` logic** 
3. **Create formatter lambdas preserving conditional bracket logic**
4. **Process all requests in parallel via VisionProcessor**
5. **Reassemble results into per-page structure** maintaining original format

#### Key Formatting Logic to Preserve
- **STRICT strategy failures**: `"[Unprocessable page]"`
- **RELAXED strategy failures**: `"[Unprocessable image]"`
- **RELAXED strategy success**: `"[{image_text}]"` (brackets added)
- **STRICT strategy success**: `"{image_text}"` (no brackets)

### Phase 2D: Binary Loader Vision Parallelization ⏳ PLANNED

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

#### Key Formatting Logic to Preserve
- **Success cases**: `"[{image_text}]"` (always brackets for binary docs)
- **Failure cases**: `"[Unprocessable Image]"` (consistent placeholder)

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

**Phase 2B: READY TO START ⏳**
- VisionProcessor implementation with unified parallel vision processing
- Support for both PDF bytes and Binary PIL Images
- Unified multithreading style with MAX_WORKERS = 8

**Next Steps:**
1. Create `VisionProcessor.py` with unified parallel vision processing
2. Integrate VisionProcessor into PDF loader (`extract_image_texts_per_page()` internals)
3. Integrate VisionProcessor into Binary loader (`extract_binary_image_texts()` internals)
4. Verify identical output and performance improvements

The architecture is well-designed and Phase 2A foundation is complete. Both loaders now have identical multi-stage structures ready for VisionProcessor integration!

# 4
Update the README to reflect the concurrency features.