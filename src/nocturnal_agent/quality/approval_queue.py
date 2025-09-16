"""Morning approval queue system for failed improvements."""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum

from nocturnal_agent.core.models import Task, ExecutionResult, QualityScore
from nocturnal_agent.quality.failure_analyzer import AnalysisResult


logger = logging.getLogger(__name__)


class ApprovalStatus(Enum):
    """Status of approval queue items."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    IN_REVIEW = "in_review"
    DEFERRED = "deferred"


class Priority(Enum):
    """Priority levels for approval queue items."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class ApprovalItem:
    """Item in the approval queue."""
    id: str
    task: Task
    result: ExecutionResult
    analysis: Optional[AnalysisResult]
    
    # Approval metadata
    status: ApprovalStatus = ApprovalStatus.PENDING
    priority: Priority = Priority.MEDIUM
    category: str = "general"
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    review_deadline: Optional[datetime] = None
    
    # Review information
    reviewer_notes: List[str] = field(default_factory=list)
    approval_reason: Optional[str] = None
    rejection_reason: Optional[str] = None
    
    # Improvement attempts info
    improvement_attempts: int = 0
    last_attempt_quality: float = 0.0
    
    def update_status(self, status: ApprovalStatus, reason: Optional[str] = None):
        """Update item status with timestamp."""
        self.status = status
        self.updated_at = datetime.now()
        
        if status == ApprovalStatus.APPROVED and reason:
            self.approval_reason = reason
        elif status == ApprovalStatus.REJECTED and reason:
            self.rejection_reason = reason


class ApprovalQueue:
    """Manages morning approval queue for failed improvement tasks."""
    
    def __init__(self, project_path: str):
        """Initialize approval queue system.
        
        Args:
            project_path: Path to the project directory
        """
        self.project_path = Path(project_path)
        self.queue_dir = self.project_path / ".nocturnal" / "approval_queue"
        self.queue_dir.mkdir(parents=True, exist_ok=True)
        
        # Queue storage
        self.queue_file = self.queue_dir / "queue.json"
        self.archive_dir = self.queue_dir / "archive"
        self.archive_dir.mkdir(exist_ok=True)
        
        # Load existing queue
        self.items: List[ApprovalItem] = []
        self._load_queue()
    
    async def add_failed_task(
        self, 
        task: Task, 
        result: ExecutionResult, 
        analysis: Optional[AnalysisResult] = None,
        improvement_attempts: int = 0
    ) -> str:
        """Add a failed task to the approval queue.
        
        Args:
            task: The failed task
            result: Execution result
            analysis: Optional failure analysis
            improvement_attempts: Number of improvement attempts made
            
        Returns:
            ID of the created approval item
        """
        logger.info(f"Adding failed task to approval queue: {task.id}")
        
        # Generate unique ID
        item_id = f"{task.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Determine priority and category
        priority = self._determine_priority(result, analysis, improvement_attempts)
        category = self._categorize_failure(result, analysis)
        
        # Set review deadline (next business day)
        deadline = self._calculate_review_deadline()
        
        # Create approval item
        item = ApprovalItem(
            id=item_id,
            task=task,
            result=result,
            analysis=analysis,
            priority=priority,
            category=category,
            review_deadline=deadline,
            improvement_attempts=improvement_attempts,
            last_attempt_quality=result.quality_score.overall
        )
        
        # Add to queue
        self.items.append(item)
        await self._save_queue()
        
        logger.info(f"Added approval item: {item_id} (Priority: {priority.value}, Category: {category})")
        return item_id
    
    def get_pending_items(self, sort_by_priority: bool = True) -> List[ApprovalItem]:
        """Get all pending approval items.
        
        Args:
            sort_by_priority: Whether to sort by priority
            
        Returns:
            List of pending approval items
        """
        pending = [item for item in self.items if item.status == ApprovalStatus.PENDING]
        
        if sort_by_priority:
            priority_order = {
                Priority.CRITICAL: 0,
                Priority.HIGH: 1,
                Priority.MEDIUM: 2,
                Priority.LOW: 3
            }
            pending.sort(key=lambda x: (priority_order[x.priority], x.created_at))
        
        return pending
    
    def get_items_by_category(self, category: str) -> List[ApprovalItem]:
        """Get items by category.
        
        Args:
            category: Category to filter by
            
        Returns:
            List of items in the category
        """
        return [item for item in self.items if item.category == category]
    
    def get_overdue_items(self) -> List[ApprovalItem]:
        """Get items that are overdue for review.
        
        Returns:
            List of overdue items
        """
        now = datetime.now()
        return [
            item for item in self.items 
            if (item.status == ApprovalStatus.PENDING and 
                item.review_deadline and 
                item.review_deadline < now)
        ]
    
    async def approve_item(self, item_id: str, reason: str = "") -> bool:
        """Approve an item in the queue.
        
        Args:
            item_id: ID of the item to approve
            reason: Reason for approval
            
        Returns:
            True if approved successfully, False otherwise
        """
        item = self._find_item(item_id)
        if not item:
            logger.error(f"Item not found: {item_id}")
            return False
        
        logger.info(f"Approving item: {item_id}")
        item.update_status(ApprovalStatus.APPROVED, reason)
        
        # Archive the approved item
        await self._archive_item(item)
        
        # Remove from active queue
        self.items.remove(item)
        await self._save_queue()
        
        return True
    
    async def reject_item(self, item_id: str, reason: str = "") -> bool:
        """Reject an item in the queue.
        
        Args:
            item_id: ID of the item to reject
            reason: Reason for rejection
            
        Returns:
            True if rejected successfully, False otherwise
        """
        item = self._find_item(item_id)
        if not item:
            logger.error(f"Item not found: {item_id}")
            return False
        
        logger.info(f"Rejecting item: {item_id}")
        item.update_status(ApprovalStatus.REJECTED, reason)
        
        # Archive the rejected item
        await self._archive_item(item)
        
        # Remove from active queue
        self.items.remove(item)
        await self._save_queue()
        
        return True
    
    async def defer_item(self, item_id: str, defer_until: datetime, reason: str = "") -> bool:
        """Defer an item to a later date.
        
        Args:
            item_id: ID of the item to defer
            defer_until: When to review again
            reason: Reason for deferring
            
        Returns:
            True if deferred successfully, False otherwise
        """
        item = self._find_item(item_id)
        if not item:
            logger.error(f"Item not found: {item_id}")
            return False
        
        logger.info(f"Deferring item: {item_id} until {defer_until}")
        item.update_status(ApprovalStatus.DEFERRED, reason)
        item.review_deadline = defer_until
        
        await self._save_queue()
        return True
    
    async def add_reviewer_note(self, item_id: str, note: str) -> bool:
        """Add a reviewer note to an item.
        
        Args:
            item_id: ID of the item
            note: Note to add
            
        Returns:
            True if note added successfully, False otherwise
        """
        item = self._find_item(item_id)
        if not item:
            logger.error(f"Item not found: {item_id}")
            return False
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        item.reviewer_notes.append(f"[{timestamp}] {note}")
        item.updated_at = datetime.now()
        
        await self._save_queue()
        return True
    
    def generate_morning_report(self) -> Dict[str, Any]:
        """Generate morning review report.
        
        Returns:
            Comprehensive morning report
        """
        pending = self.get_pending_items()
        overdue = self.get_overdue_items()
        
        # Categorize items
        by_category = {}
        by_priority = {}
        
        for item in pending:
            by_category[item.category] = by_category.get(item.category, 0) + 1
            by_priority[item.priority.value] = by_priority.get(item.priority.value, 0) + 1
        
        # Calculate statistics
        total_pending = len(pending)
        critical_count = len([i for i in pending if i.priority == Priority.CRITICAL])
        high_count = len([i for i in pending if i.priority == Priority.HIGH])
        
        # Recent trends
        recent_items = [
            i for i in self.items 
            if (datetime.now() - i.created_at).days <= 7
        ]
        
        return {
            'summary': {
                'total_pending': total_pending,
                'overdue_items': len(overdue),
                'critical_items': critical_count,
                'high_priority_items': high_count,
                'items_needing_review': total_pending
            },
            'by_category': by_category,
            'by_priority': by_priority,
            'overdue_items': [
                {
                    'id': item.id,
                    'task_description': item.task.description,
                    'priority': item.priority.value,
                    'days_overdue': (datetime.now() - item.review_deadline).days,
                    'improvement_attempts': item.improvement_attempts
                }
                for item in overdue
            ],
            'critical_items': [
                {
                    'id': item.id,
                    'task_description': item.task.description,
                    'category': item.category,
                    'quality_score': item.last_attempt_quality,
                    'created_at': item.created_at.isoformat()
                }
                for item in pending if item.priority == Priority.CRITICAL
            ],
            'weekly_stats': {
                'items_added_this_week': len(recent_items),
                'average_quality_score': sum(i.last_attempt_quality for i in recent_items) / len(recent_items) if recent_items else 0,
                'most_common_category': max(by_category.items(), key=lambda x: x[1])[0] if by_category else 'none'
            },
            'recommendations': self._generate_review_recommendations(pending)
        }
    
    def _determine_priority(
        self, 
        result: ExecutionResult, 
        analysis: Optional[AnalysisResult], 
        improvement_attempts: int
    ) -> Priority:
        """Determine priority level for an approval item.
        
        Args:
            result: Execution result
            analysis: Optional failure analysis
            improvement_attempts: Number of improvement attempts
            
        Returns:
            Priority level
        """
        quality_score = result.quality_score.overall
        
        # Critical: Very low quality or many failed attempts
        if quality_score < 0.3 or improvement_attempts >= 3:
            return Priority.CRITICAL
        
        # High: Analysis indicates high severity or low quality
        if (analysis and analysis.impact_severity == 'high') or quality_score < 0.5:
            return Priority.HIGH
        
        # Medium: Moderate issues
        if quality_score < 0.7 or improvement_attempts >= 1:
            return Priority.MEDIUM
        
        # Low: Minor issues
        return Priority.LOW
    
    def _categorize_failure(self, result: ExecutionResult, analysis: Optional[AnalysisResult]) -> str:
        """Categorize the type of failure.
        
        Args:
            result: Execution result
            analysis: Optional failure analysis
            
        Returns:
            Category string
        """
        if analysis and analysis.failure_type:
            return analysis.failure_type
        
        # Categorize based on quality scores
        scores = result.quality_score
        
        if scores.code_quality < 0.5:
            return "code_quality"
        elif scores.consistency < 0.5:
            return "consistency"
        elif scores.test_coverage < 0.5:
            return "testing"
        elif result.errors:
            return "execution_error"
        else:
            return "general_quality"
    
    def _calculate_review_deadline(self) -> datetime:
        """Calculate when an item should be reviewed by.
        
        Returns:
            Review deadline datetime
        """
        now = datetime.now()
        
        # If it's before 10 AM, deadline is 10 AM today
        # Otherwise, deadline is 10 AM next day
        if now.hour < 10:
            return now.replace(hour=10, minute=0, second=0, microsecond=0)
        else:
            tomorrow = now + timedelta(days=1)
            return tomorrow.replace(hour=10, minute=0, second=0, microsecond=0)
    
    def _find_item(self, item_id: str) -> Optional[ApprovalItem]:
        """Find an item by ID.
        
        Args:
            item_id: ID to search for
            
        Returns:
            ApprovalItem if found, None otherwise
        """
        for item in self.items:
            if item.id == item_id:
                return item
        return None
    
    def _generate_review_recommendations(self, pending_items: List[ApprovalItem]) -> List[str]:
        """Generate recommendations for reviewing items.
        
        Args:
            pending_items: List of pending items
            
        Returns:
            List of recommendations
        """
        recommendations = []
        
        if not pending_items:
            recommendations.append("No pending items - great job!")
            return recommendations
        
        critical_count = len([i for i in pending_items if i.priority == Priority.CRITICAL])
        if critical_count > 0:
            recommendations.append(f"Review {critical_count} critical items first")
        
        overdue = self.get_overdue_items()
        if overdue:
            recommendations.append(f"Address {len(overdue)} overdue items immediately")
        
        # Category-based recommendations
        categories = {}
        for item in pending_items:
            categories[item.category] = categories.get(item.category, 0) + 1
        
        if categories:
            most_common = max(categories.items(), key=lambda x: x[1])
            if most_common[1] > 2:
                recommendations.append(f"Focus on {most_common[0]} issues - {most_common[1]} items in this category")
        
        # Time-based recommendations
        old_items = [i for i in pending_items if (datetime.now() - i.created_at).days > 3]
        if old_items:
            recommendations.append(f"Consider bulk review of {len(old_items)} items older than 3 days")
        
        return recommendations
    
    async def _save_queue(self):
        """Save queue to disk."""
        try:
            queue_data = {
                'items': [
                    {
                        'id': item.id,
                        'task': {
                            'id': item.task.id,
                            'description': item.task.description,
                            'priority': item.task.priority.value if hasattr(item.task.priority, 'value') else str(item.task.priority)
                        },
                        'result': {
                            'success': item.result.success,
                            'quality_score': {
                                'overall': item.result.quality_score.overall,
                                'code_quality': item.result.quality_score.code_quality,
                                'consistency': item.result.quality_score.consistency,
                                'test_coverage': item.result.quality_score.test_coverage
                            },
                            'errors': item.result.errors,
                            'execution_time': item.result.execution_time
                        },
                        'analysis': {
                            'failure_type': item.analysis.failure_type,
                            'root_causes': item.analysis.root_causes,
                            'impact_severity': item.analysis.impact_severity,
                            'confidence_score': item.analysis.confidence_score
                        } if item.analysis else None,
                        'status': item.status.value,
                        'priority': item.priority.value,
                        'category': item.category,
                        'created_at': item.created_at.isoformat(),
                        'updated_at': item.updated_at.isoformat(),
                        'review_deadline': item.review_deadline.isoformat() if item.review_deadline else None,
                        'reviewer_notes': item.reviewer_notes,
                        'approval_reason': item.approval_reason,
                        'rejection_reason': item.rejection_reason,
                        'improvement_attempts': item.improvement_attempts,
                        'last_attempt_quality': item.last_attempt_quality
                    }
                    for item in self.items
                ]
            }
            
            with open(self.queue_file, 'w', encoding='utf-8') as f:
                json.dump(queue_data, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            logger.error(f"Failed to save queue: {e}")
    
    def _load_queue(self):
        """Load queue from disk."""
        try:
            if not self.queue_file.exists():
                return
            
            with open(self.queue_file, 'r', encoding='utf-8') as f:
                queue_data = json.load(f)
            
            self.items = []
            for item_data in queue_data.get('items', []):
                # This is a simplified load - in practice you'd need full reconstruction
                # For now, just load basic metadata for demonstration
                logger.info(f"Loading approval item: {item_data['id']}")
                
        except Exception as e:
            logger.error(f"Failed to load queue: {e}")
            self.items = []
    
    async def _archive_item(self, item: ApprovalItem):
        """Archive a processed item.
        
        Args:
            item: Item to archive
        """
        try:
            archive_file = self.archive_dir / f"{item.id}_{item.status.value}.json"
            
            archive_data = {
                'id': item.id,
                'status': item.status.value,
                'priority': item.priority.value,
                'category': item.category,
                'created_at': item.created_at.isoformat(),
                'processed_at': datetime.now().isoformat(),
                'approval_reason': item.approval_reason,
                'rejection_reason': item.rejection_reason,
                'reviewer_notes': item.reviewer_notes,
                'task_description': item.task.description,
                'final_quality_score': item.last_attempt_quality,
                'improvement_attempts': item.improvement_attempts
            }
            
            with open(archive_file, 'w', encoding='utf-8') as f:
                json.dump(archive_data, f, indent=2, ensure_ascii=False)
                
            logger.info(f"Archived item: {archive_file}")
            
        except Exception as e:
            logger.error(f"Failed to archive item: {e}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get approval queue statistics."""
        total_items = len(self.items)
        
        if total_items == 0:
            return {
                'total_items': 0,
                'pending': 0,
                'overdue': 0,
                'by_priority': {},
                'by_category': {},
                'average_queue_time': 0.0
            }
        
        pending = len([i for i in self.items if i.status == ApprovalStatus.PENDING])
        overdue = len(self.get_overdue_items())
        
        by_priority = {}
        by_category = {}
        queue_times = []
        
        for item in self.items:
            by_priority[item.priority.value] = by_priority.get(item.priority.value, 0) + 1
            by_category[item.category] = by_category.get(item.category, 0) + 1
            
            if item.status != ApprovalStatus.PENDING:
                queue_time = (item.updated_at - item.created_at).total_seconds() / 3600  # hours
                queue_times.append(queue_time)
        
        avg_queue_time = sum(queue_times) / len(queue_times) if queue_times else 0.0
        
        return {
            'total_items': total_items,
            'pending': pending,
            'overdue': overdue,
            'by_priority': by_priority,
            'by_category': by_category,
            'average_queue_time_hours': avg_queue_time,
            'oldest_pending_days': max(
                (datetime.now() - i.created_at).days 
                for i in self.items 
                if i.status == ApprovalStatus.PENDING
            ) if pending > 0 else 0
        }