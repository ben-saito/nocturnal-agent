"""Obsidian vault structure management."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from nocturnal_agent.core.models import ProjectContext


logger = logging.getLogger(__name__)


class ObsidianVaultManager:
    """Manages Obsidian vault structure and initialization."""
    
    def __init__(self, vault_path: str):
        """Initialize vault manager.
        
        Args:
            vault_path: Path to Obsidian vault directory
        """
        self.vault_path = Path(vault_path)
        self.vault_config_path = self.vault_path / ".obsidian"
        
    async def initialize_vault_structure(self, project_name: str) -> Dict[str, Any]:
        """Initialize Obsidian vault structure for a project.
        
        Args:
            project_name: Name of the project
            
        Returns:
            Dictionary with initialization results
        """
        try:
            # Create main vault directory if not exists
            self.vault_path.mkdir(parents=True, exist_ok=True)
            
            # Create project-specific directory structure
            project_dir = self.vault_path / project_name
            project_dir.mkdir(exist_ok=True)
            
            # Create subdirectories
            subdirs = [
                "patterns",        # Code patterns and conventions
                "history",        # Development history logs
                "context",        # Project context and metadata
                "knowledge",      # Learned knowledge and insights
                "templates",      # Template files
                "analysis"        # Analysis results and reports
            ]
            
            created_dirs = []
            for subdir in subdirs:
                dir_path = project_dir / subdir
                dir_path.mkdir(exist_ok=True)
                created_dirs.append(str(dir_path))
            
            # Initialize Obsidian configuration
            obsidian_config = await self._initialize_obsidian_config()
            
            # Create initial template files
            templates_created = await self._create_template_files(project_dir / "templates")
            
            # Create project index file
            index_file = await self._create_project_index(project_dir, project_name)
            
            logger.info(f"Initialized Obsidian vault structure for project: {project_name}")
            
            return {
                'status': 'success',
                'vault_path': str(self.vault_path),
                'project_directory': str(project_dir),
                'directories_created': created_dirs,
                'templates_created': templates_created,
                'index_file': index_file,
                'obsidian_config': obsidian_config
            }
            
        except Exception as e:
            logger.error(f"Failed to initialize vault structure: {e}")
            return {'status': 'error', 'error': str(e)}
    
    async def _initialize_obsidian_config(self) -> Dict[str, Any]:
        """Initialize Obsidian configuration files."""
        
        # Create .obsidian directory
        self.vault_config_path.mkdir(exist_ok=True)
        
        # App configuration
        app_config = {
            "legacyEditor": False,
            "livePreview": True,
            "showLineNumber": True,
            "spellcheck": False,
            "smartIndentList": True
        }
        
        app_config_file = self.vault_config_path / "app.json"
        with open(app_config_file, 'w', encoding='utf-8') as f:
            json.dump(app_config, f, indent=2)
        
        # Core plugins configuration
        core_plugins = {
            "file-explorer": True,
            "global-search": True,
            "switcher": True,
            "graph": True,
            "backlink": True,
            "outgoing-link": True,
            "tag-pane": True,
            "page-preview": True,
            "templates": True,
            "note-composer": True,
            "command-palette": True,
            "markdown-importer": True,
            "word-count": True,
            "open-with-default-app": True,
            "file-recovery": True
        }
        
        core_plugins_file = self.vault_config_path / "core-plugins.json"
        with open(core_plugins_file, 'w', encoding='utf-8') as f:
            json.dump(list(core_plugins.keys()), f, indent=2)
        
        # Hotkeys configuration
        hotkeys_config = {
            "switcher:open": [
                {
                    "modifiers": ["Mod"],
                    "key": "o"
                }
            ],
            "global-search:open": [
                {
                    "modifiers": ["Mod", "Shift"],
                    "key": "f"
                }
            ]
        }
        
        hotkeys_file = self.vault_config_path / "hotkeys.json"
        with open(hotkeys_file, 'w', encoding='utf-8') as f:
            json.dump(hotkeys_config, f, indent=2)
        
        return {
            'config_directory': str(self.vault_config_path),
            'app_config': app_config_file.name,
            'core_plugins': core_plugins_file.name,
            'hotkeys': hotkeys_file.name
        }
    
    async def _create_template_files(self, templates_dir: Path) -> List[str]:
        """Create Markdown template files."""
        
        templates_dir.mkdir(exist_ok=True)
        created_templates = []
        
        # Pattern documentation template
        pattern_template = """---
type: pattern
project: {{project_name}}
pattern_type: {{pattern_type}}
confidence: {{confidence}}
created: {{date}}
tags: [pattern, {{pattern_type}}]
---

# {{pattern_name}}

## Description
{{description}}

## Example
```{{language}}
{{example_code}}
```

## Usage Guidelines
{{usage_guidelines}}

## Related Patterns
{{related_patterns}}

## Confidence Score
- **Confidence**: {{confidence}}
- **Usage Count**: {{usage_count}}
- **Last Updated**: {{date}}
"""
        
        pattern_file = templates_dir / "pattern-template.md"
        pattern_file.write_text(pattern_template, encoding='utf-8')
        created_templates.append(pattern_file.name)
        
        # Development history template
        history_template = """---
type: development_history
project: {{project_name}}
task_id: {{task_id}}
timestamp: {{timestamp}}
success: {{success}}
tags: [history, {{status}}]
---

# Development History - {{task_description}}

## Task Details
- **Task ID**: {{task_id}}
- **Description**: {{task_description}}
- **Agent Used**: {{agent_used}}
- **Timestamp**: {{timestamp}}

## Execution Summary
- **Success**: {{success}}
- **Quality Score**: {{quality_score}}
- **Execution Time**: {{execution_time}}

## Generated Code
```{{language}}
{{generated_code}}
```

## Patterns Applied
{{patterns_applied}}

## Lessons Learned
{{lessons_learned}}

## Issues Encountered
{{issues_encountered}}
"""
        
        history_file = templates_dir / "history-template.md"
        history_file.write_text(history_template, encoding='utf-8')
        created_templates.append(history_file.name)
        
        # Project context template
        context_template = """---
type: project_context
project: {{project_name}}
updated: {{date}}
tags: [context, metadata]
---

# {{project_name}} - Project Context

## Project Overview
{{project_description}}

## Architecture Patterns
{{architecture_patterns}}

## Code Conventions
{{code_conventions}}

## Quality Standards
- **Minimum Quality Score**: {{quality_threshold}}
- **Consistency Threshold**: {{consistency_threshold}}

## Development Statistics
- **Total Patterns**: {{total_patterns}}
- **Success Rate**: {{success_rate}}
- **Average Quality**: {{average_quality}}

## Key Insights
{{key_insights}}
"""
        
        context_file = templates_dir / "context-template.md"
        context_file.write_text(context_template, encoding='utf-8')
        created_templates.append(context_file.name)
        
        return created_templates
    
    async def _create_project_index(self, project_dir: Path, project_name: str) -> str:
        """Create project index file."""
        
        index_content = f"""---
type: project_index
project: {project_name}
created: {datetime.now().isoformat()}
tags: [index, project]
---

# {project_name} - Nocturnal Agent Knowledge Base

## Directory Structure

### 📁 patterns/
Code patterns and conventions learned from the project
- [[patterns/naming-conventions]]
- [[patterns/architecture-decisions]]
- [[patterns/code-structure]]

### 📁 history/
Development history and execution logs
- [[history/recent-executions]]
- [[history/success-patterns]]
- [[history/failure-analysis]]

### 📁 context/
Project context and metadata
- [[context/project-overview]]
- [[context/quality-standards]]
- [[context/development-guidelines]]

### 📁 knowledge/
Learned insights and best practices
- [[knowledge/successful-patterns]]
- [[knowledge/common-issues]]
- [[knowledge/optimization-tips]]

### 📁 analysis/
Analysis results and reports
- [[analysis/consistency-reports]]
- [[analysis/quality-trends]]
- [[analysis/pattern-evolution]]

## Quick Navigation

### Recent Activity
- [[history/{datetime.now().strftime('%Y-%m-%d')}-execution-log]]

### Key Patterns
- High-confidence patterns with usage > 5
- Recently learned patterns
- Project-specific conventions

### Performance Metrics
- Current quality score: TBD
- Consistency score: TBD
- Success rate: TBD

## Tags
Use these tags to organize and find content:
- #pattern - Code patterns and conventions
- #history - Development history
- #context - Project context
- #knowledge - Learned insights
- #analysis - Reports and analysis
- #success - Successful implementations
- #failure - Failed attempts and lessons
- #high-confidence - High confidence patterns
"""
        
        index_file = project_dir / "index.md"
        index_file.write_text(index_content, encoding='utf-8')
        
        return str(index_file)
    
    def get_vault_info(self) -> Dict[str, Any]:
        """Get information about the vault."""
        
        vault_exists = self.vault_path.exists()
        config_exists = self.vault_config_path.exists()
        
        if not vault_exists:
            return {'vault_exists': False}
        
        # Count projects
        project_dirs = [
            d for d in self.vault_path.iterdir() 
            if d.is_dir() and not d.name.startswith('.')
        ]
        
        # Get vault size
        total_size = sum(
            f.stat().st_size for f in self.vault_path.rglob('*') 
            if f.is_file()
        )
        
        return {
            'vault_exists': True,
            'vault_path': str(self.vault_path),
            'config_exists': config_exists,
            'project_count': len(project_dirs),
            'project_names': [d.name for d in project_dirs],
            'total_size_bytes': total_size,
            'total_files': len(list(self.vault_path.rglob('*.md')))
        }