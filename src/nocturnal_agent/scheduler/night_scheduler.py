"""Main night scheduler coordinator."""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path

from nocturnal_agent.core.models import Task, ExecutionResult, TaskPriority, TaskStatus
from nocturnal_agent.scheduler.time_controller import TimeController, ExecutionWindow
from nocturnal_agent.scheduler.task_queue import TaskQueue, QueuedTask
from nocturnal_agent.scheduler.resource_monitor import ResourceMonitor, ResourceStatus
from nocturnal_agent.quality.quality_manager import QualityManager
# from nocturnal_agent.agents.claude_agent import ClaudeAgent  # Disabled for testing


logger = logging.getLogger(__name__)


class NightScheduler:
    """Main coordinator for night-time autonomous development."""
    
    def __init__(self, project_path: str, config, main_agent=None):
        """Initialize night scheduler.
        
        Args:
            project_path: Path to the project directory
            config: Scheduler configuration (NocturnalConfig object or dict)
            main_agent: Reference to main NocturnalAgent for session settings
        """
        self.project_path = Path(project_path)
        self.config = config
        self.main_agent = main_agent  # セッション設定へのアクセス用
        
        # NocturnalConfigオブジェクトを辞書的にアクセスできるように変換
        def safe_get(obj, key, default=None):
            if hasattr(obj, key):
                return getattr(obj, key)
            elif hasattr(obj, 'get'):
                return obj.get(key, default)
            else:
                return default
        
        # Initialize components with safe config access
        self.time_controller = TimeController(safe_get(config, 'time_control', {}))
        self.task_queue = TaskQueue(str(self.project_path), safe_get(config, 'task_queue', {}))
        self.resource_monitor = ResourceMonitor(safe_get(config, 'resource_monitoring', {}))
        self.quality_manager = QualityManager(str(self.project_path), safe_get(config, 'quality_management', {}))
        
        # Execution agents (disabled for testing)
        self.claude_agent = None  # ClaudeAgent(safe_get(config, 'claude', {}))
        
        # Scheduler state
        self.is_running = False
        self.current_task: Optional[QueuedTask] = None
        self.emergency_shutdown = False
        
        # Statistics
        self.session_stats = {
            'session_start': None,
            'tasks_attempted': 0,
            'tasks_completed': 0,
            'tasks_failed': 0,
            'quality_improvements': 0,
            'emergency_stops': 0,
            'total_execution_time': timedelta(0)
        }
        
        # Setup callbacks
        self._setup_callbacks()
    
    def _setup_callbacks(self):
        """Setup callbacks between components."""
        # Time controller callbacks
        self.time_controller.add_state_change_callback(self._on_time_window_change)
        
        # Resource monitor callbacks
        self.resource_monitor.add_status_change_callback(self._on_resource_status_change)
        self.resource_monitor.add_emergency_callback(self._on_resource_emergency)
    
    async def start(self):
        """Start the night scheduler."""
        if self.is_running:
            logger.warning("Night scheduler already running")
            return
        
        logger.info("Starting night scheduler")
        self.is_running = True
        self.session_stats['session_start'] = datetime.now()
        
        # Start components
        await self.time_controller.start_monitoring()
        await self.resource_monitor.start_monitoring()
        
        # Start main execution loop
        asyncio.create_task(self._execution_loop())
        
        logger.info("Night scheduler started successfully")
    
    async def stop(self):
        """Stop the night scheduler."""
        logger.info("Stopping night scheduler")
        self.is_running = False
        
        # Stop current task if running
        if self.current_task:
            logger.info(f"Interrupting current task: {self.current_task.task.id}")
            # Note: Actual task interruption would depend on agent implementation
        
        # Stop components
        await self.time_controller.stop_monitoring()
        await self.resource_monitor.stop_monitoring()
        await self.task_queue.stop_queue()
        
        logger.info("Night scheduler stopped")
    
    async def emergency_stop(self, reason: str = "Emergency stop"):
        """Perform emergency shutdown."""
        logger.critical(f"Emergency shutdown triggered: {reason}")
        self.emergency_shutdown = True
        self.session_stats['emergency_stops'] += 1
        
        # Stop immediately
        await self.stop()
    
    async def _execution_loop(self):
        """Main execution loop."""
        while self.is_running and not self.emergency_shutdown:
            try:
                # Check if execution is allowed
                if not self._can_execute():
                    await asyncio.sleep(60)  # Check again in 1 minute
                    continue
                
                # Get next task
                next_task = await self.task_queue.get_next_task()
                if not next_task:
                    await asyncio.sleep(30)  # No tasks available, wait
                    continue
                
                # Check if we can safely execute this task
                can_execute, reason = await self._can_execute_task(next_task)
                if not can_execute:
                    logger.warning(f"Cannot execute task {next_task.task.id}: {reason}")
                    # Put task back in queue with lower priority
                    await self.task_queue.complete_task(next_task.task.id, success=False)
                    continue
                
                # Execute the task
                await self._execute_task(next_task)
                
            except Exception as e:
                logger.error(f"Error in execution loop: {e}")
                await asyncio.sleep(60)  # Wait before retrying
    
    def _can_execute(self) -> bool:
        """Check if execution is currently allowed.
        
        Returns:
            True if execution is allowed
        """
        # Check time window
        if not self.time_controller.is_execution_allowed():
            return False
        
        # Check resource safety
        is_safe, _ = self.resource_monitor.is_safe_to_execute()
        if not is_safe:
            return False
        
        # Check emergency shutdown
        if self.emergency_shutdown:
            return False
        
        return True
    
    async def _can_execute_task(self, queued_task: QueuedTask) -> tuple[bool, str]:
        """Check if a specific task can be executed.
        
        Args:
            queued_task: Task to check
            
        Returns:
            Tuple of (can_execute, reason)
        """
        # Check time constraints
        can_start, reason = self.time_controller.can_start_task(queued_task.estimated_duration)
        if not can_start:
            return False, reason
        
        # Check resource constraints
        can_run, reason = self.resource_monitor.can_safely_run_task("default")
        if not can_run:
            return False, reason
        
        return True, "Task can be executed"
    
    async def _execute_task(self, queued_task: QueuedTask):
        """Execute a single task.
        
        Args:
            queued_task: Task to execute
        """
        task = queued_task.task
        logger.info(f"Executing task: {task.id}")
        
        self.current_task = queued_task
        self.session_stats['tasks_attempted'] += 1
        execution_start = datetime.now()
        
        try:
            # Execute task using appropriate agent
            result = await self._run_task_with_agent(task)
            
            # Process result through quality management
            final_result = await self.quality_manager.process_task_result(task, result)
            
            # Determine success
            success = final_result.success and final_result.quality_score.overall >= 0.85
            
            # Complete task in queue
            await self.task_queue.complete_task(task.id, success)
            
            # Update statistics
            execution_time = datetime.now() - execution_start
            self.session_stats['total_execution_time'] += execution_time
            
            if success:
                self.session_stats['tasks_completed'] += 1
                logger.info(f"Task completed successfully: {task.id}")
                
                # Register change with time controller
                has_changes = bool(final_result.files_modified or final_result.files_created)
                self.time_controller.register_task_completion(has_changes)
            else:
                self.session_stats['tasks_failed'] += 1
                logger.warning(f"Task failed: {task.id}")
            
            # Track quality improvements
            if hasattr(final_result, 'improvement_attempts') and final_result.improvement_attempts > 0:
                self.session_stats['quality_improvements'] += 1
            
        except Exception as e:
            logger.error(f"Task execution failed: {task.id} - {e}")
            await self.task_queue.complete_task(task.id, success=False)
            self.session_stats['tasks_failed'] += 1
            
        finally:
            self.current_task = None
    
    async def _run_task_with_agent(self, task: Task) -> ExecutionResult:
        """Run a task with the appropriate agent.
        
        Args:
            task: Task to execute
            
        Returns:
            Execution result
        """
        try:
            # Check if Spec Kit should be used based on session settings
            should_use_spec_kit = False
            spec_type_str = 'feature'
            
            if self.main_agent and hasattr(self.main_agent, 'session_settings'):
                should_use_spec_kit = self.main_agent.session_settings.get('use_spec_kit', False)
                spec_type_str = self.main_agent.session_settings.get('spec_type', 'feature')
            
            if should_use_spec_kit:
                # Use Spec Kit driven execution
                logger.info(f"Using Spec Kit driven execution for task: {task.id} (type: {spec_type_str})")
                
                from nocturnal_agent.design.spec_kit_integration import SpecType
                
                # Convert string to SpecType enum
                spec_type = SpecType.FEATURE  # default
                if spec_type_str in ['feature', 'architecture', 'api', 'design', 'process']:
                    spec_type = SpecType(spec_type_str)
                
                # Create mock executor function for now
                async def mock_executor(task_to_execute):
                    """Mock executor function"""
                    from nocturnal_agent.core.models import QualityScore, AgentType
                    await asyncio.sleep(1)  # Simulate work
                    return ExecutionResult(
                        task_id=task_to_execute.id,
                        success=True,
                        quality_score=QualityScore(
                            overall=0.92,
                            code_quality=0.9,
                            consistency=0.95,
                            test_coverage=0.9
                        ),
                        generated_code="# Spec Kit driven code\ndef spec_driven_function():\n    return True",
                        agent_used=AgentType.LOCAL_LLM,
                        execution_time=1.0
                    )
                
                # Use main agent's Spec Kit execution method
                return await self.main_agent.execute_task_with_spec_design(task, mock_executor, spec_type)
            
            else:
                # Use standard execution (mock for now)
                logger.info(f"Using standard execution for task: {task.id}")
                
                # Simulate execution
                await asyncio.sleep(1)  # Simulate work
                
                from nocturnal_agent.core.models import QualityScore, AgentType
                return ExecutionResult(
                    task_id=task.id,
                    success=True,
                    quality_score=QualityScore(
                        overall=0.9,
                        code_quality=0.85,
                        consistency=0.95,
                        test_coverage=0.9
                    ),
                    generated_code="# Standard generated code\ndef standard_function():\n    return True",
                    agent_used=AgentType.LOCAL_LLM,
                    execution_time=1.0
                )
            
        except Exception as e:
            logger.error(f"Agent execution failed: {e}")
            
            # Return failure result
            from nocturnal_agent.core.models import QualityScore, AgentType
            return ExecutionResult(
                task_id=task.id,
                success=False,
                quality_score=QualityScore(overall=0.0),
                generated_code="",
                agent_used=AgentType.LOCAL_LLM,
                errors=[f"Agent execution failed: {str(e)}"]
            )
    
    async def _on_time_window_change(self, old_state: ExecutionWindow, new_state: ExecutionWindow, timestamp: datetime):
        """Handle time window state changes.
        
        Args:
            old_state: Previous execution state
            new_state: New execution state
            timestamp: When the change occurred
        """
        logger.info(f"Time window changed: {old_state.value} -> {new_state.value}")
        
        if new_state == ExecutionWindow.INACTIVE and self.current_task:
            # Time window closed while task running - let it finish gracefully
            logger.info("Time window closed - current task will complete then scheduler will pause")
        
        if new_state == ExecutionWindow.ACTIVE:
            # Time window opened - resume queue if paused
            if self.task_queue.status.value == 'paused':
                await self.task_queue.resume_queue()
                logger.info("Time window opened - resuming task queue")
    
    async def _on_resource_status_change(self, old_status: ResourceStatus, new_status: ResourceStatus, snapshot):
        """Handle resource status changes.
        
        Args:
            old_status: Previous resource status
            new_status: New resource status
            snapshot: Current resource snapshot
        """
        logger.info(f"Resource status changed: {old_status.value} -> {new_status.value}")
        
        if new_status in [ResourceStatus.CRITICAL, ResourceStatus.EMERGENCY]:
            # Pause queue on critical/emergency resource status
            await self.task_queue.pause_queue()
            logger.warning("Critical resource status - pausing task queue")
        
        elif new_status == ResourceStatus.HEALTHY and old_status in [ResourceStatus.CRITICAL, ResourceStatus.WARNING]:
            # Resume queue when resources recover
            if self.time_controller.is_execution_allowed():
                await self.task_queue.resume_queue()
                logger.info("Resource status recovered - resuming task queue")
    
    async def _on_resource_emergency(self, snapshot):
        """Handle resource emergency conditions.
        
        Args:
            snapshot: Resource snapshot showing emergency
        """
        logger.critical("Resource emergency detected - triggering emergency shutdown")
        await self.emergency_stop(f"Resource emergency: CPU={snapshot.cpu_percent:.1f}%, Memory={snapshot.memory_percent:.1f}%")
    
    async def add_task(self, task: Task, priority_override: Optional[float] = None) -> bool:
        """Add a task to the scheduler.
        
        Args:
            task: Task to add
            priority_override: Optional priority override
            
        Returns:
            True if task was added successfully
        """
        return await self.task_queue.add_task(task, priority_override)
    
    async def remove_task(self, task_id: str) -> bool:
        """Remove a task from the scheduler.
        
        Args:
            task_id: ID of task to remove
            
        Returns:
            True if task was removed
        """
        return self.task_queue.remove_task(task_id)
    
    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive scheduler status.
        
        Returns:
            Scheduler status information
        """
        return {
            'scheduler': {
                'running': self.is_running,
                'current_task': self.current_task.task.id if self.current_task else None,
                'emergency_shutdown': self.emergency_shutdown,
                'session_stats': self.session_stats.copy()
            },
            'time_control': self.time_controller.get_status(),
            'task_queue': self.task_queue.get_queue_status(),
            'resources': self.resource_monitor.get_status(),
            'can_execute': self._can_execute(),
            'next_execution_window': str(self.time_controller.get_time_until_next_window()),
            'system_health': self._get_system_health()
        }
    
    def _get_system_health(self) -> Dict[str, Any]:
        """Get overall system health assessment.
        
        Returns:
            System health information
        """
        # Overall health based on all components
        time_healthy = self.time_controller.current_state != ExecutionWindow.MAINTENANCE
        resource_healthy = self.resource_monitor.current_status in [ResourceStatus.HEALTHY, ResourceStatus.WARNING]
        queue_healthy = len(self.task_queue.running_tasks) < self.task_queue.max_concurrent_tasks
        
        overall_healthy = time_healthy and resource_healthy and queue_healthy and not self.emergency_shutdown
        
        return {
            'overall_healthy': overall_healthy,
            'components': {
                'time_controller': time_healthy,
                'resource_monitor': resource_healthy,
                'task_queue': queue_healthy,
                'quality_manager': True  # Assume healthy unless we have specific checks
            },
            'emergency_status': self.emergency_shutdown,
            'can_execute_tasks': self._can_execute()
        }
    
    async def generate_night_report(self) -> Dict[str, Any]:
        """Generate comprehensive night execution report.
        
        Returns:
            Night execution report
        """
        # Get reports from all components
        quality_report = await self.quality_manager.generate_quality_report()
        morning_approval_report = await self.quality_manager.get_morning_approval_report()
        
        return {
            'session_summary': {
                'start_time': self.session_stats['session_start'].isoformat() if self.session_stats['session_start'] else None,
                'duration': str(datetime.now() - self.session_stats['session_start']) if self.session_stats['session_start'] else None,
                'tasks_attempted': self.session_stats['tasks_attempted'],
                'tasks_completed': self.session_stats['tasks_completed'],
                'tasks_failed': self.session_stats['tasks_failed'],
                'success_rate': (self.session_stats['tasks_completed'] / self.session_stats['tasks_attempted']) if self.session_stats['tasks_attempted'] > 0 else 0,
                'quality_improvements': self.session_stats['quality_improvements'],
                'emergency_stops': self.session_stats['emergency_stops'],
                'total_execution_time': str(self.session_stats['total_execution_time'])
            },
            'quality_management': quality_report,
            'morning_approvals': morning_approval_report,
            'resource_usage': self.resource_monitor.get_resource_trends(hours=8),
            'system_status': self.get_status(),
            'recommendations': self._generate_recommendations()
        }
    
    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations based on session performance.
        
        Returns:
            List of recommendations
        """
        recommendations = []
        
        # Success rate recommendations
        if self.session_stats['tasks_attempted'] > 0:
            success_rate = self.session_stats['tasks_completed'] / self.session_stats['tasks_attempted']
            if success_rate < 0.5:
                recommendations.append("Low task success rate - review task complexity and quality thresholds")
        
        # Resource recommendations
        if self.resource_monitor.stats['emergency_stops'] > 0:
            recommendations.append("Resource emergencies occurred - consider adjusting resource limits")
        
        # Queue recommendations
        queue_status = self.task_queue.get_queue_status()
        if queue_status['pending_tasks'] > 20:
            recommendations.append("Large task backlog - consider increasing execution window or reducing task complexity")
        
        # Quality recommendations
        if self.session_stats['quality_improvements'] > self.session_stats['tasks_completed']:
            recommendations.append("Many quality improvement cycles - review initial code generation quality")
        
        return recommendations
    
    async def pause(self):
        """Pause the scheduler."""
        logger.info("Pausing night scheduler")
        await self.time_controller.pause_execution("Manual pause")
        await self.task_queue.pause_queue()
    
    async def resume(self):
        """Resume the scheduler."""
        logger.info("Resuming night scheduler")
        await self.time_controller.resume_execution()
        await self.task_queue.resume_queue()
    
    async def enter_maintenance(self):
        """Enter maintenance mode."""
        logger.info("Entering maintenance mode")
        await self.time_controller.enter_maintenance_mode()
        await self.task_queue.drain_queue()  # Finish current tasks, don't start new ones
    
    async def exit_maintenance(self):
        """Exit maintenance mode."""
        logger.info("Exiting maintenance mode")
        await self.time_controller.exit_maintenance_mode()
        await self.task_queue.resume_queue()
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get detailed performance metrics.
        
        Returns:
            Performance metrics
        """
        return {
            'scheduler_metrics': {
                'uptime': str(datetime.now() - self.session_stats['session_start']) if self.session_stats['session_start'] else None,
                'task_throughput': self.session_stats['tasks_completed'] / ((datetime.now() - self.session_stats['session_start']).total_seconds() / 3600) if self.session_stats['session_start'] else 0,
                'success_rate': (self.session_stats['tasks_completed'] / self.session_stats['tasks_attempted']) if self.session_stats['tasks_attempted'] > 0 else 0,
                'average_task_time': str(self.session_stats['total_execution_time'] / self.session_stats['tasks_attempted']) if self.session_stats['tasks_attempted'] > 0 else None
            },
            'queue_metrics': self.task_queue.get_performance_metrics(),
            'resource_metrics': {
                'monitoring_uptime': str(datetime.now() - self.resource_monitor.stats['monitoring_start_time']) if self.resource_monitor.stats['monitoring_start_time'] else None,
                'status_changes': self.resource_monitor.stats['status_changes'],
                'emergency_stops': self.resource_monitor.stats['emergency_stops'],
                'max_resources_seen': {
                    'cpu': self.resource_monitor.stats['max_cpu_seen'],
                    'memory': self.resource_monitor.stats['max_memory_seen']
                }
            }
        }