"""Quality evaluation engine with static analysis integration."""

import asyncio
import json
import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from nocturnal_agent.core.config import QualityConfig
from nocturnal_agent.core.models import QualityScore, ProjectContext
from nocturnal_agent.agents.local_llm import LocalLLMAgent


logger = logging.getLogger(__name__)


class StaticAnalysisResult:
    """Result from static analysis tools."""
    
    def __init__(self, tool: str, exit_code: int, stdout: str, stderr: str):
        self.tool = tool
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr
        self.issues: List[Dict[str, Any]] = []
        self.score: float = 0.0
        
        self._parse_output()
    
    def _parse_output(self) -> None:
        """Parse tool output and extract issues."""
        if self.tool == "pylint":
            self._parse_pylint_output()
        elif self.tool == "flake8":
            self._parse_flake8_output()
        elif self.tool == "mypy":
            self._parse_mypy_output()
        else:
            logger.warning(f"Unknown static analysis tool: {self.tool}")
    
    def _parse_pylint_output(self) -> None:
        """Parse pylint output."""
        try:
            # Try to parse as JSON first
            if self.stdout.strip().startswith('{'):
                data = json.loads(self.stdout)
                self.issues = data if isinstance(data, list) else []
            else:
                # Parse text output
                lines = self.stdout.split('\n')
                for line in lines:
                    if ':' in line and any(level in line for level in ['E:', 'W:', 'C:', 'R:']):
                        parts = line.split(':', 4)
                        if len(parts) >= 5:
                            self.issues.append({
                                "file": parts[0],
                                "line": int(parts[1]) if parts[1].isdigit() else 0,
                                "column": int(parts[2]) if parts[2].isdigit() else 0,
                                "type": parts[3].strip(),
                                "message": parts[4].strip()
                            })
            
            # Calculate score based on issue severity
            error_count = sum(1 for issue in self.issues if issue.get("type", "").startswith("E"))
            warning_count = sum(1 for issue in self.issues if issue.get("type", "").startswith("W"))
            total_issues = len(self.issues)
            
            if total_issues == 0:
                self.score = 1.0
            else:
                # Penalty: errors -0.1, warnings -0.05 per issue
                penalty = (error_count * 0.1) + (warning_count * 0.05)
                self.score = max(0.0, 1.0 - penalty)
                
        except Exception as e:
            logger.error(f"Failed to parse pylint output: {e}")
            self.score = 0.5  # Conservative score on parse failure
    
    def _parse_flake8_output(self) -> None:
        """Parse flake8 output."""
        try:
            lines = self.stdout.split('\n')
            for line in lines:
                if ':' in line:
                    parts = line.split(':', 3)
                    if len(parts) >= 4:
                        self.issues.append({
                            "file": parts[0],
                            "line": int(parts[1]) if parts[1].isdigit() else 0,
                            "column": int(parts[2]) if parts[2].isdigit() else 0,
                            "message": parts[3].strip()
                        })
            
            # Simple scoring: -0.05 per issue
            penalty = len(self.issues) * 0.05
            self.score = max(0.0, 1.0 - penalty)
            
        except Exception as e:
            logger.error(f"Failed to parse flake8 output: {e}")
            self.score = 0.5
    
    def _parse_mypy_output(self) -> None:
        """Parse mypy output."""
        try:
            lines = self.stdout.split('\n')
            for line in lines:
                if ':' in line and 'error:' in line:
                    parts = line.split(':', 3)
                    if len(parts) >= 4:
                        self.issues.append({
                            "file": parts[0],
                            "line": int(parts[1]) if parts[1].isdigit() else 0,
                            "type": "error",
                            "message": parts[3].strip()
                        })
            
            # Type errors are more serious: -0.1 per issue
            penalty = len(self.issues) * 0.1
            self.score = max(0.0, 1.0 - penalty)
            
        except Exception as e:
            logger.error(f"Failed to parse mypy output: {e}")
            self.score = 0.5


class QualityEvaluator:
    """Comprehensive quality evaluation engine."""
    
    def __init__(self, config: QualityConfig, llm_agent: Optional[LocalLLMAgent] = None):
        """Initialize quality evaluator."""
        self.config = config
        self.llm_agent = llm_agent
        self.static_analysis_cache: Dict[str, StaticAnalysisResult] = {}
    
    async def evaluate_code(
        self, 
        code: str, 
        file_path: Optional[str] = None,
        project_context: Optional[ProjectContext] = None
    ) -> QualityScore:
        """Evaluate code quality comprehensively."""
        
        # Determine file type for appropriate analysis
        file_extension = self._get_file_extension(file_path, code)
        
        # Parallel evaluation
        tasks = []
        
        # Static analysis
        if self.config.enable_static_analysis:
            tasks.append(self._run_static_analysis(code, file_extension, file_path))
        
        # LLM-based evaluation
        if self.llm_agent:
            context = self._build_evaluation_context(project_context)
            tasks.append(self.llm_agent.evaluate_quality(code, context))
        
        # Test coverage analysis (if applicable)
        tasks.append(self._analyze_test_coverage(code, file_path))
        
        # Security analysis
        tasks.append(self._analyze_security(code, file_extension))
        
        # Performance analysis
        tasks.append(self._analyze_performance(code, file_extension))
        
        # Execute all evaluations in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Combine results
        static_scores = results[0] if not isinstance(results[0], Exception) else {}
        llm_score = results[1] if len(results) > 1 and not isinstance(results[1], Exception) else None
        test_coverage = results[-3] if len(results) > 2 and not isinstance(results[-3], Exception) else 0.0
        security_score = results[-2] if len(results) > 2 and not isinstance(results[-2], Exception) else 0.5
        performance_score = results[-1] if len(results) > 2 and not isinstance(results[-1], Exception) else 0.5
        
        # Calculate final quality score
        quality_score = self._calculate_final_score(
            static_scores, llm_score, test_coverage, security_score, performance_score
        )
        
        logger.info(f"Quality evaluation completed: overall={quality_score.overall:.3f}")
        
        return quality_score
    
    async def _run_static_analysis(
        self, 
        code: str, 
        file_extension: str, 
        file_path: Optional[str]
    ) -> Dict[str, float]:
        """Run static analysis tools."""
        if file_extension not in ['.py', '.js', '.ts', '.jsx', '.tsx']:
            return {}
        
        scores = {}
        
        # Create temporary file for analysis
        with tempfile.NamedTemporaryFile(
            mode='w', 
            suffix=file_extension, 
            delete=False
        ) as temp_file:
            temp_file.write(code)
            temp_path = temp_file.name
        
        try:
            # Run appropriate tools based on file type
            if file_extension == '.py':
                await self._run_python_analysis(temp_path, scores)
            elif file_extension in ['.js', '.ts', '.jsx', '.tsx']:
                await self._run_javascript_analysis(temp_path, scores)
            
        finally:
            # Clean up temporary file
            try:
                os.unlink(temp_path)
            except OSError:
                pass
        
        return scores
    
    async def _run_python_analysis(self, file_path: str, scores: Dict[str, float]) -> None:
        """Run Python static analysis tools."""
        for tool in self.config.static_analysis_tools:
            if tool not in ['pylint', 'flake8', 'mypy']:
                continue
            
            try:
                result = await self._run_analysis_tool(tool, file_path)
                scores[tool] = result.score
                logger.debug(f"{tool} analysis: score={result.score:.3f}, issues={len(result.issues)}")
            except Exception as e:
                logger.error(f"Failed to run {tool}: {e}")
                scores[tool] = 0.5
    
    async def _run_javascript_analysis(self, file_path: str, scores: Dict[str, float]) -> None:
        """Run JavaScript/TypeScript static analysis tools."""
        # Future implementation for JavaScript tools
        logger.info("JavaScript static analysis not yet implemented")
        scores['eslint'] = 0.7  # Placeholder
    
    async def _run_analysis_tool(self, tool: str, file_path: str) -> StaticAnalysisResult:
        """Run a specific static analysis tool."""
        cache_key = f"{tool}:{file_path}"
        if cache_key in self.static_analysis_cache:
            return self.static_analysis_cache[cache_key]
        
        # Build command
        if tool == "pylint":
            cmd = ["pylint", "--output-format=json", file_path]
        elif tool == "flake8":
            cmd = ["flake8", file_path]
        elif tool == "mypy":
            cmd = ["mypy", file_path]
        else:
            raise ValueError(f"Unknown tool: {tool}")
        
        # Run tool
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            result = StaticAnalysisResult(
                tool=tool,
                exit_code=process.returncode or 0,
                stdout=stdout.decode('utf-8', errors='ignore'),
                stderr=stderr.decode('utf-8', errors='ignore')
            )
            
            # Cache result
            self.static_analysis_cache[cache_key] = result
            
            return result
            
        except FileNotFoundError:
            logger.warning(f"Static analysis tool '{tool}' not found")
            # Return empty result if tool not available
            return StaticAnalysisResult(tool=tool, exit_code=127, stdout="", stderr=f"{tool} not found")
    
    async def _analyze_test_coverage(self, code: str, file_path: Optional[str]) -> float:
        """Analyze test coverage."""
        # Simple heuristic: check for test-related keywords
        test_indicators = [
            'def test_', 'class Test', 'import unittest', 'import pytest',
            'describe(', 'it(', 'test(', 'expect(', 'assert'
        ]
        
        test_lines = sum(1 for line in code.split('\n') 
                        if any(indicator in line for indicator in test_indicators))
        
        total_lines = len([line for line in code.split('\n') if line.strip()])
        
        if total_lines == 0:
            return 0.0
        
        # Basic coverage estimation
        coverage_ratio = min(test_lines / max(total_lines * 0.3, 1), 1.0)
        
        return coverage_ratio
    
    async def _analyze_security(self, code: str, file_extension: str) -> float:
        """Analyze code for security issues."""
        security_issues = []
        
        # Common security patterns to check
        security_patterns = {
            'hardcoded_secrets': [
                'password', 'secret', 'api_key', 'token', 'credential'
            ],
            'sql_injection': [
                'execute(', 'query(', 'raw(', 'format('
            ],
            'command_injection': [
                'os.system', 'subprocess.call', 'eval(', 'exec('
            ],
            'path_traversal': [
                '../', '..\\', 'os.path.join'
            ]
        }
        
        code_lower = code.lower()
        
        for category, patterns in security_patterns.items():
            for pattern in patterns:
                if pattern in code_lower:
                    security_issues.append({
                        'category': category,
                        'pattern': pattern,
                        'severity': 'medium'
                    })
        
        # Calculate security score
        if not security_issues:
            return 1.0
        
        # Penalty based on number and severity of issues
        penalty = len(security_issues) * 0.1
        return max(0.0, 1.0 - penalty)
    
    async def _analyze_performance(self, code: str, file_extension: str) -> float:
        """Analyze code for performance issues."""
        performance_issues = []
        
        # Performance anti-patterns
        if file_extension == '.py':
            antipatterns = [
                ('for.*in.*range.*len', 'Use enumerate() instead of range(len())'),
                ('\.append.*for.*in', 'Consider list comprehension'),
                ('import.*\\*', 'Avoid wildcard imports'),
                ('global ', 'Avoid global variables')
            ]
        else:
            antipatterns = []
        
        import re
        for pattern, description in antipatterns:
            if re.search(pattern, code, re.IGNORECASE):
                performance_issues.append({
                    'pattern': pattern,
                    'description': description,
                    'severity': 'low'
                })
        
        # Calculate performance score
        if not performance_issues:
            return 1.0
        
        penalty = len(performance_issues) * 0.05
        return max(0.0, 1.0 - penalty)
    
    def _calculate_final_score(
        self, 
        static_scores: Dict[str, float],
        llm_score: Optional[QualityScore],
        test_coverage: float,
        security_score: float,
        performance_score: float
    ) -> QualityScore:
        """Calculate final quality score from all assessments."""
        
        # Static analysis average
        if static_scores:
            static_avg = sum(static_scores.values()) / len(static_scores)
        else:
            static_avg = 0.7  # Default if no static analysis
        
        # LLM-based scores
        if llm_score:
            code_quality = llm_score.code_quality
            consistency = llm_score.consistency
        else:
            code_quality = static_avg
            consistency = 0.7  # Default
        
        # Weighted average for overall score
        weights = {
            'code_quality': 0.3,
            'consistency': 0.25,
            'test_coverage': 0.15,
            'security': 0.2,
            'performance': 0.1
        }
        
        overall = (
            weights['code_quality'] * code_quality +
            weights['consistency'] * consistency +
            weights['test_coverage'] * test_coverage +
            weights['security'] * security_score +
            weights['performance'] * performance_score
        )
        
        return QualityScore(
            overall=overall,
            code_quality=code_quality,
            consistency=consistency,
            test_coverage=test_coverage,
            security=security_score,
            performance=performance_score
        )
    
    def _get_file_extension(self, file_path: Optional[str], code: str) -> str:
        """Determine file extension from path or code content."""
        if file_path:
            return Path(file_path).suffix
        
        # Guess from content
        if 'def ' in code and 'import ' in code:
            return '.py'
        elif 'function ' in code or 'const ' in code:
            return '.js'
        elif 'interface ' in code or 'type ' in code:
            return '.ts'
        
        return '.txt'  # Default
    
    def _build_evaluation_context(self, project_context: Optional[ProjectContext]) -> str:
        """Build context string for LLM evaluation."""
        if not project_context:
            return "No project context available."
        
        context_parts = [
            f"Project: {project_context.project_name}",
            f"Patterns: {len(project_context.patterns)} learned patterns",
            f"Rules: {len(project_context.consistency_rules)} consistency rules"
        ]
        
        if project_context.patterns:
            context_parts.append("Key patterns:")
            for pattern in project_context.patterns[:3]:  # Top 3 patterns
                context_parts.append(f"- {pattern.name}: {pattern.description}")
        
        return "\n".join(context_parts)
    
    def clear_cache(self) -> None:
        """Clear static analysis cache."""
        self.static_analysis_cache.clear()
        logger.info("Static analysis cache cleared")
    
    async def batch_evaluate(
        self, 
        code_files: List[Tuple[str, str]], 
        project_context: Optional[ProjectContext] = None
    ) -> List[QualityScore]:
        """Evaluate multiple code files in batch."""
        tasks = []
        for code, file_path in code_files:
            tasks.append(self.evaluate_code(code, file_path, project_context))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions and return valid results
        quality_scores = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Failed to evaluate file {code_files[i][1]}: {result}")
                # Create default score for failed evaluation
                quality_scores.append(QualityScore(overall=0.5))
            else:
                quality_scores.append(result)
        
        return quality_scores