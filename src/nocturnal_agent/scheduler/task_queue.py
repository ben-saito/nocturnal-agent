"""Task queue management with priority-based scheduling."""

import logging
import asyncio
import heapq
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import json
from pathlib import Path

from nocturnal_agent.core.models import Task, TaskPriority, TaskStatus


logger = logging.getLogger(__name__)


class QueueStatus(Enum):
    """Task queue status."""
    ACTIVE = "active"
    PAUSED = "paused"
    DRAINING = "draining"  # No new tasks, finish existing
    STOPPED = "stopped"


@dataclass
class QueuedTask:
    """Task in the queue with scheduling metadata."""
    task: Task
    priority_score: float  # Lower scores = higher priority
    queued_at: datetime
    estimated_duration: timedelta = field(default_factory=lambda: timedelta(minutes=15))
    dependencies: List[str] = field(default_factory=list)
    retry_count: int = 0
    max_retries: int = 3
    
    def __lt__(self, other):
        """Priority queue comparison."""
        return self.priority_score < other.priority_score


class TaskQueue:
    """Priority-based task queue with intelligent scheduling."""
    
    def __init__(self, project_path: str, config: Dict[str, Any]):
        """Initialize task queue.
        
        Args:
            project_path: Path to the project directory
            config: Queue configuration
        """
        self.project_path = Path(project_path)
        self.config = config
        
        # Queue settings
        self.max_concurrent_tasks = config.get('max_concurrent_tasks', 1)
        self.max_queue_size = config.get('max_queue_size', 100)
        self.priority_weights = config.get('priority_weights', {
            'critical': 1.0,
            'high': 2.0,
            'medium': 3.0,
            'low': 4.0
        })
        
        # Queue state
        self.status = QueueStatus.ACTIVE
        self.pending_queue: List[QueuedTask] = []  # Priority queue
        self.running_tasks: Dict[str, QueuedTask] = {}
        self.completed_tasks: List[QueuedTask] = []
        self.failed_tasks: List[QueuedTask] = []
        
        # Queue persistence
        self.queue_dir = self.project_path / ".nocturnal" / "queue"
        self.queue_dir.mkdir(parents=True, exist_ok=True)
        self.queue_file = self.queue_dir / "task_queue.json"
        
        # Statistics
        self.stats = {
            'tasks_queued': 0,
            'tasks_completed': 0,
            'tasks_failed': 0,
            'average_completion_time': 0.0,
            'queue_start_time': datetime.now()
        }
        
        # Load existing queue
        self._load_queue()
    
    async def add_task(
        self, 
        task: Task, 
        priority_override: Optional[float] = None,
        estimated_duration: Optional[timedelta] = None,
        dependencies: Optional[List[str]] = None
    ) -> bool:
        """Add a task to the queue.
        
        Args:
            task: Task to add
            priority_override: Override priority score
            estimated_duration: Estimated task duration
            dependencies: Task dependencies (task IDs)
            
        Returns:
            True if task was added successfully
        """
        if self.status == QueueStatus.STOPPED:
            logger.warning("Cannot add task - queue is stopped")
            return False
        
        if len(self.pending_queue) >= self.max_queue_size:
            logger.warning("Cannot add task - queue is full")
            return False
        
        # Calculate priority score
        priority_score = priority_override or self._calculate_priority_score(task)
        
        # Create queued task
        queued_task = QueuedTask(
            task=task,
            priority_score=priority_score,
            queued_at=datetime.now(),
            estimated_duration=estimated_duration or timedelta(minutes=15),
            dependencies=dependencies or []
        )
        
        # Add to priority queue
        heapq.heappush(self.pending_queue, queued_task)
        self.stats['tasks_queued'] += 1
        
        logger.info(f"Added task to queue: {task.id} (priority: {priority_score:.2f})")
        
        # Persist queue
        await self._save_queue()
        
        return True
    
    def _calculate_priority_score(self, task: Task) -> float:
        """Calculate priority score for a task.
        
        Args:
            task: Task to prioritize
            
        Returns:
            Priority score (lower = higher priority)
        """
        base_score = self.priority_weights.get(
            task.priority.value if hasattr(task.priority, 'value') else str(task.priority),
            3.0  # Default medium priority
        )
        
        # Adjust based on task age (older tasks get higher priority)
        if task.created_at:
            age_hours = (datetime.now() - task.created_at).total_seconds() / 3600
            age_factor = min(age_hours * 0.1, 1.0)  # Max 1.0 reduction
            base_score -= age_factor
        
        # Adjust based on estimated quality
        if hasattr(task, 'estimated_quality') and task.estimated_quality > 0:
            quality_factor = (1.0 - task.estimated_quality) * 0.5  # Higher quality = higher priority
            base_score += quality_factor
        
        # Ensure minimum score
        return max(base_score, 0.1)
    
    async def get_next_task(self) -> Optional[QueuedTask]:
        """Get the next task to execute.
        
        Returns:
            Next task or None if no tasks available
        """
        if self.status not in [QueueStatus.ACTIVE, QueueStatus.DRAINING]:
            return None
        
        if len(self.running_tasks) >= self.max_concurrent_tasks:
            return None
        
        # Find next executable task (no unresolved dependencies)
        available_tasks = []
        
        while self.pending_queue:
            candidate = heapq.heappop(self.pending_queue)
            
            # Check dependencies
            if self._has_unresolved_dependencies(candidate):
                # Put back in queue with slightly lower priority
                candidate.priority_score += 0.1
                heapq.heappush(self.pending_queue, candidate)
                continue
            
            # Task is ready to run
            available_tasks.append(candidate)
            break
        
        if not available_tasks:
            return None
        
        # Start the task
        next_task = available_tasks[0]
        self.running_tasks[next_task.task.id] = next_task
        next_task.task.start_execution()
        
        logger.info(f"Starting task: {next_task.task.id}")
        return next_task
    
    def _has_unresolved_dependencies(self, queued_task: QueuedTask) -> bool:
        """Check if a task has unresolved dependencies.
        
        Args:
            queued_task: Task to check
            
        Returns:
            True if task has unresolved dependencies
        """
        if not queued_task.dependencies:
            return False
        
        # Check if all dependencies are completed
        completed_task_ids = {t.task.id for t in self.completed_tasks}
        
        for dep_id in queued_task.dependencies:
            if dep_id not in completed_task_ids:
                # Check if dependency is currently running
                if dep_id not in self.running_tasks:
                    return True  # Dependency not found
        
        return False
    
    async def complete_task(self, task_id: str, success: bool = True) -> bool:
        """Mark a task as completed.
        
        Args:
            task_id: ID of completed task
            success: Whether task completed successfully
            
        Returns:
            True if task was marked as completed
        """
        if task_id not in self.running_tasks:
            logger.warning(f"Task {task_id} not found in running tasks")
            return False
        
        queued_task = self.running_tasks.pop(task_id)
        queued_task.task.complete_execution(success)
        
        if success:
            self.completed_tasks.append(queued_task)
            self.stats['tasks_completed'] += 1
            logger.info(f"Task completed successfully: {task_id}")
        else:
            # Check if we should retry
            if queued_task.retry_count < queued_task.max_retries:
                queued_task.retry_count += 1
                queued_task.priority_score -= 0.5  # Higher priority for retry
                heapq.heappush(self.pending_queue, queued_task)
                logger.info(f"Task failed, queued for retry ({queued_task.retry_count}/{queued_task.max_retries}): {task_id}")
            else:
                self.failed_tasks.append(queued_task)
                self.stats['tasks_failed'] += 1
                logger.error(f"Task failed permanently: {task_id}")
        
        # Update statistics
        if queued_task.task.completed_at and queued_task.task.started_at:
            completion_time = (queued_task.task.completed_at - queued_task.task.started_at).total_seconds()
            self._update_average_completion_time(completion_time)
        
        # Persist queue
        await self._save_queue()
        
        return True
    
    def _update_average_completion_time(self, new_time: float):
        """Update average completion time with new data point.
        
        Args:
            new_time: New completion time in seconds
        """
        current_avg = self.stats['average_completion_time']
        completed_count = self.stats['tasks_completed']
        
        if completed_count <= 1:
            self.stats['average_completion_time'] = new_time
        else:
            # Weighted average
            self.stats['average_completion_time'] = (
                (current_avg * (completed_count - 1) + new_time) / completed_count
            )
    
    def get_queue_status(self) -> Dict[str, Any]:
        """Get current queue status.
        
        Returns:
            Queue status information
        """
        return {
            'status': self.status.value,
            'pending_tasks': len(self.pending_queue),
            'running_tasks': len(self.running_tasks),
            'completed_tasks': len(self.completed_tasks),
            'failed_tasks': len(self.failed_tasks),
            'queue_utilization': len(self.running_tasks) / self.max_concurrent_tasks,
            'statistics': self.stats.copy(),
            'next_tasks': [
                {
                    'id': qt.task.id,
                    'description': qt.task.description,
                    'priority_score': qt.priority_score,
                    'estimated_duration': str(qt.estimated_duration),
                    'dependencies': qt.dependencies
                }
                for qt in heapq.nsmallest(5, self.pending_queue)
            ],
            'running_tasks_info': [
                {
                    'id': qt.task.id,
                    'description': qt.task.description,
                    'started_at': qt.task.started_at.isoformat() if qt.task.started_at else None,
                    'estimated_duration': str(qt.estimated_duration)
                }
                for qt in self.running_tasks.values()
            ]
        }
    
    async def pause_queue(self):
        """Pause the queue (no new tasks will be started)."""
        logger.info("Pausing task queue")
        self.status = QueueStatus.PAUSED
        await self._save_queue()
    
    async def resume_queue(self):
        """Resume the queue."""
        logger.info("Resuming task queue")
        self.status = QueueStatus.ACTIVE
        await self._save_queue()
    
    async def drain_queue(self):
        """Drain the queue (finish running tasks, don't start new ones)."""
        logger.info("Draining task queue")
        self.status = QueueStatus.DRAINING
        await self._save_queue()
    
    async def stop_queue(self):
        """Stop the queue completely."""
        logger.info("Stopping task queue")
        self.status = QueueStatus.STOPPED
        
        # Move running tasks back to pending
        for task_id, queued_task in self.running_tasks.items():
            queued_task.task.status = TaskStatus.PENDING
            heapq.heappush(self.pending_queue, queued_task)
        
        self.running_tasks.clear()
        await self._save_queue()
    
    def remove_task(self, task_id: str) -> bool:
        """Remove a task from the queue.
        
        Args:
            task_id: ID of task to remove
            
        Returns:
            True if task was removed
        """
        # Check running tasks
        if task_id in self.running_tasks:
            logger.warning(f"Cannot remove running task: {task_id}")
            return False
        
        # Remove from pending queue
        original_queue = self.pending_queue[:]
        self.pending_queue = []
        
        removed = False
        for queued_task in original_queue:
            if queued_task.task.id == task_id:
                removed = True
                logger.info(f"Removed task from queue: {task_id}")
            else:
                heapq.heappush(self.pending_queue, queued_task)
        
        return removed
    
    def get_task_position(self, task_id: str) -> Optional[int]:
        """Get position of task in queue.
        
        Args:
            task_id: ID of task to find
            
        Returns:
            Position in queue (0-based) or None if not found
        """
        sorted_queue = sorted(self.pending_queue)
        
        for i, queued_task in enumerate(sorted_queue):
            if queued_task.task.id == task_id:
                return i
        
        return None
    
    def get_estimated_wait_time(self, task_id: str) -> Optional[timedelta]:
        """Get estimated wait time for a task.
        
        Args:
            task_id: ID of task
            
        Returns:
            Estimated wait time or None if task not found
        """
        position = self.get_task_position(task_id)
        if position is None:
            return None
        
        # Estimate based on average completion time and position
        avg_time = self.stats['average_completion_time'] or 900  # Default 15 minutes
        estimated_seconds = position * avg_time
        
        return timedelta(seconds=estimated_seconds)
    
    async def optimize_queue(self):
        """Optimize queue order based on current conditions."""
        logger.info("Optimizing task queue")
        
        # Re-calculate priorities for all pending tasks
        tasks_to_requeue = []
        
        while self.pending_queue:
            queued_task = heapq.heappop(self.pending_queue)
            # Re-calculate priority
            queued_task.priority_score = self._calculate_priority_score(queued_task.task)
            tasks_to_requeue.append(queued_task)
        
        # Re-add all tasks
        for queued_task in tasks_to_requeue:
            heapq.heappush(self.pending_queue, queued_task)
        
        await self._save_queue()
        logger.info(f"Queue optimized - {len(tasks_to_requeue)} tasks reordered")
    
    async def _save_queue(self):
        """Save queue state to disk."""
        try:
            # Convert datetime to ISO string for JSON serialization
            stats_serializable = self.stats.copy()
            if 'queue_start_time' in stats_serializable and isinstance(stats_serializable['queue_start_time'], datetime):
                stats_serializable['queue_start_time'] = stats_serializable['queue_start_time'].isoformat()
            
            queue_data = {
                'status': self.status.value,
                'stats': stats_serializable,
                'pending_tasks': [
                    {
                        'task_id': qt.task.id,
                        'priority_score': qt.priority_score,
                        'queued_at': qt.queued_at.isoformat(),
                        'estimated_duration': qt.estimated_duration.total_seconds(),
                        'dependencies': qt.dependencies,
                        'retry_count': qt.retry_count
                    }
                    for qt in self.pending_queue
                ],
                'running_tasks': [
                    {
                        'task_id': qt.task.id,
                        'priority_score': qt.priority_score,
                        'started_at': qt.task.started_at.isoformat() if qt.task.started_at else None
                    }
                    for qt in self.running_tasks.values()
                ]
            }
            
            with open(self.queue_file, 'w', encoding='utf-8') as f:
                json.dump(queue_data, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            logger.error(f"Failed to save queue: {e}")
    
    def _load_queue(self):
        """Load queue state from disk."""
        try:
            if not self.queue_file.exists():
                return
            
            with open(self.queue_file, 'r', encoding='utf-8') as f:
                queue_data = json.load(f)
            
            # Restore status
            self.status = QueueStatus(queue_data.get('status', 'active'))
            
            # Restore statistics
            if 'stats' in queue_data:
                self.stats.update(queue_data['stats'])
                # Convert ISO string back to datetime
                if isinstance(self.stats['queue_start_time'], str):
                    self.stats['queue_start_time'] = datetime.fromisoformat(self.stats['queue_start_time'])
            
            # Note: Tasks themselves would need to be reconstructed from a task store
            # This is a simplified version that only preserves metadata
            
            logger.info(f"Loaded queue state: {len(queue_data.get('pending_tasks', []))} pending tasks")
            
        except Exception as e:
            logger.error(f"Failed to load queue: {e}")
    
    def cleanup_completed_tasks(self, keep_count: int = 100):
        """Clean up old completed tasks.
        
        Args:
            keep_count: Number of completed tasks to keep
        """
        if len(self.completed_tasks) > keep_count:
            # Keep most recent tasks
            self.completed_tasks = self.completed_tasks[-keep_count:]
            logger.info(f"Cleaned up completed tasks, kept {keep_count}")
        
        if len(self.failed_tasks) > keep_count:
            self.failed_tasks = self.failed_tasks[-keep_count:]
            logger.info(f"Cleaned up failed tasks, kept {keep_count}")
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get queue performance metrics.
        
        Returns:
            Performance metrics
        """
        uptime = datetime.now() - self.stats['queue_start_time']
        total_processed = self.stats['tasks_completed'] + self.stats['tasks_failed']
        
        return {
            'uptime': str(uptime),
            'throughput': {
                'total_processed': total_processed,
                'tasks_per_hour': total_processed / (uptime.total_seconds() / 3600) if uptime.total_seconds() > 0 else 0,
                'success_rate': self.stats['tasks_completed'] / total_processed if total_processed > 0 else 0
            },
            'timing': {
                'average_completion_time': self.stats['average_completion_time'],
                'average_queue_wait_time': 0  # Could be calculated if tracking queued times
            },
            'capacity': {
                'max_concurrent': self.max_concurrent_tasks,
                'current_utilization': len(self.running_tasks) / self.max_concurrent_tasks,
                'queue_size': len(self.pending_queue),
                'queue_capacity': self.max_queue_size,
                'queue_utilization': len(self.pending_queue) / self.max_queue_size
            }
        }