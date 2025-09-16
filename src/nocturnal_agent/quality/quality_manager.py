"""Quality management system integrating all quality improvement components."""

import logging
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

from nocturnal_agent.core.models import (
    Task, ExecutionResult, QualityScore, FailureInfo, ImprovementPlan
)
from nocturnal_agent.quality.improvement_cycle import QualityImprovementCycle
from nocturnal_agent.quality.failure_analyzer import FailureAnalyzer
from nocturnal_agent.quality.approval_queue import ApprovalQueue


logger = logging.getLogger(__name__)


class QualityManager:
    """Central quality management system."""
    
    def __init__(self, project_path: str, config: Dict[str, Any]):
        """Initialize quality management system.
        
        Args:
            project_path: Path to the project directory
            config: Quality configuration
        """
        self.project_path = Path(project_path)
        self.config = config
        
        # Quality thresholds
        self.quality_threshold = config.get('quality_threshold', 0.85)
        self.consistency_threshold = config.get('consistency_threshold', 0.85)
        self.max_improvement_attempts = config.get('max_improvement_attempts', 3)
        
        # Initialize components
        self.improvement_cycle = QualityImprovementCycle(
            project_path=str(self.project_path),
            quality_threshold=self.quality_threshold,
            max_attempts=self.max_improvement_attempts
        )
        
        self.failure_analyzer = FailureAnalyzer(str(self.project_path))
        self.approval_queue = ApprovalQueue(str(self.project_path))
        
        # Statistics tracking
        self.session_stats = {
            'tasks_processed': 0,
            'quality_improvements_attempted': 0,
            'quality_improvements_successful': 0,
            'tasks_sent_to_approval': 0,
            'average_quality_improvement': 0.0,
            'session_start': datetime.now()
        }
    
    async def process_task_result(self, task: Task, result: ExecutionResult) -> ExecutionResult:
        """Process a task result through the complete quality management pipeline.
        
        Args:
            task: The executed task
            result: Initial execution result
            
        Returns:
            Final execution result after quality processing
        """
        logger.info(f"Processing task result for quality management: {task.id}")
        self.session_stats['tasks_processed'] += 1
        
        # Store original quality for comparison
        original_quality = result.quality_score.overall
        result.original_quality_score = result.quality_score
        
        # Step 1: Check if quality meets threshold
        if await self._meets_quality_standards(result):
            logger.info(f"Task {task.id} meets quality standards (score: {original_quality:.3f})")
            return result
        
        # Step 2: Attempt quality improvement
        logger.warning(f"Task {task.id} below quality threshold, starting improvement cycle")
        self.session_stats['quality_improvements_attempted'] += 1
        
        improved_result = await self.improvement_cycle.evaluate_and_improve(task, result)
        
        # Step 3: Evaluate improvement results
        if improved_result.quality_score.overall >= self.quality_threshold:
            logger.info(f"Quality improvement successful for task {task.id}")
            self.session_stats['quality_improvements_successful'] += 1
            
            # Update improvement statistics
            quality_gain = improved_result.quality_score.overall - original_quality
            self._update_quality_statistics(quality_gain)
            
            return improved_result
        
        # Step 4: Improvement failed - analyze and queue for approval
        logger.warning(f"Quality improvement failed for task {task.id}, analyzing failure")
        
        analysis = await self.failure_analyzer.analyze_failure(task, improved_result)
        
        # Add to approval queue
        await self.approval_queue.add_failed_task(
            task=task,
            result=improved_result,
            analysis=analysis,
            improvement_attempts=improved_result.improvement_attempts
        )
        
        self.session_stats['tasks_sent_to_approval'] += 1
        
        logger.info(f"Task {task.id} added to morning approval queue")
        return improved_result
    
    async def _meets_quality_standards(self, result: ExecutionResult) -> bool:
        """Check if result meets quality standards.
        
        Args:
            result: Execution result to check
            
        Returns:
            True if meets standards, False otherwise
        """
        quality = result.quality_score
        
        # Check overall quality
        if quality.overall < self.quality_threshold:
            return False
        
        # Check consistency separately
        if quality.consistency < self.consistency_threshold:
            return False
        
        # Check for critical errors
        if result.errors and any('critical' in error.lower() or 'fatal' in error.lower() for error in result.errors):
            return False
        
        # Check execution success
        if not result.success:
            return False
        
        return True
    
    def _update_quality_statistics(self, quality_gain: float):
        """Update quality improvement statistics.
        
        Args:
            quality_gain: Quality improvement achieved
        """
        current_avg = self.session_stats['average_quality_improvement']
        successful_count = self.session_stats['quality_improvements_successful']
        
        # Calculate new average
        if successful_count == 1:
            self.session_stats['average_quality_improvement'] = quality_gain
        else:
            total_gain = current_avg * (successful_count - 1) + quality_gain
            self.session_stats['average_quality_improvement'] = total_gain / successful_count
    
    async def generate_quality_report(self) -> Dict[str, Any]:
        """Generate comprehensive quality management report.
        
        Returns:
            Quality report dictionary
        """
        logger.info("Generating quality management report")
        
        # Get component statistics
        improvement_stats = self.improvement_cycle.get_statistics()
        analysis_stats = self.failure_analyzer.get_analysis_statistics()
        approval_stats = self.approval_queue.get_statistics()
        
        # Calculate session metrics
        session_duration = (datetime.now() - self.session_stats['session_start']).total_seconds() / 3600
        
        success_rate = 0.0
        if self.session_stats['quality_improvements_attempted'] > 0:
            success_rate = (
                self.session_stats['quality_improvements_successful'] / 
                self.session_stats['quality_improvements_attempted']
            )
        
        return {
            'session_overview': {
                'tasks_processed': self.session_stats['tasks_processed'],
                'session_duration_hours': session_duration,
                'quality_threshold': self.quality_threshold,
                'consistency_threshold': self.consistency_threshold
            },
            'quality_improvement': {
                'attempts': self.session_stats['quality_improvements_attempted'],
                'successful': self.session_stats['quality_improvements_successful'],
                'success_rate': success_rate,
                'average_improvement': self.session_stats['average_quality_improvement'],
                'improvement_cycle_stats': improvement_stats
            },
            'failure_analysis': {
                'total_analyses': analysis_stats['total_analyses'],
                'average_confidence': analysis_stats['average_confidence'],
                'common_failure_types': analysis_stats['most_common_failure_types'],
                'recent_analyses': analysis_stats['recent_analysis_count']
            },
            'approval_queue': {
                'pending_items': approval_stats['pending'],
                'overdue_items': approval_stats['overdue'],
                'items_by_priority': approval_stats['by_priority'],
                'items_by_category': approval_stats['by_category'],
                'average_queue_time': approval_stats['average_queue_time_hours']
            },
            'recommendations': await self._generate_quality_recommendations()
        }
    
    async def _generate_quality_recommendations(self) -> List[str]:
        """Generate quality improvement recommendations.
        
        Returns:
            List of recommendations
        """
        recommendations = []
        
        # Success rate recommendations
        success_rate = 0.0
        if self.session_stats['quality_improvements_attempted'] > 0:
            success_rate = (
                self.session_stats['quality_improvements_successful'] / 
                self.session_stats['quality_improvements_attempted']
            )
        
        if success_rate < 0.5 and self.session_stats['quality_improvements_attempted'] > 3:
            recommendations.append("Low improvement success rate - consider reviewing improvement strategies")
        
        # Approval queue recommendations
        approval_stats = self.approval_queue.get_statistics()
        if approval_stats['overdue'] > 0:
            recommendations.append(f"Review {approval_stats['overdue']} overdue approval items")
        
        if approval_stats['pending'] > 10:
            recommendations.append("High number of pending approvals - consider batch processing")
        
        # Analysis insights
        learning_insights = self.failure_analyzer.get_learning_insights()
        if learning_insights:
            recommendations.append(f"Apply learned insights: {learning_insights[0]}")
        
        # Quality threshold recommendations
        avg_improvement = self.session_stats['average_quality_improvement']
        if avg_improvement > 0 and avg_improvement < 0.1:
            recommendations.append("Small quality improvements - consider more aggressive improvement strategies")
        
        return recommendations
    
    async def get_morning_approval_report(self) -> Dict[str, Any]:
        """Generate morning approval report for human review.
        
        Returns:
            Morning approval report
        """
        logger.info("Generating morning approval report")
        
        morning_report = self.approval_queue.generate_morning_report()
        
        # Add quality context
        morning_report['quality_context'] = {
            'quality_threshold': self.quality_threshold,
            'recent_success_rate': 0.0,
            'common_improvement_strategies': []
        }
        
        # Calculate recent success rate
        if self.session_stats['quality_improvements_attempted'] > 0:
            morning_report['quality_context']['recent_success_rate'] = (
                self.session_stats['quality_improvements_successful'] / 
                self.session_stats['quality_improvements_attempted']
            )
        
        # Add learning insights
        learning_insights = self.failure_analyzer.get_learning_insights()
        morning_report['learning_insights'] = learning_insights[:5]  # Top 5 insights
        
        return morning_report
    
    async def approve_queued_item(self, item_id: str, reason: str = "") -> bool:
        """Approve a queued item.
        
        Args:
            item_id: ID of item to approve
            reason: Reason for approval
            
        Returns:
            True if approved successfully
        """
        logger.info(f"Approving queued item: {item_id}")
        return await self.approval_queue.approve_item(item_id, reason)
    
    async def reject_queued_item(self, item_id: str, reason: str = "") -> bool:
        """Reject a queued item.
        
        Args:
            item_id: ID of item to reject
            reason: Reason for rejection
            
        Returns:
            True if rejected successfully
        """
        logger.info(f"Rejecting queued item: {item_id}")
        return await self.approval_queue.reject_item(item_id, reason)
    
    async def defer_queued_item(self, item_id: str, defer_until: datetime, reason: str = "") -> bool:
        """Defer a queued item.
        
        Args:
            item_id: ID of item to defer
            defer_until: When to review again
            reason: Reason for deferring
            
        Returns:
            True if deferred successfully
        """
        logger.info(f"Deferring queued item: {item_id}")
        return await self.approval_queue.defer_item(item_id, defer_until, reason)
    
    def get_pending_approvals(self) -> List[Dict[str, Any]]:
        """Get list of pending approvals for review.
        
        Returns:
            List of pending approval items
        """
        pending_items = self.approval_queue.get_pending_items()
        
        return [
            {
                'id': item.id,
                'task_description': item.task.description,
                'priority': item.priority.value,
                'category': item.category,
                'quality_score': item.last_attempt_quality,
                'improvement_attempts': item.improvement_attempts,
                'created_at': item.created_at.isoformat(),
                'review_deadline': item.review_deadline.isoformat() if item.review_deadline else None,
                'failure_type': item.analysis.failure_type if item.analysis else 'unknown',
                'root_causes': item.analysis.root_causes if item.analysis else []
            }
            for item in pending_items
        ]
    
    async def cleanup_old_data(self, retention_days: int = 30):
        """Clean up old quality management data.
        
        Args:
            retention_days: Number of days to retain data
        """
        logger.info(f"Cleaning up quality data older than {retention_days} days")
        
        try:
            cutoff_date = datetime.now() - timedelta(days=retention_days)
            
            # Clean up analysis files
            analysis_dir = self.project_path / ".nocturnal" / "analysis"
            if analysis_dir.exists():
                for file_path in analysis_dir.glob("*.json"):
                    if file_path.stat().st_mtime < cutoff_date.timestamp():
                        file_path.unlink()
                        logger.debug(f"Deleted old analysis file: {file_path}")
            
            # Clean up archived approval items
            archive_dir = self.approval_queue.archive_dir
            if archive_dir.exists():
                for file_path in archive_dir.glob("*.json"):
                    if file_path.stat().st_mtime < cutoff_date.timestamp():
                        file_path.unlink()
                        logger.debug(f"Deleted old archive file: {file_path}")
            
            logger.info("Quality data cleanup completed")
            
        except Exception as e:
            logger.error(f"Failed to clean up old data: {e}")
    
    def get_system_health(self) -> Dict[str, Any]:
        """Get quality management system health status.
        
        Returns:
            System health information
        """
        try:
            # Check component health
            components_healthy = {
                'improvement_cycle': self.improvement_cycle is not None,
                'failure_analyzer': self.failure_analyzer is not None,
                'approval_queue': self.approval_queue is not None
            }
            
            # Check data directories
            data_dirs_exist = {
                'analysis_dir': (self.project_path / ".nocturnal" / "analysis").exists(),
                'approval_dir': (self.project_path / ".nocturnal" / "approval_queue").exists()
            }
            
            # Calculate overall health
            all_components_healthy = all(components_healthy.values())
            all_dirs_exist = all(data_dirs_exist.values())
            overall_healthy = all_components_healthy and all_dirs_exist
            
            return {
                'overall_healthy': overall_healthy,
                'components': components_healthy,
                'data_directories': data_dirs_exist,
                'session_stats': self.session_stats.copy(),
                'config': {
                    'quality_threshold': self.quality_threshold,
                    'consistency_threshold': self.consistency_threshold,
                    'max_improvement_attempts': self.max_improvement_attempts
                }
            }
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                'overall_healthy': False,
                'error': str(e),
                'components': {},
                'data_directories': {},
                'session_stats': {},
                'config': {}
            }