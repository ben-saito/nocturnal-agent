"""Configuration management system for Nocturnal Agent.

⚠️ DEPRECATED: このモジュールは非推奨です。
新しいコードでは `nocturnal_agent.config.config_manager` を使用してください。

後方互換性のため、このモジュールから設定クラスをインポートできますが、
実際の設定は `config.config_manager` から読み込まれます。
"""

import warnings
from typing import Any, Dict, List, Optional
from pathlib import Path

# 後方互換性のため、config.config_managerからインポート
from ..config.config_manager import (
    LLMConfig as _LLMConfig,
    ClaudeConfig as _ClaudeConfig,
    QualityConfig as _QualityConfig,
    SchedulerConfig as _SchedulerConfig,
    SafetyConfig as _SafetyConfig,
    CostConfig as _CostConfig,
    ObsidianConfig as _ObsidianConfig,
    ParallelConfig as _ParallelConfig,
    LoggingConfig as _LoggingConfig,
    ConfigManager as _ConfigManager,
    NocturnalConfig as _NocturnalConfig,
)

# 警告を表示（初回インポート時のみ）
_warning_shown = False

def _show_deprecation_warning():
    """非推奨警告を表示"""
    global _warning_shown
    if not _warning_shown:
        warnings.warn(
            "nocturnal_agent.core.config は非推奨です。"
            "nocturnal_agent.config.config_manager を使用してください。",
            DeprecationWarning,
            stacklevel=3
        )
        _warning_shown = True


# 後方互換性のためのエイリアス
# dataclassをPydanticスタイルで使用できるようにラップ
class LLMConfig:
    """Configuration for Local LLM (後方互換性のためのラッパー)."""
    
    def __init__(self, **kwargs):
        """LLMConfigの初期化"""
        _show_deprecation_warning()
        self._config = _LLMConfig(**kwargs)
    
    @property
    def model_path(self) -> str:
        return self._config.model_path
    
    @model_path.setter
    def model_path(self, value: str):
        self._config.model_path = value
    
    @property
    def api_url(self) -> str:
        return self._config.api_url
    
    @api_url.setter
    def api_url(self, value: str):
        self._config.api_url = value
    
    @property
    def timeout(self) -> int:
        return self._config.timeout
    
    @timeout.setter
    def timeout(self, value: int):
        self._config.timeout = value
    
    @property
    def max_tokens(self) -> int:
        return self._config.max_tokens
    
    @max_tokens.setter
    def max_tokens(self, value: int):
        self._config.max_tokens = value
    
    @property
    def temperature(self) -> float:
        return self._config.temperature
    
    @temperature.setter
    def temperature(self, value: float):
        self._config.temperature = value
    
    @property
    def enabled(self) -> bool:
        return self._config.enabled
    
    @enabled.setter
    def enabled(self, value: bool):
        self._config.enabled = value
    
    def dict(self) -> Dict[str, Any]:
        """辞書形式で返す（Pydantic互換）"""
        from dataclasses import asdict
        return asdict(self._config)


class ClaudeConfig:
    """Configuration for Claude Code agent (後方互換性のためのラッパー)."""
    
    def __init__(self, **kwargs):
        """ClaudeConfigの初期化"""
        _show_deprecation_warning()
        self._config = _ClaudeConfig(**kwargs)
    
    @property
    def cli_command(self) -> str:
        return self._config.cli_command
    
    @cli_command.setter
    def cli_command(self, value: str):
        self._config.cli_command = value
    
    @property
    def max_retries(self) -> int:
        return self._config.max_retries
    
    @max_retries.setter
    def max_retries(self, value: int):
        self._config.max_retries = value
    
    @property
    def timeout(self) -> int:
        return self._config.timeout
    
    @timeout.setter
    def timeout(self, value: int):
        self._config.timeout = value
    
    @property
    def enabled(self) -> bool:
        return self._config.enabled
    
    @enabled.setter
    def enabled(self, value: bool):
        self._config.enabled = value
    
    @property
    def check_auth_on_startup(self) -> bool:
        return self._config.check_auth_on_startup
    
    @check_auth_on_startup.setter
    def check_auth_on_startup(self, value: bool):
        self._config.check_auth_on_startup = value
    
    def dict(self) -> Dict[str, Any]:
        """辞書形式で返す（Pydantic互換）"""
        from dataclasses import asdict
        return asdict(self._config)


class QualityConfig:
    """Configuration for quality assessment (後方互換性のためのラッパー)."""
    
    def __init__(self, **kwargs):
        """QualityConfigの初期化"""
        _show_deprecation_warning()
        self._config = _QualityConfig(**kwargs)
    
    @property
    def overall_threshold(self) -> float:
        return self._config.overall_threshold
    
    @overall_threshold.setter
    def overall_threshold(self, value: float):
        self._config.overall_threshold = value
    
    @property
    def consistency_threshold(self) -> float:
        return self._config.consistency_threshold
    
    @consistency_threshold.setter
    def consistency_threshold(self, value: float):
        self._config.consistency_threshold = value
    
    @property
    def max_improvement_cycles(self) -> int:
        return self._config.max_improvement_cycles
    
    @max_improvement_cycles.setter
    def max_improvement_cycles(self, value: int):
        self._config.max_improvement_cycles = value
    
    @property
    def enable_static_analysis(self) -> bool:
        return self._config.enable_static_analysis
    
    @enable_static_analysis.setter
    def enable_static_analysis(self, value: bool):
        self._config.enable_static_analysis = value
    
    @property
    def static_analysis_tools(self) -> List[str]:
        return self._config.static_analysis_tools
    
    @static_analysis_tools.setter
    def static_analysis_tools(self, value: List[str]):
        self._config.static_analysis_tools = value
    
    def dict(self) -> Dict[str, Any]:
        """辞書形式で返す（Pydantic互換）"""
        from dataclasses import asdict
        return asdict(self._config)


# 他の設定クラスも同様にエイリアスとして提供
# ただし、実際の使用では直接dataclassを使用することを推奨
SchedulerConfig = _SchedulerConfig
SafetyConfig = _SafetyConfig
CostConfig = _CostConfig
ObsidianConfig = _ObsidianConfig
ParallelConfig = _ParallelConfig
LoggingConfig = _LoggingConfig

# ConfigManagerとNocturnalAgentConfigもエイリアスとして提供
ConfigManager = _ConfigManager
NocturnalAgentConfig = _NocturnalConfig


def load_config(config_path: Optional[str] = None):
    """設定を読み込む（後方互換性のため）"""
    _show_deprecation_warning()
    manager = _ConfigManager(config_path)
    return manager.load_config()


def create_default_config(output_path: str = "config/nocturnal-agent.yaml") -> None:
    """デフォルト設定ファイルを作成（後方互換性のため）"""
    _show_deprecation_warning()
    config = _NocturnalConfig()
    manager = _ConfigManager()
    manager.save_config(config)
    print(f"Default configuration created at: {output_path}")


if __name__ == "__main__":
    # Create default config for testing
    create_default_config()
