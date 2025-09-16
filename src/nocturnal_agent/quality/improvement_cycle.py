"""Quality improvement cycle management system."""

import logging
import subprocess
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field

from nocturnal_agent.core.models import (
    Task, ExecutionResult, QualityScore, FailureInfo, ImprovementPlan
)
from nocturnal_agent.core.config import LLMConfig
from nocturnal_agent.agents.local_llm import LocalLLMAgent


logger = logging.getLogger(__name__)


@dataclass
class ImprovementAttempt:
    """Record of a quality improvement attempt."""
    attempt_number: int
    timestamp: datetime
    original_quality: float
    target_quality: float
    strategy_used: str
    result_quality: float
    success: bool
    changes_made: List[str] = field(default_factory=list)
    failure_reason: Optional[str] = None
    git_commit_before: Optional[str] = None
    git_commit_after: Optional[str] = None


class QualityImprovementCycle:
    """Manages the quality improvement cycle with automatic rollback and retry."""
    
    def __init__(self, project_path: str, quality_threshold: float = 0.85, max_attempts: int = 3):
        """Initialize quality improvement cycle.
        
        Args:
            project_path: Path to the project directory
            quality_threshold: Minimum quality score required
            max_attempts: Maximum improvement attempts before giving up
        """
        self.project_path = Path(project_path)
        self.quality_threshold = quality_threshold
        self.max_attempts = max_attempts
        # Create default LLM config
        llm_config = LLMConfig()
        self.llm_agent = LocalLLMAgent(llm_config)
        
        # Track current improvement session
        self.current_task: Optional[Task] = None
        self.current_attempts: List[ImprovementAttempt] = []
        self.original_commit: Optional[str] = None
    
    async def evaluate_and_improve(self, task: Task, result: ExecutionResult) -> ExecutionResult:
        """Evaluate result quality and improve if needed.
        
        Args:
            task: The executed task
            result: Execution result to evaluate
            
        Returns:
            Final execution result after improvement attempts
        """
        logger.info(f"Starting quality evaluation for task: {task.id}")
        
        # Initialize improvement session
        self.current_task = task
        self.current_attempts = []
        self.original_commit = await self._get_current_commit()
        
        # Check if improvement is needed
        if result.quality_score.overall >= self.quality_threshold:
            logger.info(f"Quality score {result.quality_score.overall:.3f} meets threshold {self.quality_threshold}")
            return result
        
        logger.warning(f"Quality score {result.quality_score.overall:.3f} below threshold {self.quality_threshold}")
        
        # Start improvement cycle
        current_result = result
        for attempt_num in range(1, self.max_attempts + 1):
            logger.info(f"Starting improvement attempt {attempt_num}/{self.max_attempts}")
            
            # Save current state before improvement attempt
            commit_before = await self._get_current_commit()
            
            # Attempt to improve
            improved_result = await self._attempt_improvement(
                task, current_result, attempt_num
            )
            
            # Record attempt
            attempt = ImprovementAttempt(
                attempt_number=attempt_num,
                timestamp=datetime.now(),
                original_quality=result.quality_score.overall,
                target_quality=self.quality_threshold,
                strategy_used=f"llm_analysis_attempt_{attempt_num}",
                result_quality=improved_result.quality_score.overall,
                success=improved_result.quality_score.overall >= self.quality_threshold,
                changes_made=improved_result.improvements_made,
                git_commit_before=commit_before,
                git_commit_after=await self._get_current_commit()
            )
            
            # Check if improvement succeeded
            if improved_result.quality_score.overall >= self.quality_threshold:
                logger.info(f"Improvement successful! Quality: {improved_result.quality_score.overall:.3f}")
                attempt.success = True
                self.current_attempts.append(attempt)
                return improved_result
            
            # Improvement failed - rollback if quality got worse
            if improved_result.quality_score.overall < current_result.quality_score.overall:
                logger.warning(f"Quality degraded to {improved_result.quality_score.overall:.3f}, rolling back")
                await self._rollback_to_commit(commit_before)
                attempt.failure_reason = "quality_degradation"
            else:
                logger.info(f"Slight improvement to {improved_result.quality_score.overall:.3f}, keeping changes")
                current_result = improved_result
            
            self.current_attempts.append(attempt)
        
        # All attempts failed
        logger.error(f"All {self.max_attempts} improvement attempts failed")
        await self._rollback_to_original()
        
        # Return original result with failure info
        final_result = result
        final_result.quality_improvement_failed = True
        final_result.improvement_attempts = len(self.current_attempts)
        
        return final_result
    
    async def _attempt_improvement(self, task: Task, result: ExecutionResult, attempt_num: int) -> ExecutionResult:
        """Attempt to improve the code quality.
        
        Args:
            task: The original task
            result: Current execution result
            attempt_num: Current attempt number
            
        Returns:
            New execution result after improvement attempt
        """
        logger.info(f"Analyzing failure reasons for improvement attempt {attempt_num}")
        
        # Analyze what went wrong
        failure_analysis = await self._analyze_quality_issues(task, result)
        
        # Generate improvement plan
        improvement_plan = await self._generate_improvement_plan(
            task, result, failure_analysis, attempt_num
        )
        
        # Apply improvements
        try:
            improved_result = await self._apply_improvements(
                task, result, improvement_plan
            )
            
            logger.info(f"Improvement attempt {attempt_num} completed")
            return improved_result
            
        except Exception as e:
            logger.error(f"Improvement attempt {attempt_num} failed: {e}")
            
            # Return result with failure info
            failed_result = result
            failed_result.errors.append(f"Improvement attempt {attempt_num} failed: {str(e)}")
            return failed_result
    
    async def _analyze_quality_issues(self, task: Task, result: ExecutionResult) -> FailureInfo:
        """Analyze what caused the quality issues.
        
        Args:
            task: The original task
            result: Execution result with quality issues
            
        Returns:
            Analysis of failure causes
        """
        logger.debug("Analyzing quality issues with local LLM")
        
        analysis_prompt = f"""
        Analyze why this code execution had quality issues:
        
        Task: {task.description}
        Generated Code: {result.generated_code[:1000]}...
        Quality Score: {result.quality_score.overall:.3f}
        Code Quality: {result.quality_score.code_quality:.3f}
        Consistency: {result.quality_score.consistency:.3f}
        Test Coverage: {result.quality_score.test_coverage:.3f}
        
        Errors: {result.errors}
        
        Please identify the main issues that caused low quality scores and suggest specific improvements.
        """
        
        try:
            analysis_response = await self.llm_agent.analyze_task(analysis_prompt)
            
            return FailureInfo(
                primary_cause=analysis_response.get('primary_cause', 'unknown'),
                contributing_factors=analysis_response.get('contributing_factors', []),
                suggested_fixes=analysis_response.get('suggested_fixes', []),
                confidence=analysis_response.get('confidence', 0.5)
            )
            
        except Exception as e:
            logger.error(f"Failed to analyze quality issues: {e}")
            return FailureInfo(
                primary_cause="analysis_failed",
                contributing_factors=[str(e)],
                suggested_fixes=["retry_with_different_approach"],
                confidence=0.1
            )
    
    async def _generate_improvement_plan(
        self, 
        task: Task, 
        result: ExecutionResult,
        failure_info: FailureInfo,
        attempt_num: int
    ) -> ImprovementPlan:
        """Generate a plan to improve code quality.
        
        Args:
            task: The original task
            result: Current execution result
            failure_info: Analysis of what went wrong
            attempt_num: Current attempt number
            
        Returns:
            Improvement plan
        """
        logger.debug(f"Generating improvement plan for attempt {attempt_num}")
        
        plan_prompt = f"""
        Create an improvement plan based on this analysis:
        
        Original Task: {task.description}
        Current Quality: {result.quality_score.overall:.3f}
        Target Quality: {self.quality_threshold}
        
        Issues Found:
        - Primary Cause: {failure_info.primary_cause}
        - Contributing Factors: {failure_info.contributing_factors}
        - Suggested Fixes: {failure_info.suggested_fixes}
        
        Attempt Number: {attempt_num}
        
        Generate specific, actionable steps to improve the code quality.
        Consider: code structure, error handling, testing, documentation, consistency.
        """
        
        try:
            plan_response = await self.llm_agent.analyze_task(plan_prompt)
            
            return ImprovementPlan(
                strategy=plan_response.get('strategy', f'attempt_{attempt_num}_improvement'),
                specific_actions=plan_response.get('specific_actions', []),
                expected_quality_gain=plan_response.get('expected_quality_gain', 0.1),
                estimated_effort=plan_response.get('estimated_effort', 'medium'),
                risk_level=plan_response.get('risk_level', 'medium')
            )
            
        except Exception as e:
            logger.error(f"Failed to generate improvement plan: {e}")
            return ImprovementPlan(
                strategy="fallback_improvement",
                specific_actions=["refactor_code", "add_error_handling", "improve_tests"],
                expected_quality_gain=0.1,
                estimated_effort="high",
                risk_level="high"
            )
    
    async def _apply_improvements(
        self, 
        task: Task,
        result: ExecutionResult, 
        plan: ImprovementPlan
    ) -> ExecutionResult:
        """Apply the improvement plan to the code.
        
        Args:
            task: The original task
            result: Current execution result
            plan: Improvement plan to apply
            
        Returns:
            New execution result after applying improvements
        """
        logger.info(f"Applying improvement plan: {plan.strategy}")
        
        # Create improved prompt based on the plan
        improved_prompt = f"""
        Improve this code based on the following plan:
        
        Original Task: {task.description}
        Current Code: {result.generated_code}
        Current Quality: {result.quality_score.overall:.3f}
        Target Quality: {self.quality_threshold}
        
        Improvement Plan:
        Strategy: {plan.strategy}
        Actions: {plan.specific_actions}
        
        Please generate improved code that addresses the identified issues.
        Focus on: code quality, consistency, error handling, and testability.
        """
        
        try:
            # Use local LLM to improve the code
            improved_response = await self.llm_agent.generate_code(
                task.description,
                improved_prompt,
                task.project_context
            )
            
            # Create new execution result
            improved_result = ExecutionResult(
                task_id=task.id,
                success=improved_response.get('success', True),
                quality_score=improved_response.get('quality_score', result.quality_score),
                generated_code=improved_response.get('code', result.generated_code),
                agent_used=result.agent_used,
                execution_time=result.execution_time,
                improvements_made=plan.specific_actions,
                files_modified=result.files_modified
            )
            
            logger.info(f"Code improvement completed with quality: {improved_result.quality_score.overall:.3f}")
            return improved_result
            
        except Exception as e:
            logger.error(f"Failed to apply improvements: {e}")
            
            # Return original result with error
            failed_result = result
            failed_result.errors.append(f"Improvement application failed: {str(e)}")
            return failed_result
    
    async def _get_current_commit(self) -> Optional[str]:
        """Get current git commit hash."""
        try:
            result = subprocess.run(
                ['git', 'rev-parse', 'HEAD'],
                cwd=self.project_path,
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            logger.warning(f"Failed to get current commit: {e}")
            return None
    
    async def _rollback_to_commit(self, commit_hash: str) -> bool:
        """Rollback to a specific commit.
        
        Args:
            commit_hash: Git commit hash to rollback to
            
        Returns:
            True if rollback succeeded, False otherwise
        """
        if not commit_hash:
            logger.error("Cannot rollback: no commit hash provided")
            return False
        
        try:
            logger.info(f"Rolling back to commit: {commit_hash}")
            subprocess.run(
                ['git', 'reset', '--hard', commit_hash],
                cwd=self.project_path,
                check=True
            )
            logger.info("Rollback completed successfully")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Rollback failed: {e}")
            return False
    
    async def _rollback_to_original(self) -> bool:
        """Rollback to the original commit before improvement attempts."""
        if self.original_commit:
            return await self._rollback_to_commit(self.original_commit)
        else:
            logger.error("Cannot rollback: no original commit recorded")
            return False
    
    def get_improvement_history(self) -> List[ImprovementAttempt]:
        """Get history of improvement attempts for current task."""
        return self.current_attempts.copy()
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get improvement cycle statistics."""
        if not self.current_attempts:
            return {
                'total_attempts': 0,
                'successful_attempts': 0,
                'success_rate': 0.0,
                'average_quality_improvement': 0.0
            }
        
        successful = sum(1 for a in self.current_attempts if a.success)
        quality_improvements = [
            a.result_quality - a.original_quality 
            for a in self.current_attempts
        ]
        
        return {
            'total_attempts': len(self.current_attempts),
            'successful_attempts': successful,
            'success_rate': successful / len(self.current_attempts),
            'average_quality_improvement': sum(quality_improvements) / len(quality_improvements),
            'max_quality_achieved': max(a.result_quality for a in self.current_attempts),
            'strategies_used': list(set(a.strategy_used for a in self.current_attempts))
        }