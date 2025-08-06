# archive_agent/data/ProgressManager.py
# Copyright © 2025 Dr.-Ing. Paul Wilhelm <paul@wilhelm.dev>
# This file is part of Archive Agent. See LICENSE for details.

from typing import Dict, Optional, List
from dataclasses import dataclass
from enum import Enum
from rich.progress import Progress, TaskID


class TaskState(Enum):
    """Task state for tracking progress phase status."""
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"


@dataclass
class ProgressInfo:
    """
    Bundle of progress tracking information for clean API boundaries.
    """
    progress_manager: 'ProgressManager'
    phase_key: Optional[str] = None


class ProgressManager:
    """
    Centralized progress management with automatic hierarchical task coordination.
    Provides clean interfaces for files, phases, and sub-phases without exposing Rich internals.
    """

    def __init__(self, progress: Progress):
        """
        Initialize progress manager.
        :param progress: Rich Progress object to manage.
        """
        self.progress = progress
        self.task_hierarchy: Dict[str, List[str]] = {}  # parent_key -> [child_keys]
        self.task_ids: Dict[str, TaskID] = {}  # key -> rich_task_id
        self.task_weights: Dict[str, float] = {}  # child_key -> weight (0.0-1.0)
        self.task_totals: Dict[str, int] = {}  # key -> total_work
        self.task_completed: Dict[str, int] = {}  # key -> completed_work
        self.task_states: Dict[str, TaskState] = {}  # key -> current_state
        self.task_creation_order: List[str] = []  # maintains insertion order
        self.task_names: Dict[str, str] = {}  # key -> display_name
        self._file_counter = 0
        self._phase_counters: Dict[str, int] = {}  # file_key -> phase_count
        self._subphase_counters: Dict[str, int] = {}  # phase_key -> subphase_count

    def start_file(self, filename: str) -> str:
        """
        Start processing a file.
        :param filename: Display name for the file.
        :return: File key for future operations.
        """
        file_key = f"file_{self._file_counter}"
        self._file_counter += 1
        task_id = self.progress.add_task(filename, total=100)

        self.task_ids[file_key] = task_id
        self.task_hierarchy[file_key] = []
        self.task_totals[file_key] = 100
        self.task_completed[file_key] = 0
        self.task_states[file_key] = TaskState.ACTIVE
        self.task_creation_order.append(file_key)
        self.task_names[file_key] = filename
        self._phase_counters[file_key] = 0

        return file_key

    def _update_tree_symbols(self, parent_key: str):
        """
        Update tree symbols for all children under parent to show correct ├─ / └─ structure.
        :param parent_key: Parent key whose children need tree symbol updates.
        """
        if parent_key not in self.task_hierarchy:
            return

        active_children = [child for child in self.task_hierarchy[parent_key]
                           if child in self.task_ids]

        if not active_children:
            return

        # Determine indentation level based on parent type
        if parent_key.startswith('file_'):
            indent = "  "  # File level phases: 2 spaces
        elif '_phase_' in parent_key:
            indent = "    "  # Sub-phases: 4 spaces
        else:
            indent = "  "  # Default

        # Update all children with correct tree symbols
        for i, child_key in enumerate(active_children):
            is_last = (i == len(active_children) - 1)
            tree_symbol = "└─" if is_last else "├─"

            if child_key in self.task_names:
                display_name = self.task_names[child_key]

                # Add color coding based on task state
                color_code = ""
                if child_key in self.task_states:
                    state = self.task_states[child_key]
                    if state == TaskState.ACTIVE:
                        color_code = "[bold yellow]"
                    elif state == TaskState.PENDING:
                        color_code = "[dim]"
                    elif state == TaskState.COMPLETED:
                        color_code = "[green]"

                # Format with color if specified
                if color_code:
                    full_description = f"{indent}{tree_symbol} {color_code}{display_name}[/]"
                else:
                    full_description = f"{indent}{tree_symbol} {display_name}"

                # Update the task description
                self.progress.update(self.task_ids[child_key], description=full_description)

    def _find_parent_key(self, child_key: str) -> Optional[str]:
        """
        Find the parent key for a given child key.
        :param child_key: Child key to find parent for.
        :return: Parent key or None if not found.
        """
        for potential_parent, children in self.task_hierarchy.items():
            if child_key in children:
                return potential_parent
        return None

    def _cleanup_task_and_children(self, task_key: str):
        """
        Recursively clean up a task and all its children.
        :param task_key: Task key to clean up.
        """
        # Clean up all children first
        for child_key in self.task_hierarchy.get(task_key, []):
            if child_key in self.task_ids:
                self._cleanup_task_and_children(child_key)
                self.progress.remove_task(self.task_ids[child_key])
                del self.task_ids[child_key]

        # Clean up task's tracking data (but don't remove the task itself - caller does that)
        if task_key in self.task_states:
            del self.task_states[task_key]
        if task_key in self.task_totals:
            del self.task_totals[task_key]
        if task_key in self.task_completed:
            del self.task_completed[task_key]
        if task_key in self.task_names:
            del self.task_names[task_key]
        if task_key in self.task_weights:
            del self.task_weights[task_key]
        if task_key in self.task_creation_order:
            self.task_creation_order.remove(task_key)
        if task_key in self.task_hierarchy:
            del self.task_hierarchy[task_key]
        if task_key in self._subphase_counters:
            del self._subphase_counters[task_key]

    def complete_file(self, file_key: str):
        """
        Mark file as complete and clean up all associated tasks.
        :param file_key: File key from start_file().
        """
        if file_key not in self.task_ids:
            return

        # Complete file progress
        self.progress.update(self.task_ids[file_key], completed=100)
        self.task_completed[file_key] = 100
        self.task_states[file_key] = TaskState.COMPLETED

        # Recursively clean up all child tasks
        self._cleanup_task_and_children(file_key)

        # Remove the file task itself
        self.progress.remove_task(self.task_ids[file_key])

        # Clean up file tracking data
        del self.task_ids[file_key]
        if file_key in self.task_states:
            del self.task_states[file_key]
        if file_key in self.task_totals:
            del self.task_totals[file_key]
        if file_key in self.task_completed:
            del self.task_completed[file_key]
        if file_key in self.task_names:
            del self.task_names[file_key]
        if file_key in self.task_creation_order:
            self.task_creation_order.remove(file_key)
        if file_key in self.task_hierarchy:
            del self.task_hierarchy[file_key]
        if file_key in self._phase_counters:
            del self._phase_counters[file_key]

    def start_phase(self, file_key: str, phase_name: str, weight: float = 1.0, estimated_work: Optional[int] = None) -> str:
        """
        Start a processing phase under a file.
        :param file_key: Parent file key.
        :param phase_name: Display name for the phase.
        :param weight: Weight of this phase in parent progress (0.0-1.0).
        :param estimated_work: Estimated work units (if None, uses indeterminate progress).
        :return: Phase key for future operations.
        """
        if file_key not in self.task_ids:
            raise ValueError(f"File key '{file_key}' not found")

        phase_key = f"{file_key}_phase_{self._phase_counters[file_key]}"
        self._phase_counters[file_key] += 1

        # Create task with placeholder description - will be updated by _update_tree_symbols
        task_id = self.progress.add_task(f"  ├─ {phase_name}", total=estimated_work)

        self.task_ids[phase_key] = task_id
        self.task_hierarchy[file_key].append(phase_key)
        self.task_hierarchy[phase_key] = []
        self.task_weights[phase_key] = self._validate_weight(weight)
        self.task_totals[phase_key] = estimated_work or 0
        self.task_completed[phase_key] = 0
        self.task_states[phase_key] = TaskState.PENDING
        self.task_creation_order.append(phase_key)
        self.task_names[phase_key] = phase_name
        self._subphase_counters[phase_key] = 0

        # Update tree symbols for all phases under this file
        self._update_tree_symbols(file_key)

        return phase_key

    # noinspection PyMethodMayBeStatic
    def _validate_weight(self, weight: float) -> float:
        """
        Validate and normalize weight value.
        :param weight: Weight to validate.
        :return: Normalized weight.
        """
        if weight < 0:
            return 0.0
        if weight > 1.0:
            return 1.0
        return weight

    def _safe_task_operation(self, task_key: str) -> bool:
        """
        Safely check if task exists before operations.
        :param task_key: Task key to check.
        :return: True if task exists and operation can proceed.
        """
        if not task_key or task_key not in self.task_ids:
            return False
        return True

    def activate_phase(self, phase_key: str):
        """
        Mark a phase as active (currently being processed).
        :param phase_key: Phase key to activate.
        """
        if self._safe_task_operation(phase_key):
            self.task_states[phase_key] = TaskState.ACTIVE

            # Update tree symbols to reflect new active state
            parent_key = self._find_parent_key(phase_key)
            if parent_key:
                self._update_tree_symbols(parent_key)

    def update_phase(self, phase_key: str, completed: Optional[int] = None, advance: int = 0):
        """
        Update phase progress.
        :param phase_key: Phase key from start_phase().
        :param completed: Set absolute completed amount.
        :param advance: Advance progress by this amount.
        """
        if not self._safe_task_operation(phase_key):
            return

        if completed is not None:
            self.task_completed[phase_key] = completed
            self.progress.update(self.task_ids[phase_key], completed=completed)
        elif advance > 0:
            self.task_completed[phase_key] += advance
            self.progress.update(self.task_ids[phase_key], advance=advance)

        self._update_parent_progress(phase_key)

    def complete_phase(self, phase_key: str):
        """
        Complete a phase, update parent progress, and remove from display.
        :param phase_key: Phase key from start_phase().
        """
        if phase_key not in self.task_ids:
            return

        # Mark phase as complete
        total = self.task_totals[phase_key]
        if total and total > 0:
            self.progress.update(self.task_ids[phase_key], completed=total)
            self.task_completed[phase_key] = total
        else:
            self.progress.update(self.task_ids[phase_key], completed=100)
            self.task_completed[phase_key] = 100

        # Update parent progress before removal
        self._update_parent_progress(phase_key)

        # Update task state
        self.task_states[phase_key] = TaskState.COMPLETED

        # Find parent for tree symbol updates
        parent_key = self._find_parent_key(phase_key)

        # Remove completed phase from display
        self.progress.remove_task(self.task_ids[phase_key])

        # Clean up phase tracking data
        del self.task_ids[phase_key]
        if phase_key in self.task_states:
            del self.task_states[phase_key]
        if phase_key in self.task_totals:
            del self.task_totals[phase_key]
        if phase_key in self.task_completed:
            del self.task_completed[phase_key]
        if phase_key in self.task_names:
            del self.task_names[phase_key]
        if phase_key in self.task_weights:
            del self.task_weights[phase_key]
        if phase_key in self.task_creation_order:
            self.task_creation_order.remove(phase_key)

        # Remove from parent's hierarchy
        if parent_key and parent_key in self.task_hierarchy:
            if phase_key in self.task_hierarchy[parent_key]:
                self.task_hierarchy[parent_key].remove(phase_key)

        # Clean up phase's own hierarchy
        if phase_key in self.task_hierarchy:
            del self.task_hierarchy[phase_key]
        if phase_key in self._subphase_counters:
            del self._subphase_counters[phase_key]

        # Update tree symbols for remaining phases
        if parent_key:
            self._update_tree_symbols(parent_key)

    def start_subphase(self, phase_key: str, subphase_name: str, total: int) -> str:
        """
        Start a sub-phase under a phase.
        :param phase_key: Parent phase key.
        :param subphase_name: Display name for the sub-phase.
        :param total: Total work units for this sub-phase.
        :return: Sub-phase key for future operations.
        """
        if phase_key not in self.task_ids:
            raise ValueError(f"Phase key '{phase_key}' not found")

        subphase_key = f"{phase_key}_sub_{self._subphase_counters[phase_key]}"
        self._subphase_counters[phase_key] += 1

        # Create task with placeholder description - will be updated by _update_tree_symbols
        task_id = self.progress.add_task(f"    ├─ {subphase_name}", total=total)

        self.task_ids[subphase_key] = task_id
        self.task_hierarchy[phase_key].append(subphase_key)
        self.task_totals[subphase_key] = total
        self.task_completed[subphase_key] = 0
        self.task_states[subphase_key] = TaskState.PENDING
        self.task_creation_order.append(subphase_key)
        self.task_names[subphase_key] = subphase_name

        # Update tree symbols for all sub-phases under this phase
        self._update_tree_symbols(phase_key)

        return subphase_key

    def update_subphase(self, subphase_key: str, advance: int = 1):
        """
        Update sub-phase progress.
        :param subphase_key: Sub-phase key from start_subphase().
        :param advance: Amount to advance progress.
        """
        if not self._safe_task_operation(subphase_key):
            return

        self.task_completed[subphase_key] += advance
        self.progress.update(self.task_ids[subphase_key], advance=advance)

    def complete_subphase(self, subphase_key: str):
        """
        Complete a sub-phase and remove it from display.
        :param subphase_key: Sub-phase key from start_subphase().
        """
        if subphase_key not in self.task_ids:
            return

        # Find parent for tree symbol updates
        parent_key = self._find_parent_key(subphase_key)

        # Complete and remove sub-phase
        total = self.task_totals[subphase_key]
        self.progress.update(self.task_ids[subphase_key], completed=total)
        self.progress.remove_task(self.task_ids[subphase_key])

        # Clean up tracking
        del self.task_ids[subphase_key]
        if subphase_key in self.task_totals:
            del self.task_totals[subphase_key]
        if subphase_key in self.task_completed:
            del self.task_completed[subphase_key]
        if subphase_key in self.task_states:
            del self.task_states[subphase_key]
        if subphase_key in self.task_names:
            del self.task_names[subphase_key]
        if subphase_key in self.task_creation_order:
            self.task_creation_order.remove(subphase_key)

        # Remove from parent's hierarchy
        if parent_key and parent_key in self.task_hierarchy:
            if subphase_key in self.task_hierarchy[parent_key]:
                self.task_hierarchy[parent_key].remove(subphase_key)

        # Update tree symbols for remaining sub-phases
        if parent_key:
            self._update_tree_symbols(parent_key)

    def set_phase_total(self, phase_key: str, total: int):
        """
        Set or update the total work for a phase.
        :param phase_key: Phase key from start_phase().
        :param total: New total work units.
        """
        if not self._safe_task_operation(phase_key):
            return

        self.task_totals[phase_key] = total
        self.progress.update(self.task_ids[phase_key], total=total)

    def _update_parent_progress(self, child_key: str):
        """
        Update parent progress based on child completion using weights.
        :param child_key: Child key that was updated.
        """
        parent_key = self._find_parent_key(child_key)

        if not parent_key or parent_key not in self.task_ids:
            return

        # Calculate weighted progress from all children (including completed ones)
        total_weighted_progress = 0.0
        total_weight = 0.0

        for sibling_key in self.task_hierarchy[parent_key]:
            # Get weight - use default of 1.0 if not specified
            weight = self.task_weights.get(sibling_key, 1.0)
            total_weight += weight

            # Calculate sibling progress (0.0 to 1.0)
            sibling_progress = 0.0

            # Check if sibling was completed (and possibly removed)
            if sibling_key in self.task_completed and sibling_key in self.task_totals:
                sibling_total = self.task_totals[sibling_key]
                sibling_done = self.task_completed[sibling_key]
                if sibling_total > 0:
                    sibling_progress = min(1.0, sibling_done / sibling_total)
                else:
                    sibling_progress = 1.0 if sibling_done > 0 else 0.0
            elif sibling_key not in self.task_ids:
                # Sibling was completed and removed - assume 100%
                sibling_progress = 1.0

            total_weighted_progress += sibling_progress * weight

        # Update parent progress (normalize by total weight, handle edge cases)
        if total_weight > 0:
            normalized_progress = total_weighted_progress / total_weight
            parent_progress = min(100, max(0, normalized_progress * 100))

            # Only update if parent still exists
            if parent_key in self.task_ids:
                self.progress.update(self.task_ids[parent_key], completed=int(parent_progress))
                # Update our tracking too
                self.task_completed[parent_key] = int(parent_progress)
