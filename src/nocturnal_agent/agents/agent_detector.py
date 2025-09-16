"""CLI agent detection and capability assessment."""

import asyncio
import json
import logging
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from nocturnal_agent.core.models import AgentType


logger = logging.getLogger(__name__)


@dataclass
class AgentCapability:
    """Represents a capability of a coding agent."""
    name: str
    description: str
    confidence: float = 0.0  # 0.0-1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DetectedAgent:
    """Information about a detected coding agent."""
    agent_type: AgentType
    command: str
    version: str = ""
    is_authenticated: bool = False
    is_available: bool = False
    capabilities: List[AgentCapability] = field(default_factory=list)
    priority: int = 0  # Lower number = higher priority
    last_checked: Optional[str] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_capability_score(self) -> float:
        """Calculate overall capability score."""
        if not self.capabilities:
            return 0.0
        return sum(cap.confidence for cap in self.capabilities) / len(self.capabilities)


class AgentDetector:
    """Detects and assesses available CLI coding agents."""
    
    # Known CLI agents and their detection commands
    KNOWN_AGENTS = {
        AgentType.CLAUDE_CODE: {
            "commands": ["claude"],
            "version_args": ["--version"],
            "auth_check": ["auth", "status"],
            "priority": 1
        },
        AgentType.GITHUB_COPILOT: {
            "commands": ["gh", "copilot"],
            "version_args": ["--version"],
            "auth_check": ["auth", "status"],
            "priority": 2
        },
        AgentType.CURSOR: {
            "commands": ["cursor"],
            "version_args": ["--version"],
            "auth_check": [],
            "priority": 3
        }
    }
    
    def __init__(self):
        """Initialize agent detector."""
        self.detected_agents: List[DetectedAgent] = []
        self.last_scan_time: Optional[str] = None
    
    async def scan_agents(self, force_rescan: bool = False) -> List[DetectedAgent]:
        """Scan for available coding agents."""
        if not force_rescan and self.detected_agents:
            logger.info("Using cached agent detection results")
            return self.detected_agents
        
        logger.info("Scanning for available coding agents...")
        self.detected_agents = []
        
        # Scan for each known agent type
        tasks = []
        for agent_type, config in self.KNOWN_AGENTS.items():
            tasks.append(self._detect_agent(agent_type, config))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        for result in results:
            if isinstance(result, DetectedAgent):
                self.detected_agents.append(result)
            elif isinstance(result, Exception):
                logger.error(f"Agent detection failed: {result}")
        
        # Sort by priority and availability
        self.detected_agents.sort(
            key=lambda x: (not x.is_available, x.priority, -x.get_capability_score())
        )
        
        from datetime import datetime
        self.last_scan_time = datetime.now().isoformat()
        
        logger.info(f"Detected {len(self.detected_agents)} agents: "
                   f"{[agent.agent_type.value for agent in self.detected_agents]}")
        
        return self.detected_agents
    
    async def _detect_agent(self, agent_type: AgentType, config: Dict[str, Any]) -> Optional[DetectedAgent]:
        """Detect a specific agent type."""
        commands = config["commands"]
        
        # Check if command exists
        primary_command = commands[0]
        if not shutil.which(primary_command):
            logger.debug(f"{agent_type.value}: Command '{primary_command}' not found")
            return DetectedAgent(
                agent_type=agent_type,
                command=primary_command,
                is_available=False,
                error_message=f"Command '{primary_command}' not found"
            )
        
        agent = DetectedAgent(
            agent_type=agent_type,
            command=primary_command,
            priority=config.get("priority", 99)
        )
        
        try:
            # Get version information
            await self._get_version_info(agent, config)
            
            # Check authentication status
            await self._check_authentication(agent, config)
            
            # Assess capabilities
            await self._assess_capabilities(agent)
            
            agent.is_available = True
            logger.info(f"Detected {agent_type.value}: {agent.version}, "
                       f"auth={agent.is_authenticated}, "
                       f"capabilities={len(agent.capabilities)}")
            
        except Exception as e:
            logger.warning(f"Failed to detect {agent_type.value}: {e}")
            agent.is_available = False
            agent.error_message = str(e)
        
        return agent
    
    async def _get_version_info(self, agent: DetectedAgent, config: Dict[str, Any]) -> None:
        """Get version information for an agent."""
        version_args = config.get("version_args", ["--version"])
        
        try:
            # Build command
            if agent.agent_type == AgentType.GITHUB_COPILOT:
                # Special case for GitHub Copilot
                cmd = ["gh", "copilot", "--version"]
            else:
                cmd = [agent.command] + version_args
            
            # Execute command
            result = await self._run_command(cmd, timeout=10)
            
            if result["returncode"] == 0:
                version_output = result["stdout"].strip()
                agent.version = self._parse_version(version_output)
                agent.metadata["version_output"] = version_output
            else:
                logger.debug(f"Version check failed for {agent.agent_type.value}: {result['stderr']}")
                
        except Exception as e:
            logger.debug(f"Version check error for {agent.agent_type.value}: {e}")
    
    async def _check_authentication(self, agent: DetectedAgent, config: Dict[str, Any]) -> None:
        """Check authentication status for an agent."""
        auth_check = config.get("auth_check", [])
        
        if not auth_check:
            # No auth check available, assume authenticated if command exists
            agent.is_authenticated = True
            return
        
        try:
            # Build auth check command
            if agent.agent_type == AgentType.CLAUDE_CODE:
                cmd = ["claude", "auth", "status"]
            elif agent.agent_type == AgentType.GITHUB_COPILOT:
                cmd = ["gh", "auth", "status"]
            else:
                cmd = [agent.command] + auth_check
            
            # Execute command
            result = await self._run_command(cmd, timeout=15)
            
            # Parse authentication status
            if agent.agent_type == AgentType.CLAUDE_CODE:
                agent.is_authenticated = self._parse_claude_auth(result)
            elif agent.agent_type == AgentType.GITHUB_COPILOT:
                agent.is_authenticated = self._parse_github_auth(result)
            else:
                agent.is_authenticated = result["returncode"] == 0
            
            agent.metadata["auth_output"] = result["stdout"]
            
        except Exception as e:
            logger.debug(f"Auth check error for {agent.agent_type.value}: {e}")
            agent.is_authenticated = False
    
    async def _assess_capabilities(self, agent: DetectedAgent) -> None:
        """Assess the capabilities of an agent."""
        capabilities = []
        
        if agent.agent_type == AgentType.CLAUDE_CODE:
            capabilities.extend([
                AgentCapability(
                    name="code_generation",
                    description="Generate code from natural language",
                    confidence=0.9
                ),
                AgentCapability(
                    name="code_analysis",
                    description="Analyze and explain code",
                    confidence=0.85
                ),
                AgentCapability(
                    name="refactoring",
                    description="Refactor and improve code",
                    confidence=0.8
                ),
                AgentCapability(
                    name="debugging",
                    description="Debug and fix code issues",
                    confidence=0.75
                ),
                AgentCapability(
                    name="documentation",
                    description="Generate documentation",
                    confidence=0.8
                )
            ])
        
        elif agent.agent_type == AgentType.GITHUB_COPILOT:
            capabilities.extend([
                AgentCapability(
                    name="code_completion",
                    description="Auto-complete code",
                    confidence=0.9
                ),
                AgentCapability(
                    name="code_generation",
                    description="Generate code from comments",
                    confidence=0.8
                ),
                AgentCapability(
                    name="pattern_recognition",
                    description="Recognize and apply code patterns",
                    confidence=0.85
                )
            ])
        
        elif agent.agent_type == AgentType.CURSOR:
            capabilities.extend([
                AgentCapability(
                    name="code_editing",
                    description="Interactive code editing",
                    confidence=0.7
                ),
                AgentCapability(
                    name="ai_assistance",
                    description="AI-powered coding assistance",
                    confidence=0.6
                )
            ])
        
        # Adjust confidence based on authentication status
        if not agent.is_authenticated:
            for cap in capabilities:
                cap.confidence *= 0.5  # Reduce confidence if not authenticated
        
        agent.capabilities = capabilities
    
    async def _run_command(self, cmd: List[str], timeout: int = 30) -> Dict[str, Any]:
        """Run a command and return result."""
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), 
                timeout=timeout
            )
            
            return {
                "returncode": process.returncode,
                "stdout": stdout.decode('utf-8', errors='ignore'),
                "stderr": stderr.decode('utf-8', errors='ignore')
            }
            
        except asyncio.TimeoutError:
            raise RuntimeError(f"Command timeout: {' '.join(cmd)}")
        except Exception as e:
            raise RuntimeError(f"Command failed: {' '.join(cmd)} - {e}")
    
    def _parse_version(self, version_output: str) -> str:
        """Parse version from command output."""
        lines = version_output.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Common version patterns
            import re
            version_patterns = [
                r'(\d+\.\d+\.\d+)',
                r'v(\d+\.\d+\.\d+)',
                r'version (\d+\.\d+\.\d+)',
                r'(\d+\.\d+)'
            ]
            
            for pattern in version_patterns:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    return match.group(1)
            
            # If no pattern matches, return first non-empty line
            return line
        
        return "unknown"
    
    def _parse_claude_auth(self, result: Dict[str, Any]) -> bool:
        """Parse Claude authentication status."""
        if result["returncode"] != 0:
            return False
        
        output = result["stdout"].lower()
        # Look for positive authentication indicators
        auth_indicators = ["authenticated", "logged in", "valid", "active"]
        return any(indicator in output for indicator in auth_indicators)
    
    def _parse_github_auth(self, result: Dict[str, Any]) -> bool:
        """Parse GitHub authentication status."""
        if result["returncode"] != 0:
            return False
        
        output = result["stdout"].lower()
        # Look for positive authentication indicators
        auth_indicators = ["logged in", "authenticated"]
        return any(indicator in output for indicator in auth_indicators)
    
    def get_best_agent(self, required_capabilities: List[str] = None) -> Optional[DetectedAgent]:
        """Get the best available agent for given capabilities."""
        if not self.detected_agents:
            return None
        
        available_agents = [agent for agent in self.detected_agents if agent.is_available]
        
        if not available_agents:
            return None
        
        if not required_capabilities:
            # Return highest priority available agent
            return available_agents[0]
        
        # Score agents based on required capabilities
        best_agent = None
        best_score = 0.0
        
        for agent in available_agents:
            score = self._calculate_capability_match(agent, required_capabilities)
            if score > best_score:
                best_score = score
                best_agent = agent
        
        return best_agent
    
    def _calculate_capability_match(self, agent: DetectedAgent, required_capabilities: List[str]) -> float:
        """Calculate how well an agent matches required capabilities."""
        if not agent.capabilities:
            return 0.0
        
        agent_capability_names = {cap.name.lower() for cap in agent.capabilities}
        required_lower = {cap.lower() for cap in required_capabilities}
        
        # Calculate match score
        matches = len(agent_capability_names.intersection(required_lower))
        total_required = len(required_capabilities)
        
        if total_required == 0:
            return agent.get_capability_score()
        
        match_ratio = matches / total_required
        capability_score = agent.get_capability_score()
        
        # Combine match ratio with capability confidence
        return (match_ratio * 0.7) + (capability_score * 0.3)
    
    def get_agent_by_type(self, agent_type: AgentType) -> Optional[DetectedAgent]:
        """Get agent by specific type."""
        for agent in self.detected_agents:
            if agent.agent_type == agent_type and agent.is_available:
                return agent
        return None
    
    def get_authenticated_agents(self) -> List[DetectedAgent]:
        """Get all authenticated and available agents."""
        return [
            agent for agent in self.detected_agents 
            if agent.is_available and agent.is_authenticated
        ]
    
    def get_detection_summary(self) -> Dict[str, Any]:
        """Get summary of agent detection results."""
        total_detected = len(self.detected_agents)
        available_count = len([a for a in self.detected_agents if a.is_available])
        authenticated_count = len([a for a in self.detected_agents if a.is_authenticated])
        
        agent_details = []
        for agent in self.detected_agents:
            agent_details.append({
                "type": agent.agent_type.value,
                "command": agent.command,
                "version": agent.version,
                "available": agent.is_available,
                "authenticated": agent.is_authenticated,
                "capabilities": len(agent.capabilities),
                "capability_score": agent.get_capability_score(),
                "priority": agent.priority
            })
        
        return {
            "total_detected": total_detected,
            "available": available_count,
            "authenticated": authenticated_count,
            "last_scan": self.last_scan_time,
            "agents": agent_details
        }