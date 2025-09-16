"""Time control system for night execution windows."""

import logging
import asyncio
from datetime import datetime, time, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
import pytz


logger = logging.getLogger(__name__)


class ExecutionWindow(Enum):
    """Execution window states."""
    ACTIVE = "active"      # Within execution window
    INACTIVE = "inactive"  # Outside execution window  
    PAUSED = "paused"     # Manually paused
    MAINTENANCE = "maintenance"  # In maintenance mode


@dataclass
class TimeWindow:
    """Definition of a time window."""
    start_time: time
    end_time: time
    timezone: str = "UTC"
    enabled: bool = True
    
    def contains_time(self, current_time: datetime) -> bool:
        """Check if current time is within this window."""
        # Convert to window timezone
        if self.timezone != "UTC":
            tz = pytz.timezone(self.timezone)
            current_time = current_time.astimezone(tz)
        
        current_time_only = current_time.time()
        
        # Handle overnight windows (e.g., 22:00 - 06:00)
        if self.start_time > self.end_time:
            return current_time_only >= self.start_time or current_time_only <= self.end_time
        else:
            return self.start_time <= current_time_only <= self.end_time


class TimeController:
    """Controls execution time windows and scheduling."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize time controller.
        
        Args:
            config: Time configuration
        """
        self.config = config
        
        # Default execution window: 22:00 - 06:00
        self.execution_window = TimeWindow(
            start_time=time(22, 0),  # 22:00
            end_time=time(6, 0),     # 06:00
            timezone=config.get('timezone', 'UTC'),
            enabled=config.get('window_enabled', True)
        )
        
        # Task time limits
        self.max_task_duration = timedelta(minutes=config.get('max_task_minutes', 30))
        self.max_session_duration = timedelta(hours=config.get('max_session_hours', 8))
        self.max_daily_changes = config.get('max_daily_changes', 10)
        
        # Current state
        self.current_state = ExecutionWindow.INACTIVE
        self.session_start_time: Optional[datetime] = None
        self.daily_changes_count = 0
        self.last_reset_date: Optional[datetime] = None
        
        # Monitoring
        self.state_change_callbacks = []
        self.is_monitoring = False
        
    async def start_monitoring(self):
        """Start time-based monitoring and control."""
        if self.is_monitoring:
            logger.warning("Time monitoring already started")
            return
        
        logger.info("Starting time-based monitoring")
        self.is_monitoring = True
        
        # Reset daily counters if needed
        await self._check_daily_reset()
        
        # Start monitoring loop
        asyncio.create_task(self._monitoring_loop())
        
    async def stop_monitoring(self):
        """Stop time monitoring."""
        logger.info("Stopping time-based monitoring")
        self.is_monitoring = False
        
    async def _monitoring_loop(self):
        """Main monitoring loop."""
        while self.is_monitoring:
            try:
                current_time = datetime.now()
                old_state = self.current_state
                
                # Check daily reset
                await self._check_daily_reset()
                
                # Determine new state
                new_state = await self._determine_execution_state(current_time)
                
                # Update state if changed
                if new_state != old_state:
                    await self._update_execution_state(old_state, new_state, current_time)
                
                # Sleep for 1 minute before next check
                await asyncio.sleep(60)
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(10)  # Short sleep before retry
    
    async def _determine_execution_state(self, current_time: datetime) -> ExecutionWindow:
        """Determine what the execution state should be.
        
        Args:
            current_time: Current datetime
            
        Returns:
            Appropriate execution state
        """
        # Check if manually paused or in maintenance
        if self.current_state in [ExecutionWindow.PAUSED, ExecutionWindow.MAINTENANCE]:
            return self.current_state
        
        # Check if execution window is disabled
        if not self.execution_window.enabled:
            return ExecutionWindow.INACTIVE
        
        # Check daily change limit
        if self.daily_changes_count >= self.max_daily_changes:
            logger.info(f"Daily change limit reached: {self.daily_changes_count}/{self.max_daily_changes}")
            return ExecutionWindow.INACTIVE
        
        # Check session duration limit
        if self.session_start_time:
            session_duration = current_time - self.session_start_time
            if session_duration >= self.max_session_duration:
                logger.info(f"Session duration limit reached: {session_duration}")
                return ExecutionWindow.INACTIVE
        
        # Check if within execution window
        if self.execution_window.contains_time(current_time):
            return ExecutionWindow.ACTIVE
        else:
            return ExecutionWindow.INACTIVE
    
    async def _update_execution_state(
        self, 
        old_state: ExecutionWindow, 
        new_state: ExecutionWindow,
        current_time: datetime
    ):
        """Update execution state and notify callbacks.
        
        Args:
            old_state: Previous state
            new_state: New state
            current_time: Current datetime
        """
        logger.info(f"Execution state change: {old_state.value} -> {new_state.value}")
        
        self.current_state = new_state
        
        # Handle state transitions
        if new_state == ExecutionWindow.ACTIVE and old_state == ExecutionWindow.INACTIVE:
            # Starting active session
            self.session_start_time = current_time
            logger.info(f"Starting nocturnal execution session at {current_time}")
            
        elif new_state == ExecutionWindow.INACTIVE and old_state == ExecutionWindow.ACTIVE:
            # Ending active session
            if self.session_start_time:
                session_duration = current_time - self.session_start_time
                logger.info(f"Ending nocturnal session after {session_duration}")
            self.session_start_time = None
        
        # Notify callbacks
        for callback in self.state_change_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(old_state, new_state, current_time)
                else:
                    callback(old_state, new_state, current_time)
            except Exception as e:
                logger.error(f"Error in state change callback: {e}")
    
    async def _check_daily_reset(self):
        """Check if daily counters need to be reset."""
        current_date = datetime.now().date()
        
        if self.last_reset_date != current_date:
            logger.info(f"Resetting daily counters for {current_date}")
            self.daily_changes_count = 0
            self.last_reset_date = current_date
    
    def is_execution_allowed(self) -> bool:
        """Check if execution is currently allowed.
        
        Returns:
            True if execution is allowed, False otherwise
        """
        return self.current_state == ExecutionWindow.ACTIVE
    
    def get_time_until_next_window(self) -> Optional[timedelta]:
        """Get time until next execution window.
        
        Returns:
            Time until next window, or None if currently in window
        """
        if self.current_state == ExecutionWindow.ACTIVE:
            return None
        
        current_time = datetime.now()
        
        # Convert to window timezone
        if self.execution_window.timezone != "UTC":
            tz = pytz.timezone(self.execution_window.timezone)
            current_time = current_time.astimezone(tz)
        
        # Calculate next window start
        next_start = current_time.replace(
            hour=self.execution_window.start_time.hour,
            minute=self.execution_window.start_time.minute,
            second=0,
            microsecond=0
        )
        
        # If start time has passed today, move to tomorrow
        if next_start <= current_time:
            next_start += timedelta(days=1)
        
        return next_start - current_time
    
    def get_remaining_window_time(self) -> Optional[timedelta]:
        """Get remaining time in current execution window.
        
        Returns:
            Remaining time, or None if not in window
        """
        if self.current_state != ExecutionWindow.ACTIVE:
            return None
        
        current_time = datetime.now()
        
        # Convert to window timezone
        if self.execution_window.timezone != "UTC":
            tz = pytz.timezone(self.execution_window.timezone)
            current_time = current_time.astimezone(tz)
        
        # Calculate window end time
        window_end = current_time.replace(
            hour=self.execution_window.end_time.hour,
            minute=self.execution_window.end_time.minute,
            second=0,
            microsecond=0
        )
        
        # Handle overnight windows
        if self.execution_window.start_time > self.execution_window.end_time:
            if current_time.time() >= self.execution_window.start_time:
                # Currently after start time, end is tomorrow
                window_end += timedelta(days=1)
            # else: currently before end time, end is today
        
        return window_end - current_time
    
    def can_start_task(self, estimated_duration: timedelta) -> Tuple[bool, str]:
        """Check if a task can be started given time constraints.
        
        Args:
            estimated_duration: Estimated task duration
            
        Returns:
            Tuple of (can_start, reason)
        """
        if not self.is_execution_allowed():
            return False, f"Execution not allowed in state: {self.current_state.value}"
        
        # Check task duration limit
        if estimated_duration > self.max_task_duration:
            return False, f"Task duration {estimated_duration} exceeds limit {self.max_task_duration}"
        
        # Check remaining window time
        remaining_time = self.get_remaining_window_time()
        if remaining_time and estimated_duration > remaining_time:
            return False, f"Not enough time remaining in window: {remaining_time}"
        
        # Check daily change limit
        if self.daily_changes_count >= self.max_daily_changes:
            return False, f"Daily change limit reached: {self.daily_changes_count}/{self.max_daily_changes}"
        
        return True, "Task can be started"
    
    def register_task_completion(self, made_changes: bool = False):
        """Register completion of a task.
        
        Args:
            made_changes: Whether the task made changes to the codebase
        """
        if made_changes:
            self.daily_changes_count += 1
            logger.info(f"Daily changes: {self.daily_changes_count}/{self.max_daily_changes}")
    
    def add_state_change_callback(self, callback):
        """Add a callback for state changes.
        
        Args:
            callback: Function to call on state change
        """
        self.state_change_callbacks.append(callback)
    
    def remove_state_change_callback(self, callback):
        """Remove a state change callback.
        
        Args:
            callback: Function to remove
        """
        if callback in self.state_change_callbacks:
            self.state_change_callbacks.remove(callback)
    
    async def pause_execution(self, reason: str = "Manual pause"):
        """Manually pause execution.
        
        Args:
            reason: Reason for pausing
        """
        logger.info(f"Pausing execution: {reason}")
        old_state = self.current_state
        await self._update_execution_state(old_state, ExecutionWindow.PAUSED, datetime.now())
    
    async def resume_execution(self):
        """Resume execution from pause."""
        if self.current_state != ExecutionWindow.PAUSED:
            logger.warning("Cannot resume - not currently paused")
            return
        
        logger.info("Resuming execution from pause")
        current_time = datetime.now()
        new_state = await self._determine_execution_state(current_time)
        await self._update_execution_state(ExecutionWindow.PAUSED, new_state, current_time)
    
    async def enter_maintenance_mode(self):
        """Enter maintenance mode (blocks all execution)."""
        logger.info("Entering maintenance mode")
        old_state = self.current_state
        await self._update_execution_state(old_state, ExecutionWindow.MAINTENANCE, datetime.now())
    
    async def exit_maintenance_mode(self):
        """Exit maintenance mode."""
        if self.current_state != ExecutionWindow.MAINTENANCE:
            logger.warning("Cannot exit maintenance - not in maintenance mode")
            return
        
        logger.info("Exiting maintenance mode")
        current_time = datetime.now()
        new_state = await self._determine_execution_state(current_time)
        await self._update_execution_state(ExecutionWindow.MAINTENANCE, new_state, current_time)
    
    def get_status(self) -> Dict[str, Any]:
        """Get current time controller status.
        
        Returns:
            Status information
        """
        current_time = datetime.now()
        
        return {
            'current_state': self.current_state.value,
            'execution_allowed': self.is_execution_allowed(),
            'current_time': current_time.isoformat(),
            'execution_window': {
                'start': self.execution_window.start_time.isoformat(),
                'end': self.execution_window.end_time.isoformat(),
                'timezone': self.execution_window.timezone,
                'enabled': self.execution_window.enabled
            },
            'session_info': {
                'start_time': self.session_start_time.isoformat() if self.session_start_time else None,
                'duration': str(current_time - self.session_start_time) if self.session_start_time else None
            },
            'limits': {
                'max_task_duration': str(self.max_task_duration),
                'max_session_duration': str(self.max_session_duration),
                'daily_changes': f"{self.daily_changes_count}/{self.max_daily_changes}"
            },
            'timing': {
                'time_until_next_window': str(self.get_time_until_next_window()),
                'remaining_window_time': str(self.get_remaining_window_time())
            },
            'monitoring_active': self.is_monitoring
        }