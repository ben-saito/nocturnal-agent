"""Failure analysis system using local LLM."""

import logging
import json
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from pathlib import Path

from nocturnal_agent.core.models import (
    Task, ExecutionResult, QualityScore, FailureInfo
)
from nocturnal_agent.core.config import LLMConfig
from nocturnal_agent.agents.local_llm import LocalLLMAgent


logger = logging.getLogger(__name__)


@dataclass
class AnalysisResult:
    """Result of failure analysis."""
    failure_type: str
    root_causes: List[str]
    impact_severity: str  # 'low', 'medium', 'high', 'critical'
    recommended_actions: List[str]
    prompt_improvements: List[str]
    learning_points: List[str]
    confidence_score: float
    analysis_timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class PromptOptimization:
    """Suggested prompt optimization."""
    original_prompt_section: str
    improved_prompt_section: str
    reasoning: str
    expected_improvement: str


class FailureAnalyzer:
    """Analyzes execution failures and suggests improvements."""
    
    def __init__(self, project_path: str):
        """Initialize failure analyzer.
        
        Args:
            project_path: Path to the project directory
        """
        self.project_path = Path(project_path)
        # Create default LLM config
        llm_config = LLMConfig()
        self.llm_agent = LocalLLMAgent(llm_config)
        self.analysis_history: List[AnalysisResult] = []
        
        # Create analysis storage directory
        self.analysis_dir = self.project_path / ".nocturnal" / "analysis"
        self.analysis_dir.mkdir(parents=True, exist_ok=True)
    
    async def analyze_failure(self, task: Task, result: ExecutionResult) -> AnalysisResult:
        """Analyze a failed execution and provide insights.
        
        Args:
            task: The failed task
            result: Execution result with failure information
            
        Returns:
            Analysis result with insights and recommendations
        """
        logger.info(f"Analyzing failure for task: {task.id}")
        
        # Collect failure context
        context = await self._collect_failure_context(task, result)
        
        # Perform deep analysis using local LLM
        analysis = await self._perform_deep_analysis(context)
        
        # Generate prompt optimizations
        prompt_optimizations = await self._generate_prompt_optimizations(context, analysis)
        
        # Create analysis result
        analysis_result = AnalysisResult(
            failure_type=analysis.get('failure_type', 'unknown'),
            root_causes=analysis.get('root_causes', []),
            impact_severity=analysis.get('impact_severity', 'medium'),
            recommended_actions=analysis.get('recommended_actions', []),
            prompt_improvements=prompt_optimizations,
            learning_points=analysis.get('learning_points', []),
            confidence_score=analysis.get('confidence_score', 0.5)
        )
        
        # Store analysis
        await self._store_analysis(task, result, analysis_result)
        self.analysis_history.append(analysis_result)
        
        logger.info(f"Failure analysis completed with confidence: {analysis_result.confidence_score:.3f}")
        return analysis_result
    
    async def _collect_failure_context(self, task: Task, result: ExecutionResult) -> Dict[str, Any]:
        """Collect comprehensive context about the failure.
        
        Args:
            task: The failed task
            result: Execution result
            
        Returns:
            Comprehensive failure context
        """
        context = {
            'task': {
                'id': task.id,
                'description': task.description,
                'priority': task.priority.value if hasattr(task.priority, 'value') else str(task.priority),
                'requirements': task.requirements,
                'constraints': task.constraints
            },
            'result': {
                'success': result.success,
                'quality_score': {
                    'overall': result.quality_score.overall,
                    'code_quality': result.quality_score.code_quality,
                    'consistency': result.quality_score.consistency,
                    'test_coverage': result.quality_score.test_coverage
                },
                'generated_code': result.generated_code,
                'errors': result.errors,
                'execution_time': result.execution_time,
                'files_modified': result.files_modified,
                'agent_used': result.agent_used.value if hasattr(result.agent_used, 'value') else str(result.agent_used)
            },
            'environment': {
                'project_path': str(self.project_path),
                'timestamp': datetime.now().isoformat(),
                'git_status': await self._get_git_status()
            }
        }
        
        # Add recent similar failures for pattern recognition
        context['recent_failures'] = await self._get_recent_similar_failures(task, result)
        
        return context
    
    async def _perform_deep_analysis(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Perform deep analysis of the failure using local LLM.
        
        Args:
            context: Comprehensive failure context
            
        Returns:
            Analysis results
        """
        analysis_prompt = f"""
        Perform a detailed analysis of this code execution failure:
        
        TASK INFORMATION:
        - Description: {context['task']['description']}
        - Requirements: {context['task']['requirements']}
        - Constraints: {context['task']['constraints']}
        
        EXECUTION RESULT:
        - Success: {context['result']['success']}
        - Quality Scores:
          * Overall: {context['result']['quality_score']['overall']:.3f}
          * Code Quality: {context['result']['quality_score']['code_quality']:.3f}
          * Consistency: {context['result']['quality_score']['consistency']:.3f}
          * Test Coverage: {context['result']['quality_score']['test_coverage']:.3f}
        
        GENERATED CODE:
        {context['result']['generated_code'][:1500]}...
        
        ERRORS:
        {context['result']['errors']}
        
        RECENT SIMILAR FAILURES:
        {context.get('recent_failures', 'None')}
        
        Please analyze this failure and provide:
        1. failure_type: Category of failure (syntax, logic, quality, integration, etc.)
        2. root_causes: List of fundamental reasons for failure
        3. impact_severity: Severity level (low/medium/high/critical)
        4. recommended_actions: Specific actions to fix the issue
        5. learning_points: Key insights to prevent similar failures
        6. confidence_score: Your confidence in this analysis (0.0-1.0)
        
        Focus on actionable insights and prevention strategies.
        """
        
        try:
            response = await self.llm_agent.analyze_task(analysis_prompt)
            
            # Parse and validate response
            if isinstance(response, dict):
                return response
            elif isinstance(response, str):
                # Try to parse as JSON
                try:
                    return json.loads(response)
                except json.JSONDecodeError:
                    # Fall back to parsing key sections
                    return self._parse_text_analysis(response)
            else:
                raise ValueError(f"Unexpected response type: {type(response)}")
                
        except Exception as e:
            logger.error(f"Deep analysis failed: {e}")
            return self._create_fallback_analysis(context, str(e))
    
    async def _generate_prompt_optimizations(
        self, 
        context: Dict[str, Any], 
        analysis: Dict[str, Any]
    ) -> List[str]:
        """Generate prompt optimization suggestions.
        
        Args:
            context: Failure context
            analysis: Analysis results
            
        Returns:
            List of prompt improvement suggestions
        """
        optimization_prompt = f"""
        Based on this failure analysis, suggest improvements to the prompt/instructions:
        
        FAILURE TYPE: {analysis.get('failure_type', 'unknown')}
        ROOT CAUSES: {analysis.get('root_causes', [])}
        
        ORIGINAL TASK: {context['task']['description']}
        
        What specific improvements to the task prompt would prevent this type of failure?
        Consider:
        - Clarity of requirements
        - Missing constraints or context
        - Ambiguous instructions
        - Quality expectations
        - Example code patterns
        
        Provide specific, actionable prompt improvements.
        """
        
        try:
            response = await self.llm_agent.analyze_task(optimization_prompt)
            
            if isinstance(response, dict):
                return response.get('prompt_improvements', [])
            elif isinstance(response, list):
                return response
            elif isinstance(response, str):
                # Parse improvements from text
                lines = response.strip().split('\n')
                return [line.strip('- ') for line in lines if line.strip().startswith('-')]
            else:
                return ["Unable to generate prompt optimizations"]
                
        except Exception as e:
            logger.error(f"Prompt optimization failed: {e}")
            return [f"Error generating optimizations: {str(e)}"]
    
    async def _get_git_status(self) -> Dict[str, Any]:
        """Get current git status information."""
        try:
            import subprocess
            
            # Get current branch
            branch_result = subprocess.run(
                ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                cwd=self.project_path,
                capture_output=True,
                text=True,
                check=True
            )
            
            # Get commit hash
            commit_result = subprocess.run(
                ['git', 'rev-parse', 'HEAD'],
                cwd=self.project_path,
                capture_output=True,
                text=True,
                check=True
            )
            
            # Get status
            status_result = subprocess.run(
                ['git', 'status', '--porcelain'],
                cwd=self.project_path,
                capture_output=True,
                text=True,
                check=True
            )
            
            return {
                'branch': branch_result.stdout.strip(),
                'commit': commit_result.stdout.strip(),
                'has_changes': bool(status_result.stdout.strip()),
                'modified_files': [
                    line.strip()[3:] for line in status_result.stdout.strip().split('\n')
                    if line.strip()
                ]
            }
            
        except Exception as e:
            logger.warning(f"Failed to get git status: {e}")
            return {'error': str(e)}
    
    async def _get_recent_similar_failures(self, task: Task, result: ExecutionResult) -> List[Dict[str, Any]]:
        """Get recent similar failures for pattern recognition.
        
        Args:
            task: Current task
            result: Current result
            
        Returns:
            List of similar recent failures
        """
        similar_failures = []
        
        # Look through recent analysis history
        for analysis in self.analysis_history[-10:]:  # Last 10 analyses
            if (analysis.failure_type and 
                analysis.failure_type in str(result.errors).lower()):
                similar_failures.append({
                    'failure_type': analysis.failure_type,
                    'root_causes': analysis.root_causes[:2],  # Top 2 causes
                    'timestamp': analysis.analysis_timestamp.isoformat()
                })
        
        return similar_failures
    
    def _parse_text_analysis(self, text: str) -> Dict[str, Any]:
        """Parse analysis from text response.
        
        Args:
            text: Text response from LLM
            
        Returns:
            Parsed analysis dictionary
        """
        analysis = {
            'failure_type': 'unknown',
            'root_causes': [],
            'impact_severity': 'medium',
            'recommended_actions': [],
            'learning_points': [],
            'confidence_score': 0.5
        }
        
        try:
            lines = text.strip().split('\n')
            current_section = None
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Detect sections
                if 'failure_type' in line.lower():
                    current_section = 'failure_type'
                    if ':' in line:
                        analysis['failure_type'] = line.split(':', 1)[1].strip()
                elif 'root_causes' in line.lower():
                    current_section = 'root_causes'
                elif 'impact_severity' in line.lower():
                    current_section = 'impact_severity'
                    if ':' in line:
                        analysis['impact_severity'] = line.split(':', 1)[1].strip()
                elif 'recommended_actions' in line.lower():
                    current_section = 'recommended_actions'
                elif 'learning_points' in line.lower():
                    current_section = 'learning_points'
                elif 'confidence_score' in line.lower():
                    current_section = 'confidence_score'
                    if ':' in line:
                        try:
                            score = float(line.split(':', 1)[1].strip())
                            analysis['confidence_score'] = score
                        except ValueError:
                            pass
                elif line.startswith('-') and current_section in ['root_causes', 'recommended_actions', 'learning_points']:
                    analysis[current_section].append(line[1:].strip())
                    
        except Exception as e:
            logger.warning(f"Error parsing text analysis: {e}")
        
        return analysis
    
    def _create_fallback_analysis(self, context: Dict[str, Any], error: str) -> Dict[str, Any]:
        """Create fallback analysis when LLM analysis fails.
        
        Args:
            context: Failure context
            error: Error that occurred
            
        Returns:
            Fallback analysis
        """
        quality_score = context['result']['quality_score']
        
        # Determine failure type based on quality scores
        if quality_score['overall'] < 0.3:
            failure_type = 'critical_quality_failure'
        elif quality_score['code_quality'] < 0.5:
            failure_type = 'code_quality_issue'
        elif quality_score['consistency'] < 0.5:
            failure_type = 'consistency_violation'
        elif quality_score['test_coverage'] < 0.5:
            failure_type = 'insufficient_testing'
        else:
            failure_type = 'general_quality_issue'
        
        return {
            'failure_type': failure_type,
            'root_causes': [
                'Low quality scores detected',
                f'Analysis system error: {error}',
                'Insufficient code quality measures'
            ],
            'impact_severity': 'medium',
            'recommended_actions': [
                'Review generated code manually',
                'Improve code structure and error handling',
                'Add comprehensive tests',
                'Enhance consistency checks'
            ],
            'learning_points': [
                'Analysis system needs improvement',
                'Manual review required for complex failures',
                'Quality thresholds may need adjustment'
            ],
            'confidence_score': 0.3
        }
    
    async def _store_analysis(self, task: Task, result: ExecutionResult, analysis: AnalysisResult):
        """Store analysis results to disk.
        
        Args:
            task: The analyzed task
            result: Execution result
            analysis: Analysis results
        """
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"failure_analysis_{task.id}_{timestamp}.json"
            file_path = self.analysis_dir / filename
            
            analysis_data = {
                'task_id': task.id,
                'task_description': task.description,
                'quality_score': result.quality_score.overall,
                'analysis': {
                    'failure_type': analysis.failure_type,
                    'root_causes': analysis.root_causes,
                    'impact_severity': analysis.impact_severity,
                    'recommended_actions': analysis.recommended_actions,
                    'prompt_improvements': analysis.prompt_improvements,
                    'learning_points': analysis.learning_points,
                    'confidence_score': analysis.confidence_score,
                    'timestamp': analysis.analysis_timestamp.isoformat()
                },
                'context': {
                    'execution_time': result.execution_time,
                    'errors': result.errors,
                    'files_modified': result.files_modified
                }
            }
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(analysis_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Analysis stored: {file_path}")
            
        except Exception as e:
            logger.error(f"Failed to store analysis: {e}")
    
    def get_analysis_statistics(self) -> Dict[str, Any]:
        """Get statistics about failure analyses."""
        if not self.analysis_history:
            return {
                'total_analyses': 0,
                'average_confidence': 0.0,
                'most_common_failure_types': {},
                'severity_distribution': {}
            }
        
        failure_types = {}
        severities = {}
        confidences = []
        
        for analysis in self.analysis_history:
            # Count failure types
            failure_types[analysis.failure_type] = failure_types.get(analysis.failure_type, 0) + 1
            
            # Count severities
            severities[analysis.impact_severity] = severities.get(analysis.impact_severity, 0) + 1
            
            # Collect confidences
            confidences.append(analysis.confidence_score)
        
        return {
            'total_analyses': len(self.analysis_history),
            'average_confidence': sum(confidences) / len(confidences),
            'most_common_failure_types': dict(sorted(failure_types.items(), key=lambda x: x[1], reverse=True)),
            'severity_distribution': severities,
            'recent_analysis_count': len([a for a in self.analysis_history if (datetime.now() - a.analysis_timestamp).days < 7])
        }
    
    def get_learning_insights(self) -> List[str]:
        """Get accumulated learning insights from all analyses."""
        all_learning_points = []
        
        for analysis in self.analysis_history:
            all_learning_points.extend(analysis.learning_points)
        
        # Count frequency of learning points
        learning_frequency = {}
        for point in all_learning_points:
            learning_frequency[point] = learning_frequency.get(point, 0) + 1
        
        # Return most frequent learning points
        return [
            point for point, freq in sorted(learning_frequency.items(), key=lambda x: x[1], reverse=True)
            if freq > 1  # Only return points that appeared multiple times
        ][:10]  # Top 10 insights