"""Automatic backup management for safe night execution."""

import logging
import subprocess
import shutil
import json
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum


logger = logging.getLogger(__name__)


class BackupType(Enum):
    """Types of backups."""
    FULL = "full"          # Complete project backup
    GIT = "git"           # Git state backup only
    INCREMENTAL = "incremental"  # Changed files only
    CRITICAL = "critical"  # Critical files only


@dataclass
class BackupInfo:
    """Information about a backup."""
    backup_id: str
    backup_type: BackupType
    timestamp: datetime
    project_path: str
    backup_path: str
    file_count: int
    size_bytes: int
    git_commit: Optional[str] = None
    git_branch: Optional[str] = None
    integrity_hash: Optional[str] = None
    verification_status: str = "pending"  # pending, verified, failed
    metadata: Dict[str, Any] = field(default_factory=dict)


class BackupManager:
    """Manages automatic backups for safe autonomous operation."""
    
    def __init__(self, project_path: str, config: Dict[str, Any]):
        """Initialize backup manager.
        
        Args:
            project_path: Path to the project directory
            config: Backup configuration
        """
        self.project_path = Path(project_path)
        self.config = config
        
        # Backup settings
        self.backup_root = Path(config.get('backup_root', self.project_path.parent / ".nocturnal_backups"))
        self.max_backups = config.get('max_backups', 50)
        self.retention_days = config.get('retention_days', 30)
        self.auto_verify = config.get('auto_verify', True)
        self.compress_backups = config.get('compress_backups', True)
        
        # Critical files/directories to always backup
        self.critical_paths = config.get('critical_paths', [
            'src/',
            'tests/',
            'requirements.txt',
            'package.json',
            'Cargo.toml',
            'pyproject.toml',
            '.gitignore',
            'README.md'
        ])
        
        # Files/directories to exclude from backup
        self.exclude_paths = config.get('exclude_paths', [
            'node_modules/',
            '__pycache__/',
            '.git/',
            '.venv/',
            'venv/',
            'target/',
            'build/',
            'dist/',
            '.nocturnal/',
            '.DS_Store',
            '*.pyc',
            '*.log'
        ])
        
        # Initialize backup storage
        self.backup_root.mkdir(parents=True, exist_ok=True)
        self.backups_index_file = self.backup_root / "backups_index.json"
        
        # Backup history
        self.backup_history: List[BackupInfo] = []
        self._load_backup_history()
    
    async def create_pre_execution_backup(self) -> BackupInfo:
        """Create a backup before night execution starts.
        
        Returns:
            Backup information
        """
        logger.info("Creating pre-execution backup")
        
        backup_id = f"pre_exec_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Create full backup including git state
        backup_info = await self.create_backup(
            backup_type=BackupType.FULL,
            backup_id=backup_id,
            description="Pre-execution safety backup"
        )
        
        if backup_info and backup_info.verification_status == "verified":
            logger.info(f"Pre-execution backup created successfully: {backup_info.backup_id}")
        else:
            logger.error("Failed to create or verify pre-execution backup")
            raise RuntimeError("Pre-execution backup failed")
        
        return backup_info
    
    async def create_backup(
        self, 
        backup_type: BackupType = BackupType.FULL,
        backup_id: Optional[str] = None,
        description: str = ""
    ) -> Optional[BackupInfo]:
        """Create a backup of the project.
        
        Args:
            backup_type: Type of backup to create
            backup_id: Optional custom backup ID
            description: Description of the backup
            
        Returns:
            Backup information or None if failed
        """
        if not backup_id:
            backup_id = f"{backup_type.value}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        logger.info(f"Creating {backup_type.value} backup: {backup_id}")
        
        try:
            # Create backup directory
            backup_dir = self.backup_root / backup_id
            backup_dir.mkdir(parents=True, exist_ok=True)
            
            # Get git state
            git_commit, git_branch = await self._get_git_state()
            
            # Create backup based on type
            if backup_type == BackupType.FULL:
                file_count, size_bytes = await self._create_full_backup(backup_dir)
            elif backup_type == BackupType.GIT:
                file_count, size_bytes = await self._create_git_backup(backup_dir)
            elif backup_type == BackupType.INCREMENTAL:
                file_count, size_bytes = await self._create_incremental_backup(backup_dir)
            elif backup_type == BackupType.CRITICAL:
                file_count, size_bytes = await self._create_critical_backup(backup_dir)
            else:
                raise ValueError(f"Unknown backup type: {backup_type}")
            
            # Calculate integrity hash
            integrity_hash = await self._calculate_backup_hash(backup_dir)
            
            # Create backup info
            backup_info = BackupInfo(
                backup_id=backup_id,
                backup_type=backup_type,
                timestamp=datetime.now(),
                project_path=str(self.project_path),
                backup_path=str(backup_dir),
                file_count=file_count,
                size_bytes=size_bytes,
                git_commit=git_commit,
                git_branch=git_branch,
                integrity_hash=integrity_hash,
                verification_status="pending",
                metadata={
                    'description': description,
                    'config_snapshot': self.config.copy()
                }
            )
            
            # Verify backup if enabled
            if self.auto_verify:
                verification_result = await self.verify_backup(backup_info)
                backup_info.verification_status = "verified" if verification_result else "failed"
            
            # Add to history and save
            self.backup_history.append(backup_info)
            await self._save_backup_history()
            
            # Clean up old backups
            await self._cleanup_old_backups()
            
            logger.info(f"Backup created: {backup_id} ({file_count} files, {size_bytes} bytes)")
            return backup_info
            
        except Exception as e:
            logger.error(f"Failed to create backup {backup_id}: {e}")
            return None
    
    async def _create_full_backup(self, backup_dir: Path) -> Tuple[int, int]:
        """Create a full project backup.
        
        Args:
            backup_dir: Directory to store backup
            
        Returns:
            Tuple of (file_count, total_size_bytes)
        """
        file_count = 0
        total_size = 0
        
        for item in self.project_path.rglob('*'):
            # Skip if item should be excluded
            if self._should_exclude_path(item):
                continue
            
            # Calculate relative path
            rel_path = item.relative_to(self.project_path)
            backup_item = backup_dir / rel_path
            
            try:
                if item.is_file():
                    # Copy file
                    backup_item.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item, backup_item)
                    file_count += 1
                    total_size += item.stat().st_size
                elif item.is_dir():
                    # Create directory
                    backup_item.mkdir(parents=True, exist_ok=True)
                    
            except (OSError, PermissionError) as e:
                logger.warning(f"Failed to backup {item}: {e}")
        
        return file_count, total_size
    
    async def _create_git_backup(self, backup_dir: Path) -> Tuple[int, int]:
        """Create a git state backup.
        
        Args:
            backup_dir: Directory to store backup
            
        Returns:
            Tuple of (file_count, total_size_bytes)
        """
        try:
            # Create git bundle (complete repository backup)
            bundle_file = backup_dir / "repository.bundle"
            
            result = subprocess.run([
                'git', 'bundle', 'create', str(bundle_file), '--all'
            ], cwd=self.project_path, capture_output=True, text=True, check=True)
            
            # Also backup .git/config and other important git files
            git_dir = self.project_path / '.git'
            backup_git_dir = backup_dir / '.git'
            
            important_git_files = ['config', 'HEAD', 'refs/', 'hooks/']
            
            file_count = 1  # bundle file
            total_size = bundle_file.stat().st_size
            
            for git_file in important_git_files:
                src_path = git_dir / git_file
                if src_path.exists():
                    dst_path = backup_git_dir / git_file
                    
                    if src_path.is_file():
                        dst_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(src_path, dst_path)
                        file_count += 1
                        total_size += src_path.stat().st_size
                    elif src_path.is_dir():
                        shutil.copytree(src_path, dst_path, dirs_exist_ok=True)
                        for f in dst_path.rglob('*'):
                            if f.is_file():
                                file_count += 1
                                total_size += f.stat().st_size
            
            return file_count, total_size
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Git backup failed: {e}")
            raise
    
    async def _create_incremental_backup(self, backup_dir: Path) -> Tuple[int, int]:
        """Create an incremental backup (changed files only).
        
        Args:
            backup_dir: Directory to store backup
            
        Returns:
            Tuple of (file_count, total_size_bytes)
        """
        # Find files changed since last backup
        last_backup = self._get_latest_backup()
        if not last_backup:
            # No previous backup, create full backup
            return await self._create_full_backup(backup_dir)
        
        # Get files changed since last backup
        changed_files = await self._get_changed_files_since(last_backup.timestamp)
        
        file_count = 0
        total_size = 0
        
        for file_path in changed_files:
            if not file_path.exists() or self._should_exclude_path(file_path):
                continue
            
            rel_path = file_path.relative_to(self.project_path)
            backup_file = backup_dir / rel_path
            
            try:
                backup_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file_path, backup_file)
                file_count += 1
                total_size += file_path.stat().st_size
            except (OSError, PermissionError) as e:
                logger.warning(f"Failed to backup {file_path}: {e}")
        
        return file_count, total_size
    
    async def _create_critical_backup(self, backup_dir: Path) -> Tuple[int, int]:
        """Create a backup of critical files only.
        
        Args:
            backup_dir: Directory to store backup
            
        Returns:
            Tuple of (file_count, total_size_bytes)
        """
        file_count = 0
        total_size = 0
        
        for critical_path in self.critical_paths:
            src_path = self.project_path / critical_path
            
            if not src_path.exists():
                continue
            
            dst_path = backup_dir / critical_path
            
            try:
                if src_path.is_file():
                    dst_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src_path, dst_path)
                    file_count += 1
                    total_size += src_path.stat().st_size
                elif src_path.is_dir():
                    for item in src_path.rglob('*'):
                        if self._should_exclude_path(item) or not item.is_file():
                            continue
                        
                        rel_item_path = item.relative_to(self.project_path)
                        backup_item = backup_dir / rel_item_path
                        backup_item.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(item, backup_item)
                        file_count += 1
                        total_size += item.stat().st_size
                        
            except (OSError, PermissionError) as e:
                logger.warning(f"Failed to backup critical path {src_path}: {e}")
        
        return file_count, total_size
    
    def _should_exclude_path(self, path: Path) -> bool:
        """Check if a path should be excluded from backup.
        
        Args:
            path: Path to check
            
        Returns:
            True if path should be excluded
        """
        try:
            rel_path = path.relative_to(self.project_path)
            rel_path_str = str(rel_path)
            
            for exclude_pattern in self.exclude_paths:
                if exclude_pattern.endswith('/'):
                    # Directory pattern
                    if rel_path_str.startswith(exclude_pattern[:-1]):
                        return True
                elif '*' in exclude_pattern:
                    # Wildcard pattern
                    import fnmatch
                    if fnmatch.fnmatch(rel_path_str, exclude_pattern):
                        return True
                else:
                    # Exact match
                    if rel_path_str == exclude_pattern:
                        return True
            
            return False
            
        except ValueError:
            # Path is not relative to project path
            return True
    
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
            logger.warning("Failed to get git state - not a git repository?")
            return None, None
    
    async def _calculate_backup_hash(self, backup_dir: Path) -> str:
        """Calculate integrity hash for a backup.
        
        Args:
            backup_dir: Backup directory
            
        Returns:
            SHA256 hash of backup contents
        """
        hasher = hashlib.sha256()
        
        # Sort files for consistent hashing
        backup_files = sorted(backup_dir.rglob('*'))
        
        for file_path in backup_files:
            if not file_path.is_file():
                continue
            
            # Add file path and content to hash
            rel_path = file_path.relative_to(backup_dir)
            hasher.update(str(rel_path).encode('utf-8'))
            
            try:
                with open(file_path, 'rb') as f:
                    for chunk in iter(lambda: f.read(8192), b""):
                        hasher.update(chunk)
            except (OSError, PermissionError) as e:
                logger.warning(f"Failed to hash file {file_path}: {e}")
        
        return hasher.hexdigest()
    
    async def verify_backup(self, backup_info: BackupInfo) -> bool:
        """Verify integrity of a backup.
        
        Args:
            backup_info: Backup to verify
            
        Returns:
            True if backup is valid
        """
        logger.info(f"Verifying backup: {backup_info.backup_id}")
        
        try:
            backup_dir = Path(backup_info.backup_path)
            
            if not backup_dir.exists():
                logger.error(f"Backup directory not found: {backup_dir}")
                return False
            
            # Recalculate hash
            current_hash = await self._calculate_backup_hash(backup_dir)
            
            if current_hash != backup_info.integrity_hash:
                logger.error(f"Backup integrity check failed: {backup_info.backup_id}")
                return False
            
            # Additional checks based on backup type
            if backup_info.backup_type == BackupType.GIT:
                # Verify git bundle
                bundle_file = backup_dir / "repository.bundle"
                if not bundle_file.exists():
                    logger.error("Git bundle file missing")
                    return False
                
                # Test bundle validity
                try:
                    subprocess.run([
                        'git', 'bundle', 'verify', str(bundle_file)
                    ], capture_output=True, text=True, check=True)
                except subprocess.CalledProcessError:
                    logger.error("Git bundle verification failed")
                    return False
            
            logger.info(f"Backup verification successful: {backup_info.backup_id}")
            return True
            
        except Exception as e:
            logger.error(f"Backup verification failed: {e}")
            return False
    
    def _get_latest_backup(self, backup_type: Optional[BackupType] = None) -> Optional[BackupInfo]:
        """Get the most recent backup.
        
        Args:
            backup_type: Optional filter by backup type
            
        Returns:
            Latest backup info or None
        """
        filtered_backups = self.backup_history
        
        if backup_type:
            filtered_backups = [b for b in filtered_backups if b.backup_type == backup_type]
        
        if not filtered_backups:
            return None
        
        return max(filtered_backups, key=lambda b: b.timestamp)
    
    async def _get_changed_files_since(self, since_time: datetime) -> List[Path]:
        """Get files changed since a specific time.
        
        Args:
            since_time: Time threshold
            
        Returns:
            List of changed file paths
        """
        changed_files = []
        
        for item in self.project_path.rglob('*'):
            if not item.is_file() or self._should_exclude_path(item):
                continue
            
            try:
                # Check file modification time
                mtime = datetime.fromtimestamp(item.stat().st_mtime)
                if mtime > since_time:
                    changed_files.append(item)
            except (OSError, PermissionError):
                continue
        
        return changed_files
    
    async def _cleanup_old_backups(self):
        """Clean up old backups based on retention policy."""
        if len(self.backup_history) <= self.max_backups:
            return
        
        # Sort backups by timestamp (oldest first)
        sorted_backups = sorted(self.backup_history, key=lambda b: b.timestamp)
        
        # Keep most recent backups
        backups_to_remove = sorted_backups[:-self.max_backups]
        
        for backup_info in backups_to_remove:
            try:
                backup_dir = Path(backup_info.backup_path)
                if backup_dir.exists():
                    shutil.rmtree(backup_dir)
                    logger.info(f"Removed old backup: {backup_info.backup_id}")
                
                self.backup_history.remove(backup_info)
                
            except Exception as e:
                logger.error(f"Failed to remove old backup {backup_info.backup_id}: {e}")
        
        # Also remove backups older than retention period
        cutoff_date = datetime.now() - timedelta(days=self.retention_days)
        old_backups = [b for b in self.backup_history if b.timestamp < cutoff_date]
        
        for backup_info in old_backups:
            try:
                backup_dir = Path(backup_info.backup_path)
                if backup_dir.exists():
                    shutil.rmtree(backup_dir)
                    logger.info(f"Removed expired backup: {backup_info.backup_id}")
                
                self.backup_history.remove(backup_info)
                
            except Exception as e:
                logger.error(f"Failed to remove expired backup {backup_info.backup_id}: {e}")
        
        # Save updated history
        await self._save_backup_history()
    
    async def _save_backup_history(self):
        """Save backup history to disk."""
        try:
            history_data = [
                {
                    'backup_id': b.backup_id,
                    'backup_type': b.backup_type.value,
                    'timestamp': b.timestamp.isoformat(),
                    'project_path': b.project_path,
                    'backup_path': b.backup_path,
                    'file_count': b.file_count,
                    'size_bytes': b.size_bytes,
                    'git_commit': b.git_commit,
                    'git_branch': b.git_branch,
                    'integrity_hash': b.integrity_hash,
                    'verification_status': b.verification_status,
                    'metadata': b.metadata
                }
                for b in self.backup_history
            ]
            
            with open(self.backups_index_file, 'w', encoding='utf-8') as f:
                json.dump(history_data, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            logger.error(f"Failed to save backup history: {e}")
    
    def _load_backup_history(self):
        """Load backup history from disk."""
        try:
            if not self.backups_index_file.exists():
                return
            
            with open(self.backups_index_file, 'r', encoding='utf-8') as f:
                history_data = json.load(f)
            
            self.backup_history = []
            for item in history_data:
                backup_info = BackupInfo(
                    backup_id=item['backup_id'],
                    backup_type=BackupType(item['backup_type']),
                    timestamp=datetime.fromisoformat(item['timestamp']),
                    project_path=item['project_path'],
                    backup_path=item['backup_path'],
                    file_count=item['file_count'],
                    size_bytes=item['size_bytes'],
                    git_commit=item.get('git_commit'),
                    git_branch=item.get('git_branch'),
                    integrity_hash=item.get('integrity_hash'),
                    verification_status=item.get('verification_status', 'pending'),
                    metadata=item.get('metadata', {})
                )
                self.backup_history.append(backup_info)
            
            logger.info(f"Loaded {len(self.backup_history)} backup records")
            
        except Exception as e:
            logger.error(f"Failed to load backup history: {e}")
            self.backup_history = []
    
    def get_backup_status(self) -> Dict[str, Any]:
        """Get current backup system status.
        
        Returns:
            Backup status information
        """
        latest_backup = self._get_latest_backup()
        
        total_size = sum(b.size_bytes for b in self.backup_history)
        verified_backups = sum(1 for b in self.backup_history if b.verification_status == "verified")
        
        return {
            'total_backups': len(self.backup_history),
            'verified_backups': verified_backups,
            'total_size_bytes': total_size,
            'total_size_mb': total_size / (1024 * 1024),
            'backup_root': str(self.backup_root),
            'latest_backup': {
                'backup_id': latest_backup.backup_id if latest_backup else None,
                'timestamp': latest_backup.timestamp.isoformat() if latest_backup else None,
                'type': latest_backup.backup_type.value if latest_backup else None,
                'verified': latest_backup.verification_status == "verified" if latest_backup else False
            } if latest_backup else None,
            'retention_policy': {
                'max_backups': self.max_backups,
                'retention_days': self.retention_days
            },
            'storage_usage': {
                'backup_directory_exists': self.backup_root.exists(),
                'free_space_mb': self._get_free_space() / (1024 * 1024) if self.backup_root.exists() else 0
            }
        }
    
    def _get_free_space(self) -> int:
        """Get free disk space for backup directory.
        
        Returns:
            Free space in bytes
        """
        try:
            stat = shutil.disk_usage(self.backup_root)
            return stat.free
        except OSError:
            return 0
    
    def list_backups(self, limit: int = 20) -> List[Dict[str, Any]]:
        """List recent backups.
        
        Args:
            limit: Maximum number of backups to return
            
        Returns:
            List of backup information
        """
        recent_backups = sorted(self.backup_history, key=lambda b: b.timestamp, reverse=True)[:limit]
        
        return [
            {
                'backup_id': b.backup_id,
                'type': b.backup_type.value,
                'timestamp': b.timestamp.isoformat(),
                'file_count': b.file_count,
                'size_mb': b.size_bytes / (1024 * 1024),
                'git_commit': b.git_commit[:8] if b.git_commit else None,
                'git_branch': b.git_branch,
                'verified': b.verification_status == "verified",
                'description': b.metadata.get('description', '')
            }
            for b in recent_backups
        ]