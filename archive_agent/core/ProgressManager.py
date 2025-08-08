# TODO: Implement graceful shutdown of threads.

# archive_agent/core/ProgressManager.py
# Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
# This file is part of Archive Agent. See LICENSE for details.

from __future__ import annotations

import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Dict, List, Optional, NamedTuple

from rich.console import RenderableType, Console
from rich.tree import Tree
from rich.table import Table
from rich.text import Text
from rich.progress_bar import ProgressBar


# ==============================
# Config
# ==============================

@dataclass(frozen=True)
class ProgressConfig:
    """Configuration values for ProgressManager behavior."""
    remove_delay_s: float = 2
    default_total: int = 100


# ==============================
# Internal model
# ==============================

@dataclass
class _Task:
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

    def ratio(self) -> float:
        """Completion ratio in [0, 1]."""
        if self.total is None:
            return 0.0
        return max(0.0, min(1.0, self.completed / max(1, self.total)))


class TaskSnapshot(NamedTuple):
    """Immutable snapshot of a task's state for inspection/testing."""
    key: str
    name: str
    parent: Optional[str]
    weight: float
    total: Optional[int]
    completed: int
    active: bool
    removed: bool
    children: List[str]

    @property
    def ratio(self) -> float:
        """Normalized completion ratio in [0, 1]."""
        if self.total is None:
            return 0.0
        return max(0.0, min(1.0, self.completed / max(1, self.total)))


# ==============================
# Tracker (logic only)
# ==============================

class _ProgressTracker:
    """Handles task hierarchy, progress updates, and roll-ups."""

    def __init__(self, config: ProgressConfig):
        self.config = config
        self._tasks: Dict[str, _Task] = {}
        self._children: Dict[Optional[str], List[str]] = {None: []}
        self.lock = threading.RLock()

    def start_task(self, name: str, parent: Optional[str], weight: float, total: Optional[int]) -> str:
        key = uuid.uuid4().hex
        task = _Task(
            key=key,
            name=name,
            parent=parent,
            weight=max(0.0, float(weight)),
            total=int(total) if total is not None else None,
        )
        self._tasks[key] = task
        self._children.setdefault(parent, []).append(key)
        self._children.setdefault(key, [])
        return key

    def update_task(self, key: str, advance: int, completed: Optional[int]) -> None:
        task = self._tasks.get(key)
        if not task or task.removed:
            return
        if task.total is None and (completed is not None or advance):
            task.total = self.config.default_total
        if task.total is not None:
            if completed is not None:
                task.completed = max(0, min(int(completed), task.total))
            else:
                task.completed = max(0, min(task.completed + int(advance), task.total))
        self._recompute_ancestors(task.parent)

    def complete_task(self, key: str) -> None:
        if key not in self._tasks:
            return
        self._mark_subtree_complete(key)
        self._recompute_ancestors(self._tasks[key].parent)

    def set_total(self, key: str, total: int) -> None:
        task = self._tasks.get(key)
        if not task or task.removed:
            return
        total = max(1, int(total))
        task.total = total
        task.completed = min(task.completed, total)
        self._recompute_ancestors(task.parent)

    def activate_task(self, key: str) -> None:
        task = self._tasks.get(key)
        if not task or task.removed:
            return
        task.active = True

    def remove_subtree(self, root_key: str) -> None:
        if root_key not in self._tasks:
            return
        parent = self._tasks[root_key].parent
        for child in list(self._children.get(root_key, [])):
            self.remove_subtree(child)
        self._children.pop(root_key, None)
        if parent in self._children and root_key in self._children[parent]:
            self._children[parent].remove(root_key)
        self._tasks.pop(root_key, None)

    def iter_children(self, parent: Optional[str]) -> List[str]:
        kids = list(self._children.get(parent, []))
        kids.sort(key=lambda k: (self._tasks[k].created_seq if k in self._tasks else 0.0, k))
        return kids

    def get_task(self, key: str) -> Optional[_Task]:
        return self._tasks.get(key)

    def _mark_subtree_complete(self, root_key: str) -> None:
        stack = [root_key]
        while stack:
            k = stack.pop()
            task = self._tasks.get(k)
            if not task:
                continue
            if task.total is None:
                task.total = 1
            task.completed = task.total
            stack.extend(self._children.get(k, []))

    def _recompute_ancestors(self, start_parent: Optional[str]) -> None:
        cur = start_parent
        while cur is not None:
            parent_task = self._tasks.get(cur)
            if not parent_task:
                break
            kids = self._children.get(cur, [])
            if kids:
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
                if parent_task.total is None:
                    parent_task.total = self.config.default_total
                parent_task.completed = int(round(ratio * parent_task.total))
            cur = parent_task.parent


# ==============================
# Renderer (Rich only)
# ==============================

class _ProgressRenderer:
    """Converts tracker state into a Rich renderable tree."""

    def __init__(self, tracker: _ProgressTracker):
        self.tracker = tracker

    def build_renderable(self) -> RenderableType:
        root = Tree(Text("tasks", style="bold"))
        for k in self.tracker.iter_children(None):
            if self.tracker.get_task(k):
                self._add_tree_node(root, k)
        return root

    def _add_tree_node(self, tree: Tree, key: str) -> None:
        task = self.tracker.get_task(key)
        if not task:
            return
        node = tree.add(self._task_row(task))
        for child in self.tracker.iter_children(key):
            if self.tracker.get_task(child):
                self._add_tree_node(node, child)

    def _task_row(self, task: _Task) -> Table:
        total = task.total if task.total is not None else self.tracker.config.default_total
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


# ==============================
# Public Manager (glue)
# ==============================

class ProgressManager:
    """
    Public interface for progress tracking + Rich rendering.
    API matches original for drop-in replacement.
    """

    def __init__(self, console: Console, config: Optional[ProgressConfig] = None) -> None:
        self._console = console
        self._tracker = _ProgressTracker(config or ProgressConfig())
        self._renderer = _ProgressRenderer(self._tracker)

    def start_task(self, name: str, parent: Optional[str] = None,
                   weight: float = 1.0, total: Optional[int] = None) -> str:
        with self._tracker.lock:
            return self._tracker.start_task(name, parent, weight, total)

    def update_task(self, task_key: str, advance: int = 0, completed: Optional[int] = None) -> None:
        with self._tracker.lock:
            self._tracker.update_task(task_key, advance, completed)

    def complete_task(self, task_key: str) -> None:
        with self._tracker.lock:
            self._tracker.complete_task(task_key)
            t = threading.Timer(self._tracker.config.remove_delay_s,
                                self._remove_task_safe, args=(task_key,))
            t.daemon = True
            t.start()

    def set_total(self, task_key: str, total: int) -> None:
        with self._tracker.lock:
            self._tracker.set_total(task_key, total)

    def activate_task(self, task_key: str) -> None:
        with self._tracker.lock:
            self._tracker.activate_task(task_key)

    @contextmanager
    def task(self, name: str, parent: Optional[str] = None,
             weight: float = 1.0, total: Optional[int] = None):
        key = self.start_task(name, parent, weight, total)
        try:
            yield key
        finally:
            self.complete_task(key)

    def get_tree_renderable(self) -> RenderableType:
        with self._tracker.lock:
            return self._renderer.build_renderable()

    def get_task_snapshot(self, task_key: str) -> Optional[TaskSnapshot]:
        """
        Public snapshot accessor for tests or external monitoring.
        """
        with self._tracker.lock:
            task = self._tracker.get_task(task_key)
            if not task:
                return None
            children = self._tracker.iter_children(task_key)
            return TaskSnapshot(
                key=task.key,
                name=task.name,
                parent=task.parent,
                weight=task.weight,
                total=task.total,
                completed=task.completed,
                active=task.active,
                removed=task.removed,
                children=children,
            )

    def _remove_task_safe(self, task_key: str) -> None:
        with self._tracker.lock:
            self._tracker.remove_subtree(task_key)

    @property
    def remove_delay_s(self) -> float:
        """Delay before a completed task is removed from the display."""
        return self._tracker.config.remove_delay_s

    def create_progress_info(self, parent_key: str) -> "ProgressInfo":
        """
        Factory for a legacy ``ProgressInfo`` bundle.

        Parameters
        ----------
        parent_key:
            The parent task key that downstream functions should attach their
            child tasks to.

        Returns
        -------
        ProgressInfo
            A lightweight container with this manager and the given parent key.
        """
        return ProgressInfo(progress_manager=self, parent_key=parent_key)


@dataclass
class ProgressInfo:
    """Legacy parameter object for backward compatibility.

    This is preserved only to maintain interface compatibility with
    existing code that imports ProgressInfo directly from ProgressManager.
    New code should use ProgressManager APIs instead.
    """
    progress_manager: ProgressManager
    parent_key: str
