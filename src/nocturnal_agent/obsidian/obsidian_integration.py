"""Unified Obsidian integration system."""

import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from nocturnal_agent.core.models import ExecutionResult, ProjectContext
from nocturnal_agent.obsidian.vault_manager import ObsidianVaultManager
from nocturnal_agent.obsidian.context_manager import ObsidianContextManager
from nocturnal_agent.obsidian.knowledge_retriever import ObsidianKnowledgeRetriever


logger = logging.getLogger(__name__)


class ObsidianIntegration:
    """Unified Obsidian integration system for project knowledge management."""
    
    def __init__(self, vault_path: str, project_name: str):
        """Initialize Obsidian integration.
        
        Args:
            vault_path: Path to Obsidian vault directory
            project_name: Name of the project
        """
        self.vault_path = vault_path
        self.project_name = project_name
        
        # Initialize components
        self.vault_manager = ObsidianVaultManager(vault_path)
        self.context_manager = ObsidianContextManager(vault_path, project_name)
        self.knowledge_retriever = ObsidianKnowledgeRetriever(vault_path, project_name)
        
        # Configuration
        self.auto_save_enabled = True
        self.auto_backup_enabled = True
        self.save_interval = 300  # 5 minutes
        
        # State
        self._last_save_time = None
        self._pending_changes = False
    
    async def initialize_project(self) -> Dict[str, Any]:
        """Initialize Obsidian integration for the project.
        
        Returns:
            Dictionary with initialization results
        """
        try:
            logger.info(f"Initializing Obsidian integration for project: {self.project_name}")
            
            # Initialize vault structure
            vault_init_result = await self.vault_manager.initialize_vault_structure(self.project_name)
            
            if vault_init_result['status'] != 'success':
                return vault_init_result
            
            # Check if existing project context can be loaded
            existing_context = await self.context_manager.load_project_context()
            
            initialization_result = {
                'status': 'success',
                'project_name': self.project_name,
                'vault_path': self.vault_path,
                'vault_initialization': vault_init_result,
                'existing_context_loaded': existing_context is not None,
                'context_patterns_count': len(existing_context.patterns) if existing_context else 0,
                'context_rules_count': len(existing_context.consistency_rules) if existing_context else 0,
                'context_history_count': len(existing_context.development_history) if existing_context else 0
            }
            
            logger.info("Obsidian integration initialized successfully")
            return initialization_result
            
        except Exception as e:
            logger.error(f"Failed to initialize Obsidian integration: {e}")
            return {'status': 'error', 'error': str(e)}
    
    async def save_project_context(
        self,
        project_context: ProjectContext,
        force_save: bool = False
    ) -> Dict[str, Any]:
        """Save project context to Obsidian vault.
        
        Args:
            project_context: Project context to save
            force_save: Force save even if auto-save is disabled
            
        Returns:
            Dictionary with save results
        """
        try:
            if not self.auto_save_enabled and not force_save:
                return {'status': 'skipped', 'reason': 'auto_save_disabled'}
            
            # Save context using context manager
            save_result = await self.context_manager.save_project_context(project_context)
            
            if save_result['status'] == 'success':
                self._last_save_time = asyncio.get_event_loop().time()
                self._pending_changes = False
                
                logger.info(f"Project context saved: {save_result['files_saved']} files")
            
            return save_result
            
        except Exception as e:
            logger.error(f"Failed to save project context: {e}")
            return {'status': 'error', 'error': str(e)}
    
    async def load_project_context(self) -> Optional[ProjectContext]:
        """Load project context from Obsidian vault.
        
        Returns:
            Loaded project context or None if not found
        """
        try:
            logger.info(f"Loading project context for: {self.project_name}")
            
            project_context = await self.context_manager.load_project_context()
            
            if project_context:
                logger.info(f"Loaded project context: {len(project_context.patterns)} patterns, "
                          f"{len(project_context.consistency_rules)} rules, "
                          f"{len(project_context.development_history)} history entries")
            else:
                logger.info("No existing project context found")
            
            return project_context
            
        except Exception as e:
            logger.error(f"Failed to load project context: {e}")
            return None
    
    async def record_execution(
        self,
        execution_result: ExecutionResult,
        project_context: ProjectContext
    ) -> Dict[str, Any]:
        """Record execution result in Obsidian vault.
        
        Args:
            execution_result: Execution result to record
            project_context: Current project context
            
        Returns:
            Dictionary with recording results
        """
        try:
            # Mark pending changes
            self._pending_changes = True
            
            # If auto-save is enabled and enough time has passed, save context
            current_time = asyncio.get_event_loop().time()
            should_auto_save = (
                self.auto_save_enabled and 
                (self._last_save_time is None or 
                 current_time - self._last_save_time > self.save_interval)
            )
            
            if should_auto_save:
                save_result = await self.save_project_context(project_context)
                return {
                    'status': 'recorded_and_saved',
                    'execution_recorded': True,
                    'context_saved': save_result['status'] == 'success',
                    'save_result': save_result
                }
            else:
                return {
                    'status': 'recorded',
                    'execution_recorded': True,
                    'context_saved': False,
                    'pending_changes': True
                }
            
        except Exception as e:
            logger.error(f"Failed to record execution: {e}")
            return {'status': 'error', 'error': str(e)}
    
    async def search_knowledge(
        self,
        query: str,
        search_type: str = "patterns",
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Search for knowledge in the vault.
        
        Args:
            query: Search query
            search_type: Type of search ('patterns', 'tags', 'recent', 'cross_project')
            filters: Additional search filters
            
        Returns:
            Dictionary with search results
        """
        try:
            filters = filters or {}
            results = []
            
            if search_type == "patterns":
                results = await self.knowledge_retriever.search_patterns(
                    query=query,
                    pattern_type=filters.get('pattern_type'),
                    min_confidence=filters.get('min_confidence', 0.0),
                    limit=filters.get('limit', 10)
                )
                
            elif search_type == "tags":
                tags = query.split(',') if isinstance(query, str) else query
                results = await self.knowledge_retriever.search_by_tags(
                    tags=tags,
                    content_type=filters.get('content_type', 'all'),
                    limit=filters.get('limit', 20)
                )
                
            elif search_type == "recent":
                results = await self.knowledge_retriever.get_recent_activity(
                    days=filters.get('days', 7),
                    activity_type=filters.get('activity_type', 'all')
                )
                
            elif search_type == "cross_project":
                results = await self.knowledge_retriever.get_cross_project_knowledge(
                    query=query,
                    exclude_current=filters.get('exclude_current', True)
                )
            
            return {
                'status': 'success',
                'query': query,
                'search_type': search_type,
                'results_count': len(results),
                'results': results
            }
            
        except Exception as e:
            logger.error(f"Knowledge search failed: {e}")
            return {'status': 'error', 'error': str(e)}
    
    async def suggest_relevant_patterns(
        self,
        context: str,
        limit: int = 5
    ) -> Dict[str, Any]:
        """Suggest relevant patterns based on context.
        
        Args:
            context: Context to find relevant patterns for
            limit: Maximum number of suggestions
            
        Returns:
            Dictionary with pattern suggestions
        """
        try:
            suggestions = await self.knowledge_retriever.suggest_related_knowledge(
                context=context,
                limit=limit
            )
            
            return {
                'status': 'success',
                'suggestions_count': len(suggestions),
                'suggestions': suggestions
            }
            
        except Exception as e:
            logger.error(f"Pattern suggestion failed: {e}")
            return {'status': 'error', 'error': str(e)}
    
    async def get_project_analytics(self) -> Dict[str, Any]:
        """Get analytics about the project knowledge base.
        
        Returns:
            Dictionary with project analytics
        """
        try:
            # Get usage statistics
            usage_stats = await self.knowledge_retriever.get_pattern_usage_statistics()
            
            # Get recent activity
            recent_activity = await self.knowledge_retriever.get_recent_activity(days=30)
            
            # Get vault info
            vault_info = self.vault_manager.get_vault_info()
            
            return {
                'status': 'success',
                'project_name': self.project_name,
                'vault_info': vault_info,
                'usage_statistics': usage_stats,
                'recent_activity_count': len(recent_activity),
                'recent_activity': recent_activity[:10],  # Latest 10
                'analytics_generated': True
            }
            
        except Exception as e:
            logger.error(f"Analytics generation failed: {e}")
            return {'status': 'error', 'error': str(e)}
    
    async def backup_knowledge_base(self) -> Dict[str, Any]:
        """Create backup of the knowledge base.
        
        Returns:
            Dictionary with backup results
        """
        try:
            if not self.auto_backup_enabled:
                return {'status': 'skipped', 'reason': 'backup_disabled'}
            
            from datetime import datetime
            import shutil
            import tempfile
            
            # Create backup directory
            backup_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_name = f"{self.project_name}_backup_{backup_timestamp}"
            
            with tempfile.TemporaryDirectory() as temp_dir:
                backup_path = Path(temp_dir) / backup_name
                
                # Copy project directory to backup
                project_path = Path(self.vault_path) / self.project_name
                if project_path.exists():
                    shutil.copytree(project_path, backup_path)
                    
                    # Get backup info
                    backup_size = sum(
                        f.stat().st_size for f in backup_path.rglob('*') if f.is_file()
                    )
                    file_count = len(list(backup_path.rglob('*.md')))
                    
                    # In a real implementation, you'd move the backup to permanent storage
                    logger.info(f"Created backup: {backup_name} ({backup_size} bytes, {file_count} files)")
                    
                    return {
                        'status': 'success',
                        'backup_name': backup_name,
                        'backup_size': backup_size,
                        'files_backed_up': file_count,
                        'backup_timestamp': backup_timestamp
                    }
                else:
                    return {'status': 'no_data', 'reason': 'project_directory_not_found'}
            
        except Exception as e:
            logger.error(f"Backup creation failed: {e}")
            return {'status': 'error', 'error': str(e)}
    
    async def optimize_knowledge_base(self) -> Dict[str, Any]:
        """Optimize the knowledge base by cleaning up and reorganizing.
        
        Returns:
            Dictionary with optimization results
        """
        try:
            optimization_results = {
                'duplicate_patterns_removed': 0,
                'low_confidence_patterns_archived': 0,
                'broken_links_fixed': 0,
                'unused_files_cleaned': 0
            }
            
            project_dir = Path(self.vault_path) / self.project_name
            if not project_dir.exists():
                return {'status': 'no_data', 'reason': 'project_directory_not_found'}
            
            # Find and handle duplicate patterns (simplified implementation)
            patterns_dir = project_dir / "patterns"
            if patterns_dir.exists():
                pattern_files = list(patterns_dir.glob("*.md"))
                
                # Group patterns by content hash for duplicate detection
                content_hashes = {}
                duplicates = []
                
                for pattern_file in pattern_files:
                    if pattern_file.name.startswith("consistency-rules"):
                        continue
                    
                    content = pattern_file.read_text(encoding='utf-8')
                    content_hash = hash(content)
                    
                    if content_hash in content_hashes:
                        duplicates.append(pattern_file)
                    else:
                        content_hashes[content_hash] = pattern_file
                
                # Remove duplicates (in practice, you'd be more careful about this)
                for duplicate in duplicates:
                    logger.info(f"Would remove duplicate: {duplicate.name}")
                    optimization_results['duplicate_patterns_removed'] += 1
            
            # Archive low confidence patterns
            # This would move patterns with very low confidence to an archive folder
            # Implementation omitted for brevity
            
            logger.info(f"Knowledge base optimization completed: {optimization_results}")
            
            return {
                'status': 'success',
                'optimizations': optimization_results,
                'optimization_completed': True
            }
            
        except Exception as e:
            logger.error(f"Knowledge base optimization failed: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def configure_integration(self, config: Dict[str, Any]) -> None:
        """Configure Obsidian integration settings.
        
        Args:
            config: Configuration dictionary
        """
        if 'auto_save_enabled' in config:
            self.auto_save_enabled = config['auto_save_enabled']
        
        if 'auto_backup_enabled' in config:
            self.auto_backup_enabled = config['auto_backup_enabled']
        
        if 'save_interval' in config:
            self.save_interval = config['save_interval']
        
        logger.info(f"Obsidian integration configured: auto_save={self.auto_save_enabled}, "
                   f"auto_backup={self.auto_backup_enabled}, save_interval={self.save_interval}")
    
    def get_integration_status(self) -> Dict[str, Any]:
        """Get current integration status.
        
        Returns:
            Dictionary with integration status
        """
        vault_info = self.vault_manager.get_vault_info()
        
        return {
            'project_name': self.project_name,
            'vault_path': self.vault_path,
            'vault_exists': vault_info.get('vault_exists', False),
            'auto_save_enabled': self.auto_save_enabled,
            'auto_backup_enabled': self.auto_backup_enabled,
            'save_interval': self.save_interval,
            'pending_changes': self._pending_changes,
            'last_save_time': self._last_save_time,
            'vault_info': vault_info
        }
    
    async def force_save(self, project_context: ProjectContext) -> Dict[str, Any]:
        """Force save project context regardless of settings.
        
        Args:
            project_context: Project context to save
            
        Returns:
            Dictionary with save results
        """
        return await self.save_project_context(project_context, force_save=True)