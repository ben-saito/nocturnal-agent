"""Rollback management system for safe recovery from failures."""

import logging
import subprocess
import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum

from nocturnal_agent.safety.backup_manager import BackupManager, BackupInfo, BackupType


logger = logging.getLogger(__name__)


class RollbackType(Enum):
    """Types of rollback operations."""
    GIT_RESET = "git_reset"           # Git reset --hard
    FILE_RESTORE = "file_restore"     # Restore specific files
    FULL_RESTORE = "full_restore"     # Complete project restore
    SELECTIVE = "selective"           # Selective rollback
    INCREMENTAL = "incremental"       # Step-by-step rollback


class RollbackStatus(Enum):
    """Status of rollback operations."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    VERIFIED = "verified"
    CANCELLED = "cancelled"


@dataclass
class RollbackPoint:
    """Information about a rollback point."""
    rollback_id: str
    timestamp: datetime
    git_commit: Optional[str]
    git_branch: str
    backup_id: Optional[str]
    description: str
    files_snapshot: Dict[str, str]  # file_path -> hash
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RollbackOperation:
    """Information about a rollback operation."""
    operation_id: str
    rollback_type: RollbackType
    target_point: RollbackPoint
    status: RollbackStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    files_affected: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    verification_results: Dict[str, bool] = field(default_factory=dict)


class RollbackManager:
    """Manages rollback operations for safe recovery."""
    
    def __init__(self, project_path: str, backup_manager: BackupManager, config: Dict[str, Any]):
        """Initialize rollback manager.
        
        Args:
            project_path: Path to the project directory
            backup_manager: Backup manager instance
            config: Rollback configuration
        """
        self.project_path = Path(project_path)
        self.backup_manager = backup_manager
        self.config = config
        
        # Rollback settings
        self.auto_verify_rollbacks = config.get('auto_verify_rollbacks', True)
        self.max_rollback_history = config.get('max_rollback_history', 100)
        self.require_confirmation = config.get('require_confirmation', True)
        self.create_rollback_backup = config.get('create_rollback_backup', True)
        
        # Storage
        self.rollback_dir = self.project_path / ".nocturnal" / "rollbacks"
        self.rollback_dir.mkdir(parents=True, exist_ok=True)
        
        self.rollback_points_file = self.rollback_dir / "rollback_points.json"
        self.rollback_history_file = self.rollback_dir / "rollback_history.json"
        
        # State
        self.rollback_points: List[RollbackPoint] = []
        self.rollback_history: List[RollbackOperation] = []
        
        # Load existing data
        self._load_rollback_data()
    
    async def create_rollback_point(self, description: str = "") -> RollbackPoint:
        """Create a rollback point for current state.
        
        Args:
            description: Description of the rollback point
            
        Returns:
            Created rollback point
        """
        rollback_id = f"rp_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        logger.info(f"Creating rollback point: {rollback_id}")
        
        try:
            # Get current git state
            git_commit, git_branch = await self._get_git_state()
            
            if not git_commit:
                logger.warning("No git commit found - rollback point may be incomplete")
            
            # Create backup for this rollback point
            backup_id = None
            if self.create_rollback_backup:
                backup_info = await self.backup_manager.create_backup(
                    backup_type=BackupType.FULL,
                    backup_id=f"rb_{rollback_id}",
                    description=f"Rollback point backup: {description}"
                )
                if backup_info:
                    backup_id = backup_info.backup_id
            
            # Snapshot current file states
            files_snapshot = await self._create_files_snapshot()
            
            # Create rollback point
            rollback_point = RollbackPoint(
                rollback_id=rollback_id,
                timestamp=datetime.now(),
                git_commit=git_commit,
                git_branch=git_branch or "unknown",
                backup_id=backup_id,
                description=description or f"Rollback point created at {datetime.now()}",
                files_snapshot=files_snapshot,
                metadata={
                    'created_by': 'nocturnal_agent',
                    'project_path': str(self.project_path)
                }
            )
            
            # Add to rollback points
            self.rollback_points.append(rollback_point)
            
            # Clean up old rollback points
            await self._cleanup_old_rollback_points()
            
            # Save data
            await self._save_rollback_data()
            
            logger.info(f"Rollback point created successfully: {rollback_id}")
            return rollback_point
            
        except Exception as e:
            logger.error(f"Failed to create rollback point: {e}")
            raise
    
    async def rollback_to_point(
        self, 
        rollback_id: str, 
        rollback_type: RollbackType = RollbackType.GIT_RESET,
        verify_after: bool = True
    ) -> RollbackOperation:
        """Rollback to a specific rollback point.
        
        Args:
            rollback_id: ID of rollback point
            rollback_type: Type of rollback to perform
            verify_after: Whether to verify rollback after completion
            
        Returns:
            Rollback operation result
        """
        # Find rollback point
        rollback_point = self._find_rollback_point(rollback_id)
        if not rollback_point:
            raise ValueError(f"Rollback point not found: {rollback_id}")
        
        operation_id = f"rb_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        logger.info(f"Starting rollback operation {operation_id} to point {rollback_id}")
        
        # Create rollback operation
        operation = RollbackOperation(
            operation_id=operation_id,
            rollback_type=rollback_type,
            target_point=rollback_point,
            status=RollbackStatus.IN_PROGRESS,
            started_at=datetime.now()
        )
        
        try:
            # Create safety backup before rollback
            if self.create_rollback_backup:
                await self.backup_manager.create_backup(
                    backup_type=BackupType.FULL,
                    backup_id=f"pre_rollback_{operation_id}",
                    description=f"Pre-rollback safety backup for operation {operation_id}"
                )
            
            # Perform rollback based on type
            if rollback_type == RollbackType.GIT_RESET:
                await self._perform_git_reset_rollback(operation, rollback_point)
            elif rollback_type == RollbackType.FILE_RESTORE:
                await self._perform_file_restore_rollback(operation, rollback_point)
            elif rollback_type == RollbackType.FULL_RESTORE:
                await self._perform_full_restore_rollback(operation, rollback_point)
            elif rollback_type == RollbackType.SELECTIVE:
                await self._perform_selective_rollback(operation, rollback_point)
            elif rollback_type == RollbackType.INCREMENTAL:
                await self._perform_incremental_rollback(operation, rollback_point)
            else:
                raise ValueError(f"Unknown rollback type: {rollback_type}")
            
            # Mark as completed
            operation.status = RollbackStatus.COMPLETED
            operation.completed_at = datetime.now()
            
            # Verify rollback if requested
            if verify_after and self.auto_verify_rollbacks:
                verification_success = await self._verify_rollback(operation, rollback_point)
                if verification_success:
                    operation.status = RollbackStatus.VERIFIED
                else:
                    operation.status = RollbackStatus.FAILED
                    operation.errors.append("Rollback verification failed")
            
            logger.info(f"Rollback operation completed: {operation_id}")
            
        except Exception as e:
            operation.status = RollbackStatus.FAILED
            operation.completed_at = datetime.now()
            operation.errors.append(f"Rollback failed: {str(e)}")
            logger.error(f"Rollback operation failed: {operation_id} - {e}")
        
        # Save operation to history
        self.rollback_history.append(operation)
        await self._save_rollback_data()
        
        return operation
    
    async def _perform_git_reset_rollback(self, operation: RollbackOperation, target: RollbackPoint):
        """Perform git reset --hard rollback.
        
        Args:
            operation: Rollback operation
            target: Target rollback point
        """
        if not target.git_commit:
            raise ValueError("No git commit available for rollback point")
        
        logger.info(f"Performing git reset to commit: {target.git_commit}")
        
        # Reset to target commit
        result = subprocess.run([
            'git', 'reset', '--hard', target.git_commit
        ], cwd=self.project_path, capture_output=True, text=True)
        
        if result.returncode != 0:
            raise RuntimeError(f"Git reset failed: {result.stderr}")
        
        # Clean untracked files
        clean_result = subprocess.run([
            'git', 'clean', '-fd'
        ], cwd=self.project_path, capture_output=True, text=True)
        
        if clean_result.returncode != 0:
            logger.warning(f"Git clean had issues: {clean_result.stderr}")
        
        operation.files_affected = self._get_git_changed_files(target.git_commit)
        
    async def _perform_file_restore_rollback(self, operation: RollbackOperation, target: RollbackPoint):
        """Perform file-based rollback using backup.
        
        Args:
            operation: Rollback operation
            target: Target rollback point
        """
        if not target.backup_id:
            raise ValueError("No backup available for rollback point")
        
        logger.info(f"Restoring files from backup: {target.backup_id}")
        
        # Find backup
        backup_info = None
        for backup in self.backup_manager.backup_history:
            if backup.backup_id == target.backup_id:
                backup_info = backup
                break
        
        if not backup_info:
            raise ValueError(f"Backup not found: {target.backup_id}")
        
        # Restore files from backup
        backup_dir = Path(backup_info.backup_path)
        if not backup_dir.exists():
            raise FileNotFoundError(f"Backup directory not found: {backup_dir}")
        
        restored_files = []
        
        # Restore all files from backup
        for backup_file in backup_dir.rglob('*'):
            if not backup_file.is_file():
                continue
            
            rel_path = backup_file.relative_to(backup_dir)
            target_file = self.project_path / rel_path
            
            try:
                target_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(backup_file, target_file)
                restored_files.append(str(rel_path))
            except (OSError, PermissionError) as e:
                operation.errors.append(f"Failed to restore {rel_path}: {e}")
        
        operation.files_affected = restored_files
        
    async def _perform_full_restore_rollback(self, operation: RollbackOperation, target: RollbackPoint):
        """Perform full project restore.
        
        Args:
            operation: Rollback operation
            target: Target rollback point
        """
        # Combine git reset and file restore
        if target.git_commit:
            await self._perform_git_reset_rollback(operation, target)
        
        if target.backup_id:
            await self._perform_file_restore_rollback(operation, target)
    
    async def _perform_selective_rollback(self, operation: RollbackOperation, target: RollbackPoint):
        """Perform selective rollback of specific files.
        
        Args:
            operation: Rollback operation
            target: Target rollback point
        """
        # This would be implemented based on specific file selection criteria
        # For now, delegate to file restore
        await self._perform_file_restore_rollback(operation, target)
    
    async def _perform_incremental_rollback(self, operation: RollbackOperation, target: RollbackPoint):
        """Perform incremental rollback step by step.
        
        Args:
            operation: Rollback operation
            target: Target rollback point
        """
        # This would implement step-by-step rollback with verification at each step
        # For now, delegate to git reset
        await self._perform_git_reset_rollback(operation, target)
    
    async def _verify_rollback(self, operation: RollbackOperation, target: RollbackPoint) -> bool:
        """Verify that rollback was successful.
        
        Args:
            operation: Rollback operation
            target: Target rollback point
            
        Returns:
            True if verification successful
        """
        verification_results = {}
        
        # Verify git state if available
        if target.git_commit:
            current_commit, _ = await self._get_git_state()
            git_match = current_commit == target.git_commit
            verification_results['git_commit'] = git_match
            
            if not git_match:
                operation.errors.append(f"Git commit mismatch: expected {target.git_commit}, got {current_commit}")
        
        # Verify file hashes
        current_snapshot = await self._create_files_snapshot()
        files_verified = 0
        files_total = len(target.files_snapshot)
        
        for file_path, expected_hash in target.files_snapshot.items():
            current_hash = current_snapshot.get(file_path)
            file_match = current_hash == expected_hash
            verification_results[f'file_{file_path}'] = file_match
            
            if file_match:
                files_verified += 1
            else:
                operation.errors.append(f"File hash mismatch: {file_path}")
        
        # Calculate overall verification success
        file_verification_rate = files_verified / files_total if files_total > 0 else 1.0
        git_verification = verification_results.get('git_commit', True)
        
        # Require high verification rate for success
        verification_success = git_verification and file_verification_rate >= 0.95
        
        verification_results['overall_success'] = verification_success
        verification_results['file_verification_rate'] = file_verification_rate
        
        operation.verification_results = verification_results
        
        logger.info(f"Rollback verification: {verification_success} (files: {file_verification_rate:.2%})")
        return verification_success
    
    async def _get_git_state(self) -> Tuple[Optional[str], Optional[str]]:
        """Get current git commit and branch.
        
        Returns:
            Tuple of (commit_hash, branch_name)
        """
        try:
            # Get current commit
            commit_result = subprocess.run([
                'git', 'rev-parse', 'HEAD'
            ], cwd=self.project_path, capture_output=True, text=True, check=True)
            commit_hash = commit_result.stdout.strip()
            
            # Get current branch
            branch_result = subprocess.run([
                'git', 'rev-parse', '--abbrev-ref', 'HEAD'
            ], cwd=self.project_path, capture_output=True, text=True, check=True)
            branch_name = branch_result.stdout.strip()
            
            return commit_hash, branch_name
            
        except subprocess.CalledProcessError:
            return None, None
    
    def _get_git_changed_files(self, commit_hash: str) -> List[str]:
        """Get list of files changed by git reset.
        
        Args:
            commit_hash: Target commit hash
            
        Returns:
            List of changed file paths
        """
        try:
            result = subprocess.run([
                'git', 'diff', '--name-only', 'HEAD', commit_hash
            ], cwd=self.project_path, capture_output=True, text=True, check=True)
            
            return [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
            
        except subprocess.CalledProcessError:
            return []
    
    async def _create_files_snapshot(self) -> Dict[str, str]:
        """Create a snapshot of current file hashes.
        
        Returns:
            Dictionary mapping file paths to hashes
        """
        import hashlib
        
        snapshot = {}
        
        for file_path in self.project_path.rglob('*'):
            if not file_path.is_file():
                continue
            
            # Skip certain files/directories
            if any(part.startswith('.') for part in file_path.parts):
                if not file_path.name in ['.gitignore', '.env.example']:
                    continue
            
            try:
                rel_path = str(file_path.relative_to(self.project_path))
                
                hasher = hashlib.sha256()
                with open(file_path, 'rb') as f:
                    for chunk in iter(lambda: f.read(8192), b""):
                        hasher.update(chunk)
                
                snapshot[rel_path] = hasher.hexdigest()
                
            except (OSError, PermissionError):
                continue
        
        return snapshot
    
    def _find_rollback_point(self, rollback_id: str) -> Optional[RollbackPoint]:
        """Find a rollback point by ID.
        
        Args:
            rollback_id: ID to search for
            
        Returns:
            Rollback point or None if not found
        """
        for point in self.rollback_points:
            if point.rollback_id == rollback_id:
                return point
        return None
    
    async def _cleanup_old_rollback_points(self):
        """Clean up old rollback points."""
        if len(self.rollback_points) <= self.max_rollback_history:
            return
        
        # Sort by timestamp and keep most recent
        sorted_points = sorted(self.rollback_points, key=lambda p: p.timestamp, reverse=True)
        points_to_remove = sorted_points[self.max_rollback_history:]
        
        for point in points_to_remove:
            # Remove associated backup if it exists
            if point.backup_id:
                # Note: BackupManager handles its own cleanup
                pass
            
            self.rollback_points.remove(point)
            logger.info(f"Removed old rollback point: {point.rollback_id}")
    
    async def _save_rollback_data(self):
        """Save rollback data to disk."""
        try:
            # Save rollback points
            points_data = [
                {
                    'rollback_id': p.rollback_id,
                    'timestamp': p.timestamp.isoformat(),
                    'git_commit': p.git_commit,
                    'git_branch': p.git_branch,
                    'backup_id': p.backup_id,
                    'description': p.description,
                    'files_snapshot': p.files_snapshot,
                    'metadata': p.metadata
                }
                for p in self.rollback_points
            ]
            
            with open(self.rollback_points_file, 'w', encoding='utf-8') as f:
                json.dump(points_data, f, indent=2, ensure_ascii=False)
            
            # Save rollback history
            history_data = [
                {
                    'operation_id': op.operation_id,
                    'rollback_type': op.rollback_type.value,
                    'target_point_id': op.target_point.rollback_id,
                    'status': op.status.value,
                    'started_at': op.started_at.isoformat(),
                    'completed_at': op.completed_at.isoformat() if op.completed_at else None,
                    'files_affected': op.files_affected,
                    'errors': op.errors,
                    'verification_results': op.verification_results
                }
                for op in self.rollback_history
            ]
            
            with open(self.rollback_history_file, 'w', encoding='utf-8') as f:
                json.dump(history_data, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            logger.error(f"Failed to save rollback data: {e}")
    
    def _load_rollback_data(self):
        """Load rollback data from disk."""
        try:
            # Load rollback points
            if self.rollback_points_file.exists():
                with open(self.rollback_points_file, 'r', encoding='utf-8') as f:
                    points_data = json.load(f)
                
                for point_data in points_data:
                    point = RollbackPoint(
                        rollback_id=point_data['rollback_id'],
                        timestamp=datetime.fromisoformat(point_data['timestamp']),
                        git_commit=point_data.get('git_commit'),
                        git_branch=point_data.get('git_branch', 'unknown'),
                        backup_id=point_data.get('backup_id'),
                        description=point_data.get('description', ''),
                        files_snapshot=point_data.get('files_snapshot', {}),
                        metadata=point_data.get('metadata', {})
                    )
                    self.rollback_points.append(point)
            
            # Load rollback history (simplified - would need full reconstruction)
            if self.rollback_history_file.exists():
                with open(self.rollback_history_file, 'r', encoding='utf-8') as f:
                    history_data = json.load(f)
                
                logger.info(f"Loaded {len(history_data)} rollback operations from history")
            
            logger.info(f"Loaded {len(self.rollback_points)} rollback points")
            
        except Exception as e:
            logger.error(f"Failed to load rollback data: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get rollback manager status.
        
        Returns:
            Status information
        """
        recent_operations = [op for op in self.rollback_history if 
                           (datetime.now() - op.started_at).days < 7]
        
        successful_operations = [op for op in recent_operations if 
                               op.status in [RollbackStatus.COMPLETED, RollbackStatus.VERIFIED]]
        
        return {
            'rollback_points_count': len(self.rollback_points),
            'rollback_history_count': len(self.rollback_history),
            'recent_operations': len(recent_operations),
            'recent_success_rate': len(successful_operations) / len(recent_operations) if recent_operations else 0,
            'latest_rollback_point': {
                'rollback_id': self.rollback_points[-1].rollback_id if self.rollback_points else None,
                'timestamp': self.rollback_points[-1].timestamp.isoformat() if self.rollback_points else None,
                'description': self.rollback_points[-1].description if self.rollback_points else None
            } if self.rollback_points else None,
            'configuration': {
                'auto_verify_rollbacks': self.auto_verify_rollbacks,
                'max_rollback_history': self.max_rollback_history,
                'require_confirmation': self.require_confirmation,
                'create_rollback_backup': self.create_rollback_backup
            }
        }
    
    def list_rollback_points(self, limit: int = 20) -> List[Dict[str, Any]]:
        """List recent rollback points.
        
        Args:
            limit: Maximum number of points to return
            
        Returns:
            List of rollback point information
        """
        recent_points = sorted(self.rollback_points, key=lambda p: p.timestamp, reverse=True)[:limit]
        
        return [
            {
                'rollback_id': p.rollback_id,
                'timestamp': p.timestamp.isoformat(),
                'git_commit': p.git_commit[:8] if p.git_commit else None,
                'git_branch': p.git_branch,
                'backup_id': p.backup_id,
                'description': p.description,
                'files_count': len(p.files_snapshot)
            }
            for p in recent_points
        ]
    
    def list_rollback_operations(self, limit: int = 20) -> List[Dict[str, Any]]:
        """List recent rollback operations.
        
        Args:
            limit: Maximum number of operations to return
            
        Returns:
            List of rollback operation information
        """
        recent_operations = sorted(self.rollback_history, key=lambda op: op.started_at, reverse=True)[:limit]
        
        return [
            {
                'operation_id': op.operation_id,
                'rollback_type': op.rollback_type.value,
                'target_point_id': op.target_point.rollback_id,
                'status': op.status.value,
                'started_at': op.started_at.isoformat(),
                'completed_at': op.completed_at.isoformat() if op.completed_at else None,
                'duration': str(op.completed_at - op.started_at) if op.completed_at else None,
                'files_affected_count': len(op.files_affected),
                'errors_count': len(op.errors),
                'verification_success': op.verification_results.get('overall_success', False)
            }
            for op in recent_operations
        ]