"""Obsidian context management for project patterns and history."""

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from nocturnal_agent.core.models import (
    CodePattern, ConsistencyRule, DevelopmentHistory, ExecutionResult, ProjectContext
)


logger = logging.getLogger(__name__)


class ObsidianContextManager:
    """Manages project context storage and retrieval in Obsidian vault."""
    
    def __init__(self, vault_path: str, project_name: str):
        """Initialize context manager.
        
        Args:
            vault_path: Path to Obsidian vault
            project_name: Name of the project
        """
        self.vault_path = Path(vault_path)
        self.project_name = project_name
        self.project_dir = self.vault_path / project_name
        
        # Ensure project directory exists
        self.project_dir.mkdir(parents=True, exist_ok=True)
    
    async def save_project_context(self, project_context: ProjectContext) -> Dict[str, Any]:
        """Save complete project context to Obsidian vault.
        
        Args:
            project_context: Project context to save
            
        Returns:
            Dictionary with save results
        """
        try:
            saved_files = []
            
            # Save patterns
            patterns_saved = await self._save_patterns(project_context.patterns)
            saved_files.extend(patterns_saved)
            
            # Save consistency rules
            rules_saved = await self._save_consistency_rules(project_context.consistency_rules)
            saved_files.extend(rules_saved)
            
            # Save development history
            history_saved = await self._save_development_history(project_context.development_history)
            saved_files.extend(history_saved)
            
            # Update project overview
            overview_file = await self._update_project_overview(project_context)
            saved_files.append(overview_file)
            
            logger.info(f"Saved project context: {len(saved_files)} files")
            
            return {
                'status': 'success',
                'files_saved': saved_files,
                'patterns_count': len(project_context.patterns),
                'rules_count': len(project_context.consistency_rules),
                'history_count': len(project_context.development_history)
            }
            
        except Exception as e:
            logger.error(f"Failed to save project context: {e}")
            return {'status': 'error', 'error': str(e)}
    
    async def _save_patterns(self, patterns: List[CodePattern]) -> List[str]:
        """Save code patterns to Obsidian."""
        
        patterns_dir = self.project_dir / "patterns"
        patterns_dir.mkdir(exist_ok=True)
        
        saved_files = []
        
        for pattern in patterns:
            filename = f"{pattern.name.lower().replace(' ', '-')}.md"
            file_path = patterns_dir / filename
            
            # Create markdown content
            content = f"""---
type: pattern
project: {self.project_name}
pattern_type: {pattern.pattern_type}
confidence: {pattern.confidence}
usage_count: {pattern.usage_count}
created: {datetime.now().isoformat()}
tags: [pattern, {pattern.pattern_type}, confidence-{int(pattern.confidence * 10)}]
---

# {pattern.name}

## Description
{pattern.description}

## Pattern Details
- **Type**: {pattern.pattern_type}
- **Confidence**: {pattern.confidence:.3f}
- **Usage Count**: {pattern.usage_count}
- **File Path**: `{pattern.file_path or 'N/A'}`

## Example
```{self._get_language_from_pattern(pattern)}
{pattern.example or 'No example provided'}
```

## Context
{pattern.context or 'No additional context'}

## Related Patterns
{self._format_related_patterns(pattern)}

## Metadata
- **Created**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- **Pattern ID**: `{pattern.name.lower().replace(' ', '_')}`
- **Confidence Level**: {'High' if pattern.confidence > 0.8 else 'Medium' if pattern.confidence > 0.6 else 'Low'}
"""
            
            file_path.write_text(content, encoding='utf-8')
            saved_files.append(str(file_path))
        
        return saved_files
    
    async def _save_consistency_rules(self, rules: List[ConsistencyRule]) -> List[str]:
        """Save consistency rules to Obsidian."""
        
        rules_dir = self.project_dir / "patterns" / "consistency-rules"
        rules_dir.mkdir(parents=True, exist_ok=True)
        
        saved_files = []
        
        for rule in rules:
            filename = f"{rule.rule_id.lower().replace('_', '-')}.md"
            file_path = rules_dir / filename
            
            content = f"""---
type: consistency_rule
project: {self.project_name}
rule_id: {rule.rule_id}
rule_type: {rule.rule_type}
severity: {rule.severity}
enabled: {rule.enabled}
auto_fixable: {rule.auto_fixable}
created: {datetime.now().isoformat()}
tags: [rule, {rule.rule_type}, {rule.severity}]
---

# {rule.description}

## Rule Details
- **Rule ID**: `{rule.rule_id}`
- **Type**: {rule.rule_type}
- **Severity**: {rule.severity}
- **Enabled**: {'✅' if rule.enabled else '❌'}
- **Auto-fixable**: {'✅' if rule.auto_fixable else '❌'}

## Pattern
```regex
{rule.pattern}
```

## Explanation
{rule.message or 'No detailed explanation provided'}

## Examples

### ❌ Violation
```python
# Example that violates this rule
{self._generate_violation_example(rule)}
```

### ✅ Correct
```python
# Correct implementation
{self._generate_correct_example(rule)}
```

## Metadata
- **Created**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- **Category**: {rule.rule_type.replace('_', ' ').title()}
"""
            
            file_path.write_text(content, encoding='utf-8')
            saved_files.append(str(file_path))
        
        return saved_files
    
    async def _save_development_history(self, history: List[DevelopmentHistory]) -> List[str]:
        """Save development history to Obsidian."""
        
        history_dir = self.project_dir / "history"
        history_dir.mkdir(exist_ok=True)
        
        saved_files = []
        
        # Group history by date
        history_by_date = {}
        for entry in history:
            date_key = entry.timestamp.strftime('%Y-%m-%d')
            if date_key not in history_by_date:
                history_by_date[date_key] = []
            history_by_date[date_key].append(entry)
        
        # Create daily history files
        for date_key, entries in history_by_date.items():
            filename = f"{date_key}-execution-log.md"
            file_path = history_dir / filename
            
            content = f"""---
type: development_history
project: {self.project_name}
date: {date_key}
executions: {len(entries)}
created: {datetime.now().isoformat()}
tags: [history, {date_key.replace('-', '_')}]
---

# Development History - {date_key}

## Summary
- **Total Executions**: {len(entries)}
- **Successful**: {sum(1 for e in entries if e.success)}
- **Failed**: {sum(1 for e in entries if not e.success)}
- **Average Quality**: {sum(e.quality_score.overall for e in entries if e.quality_score) / len([e for e in entries if e.quality_score]):.3f if any(e.quality_score for e in entries) else 'N/A'}

## Execution Log

"""
            
            for i, entry in enumerate(entries, 1):
                status_emoji = "✅" if entry.success else "❌"
                quality_score = entry.quality_score.overall if entry.quality_score else 0.0
                
                content += f"""### {i}. {entry.task_description} {status_emoji}

**Details:**
- **Task ID**: `{entry.task_id}`
- **Agent**: {entry.agent_used}
- **Time**: {entry.timestamp.strftime('%H:%M:%S')}
- **Quality**: {quality_score:.3f}
- **Duration**: {entry.execution_time}s

**Generated Code:**
```python
{entry.generated_code[:500]}{"..." if len(entry.generated_code) > 500 else ""}
```

**Result:** {entry.result_summary or 'No summary available'}

---

"""
            
            file_path.write_text(content, encoding='utf-8')
            saved_files.append(str(file_path))
        
        return saved_files
    
    async def _update_project_overview(self, project_context: ProjectContext) -> str:
        """Update project overview file."""
        
        overview_path = self.project_dir / "context" / "project-overview.md"
        overview_path.parent.mkdir(exist_ok=True)
        
        # Calculate statistics
        total_patterns = len(project_context.patterns)
        high_confidence_patterns = sum(1 for p in project_context.patterns if p.confidence > 0.8)
        total_executions = len(project_context.development_history)
        successful_executions = sum(1 for h in project_context.development_history if h.success)
        success_rate = successful_executions / total_executions if total_executions > 0 else 0.0
        
        # Get average quality
        quality_scores = [h.quality_score.overall for h in project_context.development_history if h.quality_score]
        avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0.0
        
        content = f"""---
type: project_overview
project: {self.project_name}
updated: {datetime.now().isoformat()}
tags: [overview, context, statistics]
---

# {self.project_name} - Project Overview

## Project Statistics

### Patterns & Rules
- **Total Patterns**: {total_patterns}
- **High Confidence Patterns** (>0.8): {high_confidence_patterns}
- **Consistency Rules**: {len(project_context.consistency_rules)}
- **Active Rules**: {sum(1 for r in project_context.consistency_rules if r.enabled)}

### Development Activity
- **Total Executions**: {total_executions}
- **Successful Executions**: {successful_executions}
- **Success Rate**: {success_rate:.1%}
- **Average Quality Score**: {avg_quality:.3f}

## Key Patterns

### Most Used Patterns
"""
        
        # Add top patterns
        top_patterns = sorted(project_context.patterns, key=lambda p: p.usage_count, reverse=True)[:5]
        for pattern in top_patterns:
            content += f"- [[patterns/{pattern.name.lower().replace(' ', '-')}|{pattern.name}]] (used {pattern.usage_count} times, confidence: {pattern.confidence:.3f})\n"
        
        content += f"""
### High Confidence Patterns
"""
        
        high_conf_patterns = [p for p in project_context.patterns if p.confidence > 0.8][:5]
        for pattern in high_conf_patterns:
            content += f"- [[patterns/{pattern.name.lower().replace(' ', '-')}|{pattern.name}]] (confidence: {pattern.confidence:.3f})\n"
        
        content += f"""
## Recent Activity

### Last 7 Days
- Recent executions: [[history/{datetime.now().strftime('%Y-%m-%d')}-execution-log|Today's Log]]
- Pattern updates: {len([p for p in project_context.patterns if (datetime.now() - datetime.fromisoformat(p.context.get('created', datetime.now().isoformat()))).days < 7]) if any(hasattr(p, 'context') and p.context for p in project_context.patterns) else 'N/A'}

## Quality Trends
- Current quality threshold: 0.85
- Consistency threshold: 0.85
- Recent average quality: {avg_quality:.3f}

## Next Steps
- Continue pattern learning and refinement
- Monitor consistency rule effectiveness  
- Optimize quality improvement cycles

---
*Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
"""
        
        overview_path.write_text(content, encoding='utf-8')
        return str(overview_path)
    
    async def load_project_context(self) -> Optional[ProjectContext]:
        """Load project context from Obsidian vault.
        
        Returns:
            Loaded project context or None if not found
        """
        try:
            # Load patterns
            patterns = await self._load_patterns()
            
            # Load consistency rules  
            consistency_rules = await self._load_consistency_rules()
            
            # Load development history
            development_history = await self._load_development_history()
            
            # Create project context
            project_context = ProjectContext(
                project_name=self.project_name,
                patterns=patterns,
                consistency_rules=consistency_rules,
                development_history=development_history
            )
            
            logger.info(f"Loaded project context: {len(patterns)} patterns, {len(consistency_rules)} rules, {len(development_history)} history entries")
            
            return project_context
            
        except Exception as e:
            logger.error(f"Failed to load project context: {e}")
            return None
    
    async def _load_patterns(self) -> List[CodePattern]:
        """Load code patterns from Obsidian files."""
        
        patterns = []
        patterns_dir = self.project_dir / "patterns"
        
        if not patterns_dir.exists():
            return patterns
        
        for pattern_file in patterns_dir.glob("*.md"):
            if pattern_file.name.startswith("consistency-rules"):
                continue
                
            try:
                content = pattern_file.read_text(encoding='utf-8')
                
                # Parse frontmatter
                frontmatter = self._parse_frontmatter(content)
                
                if frontmatter.get('type') != 'pattern':
                    continue
                
                # Extract pattern name from title
                title_match = re.search(r'^# (.+)$', content, re.MULTILINE)
                pattern_name = title_match.group(1) if title_match else pattern_file.stem
                
                # Extract example code
                example_match = re.search(r'```[\w]*\n(.*?)\n```', content, re.DOTALL)
                example_code = example_match.group(1) if example_match else ""
                
                # Extract description
                desc_match = re.search(r'## Description\n(.*?)\n##', content, re.DOTALL)
                description = desc_match.group(1).strip() if desc_match else ""
                
                pattern = CodePattern(
                    name=pattern_name,
                    pattern_type=frontmatter.get('pattern_type', 'unknown'),
                    description=description,
                    example=example_code,
                    confidence=float(frontmatter.get('confidence', 0.5)),
                    usage_count=int(frontmatter.get('usage_count', 0)),
                    file_path=frontmatter.get('file_path'),
                    context={}
                )
                
                patterns.append(pattern)
                
            except Exception as e:
                logger.warning(f"Failed to load pattern from {pattern_file}: {e}")
        
        return patterns
    
    async def _load_consistency_rules(self) -> List[ConsistencyRule]:
        """Load consistency rules from Obsidian files."""
        
        rules = []
        rules_dir = self.project_dir / "patterns" / "consistency-rules"
        
        if not rules_dir.exists():
            return rules
        
        for rule_file in rules_dir.glob("*.md"):
            try:
                content = rule_file.read_text(encoding='utf-8')
                
                # Parse frontmatter
                frontmatter = self._parse_frontmatter(content)
                
                if frontmatter.get('type') != 'consistency_rule':
                    continue
                
                # Extract pattern
                pattern_match = re.search(r'```regex\n(.*?)\n```', content, re.DOTALL)
                pattern = pattern_match.group(1).strip() if pattern_match else ""
                
                rule = ConsistencyRule(
                    rule_id=frontmatter.get('rule_id', rule_file.stem),
                    rule_type=frontmatter.get('rule_type', 'style'),
                    description=frontmatter.get('description', ''),
                    pattern=pattern,
                    message=frontmatter.get('message', ''),
                    severity=frontmatter.get('severity', 'warning'),
                    enabled=frontmatter.get('enabled', True),
                    auto_fixable=frontmatter.get('auto_fixable', False)
                )
                
                rules.append(rule)
                
            except Exception as e:
                logger.warning(f"Failed to load rule from {rule_file}: {e}")
        
        return rules
    
    async def _load_development_history(self) -> List[DevelopmentHistory]:
        """Load development history from Obsidian files."""
        
        history = []
        history_dir = self.project_dir / "history"
        
        if not history_dir.exists():
            return history
        
        for history_file in history_dir.glob("*-execution-log.md"):
            try:
                content = history_file.read_text(encoding='utf-8')
                
                # Parse frontmatter
                frontmatter = self._parse_frontmatter(content)
                
                if frontmatter.get('type') != 'development_history':
                    continue
                
                # Extract execution entries (simplified parsing)
                # In a real implementation, this would be more sophisticated
                executions_count = frontmatter.get('executions', 0)
                
                # Create placeholder history entries
                # (In practice, you'd parse the actual execution details)
                for i in range(executions_count):
                    history_entry = DevelopmentHistory(
                        task_id=f"task_{i}_{history_file.stem}",
                        task_description=f"Task from {history_file.stem}",
                        agent_used="unknown",
                        timestamp=datetime.now(),
                        success=True,
                        generated_code="",
                        execution_time=0.0,
                        result_summary=""
                    )
                    history.append(history_entry)
                
            except Exception as e:
                logger.warning(f"Failed to load history from {history_file}: {e}")
        
        return history
    
    def _parse_frontmatter(self, content: str) -> Dict[str, Any]:
        """Parse YAML frontmatter from markdown content."""
        
        frontmatter_match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
        if not frontmatter_match:
            return {}
        
        import yaml
        try:
            return yaml.safe_load(frontmatter_match.group(1)) or {}
        except yaml.YAMLError:
            return {}
    
    def _get_language_from_pattern(self, pattern: CodePattern) -> str:
        """Determine programming language from pattern."""
        
        if pattern.pattern_type in ['python_naming', 'python_structure']:
            return 'python'
        elif pattern.pattern_type in ['js_naming', 'js_structure']:
            return 'javascript'
        elif pattern.pattern_type in ['ts_naming', 'ts_structure']:
            return 'typescript'
        else:
            return 'python'  # Default
    
    def _format_related_patterns(self, pattern: CodePattern) -> str:
        """Format related patterns links."""
        
        # This would be enhanced to find actual related patterns
        return "No related patterns identified yet."
    
    def _generate_violation_example(self, rule: ConsistencyRule) -> str:
        """Generate example code that violates the rule."""
        
        # Simplified example generation
        examples = {
            'naming_convention': 'myVariable = "should use snake_case"',
            'function_structure': 'def bad_function(): pass  # Missing docstring',
            'import_organization': 'import sys\nimport os  # Should be organized',
            'line_length': 'very_long_line_that_exceeds_the_maximum_allowed_length_and_should_be_split = "example"'
        }
        
        return examples.get(rule.rule_type, '# Example violation')
    
    def _generate_correct_example(self, rule: ConsistencyRule) -> str:
        """Generate example code that follows the rule."""
        
        # Simplified example generation  
        examples = {
            'naming_convention': 'my_variable = "uses snake_case correctly"',
            'function_structure': 'def good_function():\n    """Function with proper docstring."""\n    pass',
            'import_organization': 'import os\nimport sys  # Properly organized',
            'line_length': 'shorter_line = "within length limits"'
        }
        
        return examples.get(rule.rule_type, '# Example following rule')