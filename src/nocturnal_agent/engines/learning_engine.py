"""Learning engine for continuous improvement of code patterns."""

import json
import logging
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

from nocturnal_agent.core.models import (
    CodePattern, ConsistencyRule, ExecutionResult, HistoryEntry, 
    Lesson, SuccessPattern, ProjectContext, QualityScore
)
from nocturnal_agent.engines.pattern_extractor import PatternExtractor
from nocturnal_agent.engines.consistency_engine import ConsistencyChecker


logger = logging.getLogger(__name__)


class PatternLearner:
    """Learns and updates code patterns based on successful implementations."""
    
    def __init__(self, project_context: ProjectContext):
        """Initialize pattern learner."""
        self.project_context = project_context
        self.pattern_extractor = PatternExtractor()
        self.learning_threshold = 3  # Minimum occurrences to establish pattern
        self.confidence_boost_rate = 0.1
        self.pattern_decay_rate = 0.05
    
    async def learn_from_success(
        self, 
        execution_result: ExecutionResult, 
        code: str, 
        context: Dict[str, Any]
    ) -> List[CodePattern]:
        """Learn patterns from successful code generation."""
        
        if not execution_result.success or not code:
            return []
        
        learned_patterns = []
        
        try:
            # Extract patterns from successful code
            patterns = await self.pattern_extractor._analyze_python_file(code, None)
            
            # Learn naming patterns
            naming_patterns = await self._learn_naming_patterns(
                patterns.get('naming_patterns', {}),
                execution_result.quality_score
            )
            learned_patterns.extend(naming_patterns)
            
            # Learn structural patterns
            structure_patterns = await self._learn_structure_patterns(
                patterns.get('structure_patterns', {}),
                execution_result.quality_score
            )
            learned_patterns.extend(structure_patterns)
            
            # Learn architectural patterns
            arch_patterns = await self._learn_architecture_patterns(
                patterns.get('architecture_patterns', {}),
                execution_result.quality_score
            )
            learned_patterns.extend(arch_patterns)
            
            # Update existing patterns with new evidence
            await self._update_existing_patterns(learned_patterns, execution_result)
            
            # Record learning event
            await self._record_learning_event(execution_result, learned_patterns, context)
            
            logger.info(f"Learned {len(learned_patterns)} patterns from successful execution")
            
        except Exception as e:
            logger.error(f"Failed to learn from success: {e}")
        
        return learned_patterns
    
    async def learn_from_failure(
        self, 
        execution_result: ExecutionResult, 
        failure_details: Dict[str, Any],
        context: Dict[str, Any]
    ) -> List[Lesson]:
        """Learn lessons from failed executions."""
        
        if execution_result.success:
            return []
        
        lessons = []
        
        try:
            # Analyze failure patterns
            failure_analysis = await self._analyze_failure_patterns(
                execution_result, failure_details
            )
            
            # Create lessons from failures
            for analysis in failure_analysis:
                lesson = Lesson(
                    lesson_id=f"failure_{execution_result.task_id}_{datetime.now().timestamp()}",
                    title=f"Avoid {analysis['pattern_type']} that caused {analysis['error_type']}",
                    description=analysis['description'],
                    category="failure_analysis",
                    applicable_patterns=analysis.get('applicable_patterns', []),
                    confidence=analysis.get('confidence', 0.7),
                    created_at=datetime.now()
                )
                lessons.append(lesson)
            
            # Update anti-patterns
            await self._update_anti_patterns(failure_analysis)
            
            # Record failure learning event
            await self._record_failure_learning(execution_result, lessons, context)
            
            logger.info(f"Learned {len(lessons)} lessons from execution failure")
            
        except Exception as e:
            logger.error(f"Failed to learn from failure: {e}")
        
        return lessons
    
    async def _learn_naming_patterns(
        self, 
        naming_patterns: Dict[str, List], 
        quality_score: QualityScore
    ) -> List[CodePattern]:
        """Learn naming conventions from successful code."""
        
        patterns = []
        
        for category, names in naming_patterns.items():
            if not names:
                continue
            
            # Analyze case styles
            case_styles = [name_info.get('case_style', 'unknown') for name_info in names]
            style_counter = Counter(case_styles)
            
            if style_counter:
                dominant_style = style_counter.most_common(1)[0]
                style_name, style_count = dominant_style
                
                # Only learn if there's significant usage
                if style_count >= self.learning_threshold:
                    pattern = CodePattern(
                        name=f"{category}_naming_{style_name}",
                        pattern_type="naming",
                        description=f"Use {style_name} for {category.replace('_', ' ')}",
                        examples=[name['name'] for name in names[:3] if name.get('case_style') == style_name],
                        confidence=min(0.9, quality_score.consistency + 0.1),
                        usage_count=style_count,
                        project_specific=True
                    )
                    patterns.append(pattern)
        
        return patterns
    
    async def _learn_structure_patterns(
        self, 
        structure_patterns: Dict[str, Any], 
        quality_score: QualityScore
    ) -> List[CodePattern]:
        """Learn structural patterns from successful code."""
        
        patterns = []
        
        # Learn from function patterns
        func_patterns = structure_patterns.get('function_patterns', {})
        
        # Async function usage
        if func_patterns.get('async_usage', 0) > 0:
            pattern = CodePattern(
                name="async_function_usage",
                pattern_type="structure",
                description="Use async functions for I/O operations",
                examples=[],
                confidence=quality_score.performance,
                usage_count=func_patterns['async_usage'],
                project_specific=True
            )
            patterns.append(pattern)
        
        # Decorator usage
        if func_patterns.get('decorator_usage'):
            decorators = func_patterns['decorator_usage']
            common_decorators = [dec for dec_list in decorators for dec in dec_list]
            decorator_counter = Counter(common_decorators)
            
            for decorator, count in decorator_counter.most_common(3):
                if count >= self.learning_threshold:
                    pattern = CodePattern(
                        name=f"decorator_usage_{decorator}",
                        pattern_type="structure",
                        description=f"Use @{decorator} decorator pattern",
                        examples=[f"@{decorator}"],
                        confidence=quality_score.code_quality,
                        usage_count=count,
                        project_specific=True
                    )
                    patterns.append(pattern)
        
        return patterns
    
    async def _learn_architecture_patterns(
        self, 
        arch_patterns: Dict[str, Any], 
        quality_score: QualityScore
    ) -> List[CodePattern]:
        """Learn architectural patterns from successful code."""
        
        patterns = []
        
        # Learn from detected architectural patterns
        for pattern_name, usage in arch_patterns.items():
            if isinstance(usage, bool) and usage:
                pattern = CodePattern(
                    name=f"architecture_{pattern_name}",
                    pattern_type="architecture",
                    description=f"Use {pattern_name.replace('_', ' ')} pattern",
                    examples=[],
                    confidence=quality_score.overall,
                    usage_count=1,
                    project_specific=True
                )
                patterns.append(pattern)
            
            elif isinstance(usage, int) and usage >= self.learning_threshold:
                pattern = CodePattern(
                    name=f"architecture_{pattern_name}",
                    pattern_type="architecture", 
                    description=f"Use {pattern_name.replace('_', ' ')} pattern",
                    examples=[],
                    confidence=quality_score.overall,
                    usage_count=usage,
                    project_specific=True
                )
                patterns.append(pattern)
        
        return patterns
    
    async def _update_existing_patterns(
        self, 
        new_patterns: List[CodePattern], 
        execution_result: ExecutionResult
    ) -> None:
        """Update existing patterns with new evidence."""
        
        for new_pattern in new_patterns:
            # Find matching existing pattern
            existing_pattern = self._find_matching_pattern(new_pattern)
            
            if existing_pattern:
                # Boost confidence and usage count
                existing_pattern.confidence = min(
                    1.0, 
                    existing_pattern.confidence + self.confidence_boost_rate
                )
                existing_pattern.usage_count += new_pattern.usage_count
                
                # Update examples
                if new_pattern.examples:
                    existing_pattern.examples.extend(new_pattern.examples)
                    # Keep only unique examples
                    existing_pattern.examples = list(set(existing_pattern.examples))
                    # Limit to reasonable number
                    existing_pattern.examples = existing_pattern.examples[:10]
                
            else:
                # Add new pattern to project context
                self.project_context.patterns.append(new_pattern)
    
    def _find_matching_pattern(self, new_pattern: CodePattern) -> Optional[CodePattern]:
        """Find existing pattern that matches the new pattern."""
        
        for existing in self.project_context.patterns:
            if (existing.name == new_pattern.name or
                (existing.pattern_type == new_pattern.pattern_type and
                 existing.description == new_pattern.description)):
                return existing
        
        return None
    
    async def _analyze_failure_patterns(
        self, 
        execution_result: ExecutionResult, 
        failure_details: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Analyze patterns in failed executions."""
        
        analyses = []
        
        # Analyze error types
        for error in execution_result.errors:
            analysis = {
                'error_type': self._classify_error_type(error),
                'pattern_type': 'error_handling',
                'description': f"Avoid patterns that lead to: {error}",
                'confidence': 0.7,
                'applicable_patterns': []
            }
            analyses.append(analysis)
        
        # Analyze quality score failures
        quality_score = execution_result.quality_score
        
        if quality_score.code_quality < 0.7:
            analyses.append({
                'error_type': 'low_code_quality',
                'pattern_type': 'code_structure',
                'description': 'Improve code organization and readability',
                'confidence': 0.8,
                'applicable_patterns': ['naming', 'structure']
            })
        
        if quality_score.consistency < 0.7:
            analyses.append({
                'error_type': 'inconsistent_style',
                'pattern_type': 'consistency',
                'description': 'Follow established coding conventions',
                'confidence': 0.9,
                'applicable_patterns': ['naming', 'formatting']
            })
        
        return analyses
    
    def _classify_error_type(self, error: str) -> str:
        """Classify error message into error type."""
        error_lower = error.lower()
        
        if 'syntax' in error_lower:
            return 'syntax_error'
        elif 'import' in error_lower or 'module' in error_lower:
            return 'import_error'
        elif 'name' in error_lower and 'not defined' in error_lower:
            return 'name_error'
        elif 'type' in error_lower:
            return 'type_error'
        elif 'attribute' in error_lower:
            return 'attribute_error'
        else:
            return 'runtime_error'
    
    async def _update_anti_patterns(self, failure_analyses: List[Dict[str, Any]]) -> None:
        """Update anti-patterns based on failure analysis."""
        
        for analysis in failure_analyses:
            # Create or update anti-pattern rule
            rule_id = f"avoid_{analysis['error_type']}"
            
            existing_rule = self._find_rule_by_id(rule_id)
            if existing_rule:
                # Update existing rule confidence
                # Rules don't have confidence, so we could track this separately
                pass
            else:
                # Create new anti-pattern rule
                anti_rule = ConsistencyRule(
                    rule_id=rule_id,
                    name=f"Avoid {analysis['error_type']}",
                    description=analysis['description'],
                    pattern="",  # Anti-patterns don't have positive patterns
                    severity="warning",
                    auto_fixable=False,
                    fix_suggestion=analysis['description']
                )
                self.project_context.consistency_rules.append(anti_rule)
    
    def _find_rule_by_id(self, rule_id: str) -> Optional[ConsistencyRule]:
        """Find rule by ID in project context."""
        for rule in self.project_context.consistency_rules:
            if rule.rule_id == rule_id:
                return rule
        return None
    
    async def _record_learning_event(
        self, 
        execution_result: ExecutionResult, 
        patterns: List[CodePattern], 
        context: Dict[str, Any]
    ) -> None:
        """Record learning event in project history."""
        
        history_entry = HistoryEntry(
            timestamp=datetime.now(),
            action="pattern_learning",
            description=f"Learned {len(patterns)} patterns from successful execution",
            success=True,
            quality_score=execution_result.quality_score,
            agent_used=execution_result.agent_used,
            metadata={
                'task_id': execution_result.task_id,
                'patterns_learned': [p.name for p in patterns],
                'learning_context': context
            }
        )
        
        self.project_context.development_history.append(history_entry)
    
    async def _record_failure_learning(
        self, 
        execution_result: ExecutionResult, 
        lessons: List[Lesson], 
        context: Dict[str, Any]
    ) -> None:
        """Record failure learning event."""
        
        history_entry = HistoryEntry(
            timestamp=datetime.now(),
            action="failure_learning",
            description=f"Learned {len(lessons)} lessons from execution failure",
            success=False,
            quality_score=execution_result.quality_score,
            agent_used=execution_result.agent_used,
            metadata={
                'task_id': execution_result.task_id,
                'lessons_learned': [l.title for l in lessons],
                'errors': execution_result.errors,
                'learning_context': context
            }
        )
        
        self.project_context.development_history.append(history_entry)
        self.project_context.lessons_learned.extend(lessons)


class SuccessPatternAnalyzer:
    """Analyzes successful execution patterns to identify reusable strategies."""
    
    def __init__(self, project_context: ProjectContext):
        """Initialize success pattern analyzer."""
        self.project_context = project_context
        self.min_success_threshold = 3
        self.success_rate_threshold = 0.8
    
    async def analyze_success_patterns(self) -> List[SuccessPattern]:
        """Analyze development history for success patterns."""
        
        success_patterns = []
        
        # Get successful executions
        successful_executions = [
            entry for entry in self.project_context.development_history
            if entry.success and entry.quality_score and entry.quality_score.overall >= 0.8
        ]
        
        if len(successful_executions) < self.min_success_threshold:
            logger.info("Not enough successful executions to analyze patterns")
            return success_patterns
        
        # Group by agent type
        agent_patterns = await self._analyze_agent_success_patterns(successful_executions)
        success_patterns.extend(agent_patterns)
        
        # Group by task characteristics
        task_patterns = await self._analyze_task_success_patterns(successful_executions)
        success_patterns.extend(task_patterns)
        
        # Group by time patterns
        time_patterns = await self._analyze_temporal_patterns(successful_executions)
        success_patterns.extend(time_patterns)
        
        return success_patterns
    
    async def _analyze_agent_success_patterns(
        self, 
        executions: List[HistoryEntry]
    ) -> List[SuccessPattern]:
        """Analyze success patterns by agent type."""
        
        patterns = []
        
        # Group by agent
        agent_groups = defaultdict(list)
        for execution in executions:
            if execution.agent_used:
                agent_groups[execution.agent_used].append(execution)
        
        # Analyze each agent's success pattern
        for agent_type, agent_executions in agent_groups.items():
            if len(agent_executions) >= self.min_success_threshold:
                # Calculate success metrics
                total_quality = sum(e.quality_score.overall for e in agent_executions)
                avg_quality = total_quality / len(agent_executions)
                
                # Identify common implementation steps
                common_steps = await self._extract_common_steps(agent_executions)
                
                pattern = SuccessPattern(
                    pattern_id=f"agent_success_{agent_type.value}",
                    name=f"{agent_type.value} Success Pattern",
                    description=f"Successful patterns when using {agent_type.value}",
                    implementation_steps=common_steps,
                    quality_metrics={
                        'average_quality': avg_quality,
                        'execution_count': len(agent_executions),
                        'consistency_score': sum(e.quality_score.consistency for e in agent_executions) / len(agent_executions)
                    },
                    applicable_contexts=[f"agent_{agent_type.value}"],
                    success_rate=1.0  # These are all successful executions
                )
                patterns.append(pattern)
        
        return patterns
    
    async def _analyze_task_success_patterns(
        self, 
        executions: List[HistoryEntry]
    ) -> List[SuccessPattern]:
        """Analyze success patterns by task characteristics."""
        
        patterns = []
        
        # Group by task types (based on action description)
        task_groups = defaultdict(list)
        for execution in executions:
            task_type = self._classify_task_type(execution.description)
            task_groups[task_type].append(execution)
        
        # Analyze each task type
        for task_type, task_executions in task_groups.items():
            if len(task_executions) >= self.min_success_threshold:
                avg_quality = sum(e.quality_score.overall for e in task_executions) / len(task_executions)
                
                pattern = SuccessPattern(
                    pattern_id=f"task_success_{task_type}",
                    name=f"{task_type.title()} Success Pattern",
                    description=f"Successful patterns for {task_type} tasks",
                    implementation_steps=await self._extract_common_steps(task_executions),
                    quality_metrics={'average_quality': avg_quality},
                    applicable_contexts=[f"task_{task_type}"],
                    success_rate=1.0
                )
                patterns.append(pattern)
        
        return patterns
    
    async def _analyze_temporal_patterns(
        self, 
        executions: List[HistoryEntry]
    ) -> List[SuccessPattern]:
        """Analyze temporal success patterns."""
        
        patterns = []
        
        # Analyze by time of day (if relevant)
        # This is a simplified analysis
        
        recent_executions = [
            e for e in executions 
            if (datetime.now() - e.timestamp).days <= 7
        ]
        
        if len(recent_executions) >= self.min_success_threshold:
            avg_quality = sum(e.quality_score.overall for e in recent_executions) / len(recent_executions)
            
            pattern = SuccessPattern(
                pattern_id="recent_success_trend",
                name="Recent Success Trend",
                description="Recent successful execution patterns",
                implementation_steps=await self._extract_common_steps(recent_executions),
                quality_metrics={'average_quality': avg_quality},
                applicable_contexts=["recent_timeframe"],
                success_rate=1.0
            )
            patterns.append(pattern)
        
        return patterns
    
    def _classify_task_type(self, description: str) -> str:
        """Classify task type from description."""
        description_lower = description.lower()
        
        if 'function' in description_lower:
            return 'function_creation'
        elif 'class' in description_lower:
            return 'class_creation'
        elif 'fix' in description_lower or 'bug' in description_lower:
            return 'bug_fixing'
        elif 'refactor' in description_lower:
            return 'refactoring'
        elif 'test' in description_lower:
            return 'testing'
        else:
            return 'general_development'
    
    async def _extract_common_steps(self, executions: List[HistoryEntry]) -> List[str]:
        """Extract common implementation steps from successful executions."""
        
        # This is a simplified implementation
        # In practice, this would analyze the metadata and context
        
        common_steps = [
            "Analyze task requirements",
            "Apply learned patterns",
            "Generate code following conventions",
            "Validate code quality",
            "Apply consistency checks"
        ]
        
        return common_steps


class ContinuousLearner:
    """Manages continuous learning and pattern evolution."""
    
    def __init__(self, project_context: ProjectContext):
        """Initialize continuous learner."""
        self.project_context = project_context
        self.pattern_learner = PatternLearner(project_context)
        self.success_analyzer = SuccessPatternAnalyzer(project_context)
        
        self.learning_enabled = True
        self.max_patterns = 100
        self.pattern_cleanup_threshold = 0.3
    
    async def process_execution_result(
        self, 
        execution_result: ExecutionResult,
        generated_code: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process execution result for learning."""
        
        if not self.learning_enabled:
            return {'learning_disabled': True}
        
        learning_summary = {
            'patterns_learned': 0,
            'lessons_learned': 0,
            'success_patterns_found': 0,
            'timestamp': datetime.now().isoformat()
        }
        
        try:
            if execution_result.success:
                # Learn from success
                patterns = await self.pattern_learner.learn_from_success(
                    execution_result, generated_code, context
                )
                learning_summary['patterns_learned'] = len(patterns)
                
            else:
                # Learn from failure
                failure_details = {
                    'errors': execution_result.errors,
                    'quality_score': execution_result.quality_score,
                    'agent_used': execution_result.agent_used
                }
                
                lessons = await self.pattern_learner.learn_from_failure(
                    execution_result, failure_details, context
                )
                learning_summary['lessons_learned'] = len(lessons)
            
            # Periodically analyze success patterns
            if len(self.project_context.development_history) % 10 == 0:
                success_patterns = await self.success_analyzer.analyze_success_patterns()
                self.project_context.success_patterns.extend(success_patterns)
                learning_summary['success_patterns_found'] = len(success_patterns)
            
            # Periodic cleanup
            if len(self.project_context.patterns) > self.max_patterns:
                await self._cleanup_patterns()
            
            # Update project context timestamp
            self.project_context.update_timestamp()
            
        except Exception as e:
            logger.error(f"Learning process failed: {e}")
            learning_summary['error'] = str(e)
        
        return learning_summary
    
    async def _cleanup_patterns(self) -> None:
        """Clean up low-confidence or unused patterns."""
        
        patterns_to_keep = []
        
        for pattern in self.project_context.patterns:
            # Keep patterns with high confidence or recent usage
            if (pattern.confidence > self.pattern_cleanup_threshold or 
                pattern.usage_count > 5):
                patterns_to_keep.append(pattern)
        
        removed_count = len(self.project_context.patterns) - len(patterns_to_keep)
        self.project_context.patterns = patterns_to_keep
        
        logger.info(f"Cleaned up {removed_count} low-confidence patterns")
    
    def get_learning_statistics(self) -> Dict[str, Any]:
        """Get learning system statistics."""
        
        total_history = len(self.project_context.development_history)
        successful_history = sum(
            1 for h in self.project_context.development_history if h.success
        )
        
        return {
            'total_patterns': len(self.project_context.patterns),
            'total_rules': len(self.project_context.consistency_rules),
            'total_lessons': len(self.project_context.lessons_learned),
            'total_success_patterns': len(self.project_context.success_patterns),
            'development_history_count': total_history,
            'success_rate': successful_history / max(total_history, 1),
            'learning_enabled': self.learning_enabled,
            'avg_pattern_confidence': sum(p.confidence for p in self.project_context.patterns) / max(len(self.project_context.patterns), 1)
        }
    
    def enable_learning(self) -> None:
        """Enable learning system."""
        self.learning_enabled = True
        logger.info("Learning system enabled")
    
    def disable_learning(self) -> None:
        """Disable learning system."""
        self.learning_enabled = False
        logger.info("Learning system disabled")
    
    async def export_learned_knowledge(self) -> Dict[str, Any]:
        """Export learned knowledge for backup or transfer."""
        
        return {
            'patterns': [
                {
                    'name': p.name,
                    'type': p.pattern_type,
                    'description': p.description,
                    'examples': p.examples,
                    'confidence': p.confidence,
                    'usage_count': p.usage_count
                }
                for p in self.project_context.patterns
            ],
            'rules': [
                {
                    'id': r.rule_id,
                    'name': r.name,
                    'description': r.description,
                    'pattern': r.pattern,
                    'severity': r.severity
                }
                for r in self.project_context.consistency_rules
            ],
            'lessons': [
                {
                    'id': l.lesson_id,
                    'title': l.title,
                    'description': l.description,
                    'category': l.category,
                    'confidence': l.confidence
                }
                for l in self.project_context.lessons_learned
            ],
            'export_timestamp': datetime.now().isoformat(),
            'project_name': self.project_context.project_name
        }