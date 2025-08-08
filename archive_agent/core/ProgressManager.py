# archive_agent/data/ProgressManager.py
# Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
# This file is part of Archive Agent. See LICENSE for details.

from __future__ import annotations

import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from rich.console import RenderableType, Console
from rich.tree import Tree
from rich.table import Table
from rich.text import Text
from rich.progress_bar import ProgressBar


# ----------------------------- Public API shim -----------------------------

@dataclass
class ProgressInfo:
    """
    Bundle of progress tracking information for clean API boundaries.

    USAGE PATTERN:
    - Functions accept: ``some_function(..., progress_info: ProgressInfo)``
    - No Optional[] needed; progress tracking is always enabled.

    :param progress_manager: The active :class:`ProgressManager` instance.
    :param parent_key: The task key to use as parent for nested work.
    """
    progress_manager: "ProgressManager"
    parent_key: str


# ----------------------------- Internal model -----------------------------

@dataclass
class _Task:
    """
    Internal task state.

    :param key: Unique task identifier.
    :param name: Human-readable task name.
    :param parent: Parent task key, or ``None`` for root.
    :param weight: Contribution to parent's progress (0..1).
    :param total: Total work units; if ``None``, task is indeterminate until set.
    :param completed: Completed work units.
    :param active: Whether the task is visually highlighted as active.
    :param created_seq: Monotonic timestamp used for deterministic ordering.
    :param children: Ordered list of child keys.
    :param removed: If true, the task is scheduled/has been removed from the tree.
    """
    key: str
    name: str
    parent: Optional[str]
    weight: float
    total: Optional[int]
    completed: int = 0
    active: bool = False
    created_seq: float = field(default_factory=time.perf_counter)
    children: List[str] = field(default_factory=list)
    removed: bool = False

    # Derived helpers (no storage)
    def ratio(self) -> float:
        """
        Completion ratio in [0, 1].

        - Determinate: ``completed / max(total, 1)``
        - Indeterminate: 1.0 only when marked fully complete by the manager.
        """
        if self.total is None:
            # Indeterminate tasks only report progress when we have completion.
            return 1.0 if self.completed > 0 and self.total == 0 else 0.0
        return max(0.0, min(1.0, self.completed / max(1, self.total)))


# ----------------------------- Manager implementation -----------------------------

class ProgressManager:
    """
    GENERIC HIERARCHICAL PROGRESS MANAGER

    This manager renders a deterministic parent→child hierarchy using a custom
    Rich ``Tree`` + ``ProgressBar`` view. It does **not** rely on
    ``rich.progress.Progress`` row ordering (which is insertion-ordered and
    non-reorderable), so concurrent creation still yields a stable hierarchy.

    Thread-safety is ensured via an ``RLock`` guarding all state mutations
    and render rebuilds.

    Key behaviors implemented:

    - **Thread-safe**: All public methods acquire the same re-entrant lock.
    - **Hierarchy**: Parents always precede children; siblings keep insertion order.
    - **Weighted roll-up**: Parent completion is the normalized weighted sum of
      child ratios. If a parent has both determinate and indeterminate children,
      indeterminate children contribute 0 until marked complete.
    - **Auto-hide**: ``complete_task()`` marks a node complete and removes the
      subtree shortly after (default ~0.35 s) for a clean view.
    - **Active highlighting**: ``activate_task()`` visually emphasizes the row.

    The constructor accepts a ``rich.progress.Progress`` instance solely to reuse
    its console. Rendering is handled internally via ``Live``.
    """

    # How long a completed node stays visible before being removed (seconds)
    _REMOVE_DELAY_S: float = 0.35

    def __init__(self, console: Console) -> None:
        """
        Initialize the manager.

        :param console: Rich console for rendering output.
        """
        self._console = console

        # State
        self._tasks: Dict[str, _Task] = {}
        self._children: Dict[Optional[str], List[str]] = {None: []}

        # Concurrency
        self._lock: threading.RLock = threading.RLock()

    # ----------------------------- Public API -----------------------------

    def start_task(
        self,
        name: str,
        parent: Optional[str] = None,
        weight: float = 1.0,
        total: Optional[int] = None,
    ) -> str:
        """
        Start a new progress task.

        :param name: Human-readable task name (e.g., ``"Chunking"``).
        :param parent: Parent task key or ``None`` for root.
        :param weight: Weight in parent's progress (0.0–1.0).
        :param total: Total work units. If ``None``, progress is indeterminate.
        :returns: Generated task key.
        """
        with self._lock:
            key = uuid.uuid4().hex
            task = _Task(
                key=key,
                name=name,
                parent=parent,
                weight=max(0.0, float(weight)),
                total=int(total) if total is not None else None,
                completed=0,
                active=False,
            )
            self._tasks[key] = task

            # Parent linkage
            if parent not in self._children:
                self._children[parent] = []
            self._children[parent].append(key)
            if key not in self._children:
                self._children[key] = []

            # Pending parents get a default total of 100 for display if unset
            # (purely visual; real roll-up ignores this sentinel).
            self._refresh()
            return key

    def update_task(
        self,
        task_key: str,
        advance: int = 0,
        completed: Optional[int] = None,
    ) -> None:
        """
        Update a task's progress.

        :param task_key: Task key returned by :meth:`start_task`.
        :param advance: Increment progress by this amount.
        :param completed: Set absolute progress to this value.
        """
        with self._lock:
            task = self._tasks.get(task_key)
            if not task or task.removed:
                return

            # Ensure determinate when updating absolute or advancing indeterminate.
            if task.total is None and (completed is not None or advance):
                # Default to a 100-unit scale for indeterminate tasks that start reporting.
                task.total = 100

            if task.total is None:
                # Still indeterminate and not receiving absolutes—no change.
                pass
            else:
                if completed is not None:
                    task.completed = max(0, min(int(completed), task.total))
                else:
                    task.completed = max(0, min(task.completed + int(advance), task.total))

            # Propagate upward
            self._recompute_ancestors(task.parent)
            self._refresh()

    def complete_task(self, task_key: str) -> None:
        """
        Mark a task (and its subtree) complete and schedule removal.

        :param task_key: Task key returned by :meth:`start_task`.
        """
        with self._lock:
            if task_key not in self._tasks:
                return
            self._mark_subtree_complete(task_key)
            self._recompute_ancestors(self._tasks[task_key].parent)
            self._refresh()

            # Schedule removal after a short delay for visual feedback
            t = threading.Timer(self._REMOVE_DELAY_S, self._remove_task_safe, args=(task_key,))
            t.daemon = True
            t.start()

    def set_total(self, task_key: str, total: int) -> None:
        """
        Set or update total work units for a task.

        :param task_key: Task key.
        :param total: New total (> 0).
        """
        with self._lock:
            task = self._tasks.get(task_key)
            if not task or task.removed:
                return
            total = max(1, int(total))
            task.total = total
            task.completed = min(task.completed, total)
            self._recompute_ancestors(task.parent)
            self._refresh()

    def activate_task(self, task_key: str) -> None:
        """
        Mark a task as visually active (highlighted).

        :param task_key: Task key.
        """
        with self._lock:
            task = self._tasks.get(task_key)
            if not task or task.removed:
                return
            task.active = True
            self._refresh()

    @contextmanager
    def task(
        self,
        name: str,
        parent: Optional[str] = None,
        weight: float = 1.0,
        total: Optional[int] = None,
    ):
        """
        Context manager for automatic task completion.

        :param name: Human-readable task name.
        :param parent: Parent task key or ``None``.
        :param weight: Weight in parent's progress (0.0–1.0).
        :param total: Total work units (``None`` for indeterminate).
        :yields: Task key.
        """
        key = self.start_task(name=name, parent=parent, weight=weight, total=total)
        try:
            yield key
        finally:
            self.complete_task(key)

    def create_progress_info(self, parent_key: str) -> ProgressInfo:
        """
        Factory method for creating ProgressInfo instances.
        Encapsulates all progress tracking logic within ProgressManager.

        :param parent_key: The parent task key for nested progress tracking.
        :return: ProgressInfo instance configured for this manager.
        """
        return ProgressInfo(progress_manager=self, parent_key=parent_key)

    def get_tree_renderable(self) -> RenderableType:
        """
        Get the current tree renderable for integration with other displays.

        :return: The current tree structure for external rendering.
        """
        with self._lock:
            return self._build_renderable()

    # ----------------------------- Internals -----------------------------

    def _remove_task_safe(self, task_key: str) -> None:
        """Timer target: remove subtree under lock, then refresh."""
        with self._lock:
            self._remove_subtree(task_key)
            self._refresh()

    def _remove_subtree(self, root_key: str) -> None:
        """Remove a node and its descendants from state."""
        if root_key not in self._tasks:
            return
        parent = self._tasks[root_key].parent
        for child in list(self._children.get(root_key, [])):
            self._remove_subtree(child)
        self._children.pop(root_key, None)
        if parent in self._children and root_key in self._children[parent]:
            self._children[parent].remove(root_key)
        self._tasks[root_key].removed = True
        self._tasks.pop(root_key, None)

    def _mark_subtree_complete(self, root_key: str) -> None:
        """Set completed == total (or synthetic complete) for subtree."""
        stack = [root_key]
        while stack:
            k = stack.pop()
            task = self._tasks.get(k)
            if not task:
                continue
            if task.total is None:
                # For indeterminate tasks, use a synthetic total=1 complete=1
                task.total = 1
                task.completed = 1
            else:
                task.completed = task.total
            stack.extend(self._children.get(k, []))

    def _recompute_ancestors(self, start_parent: Optional[str]) -> None:
        """
        Recompute weighted parent progress up to the root.

        Parent ratio is computed as:

        $$R_p = \\frac{\\sum_i w_i R_i}{\\sum_i w_i + \\epsilon}$$

        where :math:`R_i` is the child ratio in [0, 1] and :math:`w_i` is the child's weight.
        Parents with ``total`` unset are treated as 100 for display only.
        """
        cur = start_parent
        while cur is not None:
            parent_task = self._tasks.get(cur)
            if not parent_task:
                break
            kids = self._children.get(cur, [])
            if not kids:
                # No children: leave as-is.
                cur = parent_task.parent
                continue

            w_sum = 0.0
            acc = 0.0
            for ck in kids:
                ct = self._tasks.get(ck)
                if not ct:
                    continue
                w = max(0.0, float(ct.weight))
                r = ct.ratio()
                w_sum += w
                acc += w * r

            ratio = (acc / w_sum) if w_sum > 0 else 0.0

            # Ensure a visual total for parents; real child roll-up is encoded in ratio.
            if parent_task.total is None:
                parent_task.total = 100
            parent_task.completed = int(round(ratio * parent_task.total))

            cur = parent_task.parent

    def _iter_children(self, parent: Optional[str]) -> List[str]:
        """
        Deterministic child order: insertion order by default, with created_seq as tiebreaker.
        """
        kids = list(self._children.get(parent, []))
        kids.sort(key=lambda k: (self._tasks[k].created_seq if k in self._tasks else 0.0, k))
        return kids

    # noinspection PyMethodMayBeStatic
    def _task_row(self, task: _Task) -> Table:
        """
        Render a single task row as a two-line grid:
        - header: name + "XX% (c/t)"
        - bar: ProgressBar matching completion
        """
        total = task.total if task.total is not None else 100
        completed = min(task.completed, total)
        pct = (completed / max(1, total)) * 100.0

        name_text = Text(task.name)
        if task.active:
            name_text.stylize("bold")

        header = Table.grid(padding=(0, 1))
        header.add_column(ratio=6)
        header.add_column(justify="right", ratio=1)
        header.add_row(name_text, Text(f"{pct:>3.0f}% ({completed}/{total})"))

        bar = ProgressBar(total=total, completed=completed)

        row = Table.grid()
        row.add_row(header)
        row.add_row(bar)
        return row

    def _add_tree_node(self, tree: Tree, key: str) -> None:
        task = self._tasks[key]
        node = tree.add(self._task_row(task))
        for child in self._iter_children(key):
            if child in self._tasks:
                self._add_tree_node(node, child)

    def _build_renderable(self) -> RenderableType:
        """
        Build the full hierarchical renderable.
        """
        root = Tree(Text("tasks", style="bold"))
        for k in self._iter_children(None):
            if k in self._tasks:
                self._add_tree_node(root, k)
        return root

    def _refresh(self) -> None:
        """
        Refresh is handled externally - this is a no-op.
        The external Live display will call get_tree_renderable() as needed.
        """
        pass
