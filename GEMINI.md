# System Documentation: Multithreading & Live Display

This document describes the architecture for the multithreaded processing and interactive `rich.Live` display in the Archive Agent.

## 1. Relevant Files

-   `archive_agent/core/CliManager.py`: Implements the display and logging context.
-   `archive_agent/core/CommitManager.py`: Consumes the display logic and runs the parallel processing.
-   `archive_agent/__init__.py`: Configures the application's global logging style.

---

## 2. Core Requirements

The implementation must satisfy these four requirements:
1.  **True Parallel Processing**: Worker threads must execute I/O-bound tasks concurrently without being serialized by logging or UI updates.
2.  **Styled Logging**: All log output, even during concurrent operations, must use the single, custom-styled `RichHandler` defined in `__init__.py`.
3.  **Clean Live Display**: The live display must show a stable status block, with verbose logs appearing as a persistent, scrolling history above it without interleaving or glitching.
4.  **Real-time Updates**: The status block (progress bars, tables) must update smoothly.

---

## 3. System Architecture

### 3.1. Core Problem: Concurrency vs. `rich.Live`

The fundamental challenge is that `rich.Live` uses an internal lock to manage screen updates. If multiple worker threads attempt to log or print directly to the console, they will contend for this lock. This forces the threads to execute one by one, serializing their execution and defeating the purpose of multithreading for concurrent tasks.

### 3.2. Architectural Solution: Decoupled Logging

The architecture decouples worker threads from the console to ensure true parallel processing. All logging and printing is funneled through a single, dedicated "printer thread" that is the sole manager of the `Live` display.

The pattern is as follows:
1.  Worker threads place log records onto a thread-safe `queue.Queue` instead of writing to the console.
2.  The printer thread is the only consumer of this queue. It safely handles each message and updates the `Live` display without lock contention.

### 3.3. Implementation Layers

This architecture is implemented in `CliManager` through two layered context managers.

#### 3.3.1. Low-Level Orchestration: `live_context`

The `live_context` manager is the core orchestrator of the decoupled logging system. Its responsibilities are:

1.  **Find and Redirect the Global `RichHandler`**: It finds the single, globally-configured `RichHandler` instance from the root logger. It then temporarily redirects the handler's output to the `Live` object's internal console.
    -   **CRITICAL DESIGN CONSTRAINT**: The system **must not** create a new `RichHandler`. Doing so would bypass the central styling configuration (e.g., timestamps, custom highlighters) defined in `__init__.py`, leading to incorrectly formatted log output.
2.  **Funnel All Logs to the Queue**: It replaces the root logger's handlers with a single `QueueHandler`, ensuring every log message from anywhere in the application is captured and put onto the queue.
3.  **Manage the Printer Thread**: It starts the dedicated printer thread to process the queue and guarantees that it is safely shut down when the context is exited.
4.  **Guaranteed Restoration**: In a `finally` block, it restores the original logger handlers and, most importantly, restores the original console to the `RichHandler`, ensuring normal logging continues after the `Live` display is closed.

#### 3.3.2. High-Level Abstraction: `progress_context`

The `progress_context` manager provides a simple, high-level abstraction for components like `CommitManager` that need to display progress. This centralizes UI logic in `CliManager` and decouples other components from UI implementation details.

-   **Responsibilities**:
    1.  It acts as the single entry point for creating live progress displays.
    2.  It constructs all necessary `rich` components (`Progress`, `Group`, `Live`, etc.) for a consistent look and feel.
    3.  It automatically includes shared UI elements, like the AI token usage table.
    4.  It internally wraps the entire operation within the `live_context` manager, so that safe, concurrent logging is handled automatically.
    5.  It yields the necessary `rich.Progress` handles back to the caller.

-   **Decoupling Callers**:
    Callers like `CommitManager` use the `progress_context` in a simple `with` block. Inside this block, they use the yielded handles to report progress. This allows the caller to be completely ignorant of the underlying `rich` objects or the multithreaded logging complexity.

### 3.4. Challenge: Dynamic UI Updates

A challenge is ensuring dynamic UI elements, like the AI token usage table, update in real-time. While worker threads correctly update the underlying statistics (protected by a `threading.Lock`), the `Live` object, if initialized with static content, will not reflect these changes.

**CRITICAL SAFETY CONCERN**: Any solution must be implemented with extreme care, ensuring it does **not** compromise the core architecture. Specifically, it must not:
1.  Interfere with the decoupled logging mechanism.
2.  Introduce new race conditions or thread-safety issues.
3.  Degrade the concurrency of the worker threads.

**The Safe Solution**: The solution is to make the `Live` object's content dynamic without violating the architectural principles.

1.  **Timed Queue Read**: The printer thread's `queue.get()` call uses a short timeout (`0.1s`) instead of being fully blocking.
2.  **Periodic Refresh**: When the timeout occurs (i.e., during brief idle periods with no new log messages), the printer thread's loop continues. At the end of every loop iteration (whether a log was processed or not), it calls `live.update()`.
3.  **Dynamic Renderable**: To provide the `live.update()` method with fresh content, a `get_renderable` function is passed down from `progress_context` to the printer thread. This function, when called, generates a new `rich.Group` containing the progress bars and a **newly-rendered table** with the latest, thread-safely read statistics.

This solution is surgically precise. It confines all UI update logic to the single printer thread, fully respecting the existing locks and queues. It ensures the display is dynamic while upholding the system's foundational guarantees of safety and concurrency.

This solution is surgically precise. It confines all UI update logic to the single printer thread, fully respecting the existing locks and queues. It ensures the display is dynamic while upholding the system's foundational guarantees of safety and concurrency.

### 3.5. Challenge: Accurate Real-time Statistics

Providing accurate, real-time updates for cumulative statistics like AI token usage is a significant challenge. The system solves this with a dual-mechanism architecture that balances liveness with correctness. Understanding the separation of concerns is critical.

1.  **Authoritative Accounting in `AiManager`**: For each file being processed, a worker thread uses a dedicated `AiManager` instance. This instance is the **source of truth** for usage statistics, meticulously tracking detailed data like `prompt_tokens`, `completion_tokens`, and `cost`. At the end of a file's processing, `CommitManager` aggregates this detailed, accurate data. This final aggregation ensures the final numbers are always correct.

2.  **Live UI Updates in `CliManager`**: The `CliManager` is responsible for the live display. The core challenge is that the `CliManager`'s formatting callbacks (e.g., `format_ai_chunk`) are only passed an `AiResult` object.
    -   **CRITICAL DESIGN CONSTRAINT**: The `AiResult` class is effectively immutable due to its instances being cached. It cannot be changed. It only provides a `total_tokens` field for a given operation and lacks the detailed breakdown.

**The Safe Architectural Pattern for Live Updates**:
The solution is to use the `CliManager` to provide live updates to the UI without interfering with the authoritative accounting happening in `AiManager`.

-   **Leverage Existing Methods**: The `CliManager` already has a thread-safe `update_ai_usage(stats: Dict[str, int])` method, which uses a lock to safely update the `ai_usage_stats` dictionary that backs the UI table.
-   **Use Context for Categorization**: The implementation adds a single line inside each `format_ai_*` method (e.g., `format_ai_chunk`). This line calls `self.update_ai_usage()`. Because the call is made from within a specific formatting method, the category is known (e.g., `'chunk'`). The `result.total_tokens` is passed for that category.
-   **Embrace the Dual System**: This approach provides immediate, real-time feedback in the UI. It does not attempt to replicate the detailed accounting of `AiManager`, which would be complex and error-prone. The live stats are for user feedback, and the final, authoritative stats from `CommitManager` ensure ultimate correctness. This avoids over-engineering and respects the system's established separation of concerns.

---

## 4. Best Practices for Development and Verification

1.  **Keep This Document Current and Timeless**: After any implementation change to this system, this `GEMINI.md` file must be updated to reflect the new architecture and its rationale. All descriptions should be in the **present tense** to accurately represent the current state of the project.

2.  **Static Analysis**: Run the audit script as a baseline check. It is a necessary but **insufficient** step.
    ```bash
    ./audit.sh
    ```

3.  **Manual Runtime Verification**: The audit script **cannot** validate multithreaded runtime behavior. **The user must perform a final, manual verification** by running the application and visually confirming that all four core requirements are met.
    ```bash
    ./archive-agent.sh update --verbose --nocache
    ```
    **Note**: If there are files that have been removed from the watchlist, the script will pause for a confirmation prompt. This is expected behavior. The core concurrency and logging test is successful if the live display runs without errors up to that point.

4.  **Avoid Deadlocks in Post-Processing**: After the `progress_context` exits, the printer thread may still be active. Be extremely cautious when implementing methods that are called *after* the live display is finished. If such a method acquires a lock that is *also* used by the printer thread's `get_renderable` function (like the `ai_usage_stats` lock), it **must not** attempt to send output to the printer thread's queue (e.g., via `_print`). Doing so will cause a deadlock: the main thread will hold the lock and wait for the queue, while the printer thread holds the queue and waits for the lock. In these specific cases, print directly to the console (e.g., `self.console.print(...)`) to bypass the printer thread entirely.