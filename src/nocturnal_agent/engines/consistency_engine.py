"""Consistency engine for real-time code consistency checking."""

import ast
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from nocturnal_agent.core.models import (
    CodePattern, ConsistencyRule, ConsistencyScore, Violation, Correction, ProjectContext
)
from nocturnal_agent.engines.pattern_extractor import PatternExtractor, CodeAnalyzer


logger = logging.getLogger(__name__)


class ConsistencyChecker:
    """Real-time consistency checker for generated code."""
    
    def __init__(self, project_context: ProjectContext):
        """Initialize consistency checker."""
        self.project_context = project_context
        self.consistency_threshold = 0.85
        self.cached_violations: Dict[str, List[Violation]] = {}
        
        # Built-in rules that are always applied
        self.builtin_rules = self._create_builtin_rules()
        
        # Combine project rules with built-in rules
        self.active_rules = self.builtin_rules + project_context.consistency_rules
    
    def _create_builtin_rules(self) -> List[ConsistencyRule]:
        """Create built-in consistency rules."""
        return [
            # Python specific rules
            ConsistencyRule(
                rule_id="python_function_naming",
                name="Python function naming",
                description="Functions should use snake_case",
                pattern=r"^[a-z_][a-z0-9_]*$",
                severity="warning",
                auto_fixable=False,
                fix_suggestion="Use snake_case for function names (e.g., my_function)"
            ),
            ConsistencyRule(
                rule_id="python_class_naming",
                name="Python class naming", 
                description="Classes should use PascalCase",
                pattern=r"^[A-Z][a-zA-Z0-9]*$",
                severity="warning",
                auto_fixable=False,
                fix_suggestion="Use PascalCase for class names (e.g., MyClass)"
            ),
            ConsistencyRule(
                rule_id="python_constant_naming",
                name="Python constant naming",
                description="Constants should use UPPER_CASE",
                pattern=r"^[A-Z][A-Z0-9_]*$",
                severity="info",
                auto_fixable=False,
                fix_suggestion="Use UPPER_CASE for constants (e.g., MAX_SIZE)"
            ),
            ConsistencyRule(
                rule_id="no_single_letter_vars",
                name="Avoid single letter variables",
                description="Variables should have descriptive names, not single letters",
                pattern=r"^(?![a-z]$)[a-zA-Z_][a-zA-Z0-9_]*$",
                severity="info",
                auto_fixable=False,
                fix_suggestion="Use descriptive variable names instead of single letters"
            ),
            # Documentation rules
            ConsistencyRule(
                rule_id="function_docstring",
                name="Function docstring requirement",
                description="Public functions should have docstrings",
                pattern="",  # Special rule handled separately
                severity="info",
                auto_fixable=True,
                fix_suggestion="Add docstring to describe function purpose"
            ),
            ConsistencyRule(
                rule_id="class_docstring", 
                name="Class docstring requirement",
                description="Classes should have docstrings",
                pattern="",  # Special rule handled separately
                severity="info",
                auto_fixable=True,
                fix_suggestion="Add docstring to describe class purpose"
            )
        ]
    
    async def check_consistency(self, code: str, file_path: Optional[str] = None) -> ConsistencyScore:
        """Check code consistency against project patterns and rules."""
        violations = []
        suggestions = []
        
        try:
            # Parse code for analysis
            if file_path and file_path.endswith('.py'):
                ast_violations = await self._check_python_consistency(code, file_path)
                violations.extend(ast_violations)
            else:
                # Generic text-based checking
                text_violations = await self._check_text_consistency(code, file_path)
                violations.extend(text_violations)
            
            # Check against project-specific patterns
            pattern_violations = await self._check_pattern_consistency(code, file_path)
            violations.extend(pattern_violations)
            
            # Generate suggestions based on violations
            suggestions = self._generate_suggestions(violations)
            
            # Calculate consistency score
            score = self._calculate_consistency_score(violations, code)
            
            # Cache violations for future reference
            if file_path:
                self.cached_violations[file_path] = violations
            
            return ConsistencyScore(
                overall=score,
                naming_conventions=self._calculate_naming_score(violations),
                code_structure=self._calculate_structure_score(violations),
                documentation=self._calculate_documentation_score(violations),
                architecture_alignment=self._calculate_architecture_score(violations),
                violations=[self._violation_to_dict(v) for v in violations],
                suggestions=suggestions
            )
            
        except Exception as e:
            logger.error(f"Consistency check failed: {e}")
            return ConsistencyScore(overall=0.5)  # Conservative score on error
    
    async def _check_python_consistency(self, code: str, file_path: str) -> List[Violation]:
        """Check Python code consistency using AST analysis."""
        violations = []
        
        try:
            tree = ast.parse(code)
            analyzer = CodeAnalyzer()
            analyzer.visit(tree)
            
            # Check function naming
            for func_info in analyzer.patterns['functions']:
                violations.extend(self._check_function_consistency(func_info, file_path))
            
            # Check class naming
            for class_info in analyzer.patterns['classes']:
                violations.extend(self._check_class_consistency(class_info, file_path))
            
            # Check variable naming
            for var_info in analyzer.patterns['variables']:
                violations.extend(self._check_variable_consistency(var_info, file_path))
            
            # Check documentation
            violations.extend(self._check_documentation_consistency(analyzer.patterns, file_path))
            
        except SyntaxError as e:
            violations.append(Violation(
                violation_id=f"syntax_error_{hash(str(e))}",
                rule_id="syntax_error",
                severity="error",
                message=f"Syntax error: {e}",
                file_path=file_path or "",
                line_number=getattr(e, 'lineno', 0)
            ))
        
        return violations
    
    async def _check_text_consistency(self, code: str, file_path: Optional[str]) -> List[Violation]:
        """Check consistency using text-based rules."""
        violations = []
        
        lines = code.split('\n')
        
        for line_num, line in enumerate(lines, 1):
            # Check for common anti-patterns
            if re.search(r'\btodo\b|\bfixme\b|\bhack\b', line.lower()):
                violations.append(Violation(
                    violation_id=f"todo_comment_{file_path}_{line_num}",
                    rule_id="no_todo_comments",
                    severity="info",
                    message="TODO/FIXME comment found",
                    file_path=file_path or "",
                    line_number=line_num,
                    suggestion="Complete the TODO item or create a proper issue"
                ))
            
            # Check line length (configurable)
            if len(line) > 100:
                violations.append(Violation(
                    violation_id=f"line_length_{file_path}_{line_num}",
                    rule_id="max_line_length",
                    severity="info",
                    message=f"Line too long ({len(line)} characters)",
                    file_path=file_path or "",
                    line_number=line_num,
                    suggestion="Break long line into multiple lines"
                ))
            
            # Check for trailing whitespace
            if line.endswith(' ') or line.endswith('\t'):
                violations.append(Violation(
                    violation_id=f"trailing_whitespace_{file_path}_{line_num}",
                    rule_id="no_trailing_whitespace",
                    severity="info",
                    message="Trailing whitespace found",
                    file_path=file_path or "",
                    line_number=line_num,
                    auto_fixable=True,
                    suggestion="Remove trailing whitespace"
                ))
        
        return violations
    
    async def _check_pattern_consistency(self, code: str, file_path: Optional[str]) -> List[Violation]:
        """Check consistency against project-specific patterns."""
        violations = []
        
        # Check against learned patterns
        for pattern in self.project_context.patterns:
            if pattern.pattern_type == "naming":
                # Check if code follows the learned naming pattern
                pattern_violations = self._check_naming_pattern(code, pattern, file_path)
                violations.extend(pattern_violations)
            
            elif pattern.pattern_type == "structure":
                # Check structural consistency
                structure_violations = self._check_structure_pattern(code, pattern, file_path)
                violations.extend(structure_violations)
        
        return violations
    
    def _check_function_consistency(self, func_info: Dict, file_path: str) -> List[Violation]:
        """Check function consistency against rules."""
        violations = []
        
        # Check naming convention
        func_name = func_info['name']
        
        # Apply function naming rule
        naming_rule = self._get_rule_by_id("python_function_naming")
        if naming_rule and not re.match(naming_rule.pattern, func_name):
            violations.append(Violation(
                violation_id=f"func_naming_{file_path}_{func_info.get('line_number', 0)}",
                rule_id=naming_rule.rule_id,
                severity=naming_rule.severity,
                message=f"Function '{func_name}' doesn't follow naming convention",
                file_path=file_path,
                line_number=func_info.get('line_number', 0),
                suggestion=naming_rule.fix_suggestion
            ))
        
        # Check for single letter function names
        single_letter_rule = self._get_rule_by_id("no_single_letter_vars")
        if single_letter_rule and len(func_name) == 1:
            violations.append(Violation(
                violation_id=f"single_letter_func_{file_path}_{func_info.get('line_number', 0)}",
                rule_id="no_single_letter_functions",
                severity="warning",
                message=f"Function '{func_name}' has single letter name",
                file_path=file_path,
                line_number=func_info.get('line_number', 0),
                suggestion="Use descriptive function name"
            ))
        
        # Check complexity
        complexity = func_info.get('complexity', 1)
        if complexity > 10:
            violations.append(Violation(
                violation_id=f"high_complexity_{file_path}_{func_info.get('line_number', 0)}",
                rule_id="function_complexity",
                severity="warning",
                message=f"Function '{func_name}' has high complexity ({complexity})",
                file_path=file_path,
                line_number=func_info.get('line_number', 0),
                suggestion="Consider breaking function into smaller functions"
            ))
        
        return violations
    
    def _check_class_consistency(self, class_info: Dict, file_path: str) -> List[Violation]:
        """Check class consistency against rules."""
        violations = []
        
        class_name = class_info['name']
        
        # Check naming convention
        naming_rule = self._get_rule_by_id("python_class_naming")
        if naming_rule and not re.match(naming_rule.pattern, class_name):
            violations.append(Violation(
                violation_id=f"class_naming_{file_path}_{class_info.get('line_number', 0)}",
                rule_id=naming_rule.rule_id,
                severity=naming_rule.severity,
                message=f"Class '{class_name}' doesn't follow naming convention",
                file_path=file_path,
                line_number=class_info.get('line_number', 0),
                suggestion=naming_rule.fix_suggestion
            ))
        
        return violations
    
    def _check_variable_consistency(self, var_info: Dict, file_path: str) -> List[Violation]:
        """Check variable consistency against rules."""
        violations = []
        
        var_name = var_info['name']
        
        # Check for single letter variables (except common ones like i, j, k in loops)
        if (len(var_name) == 1 and 
            var_name not in ['i', 'j', 'k', 'x', 'y', 'z'] and
            var_info.get('context') != 'loop'):
            
            violations.append(Violation(
                violation_id=f"single_letter_var_{file_path}_{var_info.get('line_number', 0)}",
                rule_id="no_single_letter_vars",
                severity="info",
                message=f"Variable '{var_name}' has single letter name",
                file_path=file_path,
                line_number=var_info.get('line_number', 0),
                suggestion="Use descriptive variable name"
            ))
        
        # Check constant naming
        if var_info.get('is_constant'):
            constant_rule = self._get_rule_by_id("python_constant_naming")
            if constant_rule and not re.match(constant_rule.pattern, var_name):
                violations.append(Violation(
                    violation_id=f"constant_naming_{file_path}_{var_info.get('line_number', 0)}",
                    rule_id=constant_rule.rule_id,
                    severity=constant_rule.severity,
                    message=f"Constant '{var_name}' doesn't follow naming convention",
                    file_path=file_path,
                    line_number=var_info.get('line_number', 0),
                    suggestion=constant_rule.fix_suggestion
                ))
        
        return violations
    
    def _check_documentation_consistency(self, patterns: Dict, file_path: str) -> List[Violation]:
        """Check documentation consistency."""
        violations = []
        
        # Check function docstrings
        for func_info in patterns['functions']:
            if (not func_info.get('is_private') and 
                not func_info.get('docstring') and
                func_info.get('name', '').startswith('_') is False):
                
                violations.append(Violation(
                    violation_id=f"missing_func_docstring_{file_path}_{func_info.get('line_number', 0)}",
                    rule_id="function_docstring",
                    severity="info",
                    message=f"Public function '{func_info['name']}' missing docstring",
                    file_path=file_path,
                    line_number=func_info.get('line_number', 0),
                    auto_fixable=True,
                    suggestion="Add docstring to describe function purpose and parameters"
                ))
        
        # Check class docstrings
        for class_info in patterns['classes']:
            if not class_info.get('docstring'):
                violations.append(Violation(
                    violation_id=f"missing_class_docstring_{file_path}_{class_info.get('line_number', 0)}",
                    rule_id="class_docstring",
                    severity="info",
                    message=f"Class '{class_info['name']}' missing docstring",
                    file_path=file_path,
                    line_number=class_info.get('line_number', 0),
                    auto_fixable=True,
                    suggestion="Add docstring to describe class purpose"
                ))
        
        return violations
    
    def _check_naming_pattern(self, code: str, pattern: CodePattern, file_path: Optional[str]) -> List[Violation]:
        """Check code against learned naming patterns."""
        violations = []
        
        # Implementation would check if new code follows the learned patterns
        # This is a simplified version
        
        return violations
    
    def _check_structure_pattern(self, code: str, pattern: CodePattern, file_path: Optional[str]) -> List[Violation]:
        """Check code against learned structural patterns.""" 
        violations = []
        
        # Implementation would check structural consistency
        # This is a simplified version
        
        return violations
    
    def _get_rule_by_id(self, rule_id: str) -> Optional[ConsistencyRule]:
        """Get rule by ID."""
        for rule in self.active_rules:
            if rule.rule_id == rule_id:
                return rule
        return None
    
    def _calculate_consistency_score(self, violations: List[Violation], code: str) -> float:
        """Calculate overall consistency score."""
        if not code.strip():
            return 0.0
        
        # Base score
        base_score = 1.0
        
        # Penalty for violations based on severity
        penalty = 0.0
        for violation in violations:
            if violation.severity == "error":
                penalty += 0.2
            elif violation.severity == "warning":
                penalty += 0.1
            elif violation.severity == "info":
                penalty += 0.05
        
        # Normalize penalty based on code size
        lines_of_code = len(code.split('\n'))
        normalized_penalty = penalty / max(lines_of_code / 10, 1)
        
        final_score = max(0.0, base_score - normalized_penalty)
        return min(final_score, 1.0)
    
    def _calculate_naming_score(self, violations: List[Violation]) -> float:
        """Calculate naming conventions score."""
        naming_violations = [v for v in violations if 'naming' in v.rule_id]
        
        if not naming_violations:
            return 1.0
        
        # Penalty based on naming violations
        penalty = len(naming_violations) * 0.1
        return max(0.0, 1.0 - penalty)
    
    def _calculate_structure_score(self, violations: List[Violation]) -> float:
        """Calculate code structure score."""
        structure_violations = [v for v in violations if 
                              v.rule_id in ['function_complexity', 'line_length']]
        
        if not structure_violations:
            return 1.0
        
        penalty = len(structure_violations) * 0.15
        return max(0.0, 1.0 - penalty)
    
    def _calculate_documentation_score(self, violations: List[Violation]) -> float:
        """Calculate documentation score."""
        doc_violations = [v for v in violations if 'docstring' in v.rule_id]
        
        if not doc_violations:
            return 1.0
        
        penalty = len(doc_violations) * 0.1
        return max(0.0, 1.0 - penalty)
    
    def _calculate_architecture_score(self, violations: List[Violation]) -> float:
        """Calculate architecture alignment score."""
        # Check alignment with project patterns
        # For now, return based on general violations
        arch_violations = [v for v in violations if v.severity == "error"]
        
        if not arch_violations:
            return 0.9
        
        penalty = len(arch_violations) * 0.2
        return max(0.0, 0.9 - penalty)
    
    def _generate_suggestions(self, violations: List[Violation]) -> List[str]:
        """Generate improvement suggestions based on violations."""
        suggestions = []
        
        # Group violations by type
        violation_types = {}
        for violation in violations:
            if violation.rule_id not in violation_types:
                violation_types[violation.rule_id] = []
            violation_types[violation.rule_id].append(violation)
        
        # Generate suggestions for each type
        for rule_id, rule_violations in violation_types.items():
            count = len(rule_violations)
            if count == 1:
                suggestions.append(rule_violations[0].suggestion or f"Fix {rule_id} violation")
            else:
                suggestions.append(f"Fix {count} {rule_id} violations")
        
        return suggestions
    
    def _violation_to_dict(self, violation: Violation) -> Dict[str, Any]:
        """Convert violation to dictionary."""
        return {
            'id': violation.violation_id,
            'rule': violation.rule_id,
            'severity': violation.severity,
            'message': violation.message,
            'file': violation.file_path,
            'line': violation.line_number,
            'suggestion': violation.suggestion,
            'auto_fixable': violation.auto_fixable
        }
    
    async def suggest_corrections(self, violations: List[Violation]) -> List[Correction]:
        """Suggest corrections for violations."""
        corrections = []
        
        for violation in violations:
            if violation.auto_fixable:
                correction = await self._generate_correction(violation)
                if correction:
                    corrections.append(correction)
        
        return corrections
    
    async def _generate_correction(self, violation: Violation) -> Optional[Correction]:
        """Generate correction for a specific violation."""
        if violation.rule_id == "no_trailing_whitespace":
            return Correction(
                violation_id=violation.violation_id,
                original_code="line with trailing spaces   ",
                corrected_code="line with trailing spaces",
                explanation="Removed trailing whitespace",
                confidence=0.95
            )
        
        elif "docstring" in violation.rule_id:
            if "function" in violation.rule_id:
                return Correction(
                    violation_id=violation.violation_id,
                    original_code="def my_function():",
                    corrected_code='def my_function():\n    """Function description."""',
                    explanation="Added function docstring",
                    confidence=0.7
                )
        
        return None
    
    def update_rules(self, new_rules: List[ConsistencyRule]) -> None:
        """Update consistency rules."""
        # Remove old project rules and add new ones
        self.active_rules = self.builtin_rules + self.project_context.consistency_rules + new_rules
        logger.info(f"Updated consistency rules: {len(self.active_rules)} active rules")
    
    def get_rule_statistics(self) -> Dict[str, Any]:
        """Get statistics about rule violations."""
        stats = {
            'total_rules': len(self.active_rules),
            'builtin_rules': len(self.builtin_rules),
            'project_rules': len(self.project_context.consistency_rules),
            'cached_violations': {file_path: len(violations) 
                                for file_path, violations in self.cached_violations.items()}
        }
        
        return stats