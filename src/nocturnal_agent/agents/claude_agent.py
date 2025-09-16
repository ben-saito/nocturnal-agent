"""Claude Code CLI agent implementation."""

import asyncio
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from nocturnal_agent.core.config import ClaudeConfig
from nocturnal_agent.core.models import (
    Task, ExecutionResult, QualityScore, AgentType
)
from nocturnal_agent.agents.cli_executor import (
    AgentCLIInterface, CLIExecutor, CLIExecutionContext, CLICommand
)
from nocturnal_agent.agents.agent_detector import DetectedAgent


logger = logging.getLogger(__name__)


class ClaudePrompt:
    """Represents a prompt for Claude CLI."""
    
    def __init__(self, content: str, files: Optional[List[str]] = None):
        """Initialize Claude prompt."""
        self.content = content
        self.files = files or []
        self.metadata: Dict[str, Any] = {}
    
    def to_file(self, file_path: str) -> None:
        """Write prompt to file."""
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(self.content)


class ClaudeResponse:
    """Represents Claude CLI response."""
    
    def __init__(self, raw_output: str, success: bool, execution_time: float):
        """Initialize Claude response."""
        self.raw_output = raw_output
        self.success = success
        self.execution_time = execution_time
        self.generated_code: str = ""
        self.explanation: str = ""
        self.suggestions: List[str] = []
        self.files_modified: List[str] = []
        
        self._parse_response()
    
    def _parse_response(self) -> None:
        """Parse Claude response and extract information."""
        if not self.success or not self.raw_output:
            return
        
        # Try to extract code blocks
        import re
        
        # Look for code blocks
        code_blocks = re.findall(r'```(?:\w+)?\n(.*?)\n```', self.raw_output, re.DOTALL)
        if code_blocks:
            self.generated_code = '\n\n'.join(code_blocks)
        
        # Extract explanations (text before/after code blocks)
        lines = self.raw_output.split('\n')
        explanation_lines = []
        in_code_block = False
        
        for line in lines:
            if line.strip().startswith('```'):
                in_code_block = not in_code_block
                continue
            if not in_code_block:
                explanation_lines.append(line)
        
        self.explanation = '\n'.join(explanation_lines).strip()
        
        # Extract suggestions (lines starting with common suggestion patterns)
        suggestion_patterns = [
            r'(?:Consider|Try|You might want to|Suggestion|Recommend)',
            r'(?:Alternatively|Another option|You could also)',
            r'(?:Note|Important|Warning)'
        ]
        
        for line in explanation_lines:
            line = line.strip()
            if any(re.search(pattern, line, re.IGNORECASE) for pattern in suggestion_patterns):
                self.suggestions.append(line)


class ClaudeAgent(AgentCLIInterface):
    """Claude Code CLI agent implementation."""
    
    def __init__(self, agent: DetectedAgent, executor: CLIExecutor, config: ClaudeConfig):
        """Initialize Claude agent."""
        super().__init__(agent, executor)
        self.config = config
        self.conversation_history: List[Dict[str, Any]] = []
    
    async def execute_task(self, task: Task, context: CLIExecutionContext) -> ExecutionResult:
        """Execute task using Claude CLI."""
        start_time = asyncio.get_event_loop().time()
        
        try:
            # Build prompt for the task
            prompt = self._build_task_prompt(task)
            
            # Execute with Claude
            response = await self._execute_claude_prompt(prompt, context, task)
            
            if not response.success:
                return self._create_failure_result(task, "Claude execution failed", response.raw_output)
            
            # Analyze generated code quality
            quality_score = await self._analyze_generated_code(response.generated_code, task)
            
            # Create execution result
            execution_time = asyncio.get_event_loop().time() - start_time
            
            result = ExecutionResult(
                task_id=task.id,
                success=True,
                quality_score=quality_score,
                generated_code=response.generated_code,
                agent_used=AgentType.CLAUDE_CODE,
                execution_time=execution_time,
                improvements_made=response.suggestions,
                files_modified=response.files_modified
            )
            
            # Record conversation
            self._record_conversation(task, prompt, response)
            
            logger.info(f"Claude task execution completed: quality={quality_score.overall:.3f}")
            
            return result
            
        except Exception as e:
            logger.error(f"Claude task execution failed: {e}")
            return self._create_failure_result(task, str(e))
    
    async def _execute_claude_prompt(
        self, 
        prompt: ClaudePrompt, 
        context: CLIExecutionContext,
        task: Task
    ) -> ClaudeResponse:
        """Execute prompt with Claude CLI."""
        
        # Create prompt file
        prompt_file = context.create_temp_file(prompt.content, suffix=".md")
        
        # Build Claude command
        claude_args = [prompt_file]
        
        # Add file references if any
        if prompt.files:
            for file_path in prompt.files:
                if os.path.exists(file_path):
                    claude_args.extend(["--file", file_path])
        
        # Add working directory context
        if task.working_directory:
            claude_args.extend(["--directory", task.working_directory])
        
        command = CLICommand(
            command=[self.base_command] + claude_args,
            working_dir=task.working_directory,
            timeout=self.config.timeout
        )
        
        # Execute with retries
        last_error = None
        for attempt in range(self.config.max_retries):
            try:
                result = await self.executor.execute_command(command)
                
                if result.success:
                    return ClaudeResponse(
                        raw_output=result.stdout,
                        success=True,
                        execution_time=result.execution_time
                    )
                else:
                    last_error = result.stderr
                    logger.warning(f"Claude attempt {attempt + 1} failed: {result.stderr}")
                    
                    # Wait before retry
                    if attempt < self.config.max_retries - 1:
                        await asyncio.sleep(2 ** attempt)  # Exponential backoff
                        
            except Exception as e:
                last_error = str(e)
                logger.warning(f"Claude attempt {attempt + 1} error: {e}")
                
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
        
        # All retries failed
        return ClaudeResponse(
            raw_output=last_error or "Unknown error",
            success=False,
            execution_time=0.0
        )
    
    def _build_task_prompt(self, task: Task) -> ClaudePrompt:
        """Build prompt for Claude based on task."""
        
        # Start with task description
        prompt_parts = [
            f"# Development Task: {task.description}",
            ""
        ]
        
        # Add requirements
        if task.requirements:
            prompt_parts.extend([
                "## Requirements:",
                *[f"- {req}" for req in task.requirements],
                ""
            ])
        
        # Add constraints
        if task.constraints:
            prompt_parts.extend([
                "## Constraints:",
                *[f"- {constraint}" for constraint in task.constraints],
                ""
            ])
        
        # Add context from project
        if task.project_context:
            prompt_parts.extend([
                "## Project Context:",
                f"Project: {task.project_context.project_name}",
                ""
            ])
            
            # Add relevant patterns
            if task.project_context.patterns:
                prompt_parts.extend([
                    "### Code Patterns to Follow:",
                    *[f"- {pattern.name}: {pattern.description}" 
                      for pattern in task.project_context.patterns[:5]],
                    ""
                ])
            
            # Add consistency rules
            if task.project_context.consistency_rules:
                prompt_parts.extend([
                    "### Consistency Rules:",
                    *[f"- {rule.name}: {rule.description}" 
                      for rule in task.project_context.consistency_rules[:5]],
                    ""
                ])
        
        # Add quality requirements
        prompt_parts.extend([
            "## Quality Requirements:",
            f"- Minimum quality threshold: {task.minimum_quality_threshold}",
            f"- Consistency threshold: {task.consistency_threshold}",
            "- Follow best practices and coding standards",
            "- Include appropriate error handling",
            "- Add clear documentation and comments",
            ""
        ])
        
        # Add specific instructions
        prompt_parts.extend([
            "## Instructions:",
            "1. Analyze the task requirements carefully",
            "2. Generate high-quality, well-documented code",
            "3. Follow the project patterns and consistency rules",
            "4. Ensure the code meets all quality requirements",
            "5. Provide clear explanations for your implementation choices",
            "",
            "Please implement the solution and explain your approach."
        ])
        
        # Collect relevant files
        files = []
        if task.target_files:
            files.extend(task.target_files)
        
        prompt_content = "\n".join(prompt_parts)
        return ClaudePrompt(content=prompt_content, files=files)
    
    async def _analyze_generated_code(self, code: str, task: Task) -> QualityScore:
        """Analyze quality of generated code."""
        if not code.strip():
            return QualityScore(overall=0.0)
        
        # Basic heuristic analysis
        lines = code.split('\n')
        non_empty_lines = [line for line in lines if line.strip()]
        
        # Calculate basic metrics
        total_lines = len(non_empty_lines)
        comment_lines = len([line for line in non_empty_lines 
                           if line.strip().startswith(('#', '//', '/*', '*', '"""', "'''"))])
        
        # Estimate scores based on heuristics
        documentation_ratio = comment_lines / max(total_lines, 1)
        
        # Basic quality metrics
        code_quality = min(0.8 + (documentation_ratio * 0.2), 1.0)
        consistency = 0.8  # Assume Claude follows good patterns
        test_coverage = 0.3 if 'test' in code.lower() else 0.1
        security = 0.8  # Claude generally follows security practices
        performance = 0.7  # Reasonable default
        
        overall = (code_quality * 0.3 + consistency * 0.25 + 
                  test_coverage * 0.15 + security * 0.2 + performance * 0.1)
        
        return QualityScore(
            overall=overall,
            code_quality=code_quality,
            consistency=consistency,
            test_coverage=test_coverage,
            security=security,
            performance=performance
        )
    
    def _record_conversation(self, task: Task, prompt: ClaudePrompt, response: ClaudeResponse) -> None:
        """Record conversation for learning purposes."""
        conversation_entry = {
            "timestamp": asyncio.get_event_loop().time(),
            "task_id": task.id,
            "task_description": task.description,
            "prompt_content": prompt.content[:500] + "..." if len(prompt.content) > 500 else prompt.content,
            "response_success": response.success,
            "generated_code_length": len(response.generated_code),
            "suggestions_count": len(response.suggestions),
            "execution_time": response.execution_time
        }
        
        self.conversation_history.append(conversation_entry)
        
        # Keep only recent conversations
        if len(self.conversation_history) > 100:
            self.conversation_history = self.conversation_history[-50:]
    
    def _create_failure_result(self, task: Task, error_message: str, details: str = "") -> ExecutionResult:
        """Create failure execution result."""
        return ExecutionResult(
            task_id=task.id,
            success=False,
            quality_score=QualityScore(),
            agent_used=AgentType.CLAUDE_CODE,
            errors=[error_message, details] if details else [error_message]
        )
    
    async def test_connection(self) -> bool:
        """Test Claude CLI connection."""
        try:
            # Try simple version check
            command = CLICommand([self.base_command, "--version"], timeout=10)
            result = await self.executor.execute_command(command)
            
            if not result.success:
                return False
            
            # Try auth status check if configured
            if self.config.check_auth_on_startup:
                auth_command = CLICommand([self.base_command, "auth", "status"], timeout=15)
                auth_result = await self.executor.execute_command(auth_command)
                return auth_result.success
            
            return True
            
        except Exception as e:
            logger.error(f"Claude connection test failed: {e}")
            return False
    
    async def generate_code(
        self, 
        prompt: str, 
        context_files: Optional[List[str]] = None,
        working_dir: Optional[str] = None
    ) -> str:
        """Generate code with Claude CLI (utility method)."""
        
        # Create temporary context
        async with CLIExecutionContext(working_dir) as context:
            claude_prompt = ClaudePrompt(
                content=prompt, 
                files=context_files or []
            )
            
            # Create dummy task for execution
            from nocturnal_agent.core.models import Task
            dummy_task = Task(
                description="Code generation request",
                working_directory=working_dir
            )
            
            response = await self._execute_claude_prompt(claude_prompt, context, dummy_task)
            
            if response.success:
                return response.generated_code
            else:
                raise RuntimeError(f"Code generation failed: {response.raw_output}")
    
    def get_conversation_summary(self) -> Dict[str, Any]:
        """Get summary of conversation history."""
        if not self.conversation_history:
            return {"total_conversations": 0}
        
        total = len(self.conversation_history)
        successful = sum(1 for conv in self.conversation_history if conv["response_success"])
        avg_time = sum(conv["execution_time"] for conv in self.conversation_history) / total
        
        return {
            "total_conversations": total,
            "successful": successful,
            "success_rate": successful / total,
            "average_execution_time": avg_time,
            "recent_tasks": [
                {
                    "task_id": conv["task_id"],
                    "description": conv["task_description"][:100] + "..." 
                    if len(conv["task_description"]) > 100 else conv["task_description"],
                    "success": conv["response_success"]
                }
                for conv in self.conversation_history[-5:]
            ]
        }