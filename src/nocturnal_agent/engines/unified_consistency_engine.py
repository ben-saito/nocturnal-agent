"""Unified consistency engine integrating all consistency features."""

import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from nocturnal_agent.core.models import (
    CodePattern, ConsistencyRule, ConsistencyScore, ProjectContext,
    ExecutionResult, Violation, Correction
)
from nocturnal_agent.engines.pattern_extractor import PatternExtractor
from nocturnal_agent.engines.consistency_engine import ConsistencyChecker
from nocturnal_agent.engines.learning_engine import ContinuousLearner


logger = logging.getLogger(__name__)


class UnifiedConsistencyEngine:
    """Unified consistency engine with pattern extraction, checking, and learning."""
    
    def __init__(self, project_context: ProjectContext):
        """Initialize unified consistency engine."""
        self.project_context = project_context
        
        # Initialize sub-engines
        self.pattern_extractor = PatternExtractor()
        self.consistency_checker = ConsistencyChecker(project_context)
        self.continuous_learner = ContinuousLearner(project_context)
        
        # Engine configuration
        self.auto_extract_patterns = True
        self.auto_learning_enabled = True
        self.consistency_threshold = 0.85
        
        # Cache for performance
        self._pattern_cache: Dict[str, Dict] = {}
        self._consistency_cache: Dict[str, ConsistencyScore] = {}
    
    async def initialize_project_patterns(
        self, 
        project_directory: str,
        force_reextract: bool = False
    ) -> Dict[str, Any]:
        """Initialize project patterns by analyzing existing codebase."""
        
        if not force_reextract and self.project_context.patterns:
            logger.info("Using existing project patterns")
            return {'status': 'using_existing', 'patterns_count': len(self.project_context.patterns)}
        
        logger.info(f"Extracting patterns from project directory: {project_directory}")
        
        try:
            # Extract patterns from codebase
            extracted_patterns = await self.pattern_extractor.extract_patterns_from_directory(
                project_directory
            )
            
            # Generate code patterns and rules
            code_patterns = self.pattern_extractor.generate_code_patterns(
                extracted_patterns, 
                self.project_context.project_name
            )
            
            consistency_rules = self.pattern_extractor.generate_consistency_rules(
                extracted_patterns,
                self.project_context.project_name
            )
            
            # Update project context
            self.project_context.patterns.extend(code_patterns)
            self.project_context.consistency_rules.extend(consistency_rules)
            
            # Update consistency checker with new rules
            self.consistency_checker.update_rules(consistency_rules)
            
            # Cache extracted patterns
            self._pattern_cache[project_directory] = extracted_patterns
            
            logger.info(f"Extracted {len(code_patterns)} patterns and {len(consistency_rules)} rules")
            
            return {
                'status': 'patterns_extracted',
                'patterns_count': len(code_patterns),
                'rules_count': len(consistency_rules),
                'files_analyzed': len(extracted_patterns.get('files_analyzed', [])),
                'consistency_score': extracted_patterns.get('insights', {}).get('consistency_score', 0.0)
            }
            
        except Exception as e:
            logger.error(f"Failed to initialize project patterns: {e}")
            return {'status': 'error', 'error': str(e)}
    
    async def check_code_consistency(
        self, 
        code: str, 
        file_path: Optional[str] = None,
        use_cache: bool = True
    ) -> ConsistencyScore:
        """Check code consistency against project patterns."""
        
        cache_key = f"{hash(code)}_{file_path}"
        
        # Check cache first
        if use_cache and cache_key in self._consistency_cache:
            return self._consistency_cache[cache_key]
        
        try:
            # Perform consistency check
            consistency_score = await self.consistency_checker.check_consistency(
                code, file_path
            )
            
            # Cache result
            if use_cache:
                self._consistency_cache[cache_key] = consistency_score
            
            # Log significant inconsistencies
            if consistency_score.overall < self.consistency_threshold:
                logger.warning(f"Code consistency below threshold: {consistency_score.overall:.3f}")
                for violation in consistency_score.violations:
                    logger.debug(f"Violation: {violation}")
            
            return consistency_score
            
        except Exception as e:
            logger.error(f"Consistency check failed: {e}")
            return ConsistencyScore(overall=0.5)  # Conservative fallback
    
    async def process_execution_result(
        self,
        execution_result: ExecutionResult,
        generated_code: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Process execution result for learning and improvement."""
        
        if not self.auto_learning_enabled:
            return {'learning_disabled': True}
        
        context = context or {}
        
        try:
            # Learn from execution result
            learning_summary = await self.continuous_learner.process_execution_result(
                execution_result, generated_code, context
            )
            
            # Update consistency checker with new learned rules
            if learning_summary.get('patterns_learned', 0) > 0:
                self.consistency_checker.update_rules(self.project_context.consistency_rules)
                # Clear cache to reflect new rules
                self._consistency_cache.clear()
            
            return learning_summary
            
        except Exception as e:
            logger.error(f"Failed to process execution result: {e}")
            return {'error': str(e)}
    
    async def suggest_improvements(
        self, 
        code: str, 
        file_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """Suggest code improvements based on consistency analysis."""
        
        try:
            # Check consistency
            consistency_score = await self.check_code_consistency(code, file_path)
            
            # Generate suggestions
            suggestions = {
                'consistency_score': consistency_score.overall,
                'violations': consistency_score.violations,
                'suggestions': consistency_score.suggestions,
                'improvements': []
            }
            
            # Specific improvement suggestions based on violations
            violation_types = {}
            for violation in consistency_score.violations:
                vtype = violation.get('rule', 'unknown')
                if vtype not in violation_types:
                    violation_types[vtype] = []
                violation_types[vtype].append(violation)
            
            # Generate targeted improvements
            for violation_type, violations in violation_types.items():
                count = len(violations)
                if count > 1:
                    suggestions['improvements'].append(
                        f"Fix {count} {violation_type} violations to improve consistency"
                    )
                else:
                    suggestions['improvements'].append(
                        f"Fix {violation_type} violation: {violations[0].get('message', '')}"
                    )
            
            # Pattern-based suggestions
            pattern_suggestions = await self._generate_pattern_suggestions(code, consistency_score)
            suggestions['improvements'].extend(pattern_suggestions)
            
            return suggestions
            
        except Exception as e:
            logger.error(f"Failed to suggest improvements: {e}")
            return {'error': str(e)}
    
    async def _generate_pattern_suggestions(
        self, 
        code: str, 
        consistency_score: ConsistencyScore
    ) -> List[str]:
        """Generate suggestions based on learned patterns."""
        
        suggestions = []
        
        # Suggest patterns based on project history
        for pattern in self.project_context.patterns[:5]:  # Top 5 patterns
            if pattern.confidence > 0.8 and pattern.usage_count > 3:
                if pattern.pattern_type == "naming" and consistency_score.naming_conventions < 0.8:
                    suggestions.append(f"Consider applying {pattern.description}")
                elif pattern.pattern_type == "structure" and consistency_score.code_structure < 0.8:
                    suggestions.append(f"Consider using {pattern.description}")
        
        return suggestions
    
    async def auto_fix_violations(
        self, 
        code: str, 
        file_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """Automatically fix fixable violations."""
        
        try:
            # Check consistency to get violations
            consistency_score = await self.check_code_consistency(code, file_path)
            
            # Find fixable violations
            fixable_violations = [
                v for v in consistency_score.violations 
                if v.get('auto_fixable', False)
            ]
            
            if not fixable_violations:
                return {
                    'status': 'no_fixable_violations',
                    'original_code': code,
                    'fixed_code': code
                }
            
            # Generate corrections
            violation_objects = [
                Violation(
                    violation_id=v['id'],
                    rule_id=v['rule'],
                    severity=v['severity'],
                    message=v['message'],
                    file_path=v['file'],
                    line_number=v['line'],
                    auto_fixable=v['auto_fixable']
                )
                for v in fixable_violations
            ]
            
            corrections = await self.consistency_checker.suggest_corrections(violation_objects)
            
            # Apply corrections
            fixed_code = code
            applied_fixes = []
            
            for correction in corrections:
                if correction.confidence > 0.7:
                    fixed_code = fixed_code.replace(
                        correction.original_code, 
                        correction.corrected_code
                    )
                    applied_fixes.append(correction.explanation)
            
            return {
                'status': 'fixes_applied',
                'original_code': code,
                'fixed_code': fixed_code,
                'fixes_applied': applied_fixes,
                'violations_fixed': len(applied_fixes)
            }
            
        except Exception as e:
            logger.error(f"Auto-fix failed: {e}")
            return {'status': 'error', 'error': str(e)}
    
    async def get_project_insights(self) -> Dict[str, Any]:
        """Get insights about project consistency and patterns."""
        
        try:
            # Learning statistics
            learning_stats = self.continuous_learner.get_learning_statistics()
            
            # Rule statistics
            rule_stats = self.consistency_checker.get_rule_statistics()
            
            # Pattern analysis
            pattern_stats = self._analyze_pattern_statistics()
            
            # Recent performance
            recent_performance = self._analyze_recent_performance()
            
            return {
                'project_name': self.project_context.project_name,
                'learning_statistics': learning_stats,
                'rule_statistics': rule_stats,
                'pattern_statistics': pattern_stats,
                'recent_performance': recent_performance,
                'consistency_threshold': self.consistency_threshold,
                'auto_learning_enabled': self.auto_learning_enabled,
                'patterns_initialized': len(self.project_context.patterns) > 0
            }
            
        except Exception as e:
            logger.error(f"Failed to get project insights: {e}")
            return {'error': str(e)}
    
    def _analyze_pattern_statistics(self) -> Dict[str, Any]:
        """Analyze pattern usage statistics."""
        
        patterns = self.project_context.patterns
        
        if not patterns:
            return {'total_patterns': 0}
        
        # Group by type
        pattern_types = {}
        for pattern in patterns:
            ptype = pattern.pattern_type
            if ptype not in pattern_types:
                pattern_types[ptype] = []
            pattern_types[ptype].append(pattern)
        
        # Calculate statistics
        avg_confidence = sum(p.confidence for p in patterns) / len(patterns)
        high_confidence_patterns = sum(1 for p in patterns if p.confidence > 0.8)
        
        return {
            'total_patterns': len(patterns),
            'pattern_types': {ptype: len(plist) for ptype, plist in pattern_types.items()},
            'average_confidence': avg_confidence,
            'high_confidence_patterns': high_confidence_patterns,
            'most_used_pattern': max(patterns, key=lambda p: p.usage_count).name if patterns else None
        }
    
    def _analyze_recent_performance(self) -> Dict[str, Any]:
        """Analyze recent consistency performance."""
        
        # Get recent history entries
        from datetime import datetime, timedelta
        
        recent_cutoff = datetime.now() - timedelta(days=7)
        recent_entries = [
            entry for entry in self.project_context.development_history
            if entry.timestamp >= recent_cutoff
        ]
        
        if not recent_entries:
            return {'no_recent_data': True}
        
        # Calculate recent performance metrics
        successful_entries = [e for e in recent_entries if e.success]
        
        avg_quality = 0.0
        if successful_entries:
            quality_scores = [e.quality_score.overall for e in successful_entries if e.quality_score]
            if quality_scores:
                avg_quality = sum(quality_scores) / len(quality_scores)
        
        return {
            'recent_executions': len(recent_entries),
            'successful_executions': len(successful_entries),
            'success_rate': len(successful_entries) / len(recent_entries),
            'average_quality': avg_quality,
            'period_days': 7
        }
    
    def configure_engine(self, config: Dict[str, Any]) -> None:
        """Configure engine settings."""
        
        if 'consistency_threshold' in config:
            self.consistency_threshold = config['consistency_threshold']
            
        if 'auto_extract_patterns' in config:
            self.auto_extract_patterns = config['auto_extract_patterns']
            
        if 'auto_learning_enabled' in config:
            self.auto_learning_enabled = config['auto_learning_enabled']
            if config['auto_learning_enabled']:
                self.continuous_learner.enable_learning()
            else:
                self.continuous_learner.disable_learning()
        
        logger.info(f"Consistency engine configured: threshold={self.consistency_threshold}")
    
    def clear_caches(self) -> None:
        """Clear all caches."""
        self._pattern_cache.clear()
        self._consistency_cache.clear()
        logger.info("Consistency engine caches cleared")
    
    async def export_project_knowledge(self) -> Dict[str, Any]:
        """Export all learned project knowledge."""
        
        try:
            # Export from learning engine
            learned_knowledge = await self.continuous_learner.export_learned_knowledge()
            
            # Add engine-specific data
            engine_data = {
                'consistency_threshold': self.consistency_threshold,
                'auto_learning_enabled': self.auto_learning_enabled,
                'cache_statistics': {
                    'pattern_cache_size': len(self._pattern_cache),
                    'consistency_cache_size': len(self._consistency_cache)
                }
            }
            
            return {
                **learned_knowledge,
                'engine_configuration': engine_data
            }
            
        except Exception as e:
            logger.error(f"Failed to export project knowledge: {e}")
            return {'error': str(e)}