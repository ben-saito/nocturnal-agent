"""Unit tests for configuration management."""

import os
import tempfile
from pathlib import Path

import pytest
import yaml

from nocturnal_agent.core.config import (
    ConfigManager, NocturnalAgentConfig, LLMConfig, ClaudeConfig,
    QualityConfig, SchedulerConfig, SafetyConfig, load_config
)


class TestNocturnalAgentConfig:
    """Test main configuration model."""
    
    def test_default_config_creation(self):
        """Test creating config with default values."""
        config = NocturnalAgentConfig()
        
        assert config.project_name == "nocturnal-agent"
        assert config.working_directory == "."
        assert config.debug_mode is False
        assert config.dry_run is False
        
        # Test nested configurations
        assert config.llm.enabled is True
        assert config.agents.claude.enabled is True
        assert config.quality.overall_threshold == 0.85
        assert config.scheduler.start_time == "22:00"
        assert config.scheduler.end_time == "06:00"
        assert config.safety.enable_backups is True
    
    def test_config_with_custom_values(self):
        """Test creating config with custom values."""
        config = NocturnalAgentConfig(
            project_name="my-project",
            debug_mode=True,
            llm=LLMConfig(enabled=False),
            quality=QualityConfig(overall_threshold=0.9)
        )
        
        assert config.project_name == "my-project"
        assert config.debug_mode is True
        assert config.llm.enabled is False
        assert config.quality.overall_threshold == 0.9


class TestLLMConfig:
    """Test LLM configuration."""
    
    def test_llm_config_defaults(self):
        """Test LLM config default values."""
        config = LLMConfig()
        
        assert config.model_path == "models/codellama-13b"
        assert config.api_url == "http://localhost:1234/v1"
        assert config.timeout == 300
        assert config.max_tokens == 4096
        assert config.temperature == 0.7
        assert config.enabled is True
    
    def test_llm_config_custom(self):
        """Test LLM config with custom values."""
        config = LLMConfig(
            model_path="models/custom-model",
            api_url="http://localhost:8080/v1",
            timeout=600,
            enabled=False
        )
        
        assert config.model_path == "models/custom-model"
        assert config.api_url == "http://localhost:8080/v1"
        assert config.timeout == 600
        assert config.enabled is False


class TestClaudeConfig:
    """Test Claude configuration."""
    
    def test_claude_config_defaults(self):
        """Test Claude config default values."""
        config = ClaudeConfig()
        
        assert config.cli_command == "claude"
        assert config.max_retries == 3
        assert config.timeout == 300
        assert config.enabled is True
        assert config.check_auth_on_startup is True


class TestQualityConfig:
    """Test quality configuration."""
    
    def test_quality_config_defaults(self):
        """Test quality config default values."""
        config = QualityConfig()
        
        assert config.overall_threshold == 0.85
        assert config.consistency_threshold == 0.85
        assert config.max_improvement_cycles == 3
        assert config.enable_static_analysis is True
        assert "pylint" in config.static_analysis_tools
        assert "flake8" in config.static_analysis_tools
        assert "mypy" in config.static_analysis_tools
    
    def test_quality_config_validation(self):
        """Test quality config validation."""
        # Valid config
        config = QualityConfig(overall_threshold=0.8, consistency_threshold=0.9)
        assert config.overall_threshold == 0.8
        assert config.consistency_threshold == 0.9
        
        # Test boundary values
        config = QualityConfig(overall_threshold=0.0)
        assert config.overall_threshold == 0.0
        
        config = QualityConfig(overall_threshold=1.0)
        assert config.overall_threshold == 1.0


class TestSchedulerConfig:
    """Test scheduler configuration."""
    
    def test_scheduler_config_defaults(self):
        """Test scheduler config default values."""
        config = SchedulerConfig()
        
        assert config.start_time == "22:00"
        assert config.end_time == "06:00"
        assert config.max_changes_per_night == 10
        assert config.max_task_duration_minutes == 30
        assert config.check_interval_seconds == 30
        assert config.timezone == "local"


class TestSafetyConfig:
    """Test safety configuration."""
    
    def test_safety_config_defaults(self):
        """Test safety config default values."""
        config = SafetyConfig()
        
        assert config.enable_backups is True
        assert config.backup_before_execution is True
        assert config.max_file_changes_per_task == 20
        assert config.cpu_limit_percent == 80.0
        assert config.memory_limit_gb == 8.0
        
        # Test dangerous commands list
        assert "rm" in config.dangerous_commands
        assert "sudo rm" in config.dangerous_commands
        assert "format" in config.dangerous_commands
        
        # Test protected paths
        assert "/etc" in config.protected_paths
        assert "C:\\Windows" in config.protected_paths


class TestConfigManager:
    """Test configuration manager."""
    
    def test_config_manager_creation(self):
        """Test creating a ConfigManager instance."""
        manager = ConfigManager()
        assert manager.config_path is None
        assert manager._config is None
        
        manager = ConfigManager("/path/to/config.yaml")
        assert manager.config_path == "/path/to/config.yaml"
    
    def test_load_default_config(self):
        """Test loading default config when no file exists."""
        manager = ConfigManager("/nonexistent/path/config.yaml")
        config = manager.load_config()
        
        assert isinstance(config, NocturnalAgentConfig)
        assert config.project_name == "nocturnal-agent"
    
    def test_save_and_load_config(self):
        """Test saving and loading configuration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "test_config.yaml"
            
            # Create custom config
            original_config = NocturnalAgentConfig(
                project_name="test-project",
                debug_mode=True,
                quality=QualityConfig(overall_threshold=0.9)
            )
            
            # Save config
            manager = ConfigManager(str(config_path))
            manager.save_config(original_config)
            
            assert config_path.exists()
            
            # Load config
            new_manager = ConfigManager(str(config_path))
            loaded_config = new_manager.load_config()
            
            assert loaded_config.project_name == "test-project"
            assert loaded_config.debug_mode is True
            assert loaded_config.quality.overall_threshold == 0.9
    
    def test_env_overrides(self):
        """Test environment variable overrides."""
        # Set environment variables
        os.environ["NOCTURNAL_PROJECT_NAME"] = "env-project"
        os.environ["NOCTURNAL_DEBUG_MODE"] = "true"
        os.environ["NOCTURNAL_QUALITY_OVERALL_THRESHOLD"] = "0.95"
        
        try:
            manager = ConfigManager()
            config = manager.load_config()
            
            assert config.project_name == "env-project"
            assert config.debug_mode is True
            assert config.quality.overall_threshold == 0.95
        finally:
            # Clean up environment variables
            for key in ["NOCTURNAL_PROJECT_NAME", "NOCTURNAL_DEBUG_MODE", "NOCTURNAL_QUALITY_OVERALL_THRESHOLD"]:
                if key in os.environ:
                    del os.environ[key]
    
    def test_convert_env_value(self):
        """Test environment value conversion."""
        manager = ConfigManager()
        
        # Boolean values
        assert manager._convert_env_value("true") is True
        assert manager._convert_env_value("false") is False
        assert manager._convert_env_value("1") is True
        assert manager._convert_env_value("0") is False
        
        # Numeric values
        assert manager._convert_env_value("42") == 42
        assert manager._convert_env_value("3.14") == 3.14
        
        # List values
        assert manager._convert_env_value("a,b,c") == ["a", "b", "c"]
        assert manager._convert_env_value("x, y, z") == ["x", "y", "z"]
        
        # String values
        assert manager._convert_env_value("hello") == "hello"


class TestLoadConfig:
    """Test load_config function."""
    
    def test_load_config_function(self):
        """Test the load_config convenience function."""
        config = load_config()
        assert isinstance(config, NocturnalAgentConfig)
    
    def test_load_config_with_path(self):
        """Test load_config with specific path."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "test.yaml"
            
            # Create test config file
            test_config = {
                "project_name": "test-from-file",
                "debug_mode": True
            }
            
            with open(config_path, 'w') as f:
                yaml.dump(test_config, f)
            
            config = load_config(str(config_path))
            assert config.project_name == "test-from-file"
            assert config.debug_mode is True


if __name__ == "__main__":
    pytest.main([__file__])