"""Configuration management system for Nocturnal Agent."""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from pydantic import BaseModel, Field, validator


class LLMConfig(BaseModel):
    """Configuration for Local LLM."""
    model_path: str = "models/codellama-13b"
    api_url: str = "http://localhost:1234/v1"
    timeout: int = 300  # 5 minutes
    max_tokens: int = 4096
    temperature: float = 0.7
    enabled: bool = True


class ClaudeConfig(BaseModel):
    """Configuration for Claude Code agent."""
    cli_command: str = "claude"
    max_retries: int = 3
    timeout: int = 300  # 5 minutes
    enabled: bool = True
    check_auth_on_startup: bool = True


class AgentConfig(BaseModel):
    """Configuration for external agents."""
    claude: ClaudeConfig = Field(default_factory=ClaudeConfig)
    # Future agents will be added here
    # github_copilot: GitHubCopilotConfig = Field(default_factory=GitHubCopilotConfig)
    # openai_codex: OpenAICodexConfig = Field(default_factory=OpenAICodexConfig)


class QualityConfig(BaseModel):
    """Configuration for quality assessment."""
    overall_threshold: float = Field(0.85, ge=0.0, le=1.0)
    consistency_threshold: float = Field(0.85, ge=0.0, le=1.0)
    max_improvement_cycles: int = Field(3, ge=1, le=10)
    enable_static_analysis: bool = True
    static_analysis_tools: List[str] = Field(default_factory=lambda: ["pylint", "flake8", "mypy"])


class SchedulerConfig(BaseModel):
    """Configuration for night scheduler."""
    start_time: str = "22:00"  # 22:00
    end_time: str = "06:00"    # 06:00
    max_changes_per_night: int = Field(10, ge=1, le=50)
    max_task_duration_minutes: int = Field(30, ge=5, le=120)
    check_interval_seconds: int = Field(30, ge=10, le=300)
    timezone: str = "local"


class SafetyConfig(BaseModel):
    """Configuration for safety mechanisms."""
    enable_backups: bool = True
    backup_before_execution: bool = True
    max_file_changes_per_task: int = Field(20, ge=1, le=100)
    cpu_limit_percent: float = Field(80.0, ge=10.0, le=95.0)
    memory_limit_gb: float = Field(8.0, ge=1.0, le=32.0)
    dangerous_commands: List[str] = Field(default_factory=lambda: [
        "rm", "rmdir", "del", "format", "fdisk", "mkfs", "dd",
        "sudo rm", "sudo rmdir", "sudo del"
    ])
    protected_paths: List[str] = Field(default_factory=lambda: [
        "/etc", "/sys", "/proc", "/dev", "/boot",
        "C:\\Windows", "C:\\System32", "C:\\Program Files"
    ])


class CostConfig(BaseModel):
    """Configuration for cost management."""
    monthly_budget_usd: float = Field(10.0, ge=0.0, le=1000.0)
    local_llm_priority: bool = True
    free_tool_preference_percent: float = Field(90.0, ge=50.0, le=100.0)
    track_api_usage: bool = True
    warn_at_budget_percent: float = Field(80.0, ge=50.0, le=95.0)


class ObsidianConfig(BaseModel):
    """Configuration for Obsidian integration."""
    vault_path: str = "knowledge-vault"
    auto_create_vault: bool = True
    markdown_template_path: Optional[str] = None
    enable_frontmatter: bool = True
    enable_backlinks: bool = True


class ParallelConfig(BaseModel):
    """Configuration for parallel execution."""
    max_parallel_branches: int = Field(5, ge=1, le=10)
    high_quality_threshold: float = Field(0.85, ge=0.7, le=1.0)
    medium_quality_threshold: float = Field(0.70, ge=0.5, le=0.84)
    enable_experimental_branches: bool = True
    merge_strategy: str = Field("auto", pattern="^(auto|manual|quality_based)$")


class LoggingConfig(BaseModel):
    """Configuration for logging."""
    level: str = Field("INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    format: str = "json"  # json or text
    file_path: Optional[str] = "logs/nocturnal-agent.log"
    max_file_size_mb: int = Field(100, ge=1, le=1000)
    backup_count: int = Field(5, ge=1, le=20)
    enable_structlog: bool = True


class NocturnalAgentConfig(BaseModel):
    """Main configuration for Nocturnal Agent."""
    # Core settings
    project_name: str = "nocturnal-agent"
    working_directory: str = "."
    
    # Component configurations
    llm: LLMConfig = Field(default_factory=LLMConfig)
    agents: AgentConfig = Field(default_factory=AgentConfig)
    quality: QualityConfig = Field(default_factory=QualityConfig)
    scheduler: SchedulerConfig = Field(default_factory=SchedulerConfig)
    safety: SafetyConfig = Field(default_factory=SafetyConfig)
    cost: CostConfig = Field(default_factory=CostConfig)
    obsidian: ObsidianConfig = Field(default_factory=ObsidianConfig)
    parallel: ParallelConfig = Field(default_factory=ParallelConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    
    # Advanced settings
    debug_mode: bool = False
    dry_run: bool = False
    
    @validator('working_directory')
    def validate_working_directory(cls, v):
        """Validate working directory exists."""
        path = Path(v)
        if not path.exists():
            raise ValueError(f"Working directory does not exist: {v}")
        return str(path.absolute())
    
    @validator('scheduler')
    def validate_scheduler_times(cls, v):
        """Validate scheduler time format."""
        import re
        time_pattern = r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$'
        if not re.match(time_pattern, v.start_time):
            raise ValueError(f"Invalid start_time format: {v.start_time}")
        if not re.match(time_pattern, v.end_time):
            raise ValueError(f"Invalid end_time format: {v.end_time}")
        return v


class ConfigManager:
    """Manages configuration loading and validation."""
    
    DEFAULT_CONFIG_PATHS = [
        "config/nocturnal-agent.yaml",
        "config/nocturnal-agent.yml",
        "nocturnal-agent.yaml",
        "nocturnal-agent.yml",
        "~/.nocturnal-agent/config.yaml",
        "~/.config/nocturnal-agent/config.yaml",
    ]
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize config manager."""
        self.config_path = config_path
        self._config: Optional[NocturnalAgentConfig] = None
    
    def load_config(self) -> NocturnalAgentConfig:
        """Load configuration from file or create default."""
        if self._config is not None:
            return self._config
        
        config_data = {}
        
        # Load from file if exists
        config_file = self._find_config_file()
        if config_file:
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config_data = yaml.safe_load(f) or {}
            except Exception as e:
                raise ValueError(f"Failed to load config from {config_file}: {e}")
        
        # Override with environment variables
        config_data.update(self._load_env_overrides())
        
        # Create and validate config
        self._config = NocturnalAgentConfig(**config_data)
        return self._config
    
    def save_config(self, config: NocturnalAgentConfig, path: Optional[str] = None) -> None:
        """Save configuration to file."""
        config_path = path or self.config_path or "config/nocturnal-agent.yaml"
        
        # Ensure directory exists
        config_dir = Path(config_path).parent
        config_dir.mkdir(parents=True, exist_ok=True)
        
        # Convert to dict and save
        config_dict = config.dict()
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config_dict, f, default_flow_style=False, indent=2)
    
    def _find_config_file(self) -> Optional[str]:
        """Find configuration file in default locations."""
        if self.config_path:
            if Path(self.config_path).exists():
                return self.config_path
            return None
        
        for config_path in self.DEFAULT_CONFIG_PATHS:
            expanded_path = Path(config_path).expanduser()
            if expanded_path.exists():
                return str(expanded_path)
        
        return None
    
    def _load_env_overrides(self) -> Dict[str, Any]:
        """Load configuration overrides from environment variables."""
        env_config = {}
        prefix = "NOCTURNAL_"
        
        for key, value in os.environ.items():
            if not key.startswith(prefix):
                continue
            
            # Convert NOCTURNAL_SCHEDULER_START_TIME -> scheduler.start_time
            config_key = key[len(prefix):].lower()
            key_parts = config_key.split('_')
            
            # Build nested dict
            current = env_config
            for part in key_parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]
            
            # Convert value to appropriate type
            current[key_parts[-1]] = self._convert_env_value(value)
        
        return env_config
    
    def _convert_env_value(self, value: str) -> Any:
        """Convert environment variable string to appropriate type."""
        # Boolean values
        if value.lower() in ('true', '1', 'yes', 'on'):
            return True
        if value.lower() in ('false', '0', 'no', 'off'):
            return False
        
        # Numeric values
        try:
            if '.' in value:
                return float(value)
            return int(value)
        except ValueError:
            pass
        
        # List values (comma-separated)
        if ',' in value:
            return [item.strip() for item in value.split(',')]
        
        return value


def load_config(config_path: Optional[str] = None) -> NocturnalAgentConfig:
    """Load configuration from file or environment."""
    manager = ConfigManager(config_path)
    return manager.load_config()


def create_default_config(output_path: str = "config/nocturnal-agent.yaml") -> None:
    """Create default configuration file."""
    config = NocturnalAgentConfig()
    manager = ConfigManager()
    manager.save_config(config, output_path)
    print(f"Default configuration created at: {output_path}")


if __name__ == "__main__":
    # Create default config for testing
    create_default_config()