"""Safety coordinator that integrates all safety systems."""

import logging
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable

from nocturnal_agent.safety.backup_manager import BackupManager, BackupType, BackupInfo
from nocturnal_agent.safety.danger_detector import DangerDetector, DangerDetection, DangerLevel
from nocturnal_agent.safety.rollback_manager import RollbackManager, RollbackPoint, RollbackType
from nocturnal_agent.core.models import Task, ExecutionResult


logger = logging.getLogger(__name__)


class SafetyCoordinator:
    """Coordinates all safety systems for secure autonomous operation."""
    
    def __init__(self, project_path: str, config: Dict[str, Any]):
        """Initialize safety coordinator.
        
        Args:
            project_path: Path to the project directory
            config: Safety configuration
        """
        self.project_path = Path(project_path)
        self.config = config
        
        # Initialize safety components
        self.backup_manager = BackupManager(str(self.project_path), config.get('backup', {}))
        self.danger_detector = DangerDetector(config.get('danger_detection', {}))
        self.rollback_manager = RollbackManager(
            str(self.project_path), 
            self.backup_manager, 
            config.get('rollback', {})
        )
        
        # Safety settings
        self.auto_backup_before_execution = config.get('auto_backup_before_execution', True)
        self.auto_create_rollback_points = config.get('auto_create_rollback_points', True)
        self.block_dangerous_operations = config.get('block_dangerous_operations', True)
        self.safety_check_interval = config.get('safety_check_interval_hours', 1)
        
        # State tracking
        self.safety_active = False
        self.current_session_backup: Optional[BackupInfo] = None
        self.current_rollback_point: Optional[RollbackPoint] = None
        self.safety_violations: List[Dict[str, Any]] = []
        
        # Callbacks for safety events
        self.danger_callbacks: List[Callable] = []
        self.backup_callbacks: List[Callable] = []
        self.rollback_callbacks: List[Callable] = []
        
        # Statistics
        self.safety_stats = {
            'session_start': None,
            'backups_created': 0,
            'rollback_points_created': 0,
            'dangers_detected': 0,
            'operations_blocked': 0,
            'emergency_rollbacks': 0,
            'successful_recoveries': 0
        }
    
    async def initialize_safety_session(self) -> bool:
        """Initialize a new safety session for night execution.
        
        Returns:
            True if initialization successful
        """
        logger.info("Initializing safety session")
        
        try:
            self.safety_stats['session_start'] = datetime.now()
            self.safety_active = True
            
            # Create pre-execution backup
            if self.auto_backup_before_execution:
                logger.info("Creating pre-execution safety backup")
                self.current_session_backup = await self.backup_manager.create_pre_execution_backup()
                self.safety_stats['backups_created'] += 1
                
                # Notify backup callbacks
                for callback in self.backup_callbacks:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback('backup_created', self.current_session_backup)
                        else:
                            callback('backup_created', self.current_session_backup)
                    except Exception as e:
                        logger.error(f"Backup callback failed: {e}")
            
            # Create initial rollback point
            if self.auto_create_rollback_points:
                logger.info("Creating initial rollback point")
                self.current_rollback_point = await self.rollback_manager.create_rollback_point(
                    "Session start - pre-execution state"
                )
                self.safety_stats['rollback_points_created'] += 1
                
                # Notify rollback callbacks
                for callback in self.rollback_callbacks:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback('rollback_point_created', self.current_rollback_point)
                        else:
                            callback('rollback_point_created', self.current_rollback_point)
                    except Exception as e:
                        logger.error(f"Rollback callback failed: {e}")
            
            logger.info("Safety session initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize safety session: {e}")
            self.safety_active = False
            return False
    
    async def finalize_safety_session(self) -> Dict[str, Any]:
        """Finalize safety session and generate report.
        
        Returns:
            Safety session report
        """
        logger.info("Finalizing safety session")
        
        session_report = {
            'session_duration': str(datetime.now() - self.safety_stats['session_start']) 
                              if self.safety_stats['session_start'] else None,
            'statistics': self.safety_stats.copy(),
            'safety_violations': self.safety_violations.copy(),
            'backup_status': self.backup_manager.get_backup_status(),
            'rollback_status': self.rollback_manager.get_status(),
            'danger_detection_status': self.danger_detector.get_status(),
            'session_backup': {
                'backup_id': self.current_session_backup.backup_id if self.current_session_backup else None,
                'verified': self.current_session_backup.verification_status == "verified" 
                          if self.current_session_backup else False
            },
            'current_rollback_point': {
                'rollback_id': self.current_rollback_point.rollback_id if self.current_rollback_point else None,
                'timestamp': self.current_rollback_point.timestamp.isoformat() 
                           if self.current_rollback_point else None
            }
        }
        
        # Create final backup if significant changes were made
        if self.safety_stats['backups_created'] > 1 or self.safety_stats['rollback_points_created'] > 1:
            try:
                final_backup = await self.backup_manager.create_backup(
                    backup_type=BackupType.INCREMENTAL,
                    backup_id=f"session_end_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    description="End of safety session backup"
                )
                session_report['final_backup'] = final_backup.backup_id if final_backup else None
            except Exception as e:
                logger.error(f"Failed to create final backup: {e}")
                session_report['final_backup_error'] = str(e)
        
        self.safety_active = False
        logger.info("Safety session finalized")
        
        return session_report
    
    async def pre_task_safety_check(self, task: Task, planned_code: str = "") -> Dict[str, Any]:
        """Perform safety checks before task execution.
        
        Args:
            task: Task to be executed
            planned_code: Code that will be executed (if available)
            
        Returns:
            Safety check results
        """
        logger.debug(f"Performing pre-task safety check for: {task.id}")
        
        safety_result = {
            'safe_to_execute': True,
            'danger_level': DangerLevel.SAFE,
            'warnings': [],
            'blocking_issues': [],
            'recommendations': []
        }
        
        # Analyze planned code for dangers
        if planned_code:
            danger_analysis = self.danger_detector.analyze_code(planned_code)
            
            safety_result['danger_analysis'] = {
                'is_dangerous': danger_analysis.is_dangerous,
                'danger_level': danger_analysis.danger_level.value,
                'detected_patterns': [p.name for p in danger_analysis.detected_patterns],
                'risk_description': danger_analysis.risk_description
            }
            
            if danger_analysis.is_dangerous:
                self.safety_stats['dangers_detected'] += 1
                
                # Record safety violation
                violation = {
                    'task_id': task.id,
                    'timestamp': datetime.now().isoformat(),
                    'danger_level': danger_analysis.danger_level.value,
                    'patterns': [p.name for p in danger_analysis.detected_patterns],
                    'blocked': len(danger_analysis.blocked_operations) > 0
                }
                self.safety_violations.append(violation)
                
                # Notify danger callbacks
                for callback in self.danger_callbacks:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback('danger_detected', danger_analysis, task)
                        else:
                            callback('danger_detected', danger_analysis, task)
                    except Exception as e:
                        logger.error(f"Danger callback failed: {e}")
                
                # Update safety result
                if danger_analysis.blocked_operations and self.block_dangerous_operations:
                    safety_result['safe_to_execute'] = False
                    safety_result['blocking_issues'].extend(danger_analysis.blocked_operations)
                    self.safety_stats['operations_blocked'] += 1
                
                safety_result['danger_level'] = danger_analysis.danger_level
                safety_result['warnings'].append(danger_analysis.risk_description)
                safety_result['recommendations'].append(danger_analysis.recommended_action)
        
        # Check if backup is healthy
        backup_status = self.backup_manager.get_backup_status()
        if not backup_status['latest_backup'] or not backup_status['latest_backup']['verified']:
            safety_result['warnings'].append("No verified backup available for recovery")
            safety_result['recommendations'].append("Create verified backup before proceeding")
        
        return safety_result
    
    async def post_task_safety_check(self, task: Task, result: ExecutionResult) -> Dict[str, Any]:
        """Perform safety checks after task execution.
        
        Args:
            task: Executed task
            result: Task execution result
            
        Returns:
            Post-execution safety status
        """
        logger.debug(f"Performing post-task safety check for: {task.id}")
        
        safety_status = {
            'task_completed_safely': result.success,
            'recovery_needed': False,
            'rollback_recommended': False,
            'backup_created': False,
            'actions_taken': []
        }
        
        # Create rollback point for successful significant changes
        if result.success and (result.files_modified or result.files_created):
            if self.auto_create_rollback_points:
                try:
                    rollback_point = await self.rollback_manager.create_rollback_point(
                        f"After task {task.id}: {task.description[:50]}..."
                    )
                    self.current_rollback_point = rollback_point
                    self.safety_stats['rollback_points_created'] += 1
                    safety_status['rollback_point_created'] = rollback_point.rollback_id
                    safety_status['actions_taken'].append("Created rollback point")
                except Exception as e:
                    logger.error(f"Failed to create post-task rollback point: {e}")
                    safety_status['rollback_point_error'] = str(e)
        
        # Check if quality issues warrant rollback
        if not result.success or (result.quality_score and result.quality_score.overall < 0.3):
            safety_status['rollback_recommended'] = True
            safety_status['recovery_needed'] = True
            safety_status['actions_taken'].append("Flagged for potential rollback")
            
            logger.warning(f"Task {task.id} may need rollback due to quality issues")
        
        # Create incremental backup for significant changes
        if result.files_modified and len(result.files_modified) > 5:
            try:
                backup = await self.backup_manager.create_backup(
                    backup_type=BackupType.INCREMENTAL,
                    backup_id=f"post_task_{task.id}",
                    description=f"Backup after task {task.id}"
                )
                if backup:
                    safety_status['backup_created'] = True
                    safety_status['backup_id'] = backup.backup_id
                    safety_status['actions_taken'].append("Created incremental backup")
                    self.safety_stats['backups_created'] += 1
            except Exception as e:
                logger.error(f"Failed to create post-task backup: {e}")
                safety_status['backup_error'] = str(e)
        
        return safety_status
    
    async def emergency_recovery(self, reason: str = "Emergency recovery triggered") -> Dict[str, Any]:
        """Perform emergency recovery to last safe state.
        
        Args:
            reason: Reason for emergency recovery
            
        Returns:
            Recovery operation result
        """
        logger.critical(f"EMERGENCY RECOVERY: {reason}")
        self.safety_stats['emergency_rollbacks'] += 1
        
        recovery_result = {
            'recovery_attempted': True,
            'recovery_successful': False,
            'method_used': None,
            'recovered_to': None,
            'errors': []
        }
        
        try:
            # Try rollback to current rollback point first
            if self.current_rollback_point:
                logger.info("Attempting rollback to current rollback point")
                rollback_op = await self.rollback_manager.rollback_to_point(
                    self.current_rollback_point.rollback_id,
                    RollbackType.FULL_RESTORE
                )
                
                if rollback_op.status.value in ['completed', 'verified']:
                    recovery_result['recovery_successful'] = True
                    recovery_result['method_used'] = 'rollback_point'
                    recovery_result['recovered_to'] = self.current_rollback_point.rollback_id
                    self.safety_stats['successful_recoveries'] += 1
                else:
                    recovery_result['errors'].extend(rollback_op.errors)
            
            # If rollback failed, try backup restore
            if not recovery_result['recovery_successful'] and self.current_session_backup:
                logger.info("Attempting backup restore")
                
                # Create a temporary rollback point for backup restore
                temp_rollback_point = RollbackPoint(
                    rollback_id="emergency_backup_restore",
                    timestamp=self.current_session_backup.timestamp,
                    git_commit=self.current_session_backup.git_commit,
                    git_branch=self.current_session_backup.git_branch or "unknown",
                    backup_id=self.current_session_backup.backup_id,
                    description=f"Emergency restore: {reason}",
                    files_snapshot={},
                    metadata={}
                )
                
                rollback_op = await self.rollback_manager.rollback_to_point(
                    temp_rollback_point.rollback_id,
                    RollbackType.FILE_RESTORE
                )
                
                if rollback_op.status.value in ['completed', 'verified']:
                    recovery_result['recovery_successful'] = True
                    recovery_result['method_used'] = 'backup_restore'
                    recovery_result['recovered_to'] = self.current_session_backup.backup_id
                    self.safety_stats['successful_recoveries'] += 1
                else:
                    recovery_result['errors'].extend(rollback_op.errors)
            
            # If all else fails, try git reset to session backup commit
            if (not recovery_result['recovery_successful'] and 
                self.current_session_backup and 
                self.current_session_backup.git_commit):
                
                logger.info("Attempting git reset to session backup commit")
                try:
                    import subprocess
                    result = subprocess.run([
                        'git', 'reset', '--hard', self.current_session_backup.git_commit
                    ], cwd=self.project_path, capture_output=True, text=True, check=True)
                    
                    recovery_result['recovery_successful'] = True
                    recovery_result['method_used'] = 'git_reset'
                    recovery_result['recovered_to'] = self.current_session_backup.git_commit
                    self.safety_stats['successful_recoveries'] += 1
                    
                except subprocess.CalledProcessError as e:
                    recovery_result['errors'].append(f"Git reset failed: {e}")
            
        except Exception as e:
            logger.error(f"Emergency recovery failed: {e}")
            recovery_result['errors'].append(f"Recovery exception: {str(e)}")
        
        # Notify recovery callbacks
        for callback in self.rollback_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback('emergency_recovery', recovery_result)
                else:
                    callback('emergency_recovery', recovery_result)
            except Exception as e:
                logger.error(f"Recovery callback failed: {e}")
        
        if recovery_result['recovery_successful']:
            logger.info("Emergency recovery completed successfully")
        else:
            logger.critical("Emergency recovery failed - manual intervention required")
        
        return recovery_result
    
    async def safety_health_check(self) -> Dict[str, Any]:
        """Perform comprehensive safety system health check.
        
        Returns:
            Health check results
        """
        health_status = {
            'overall_healthy': True,
            'components': {},
            'issues': [],
            'recommendations': []
        }
        
        # Check backup manager health
        backup_status = self.backup_manager.get_backup_status()
        backup_healthy = (
            backup_status['total_backups'] > 0 and
            backup_status['verified_backups'] > 0 and
            backup_status['latest_backup'] and
            backup_status['latest_backup']['verified']
        )
        health_status['components']['backup_manager'] = backup_healthy
        
        if not backup_healthy:
            health_status['issues'].append("Backup system issues detected")
            health_status['recommendations'].append("Create and verify backups")
        
        # Check rollback manager health
        rollback_status = self.rollback_manager.get_status()
        rollback_healthy = (
            rollback_status['rollback_points_count'] > 0 and
            rollback_status['recent_success_rate'] >= 0.8
        )
        health_status['components']['rollback_manager'] = rollback_healthy
        
        if not rollback_healthy:
            health_status['issues'].append("Rollback system issues detected")
            health_status['recommendations'].append("Create rollback points and verify functionality")
        
        # Check danger detector health
        danger_status = self.danger_detector.get_status()
        danger_healthy = danger_status['enabled_patterns'] > 0
        health_status['components']['danger_detector'] = danger_healthy
        
        if not danger_healthy:
            health_status['issues'].append("Danger detection system disabled or misconfigured")
            health_status['recommendations'].append("Enable danger detection patterns")
        
        # Overall health assessment
        health_status['overall_healthy'] = all(health_status['components'].values())
        
        # Check safety session state
        if self.safety_active and not self.current_session_backup:
            health_status['issues'].append("Safety session active but no session backup")
            health_status['recommendations'].append("Create session backup immediately")
            health_status['overall_healthy'] = False
        
        return health_status
    
    def add_danger_callback(self, callback: Callable):
        """Add callback for danger detection events."""
        self.danger_callbacks.append(callback)
    
    def add_backup_callback(self, callback: Callable):
        """Add callback for backup events."""
        self.backup_callbacks.append(callback)
    
    def add_rollback_callback(self, callback: Callable):
        """Add callback for rollback events."""
        self.rollback_callbacks.append(callback)
    
    def remove_callback(self, callback: Callable):
        """Remove a callback from all callback lists."""
        for callback_list in [self.danger_callbacks, self.backup_callbacks, self.rollback_callbacks]:
            if callback in callback_list:
                callback_list.remove(callback)
    
    def get_safety_status(self) -> Dict[str, Any]:
        """Get comprehensive safety system status.
        
        Returns:
            Complete safety status
        """
        return {
            'safety_active': self.safety_active,
            'session_info': {
                'start_time': self.safety_stats['session_start'].isoformat() 
                            if self.safety_stats['session_start'] else None,
                'duration': str(datetime.now() - self.safety_stats['session_start']) 
                          if self.safety_stats['session_start'] else None,
                'session_backup': self.current_session_backup.backup_id 
                                if self.current_session_backup else None,
                'current_rollback_point': self.current_rollback_point.rollback_id 
                                        if self.current_rollback_point else None
            },
            'statistics': self.safety_stats.copy(),
            'safety_violations_count': len(self.safety_violations),
            'recent_violations': self.safety_violations[-5:] if self.safety_violations else [],
            'component_status': {
                'backup_manager': self.backup_manager.get_backup_status(),
                'danger_detector': self.danger_detector.get_status(),
                'rollback_manager': self.rollback_manager.get_status()
            },
            'configuration': {
                'auto_backup_before_execution': self.auto_backup_before_execution,
                'auto_create_rollback_points': self.auto_create_rollback_points,
                'block_dangerous_operations': self.block_dangerous_operations,
                'safety_check_interval': self.safety_check_interval
            }
        }
    
    async def generate_safety_report(self) -> Dict[str, Any]:
        """Generate comprehensive safety report.
        
        Returns:
            Detailed safety report
        """
        health_check = await self.safety_health_check()
        
        return {
            'report_timestamp': datetime.now().isoformat(),
            'session_summary': {
                'active': self.safety_active,
                'duration': str(datetime.now() - self.safety_stats['session_start']) 
                          if self.safety_stats['session_start'] else None,
                'statistics': self.safety_stats.copy()
            },
            'health_check': health_check,
            'safety_violations': {
                'total': len(self.safety_violations),
                'recent': self.safety_violations[-10:],
                'by_danger_level': self._group_violations_by_level()
            },
            'component_reports': {
                'backups': {
                    'status': self.backup_manager.get_backup_status(),
                    'recent_backups': self.backup_manager.list_backups(10)
                },
                'rollbacks': {
                    'status': self.rollback_manager.get_status(),
                    'recent_points': self.rollback_manager.list_rollback_points(10),
                    'recent_operations': self.rollback_manager.list_rollback_operations(10)
                },
                'danger_detection': {
                    'status': self.danger_detector.get_status(),
                    'active_patterns': self.danger_detector.list_patterns()
                }
            },
            'recommendations': self._generate_safety_recommendations(health_check)
        }
    
    def _group_violations_by_level(self) -> Dict[str, int]:
        """Group safety violations by danger level."""
        groups = {}
        for violation in self.safety_violations:
            level = violation.get('danger_level', 'unknown')
            groups[level] = groups.get(level, 0) + 1
        return groups
    
    def _generate_safety_recommendations(self, health_check: Dict[str, Any]) -> List[str]:
        """Generate safety recommendations based on health check."""
        recommendations = []
        
        if not health_check['overall_healthy']:
            recommendations.extend(health_check['recommendations'])
        
        # Statistics-based recommendations
        stats = self.safety_stats
        
        if stats['dangers_detected'] > stats['operations_blocked']:
            recommendations.append("Many dangers detected but not blocked - review danger detection settings")
        
        if stats['emergency_rollbacks'] > 0 and stats['successful_recoveries'] < stats['emergency_rollbacks']:
            recommendations.append("Some emergency recoveries failed - verify backup and rollback systems")
        
        if stats['backups_created'] == 0:
            recommendations.append("No backups created this session - enable automatic backups")
        
        if stats['rollback_points_created'] == 0:
            recommendations.append("No rollback points created - enable automatic rollback points")
        
        return recommendations