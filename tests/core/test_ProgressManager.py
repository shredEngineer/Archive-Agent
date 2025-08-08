"""
Unit tests for archive_agent.core.ProgressManager.

These tests validate:
- Hierarchical parent→child ordering
- Weighted roll-up of child progress to parents
- Auto-hide (timed removal) on completion
- Activation (highlight) flag
- Basic thread-safety under concurrent updates
"""

from __future__ import annotations

import io
import threading
import time

from rich.console import Console

from archive_agent.core.ProgressManager import ProgressManager


def _make_manager() -> ProgressManager:
    """
    Create a ProgressManager with a non-interactive console.

    :returns: Fresh ProgressManager instance safe for test output capture.
    """
    console = Console(file=io.StringIO(), force_terminal=False, color_system=None, soft_wrap=True)
    return ProgressManager(console=console)


def test_hierarchy_creation_and_order() -> None:
    """
    Ensure tasks appear in deterministic parent→child order with stable sibling insertion order.
    """
    pm = _make_manager()
    root = pm.start_task("root")
    a = pm.start_task("A", parent=root)
    b = pm.start_task("B", parent=root)
    a1 = pm.start_task("A1", parent=a)
    a2 = pm.start_task("A2", parent=a)
    b1 = pm.start_task("B1", parent=b)

    # Validate sibling insertion order via public snapshots
    snap_a = pm.get_task_snapshot(a)
    snap_b = pm.get_task_snapshot(b)
    assert snap_a is not None and snap_b is not None

    assert snap_a.children == [a1, a2]
    assert snap_b.children == [b1]

    # Sanity: renderable builds without error
    _ = pm.get_tree_renderable()


def test_weighted_rollup() -> None:
    """
    Verify parent completion is the weighted average of child ratios.

    Scenario:
      parent P has children:
        C1 (w=2, total=10) with completed=5  → ratio=0.5
        C2 (w=1, total=20) with completed=10 → ratio=0.5
      Weighted ratio = (2*0.5 + 1*0.5) / (2+1) = 0.5
      Parent total is normalized to 100 internally; completed should be ~50.
    """
    pm = _make_manager()
    p = pm.start_task("P")  # parent (total will be set to 100 by manager)
    c1 = pm.start_task("C1", parent=p, weight=2.0, total=10)
    c2 = pm.start_task("C2", parent=p, weight=1.0, total=20)

    pm.update_task(c1, completed=5)
    pm.update_task(c2, completed=10)

    snap_p = pm.get_task_snapshot(p)
    assert snap_p is not None
    assert snap_p.total == 100
    assert snap_p.completed == 50


def test_complete_task_auto_hide() -> None:
    """
    Completing a task should mark it done and remove it (and its subtree) after a short delay.
    """
    pm = _make_manager()
    root = pm.start_task("root")
    child = pm.start_task("child", parent=root, total=5)
    pm.update_task(child, completed=5)
    pm.complete_task(root)

    # Allow timer to fire (manager uses ~0.35 s delay by default).
    # Access via the public property for robustness.
    time.sleep(pm.remove_delay_s + 0.25)

    assert pm.get_task_snapshot(root) is None
    assert pm.get_task_snapshot(child) is None


def test_activate_task_flag() -> None:
    """
    Activating a task should set its internal 'active' flag for styling.
    """
    pm = _make_manager()
    k = pm.start_task("active-task")
    pm.activate_task(k)
    snap = pm.get_task_snapshot(k)
    assert snap is not None
    assert snap.active is True


def test_concurrent_updates_thread_safety() -> None:
    """
    Multiple threads updating different children should roll up deterministically.

    Setup:
        P (parent)
          C1 (w=1, total=100) — thread A increments 100 steps
          C2 (w=1, total=100) — thread B increments 50 steps

    Expectation:
        C1 ratio = 1.0, C2 ratio = 0.5 → parent ratio = (1.0 + 0.5)/2 = 0.75
        Parent completed ≈ 75 (on a 100-scale).
    """
    pm = _make_manager()
    p = pm.start_task("P")
    c1 = pm.start_task("C1", parent=p, weight=1.0, total=100)
    c2 = pm.start_task("C2", parent=p, weight=1.0, total=100)

    def run_increments(task_key: str, steps: int) -> None:
        for _ in range(steps):
            pm.update_task(task_key, advance=1)

    t1 = threading.Thread(target=run_increments, args=(c1, 100))
    t2 = threading.Thread(target=run_increments, args=(c2, 50))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # Allow any final roll-up to settle
    time.sleep(0.05)

    snap_p = pm.get_task_snapshot(p)
    assert snap_p is not None
    assert snap_p.total == 100
    # Allow for integer rounding
    assert 74 <= snap_p.completed <= 76
