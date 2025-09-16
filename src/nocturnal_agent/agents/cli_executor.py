"""CLI execution framework for coding agents."""

import asyncio
import json
import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from nocturnal_agent.core.models import Task, ExecutionResult, QualityScore, AgentType
from nocturnal_agent.agents.agent_detector import DetectedAgent


logger = logging.getLogger(__name__)


class CLIExecutionContext:
    """Context for CLI execution with temporary file management."""
    
    def __init__(self, working_dir: Optional[str] = None):
        """Initialize execution context."""
        self.working_dir = working_dir
        self.temp_dir: Optional[str] = None
        self.temp_files: List[str] = []
        self.created_files: List[str] = []
        self.modified_files: List[str] = []
    
    async def __aenter__(self):
        """Enter async context manager."""
        self.temp_dir = tempfile.mkdtemp(prefix="nocturnal_agent_")
        logger.debug(f"Created temporary directory: {self.temp_dir}")
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context manager."""
        await self.cleanup()
    
    def create_temp_file(self, content: str, suffix: str = ".txt") -> str:
        """Create a temporary file with content."""
        if not self.temp_dir:
            raise RuntimeError("Context not initialized")
        
        fd, temp_path = tempfile.mkstemp(dir=self.temp_dir, suffix=suffix)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                f.write(content)
        except Exception:
            os.close(fd)
            raise
        
        self.temp_files.append(temp_path)
        return temp_path
    
    def get_temp_path(self, filename: str) -> str:
        """Get path for a temporary file."""
        if not self.temp_dir:
            raise RuntimeError("Context not initialized")
        return os.path.join(self.temp_dir, filename)
    
    async def cleanup(self) -> None:
        """Clean up temporary files and directories."""
        if self.temp_dir and os.path.exists(self.temp_dir):
            import shutil
            try:
                shutil.rmtree(self.temp_dir)
                logger.debug(f"Cleaned up temporary directory: {self.temp_dir}")
            except Exception as e:
                logger.warning(f"Failed to clean up temp directory {self.temp_dir}: {e}")


class CLICommand:
    """Represents a CLI command to be executed."""
    
    def __init__(
        self,
        command: List[str],
        working_dir: Optional[str] = None,
        env_vars: Optional[Dict[str, str]] = None,
        timeout: int = 300,
        input_data: Optional[str] = None
    ):
        """Initialize CLI command."""
        self.command = command
        self.working_dir = working_dir
        self.env_vars = env_vars or {}
        self.timeout = timeout
        self.input_data = input_data
        
        # Execution results
        self.returncode: Optional[int] = None
        self.stdout: str = ""
        self.stderr: str = ""
        self.execution_time: float = 0.0
        self.success: bool = False


class CLIExecutor:
    """Executes CLI commands with proper process management."""
    
    def __init__(self, max_concurrent: int = 3):
        """Initialize CLI executor."""
        self.max_concurrent = max_concurrent
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self.execution_history: List[Dict[str, Any]] = []
    
    async def execute_command(self, command: CLICommand) -> CLICommand:
        """Execute a CLI command with timeout and error handling."""
        async with self._semaphore:
            return await self._execute_single_command(command)
    
    async def _execute_single_command(self, command: CLICommand) -> CLICommand:
        """Execute a single CLI command."""
        start_time = time.time()
        
        try:
            # Prepare environment
            env = os.environ.copy()
            env.update(command.env_vars)
            
            # Log command execution
            logger.info(f"Executing: {' '.join(command.command)}")
            if command.working_dir:
                logger.debug(f"Working directory: {command.working_dir}")
            
            # Create subprocess
            process = await asyncio.create_subprocess_exec(
                *command.command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.PIPE if command.input_data else None,
                cwd=command.working_dir,
                env=env
            )
            
            # Execute with timeout
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(
                        input=command.input_data.encode('utf-8') if command.input_data else None
                    ),
                    timeout=command.timeout
                )
            except asyncio.TimeoutError:
                # Kill process on timeout
                process.kill()
                await process.wait()
                raise asyncio.TimeoutError(f"Command timed out after {command.timeout} seconds")
            
            # Store results
            command.returncode = process.returncode
            command.stdout = stdout.decode('utf-8', errors='ignore')
            command.stderr = stderr.decode('utf-8', errors='ignore')
            command.success = process.returncode == 0
            
        except Exception as e:
            logger.error(f"Command execution failed: {e}")
            command.returncode = -1
            command.stderr = str(e)
            command.success = False
        
        finally:
            command.execution_time = time.time() - start_time
        
        # Log execution summary
        logger.info(f"Command completed in {command.execution_time:.2f}s, "
                   f"exit_code={command.returncode}, success={command.success}")
        
        if not command.success:
            logger.debug(f"Command stderr: {command.stderr}")
        
        # Record execution
        self.execution_history.append({
            "command": command.command,
            "working_dir": command.working_dir,
            "returncode": command.returncode,
            "execution_time": command.execution_time,
            "success": command.success,
            "timestamp": time.time()
        })
        
        return command
    
    async def execute_batch(self, commands: List[CLICommand]) -> List[CLICommand]:
        """Execute multiple commands concurrently."""
        tasks = [self.execute_command(cmd) for cmd in commands]
        return await asyncio.gather(*tasks)
    
    def get_execution_stats(self) -> Dict[str, Any]:
        """Get execution statistics."""
        if not self.execution_history:
            return {"total_executions": 0}
        
        total = len(self.execution_history)
        successful = sum(1 for exec in self.execution_history if exec["success"])
        avg_time = sum(exec["execution_time"] for exec in self.execution_history) / total
        
        return {
            "total_executions": total,
            "successful": successful,
            "success_rate": successful / total,
            "average_execution_time": avg_time,
            "recent_executions": self.execution_history[-10:]  # Last 10
        }


class AgentCLIInterface:
    """Base interface for CLI-based coding agents."""
    
    def __init__(self, agent: DetectedAgent, executor: CLIExecutor):
        """Initialize agent CLI interface."""
        self.agent = agent
        self.executor = executor
        self.base_command = agent.command
    
    async def execute_task(self, task: Task, context: CLIExecutionContext) -> ExecutionResult:
        """Execute a task using this agent (to be implemented by subclasses)."""
        raise NotImplementedError("Subclasses must implement execute_task")
    
    async def test_connection(self) -> bool:
        """Test if agent is responding."""
        try:
            # Try a simple version check
            command = CLICommand([self.base_command, "--version"], timeout=10)
            result = await self.executor.execute_command(command)
            return result.success
        except Exception:
            return False
    
    def build_command(
        self, 
        args: List[str], 
        working_dir: Optional[str] = None,
        timeout: int = 300
    ) -> CLICommand:
        """Build a CLI command for this agent."""
        full_command = [self.base_command] + args
        return CLICommand(
            command=full_command,
            working_dir=working_dir,
            timeout=timeout
        )
    
    def parse_output(self, output: str) -> Dict[str, Any]:
        """Parse agent output (to be implemented by subclasses)."""
        return {"raw_output": output}


class AgentManager:
    """Manages multiple CLI coding agents."""
    
    def __init__(self, executor: CLIExecutor):
        """Initialize agent manager."""
        self.executor = executor
        self.agents: Dict[AgentType, AgentCLIInterface] = {}
        self.default_agent: Optional[AgentCLIInterface] = None
    
    def register_agent(self, agent_type: AgentType, interface: AgentCLIInterface) -> None:
        """Register an agent interface."""
        self.agents[agent_type] = interface
        logger.info(f"Registered agent: {agent_type.value}")
        
        # Set as default if it's the first or highest priority
        if (not self.default_agent or 
            interface.agent.priority < self.default_agent.agent.priority):
            self.default_agent = interface
            logger.info(f"Set default agent: {agent_type.value}")
    
    async def execute_with_agent(
        self, 
        task: Task, 
        agent_type: Optional[AgentType] = None,
        fallback: bool = True
    ) -> ExecutionResult:
        """Execute task with specified agent or default."""
        
        # Select agent
        selected_agent = None
        if agent_type and agent_type in self.agents:
            selected_agent = self.agents[agent_type]
        elif self.default_agent:
            selected_agent = self.default_agent
        
        if not selected_agent:
            raise RuntimeError("No agent available for task execution")
        
        # Execute with context
        async with CLIExecutionContext(task.working_directory) as context:
            try:
                result = await selected_agent.execute_task(task, context)
                result.agent_used = selected_agent.agent.agent_type
                return result
                
            except Exception as e:
                logger.error(f"Task execution failed with {selected_agent.agent.agent_type.value}: {e}")
                
                # Try fallback if enabled
                if fallback and len(self.agents) > 1:
                    return await self._try_fallback(task, selected_agent.agent.agent_type)
                
                # Return failure result
                return ExecutionResult(
                    task_id=task.id,
                    success=False,
                    quality_score=QualityScore(),
                    agent_used=selected_agent.agent.agent_type,
                    errors=[str(e)]
                )
    
    async def _try_fallback(self, task: Task, failed_agent: AgentType) -> ExecutionResult:
        """Try executing with fallback agents."""
        logger.info(f"Attempting fallback execution after {failed_agent.value} failure")
        
        # Try other available agents
        for agent_type, interface in self.agents.items():
            if agent_type == failed_agent:
                continue
            
            if not interface.agent.is_available:
                continue
            
            try:
                async with CLIExecutionContext(task.working_directory) as context:
                    result = await interface.execute_task(task, context)
                    result.agent_used = agent_type
                    logger.info(f"Fallback successful with {agent_type.value}")
                    return result
                    
            except Exception as e:
                logger.warning(f"Fallback failed with {agent_type.value}: {e}")
                continue
        
        # All agents failed
        logger.error("All available agents failed to execute task")
        return ExecutionResult(
            task_id=task.id,
            success=False,
            quality_score=QualityScore(),
            agent_used=failed_agent,
            errors=["All available agents failed"]
        )
    
    async def health_check_all(self) -> Dict[AgentType, bool]:
        """Check health of all registered agents."""
        results = {}
        tasks = []
        
        for agent_type, interface in self.agents.items():
            tasks.append(self._check_agent_health(agent_type, interface))
        
        health_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, (agent_type, _) in enumerate(self.agents.items()):
            result = health_results[i]
            results[agent_type] = result if isinstance(result, bool) else False
        
        return results
    
    async def _check_agent_health(self, agent_type: AgentType, interface: AgentCLIInterface) -> bool:
        """Check health of a single agent."""
        try:
            return await interface.test_connection()
        except Exception as e:
            logger.error(f"Health check failed for {agent_type.value}: {e}")
            return False
    
    def get_available_agents(self) -> List[AgentType]:
        """Get list of available agent types."""
        return [
            agent_type for agent_type, interface in self.agents.items()
            if interface.agent.is_available and interface.agent.is_authenticated
        ]
    
    def get_agent_capabilities(self) -> Dict[AgentType, List[str]]:
        """Get capabilities of all agents."""
        capabilities = {}
        for agent_type, interface in self.agents.items():
            capabilities[agent_type] = [
                cap.name for cap in interface.agent.capabilities
            ]
        return capabilities