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

## Phase 2: PDF/Binary Document Vision Parallelization (PLANNED)

### Objectives
Split the loaders to parallelize AI vision calls for images within documents.

**2.1 Make loader.prepare() gather and return AI vision requests**
- PDF Loader: Extract all images from `extract_image_texts_per_page()` into vision request list
- Binary Document Loader: Extract all images from `load_binary_document_images()` into vision request list
- Return structured vision requests with context (page numbers, image indices, etc.)

**2.2 Execute AI vision requests in parallel**
- Create dedicated vision processing class in `archive_agent/data/`
- Use `ThreadPoolExecutor` with `MAX_WORKERS = 8` pattern
- Each vision worker gets isolated AiManager instance
- Maintain context for proper result assembly

**2.3 Feed AI vision results back into loader.process()**
- Match vision results back to original context (page/image location)
- Handle vision failures gracefully (placeholder text)
- Preserve existing error handling patterns

**2.4 Make loader.format() compile and return the final text**
- Assemble final document text combining layout text and vision results
- Maintain existing text formatting and line mapping
- Preserve page/line reference tracking

### Implementation Challenges
- **Context Preservation**: Vision requests must retain page/image context for reassembly
- **Error Handling**: Vision failures must not break document processing
- **Text Assembly**: Final text must maintain exact same format as current sequential approach
- **Progress Tracking**: Vision processing should show fine-grained progress

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

**Phase 1 Status: COMPLETED ✅**
- All objectives achieved
- Architecture verified and tested
- Ready for production use
- Foundation established for Phase 2 implementation

# 4
Update the README to reflect the concurrency features.