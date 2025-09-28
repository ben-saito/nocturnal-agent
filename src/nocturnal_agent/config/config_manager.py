"""設定管理システム"""

import os
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass, asdict

from ..core.models import AgentType


@dataclass
class DatabaseConfig:
    """データベース設定"""
    type: str = "sqlite"
    path: str = "./data/nocturnal_agent.db"
    backup_enabled: bool = True
    backup_interval_hours: int = 24


@dataclass
class AgentConfig:
    """エージェント設定"""
    primary_agent: AgentType = AgentType.LOCAL_LLM
    fallback_agents: List[AgentType] = None
    claude_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    max_retries: int = 3
    timeout_seconds: int = 300
    retry_delay: int = 10  # 新しいフィールド: リトライ間隔（秒）

    def __post_init__(self):
        if self.fallback_agents is None:
            self.fallback_agents = [AgentType.CLAUDE_CODE]


@dataclass
class CostConfig:
    """コスト管理設定"""
    monthly_budget: float = 10.0
    storage_path: str = "./data/cost_data"
    alert_thresholds: List[float] = None
    free_tool_target_rate: float = 0.9
    emergency_mode_threshold: float = 0.95
    free_tools: List[str] = None

    def __post_init__(self):
        if self.alert_thresholds is None:
            self.alert_thresholds = [0.5, 0.8, 0.9, 0.95]
        if self.free_tools is None:
            self.free_tools = ["local_llm", "github_api", "file_operations"]


@dataclass
class SafetyConfig:
    """安全性設定"""
    enabled: bool = True
    backup_before_execution: bool = True
    backup_before_changes: bool = True  # 新しいフィールド
    danger_detection_enabled: bool = True
    rollback_enabled: bool = True
    max_rollback_points: int = 10
    max_file_changes: int = 50  # 新しいフィールド
    backup_retention_days: int = 7
    validate_design_files: bool = True  # 新しいフィールド
    require_confirmation: bool = False  # 新しいフィールド
    dangerous_operations_blocked: List[str] = None
    excluded_directories: List[str] = None  # 新しいフィールド
    excluded_file_patterns: List[str] = None  # 新しいフィールド

    def __post_init__(self):
        if self.dangerous_operations_blocked is None:
            self.dangerous_operations_blocked = [
                "rm -rf", "format", "del /q", "sudo rm", "DROP TABLE"
            ]
        if self.excluded_directories is None:
            self.excluded_directories = [".git", "node_modules", "__pycache__", ".venv"]
        if self.excluded_file_patterns is None:
            self.excluded_file_patterns = ["*.log", "*.tmp", "*.pyc"]


@dataclass
class ParallelConfig:
    """並行実行設定"""
    max_parallel_executions: int = 3
    execution_timeout_seconds: int = 600
    quality_assessment_enabled: bool = True
    high_quality_threshold: float = 0.85
    medium_quality_threshold: float = 0.7
    branch_prefix: str = "nocturnal"
    max_parallel_branches: int = 5


@dataclass
class LoggingConfig:
    """ログ設定"""
    level: str = "INFO"
    format: str = "structured"  # structured, simple
    output_path: str = "./logs"
    max_file_size_mb: int = 100
    retention_days: int = 30
    console_output: bool = True
    file_output: bool = True


@dataclass
class NocturnalConfig:
    """メイン設定クラス"""
    # 基本設定
    project_name: str = "Nocturnal Agent Project"
    workspace_path: str = "./"
    working_directory: str = "./"  # 新しいフィールド（workspace_pathの別名）
    project_type: str = "general"  # 新しいフィールド
    created_at: str = ""  # 新しいフィールド
    data_directory: str = "./data"
    log_directory: str = "./logs"
    
    # コンポーネント設定
    database: DatabaseConfig = None
    agents: AgentConfig = None
    cost_management: CostConfig = None
    safety: SafetyConfig = None
    parallel_execution: ParallelConfig = None
    logging: LoggingConfig = None
    
    # スケジューラー設定
    night_start_hour: int = 22
    night_end_hour: int = 6
    timezone: str = "Asia/Tokyo"
    
    # 品質設定
    target_quality_threshold: float = 0.8
    minimum_quality_threshold: float = 0.6
    
    def __post_init__(self):
        """デフォルト値の初期化"""
        if self.database is None:
            self.database = DatabaseConfig()
        if self.agents is None:
            self.agents = AgentConfig()
        if self.cost_management is None:
            self.cost_management = CostConfig()
        if self.safety is None:
            self.safety = SafetyConfig()
        if self.parallel_execution is None:
            self.parallel_execution = ParallelConfig()
        if self.logging is None:
            self.logging = LoggingConfig()


class ConfigManager:
    """設定管理マネージャー"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = Path(config_path) if config_path else Path("./config/nocturnal_config.yaml")
        self.logger = logging.getLogger(__name__)
        self._config: Optional[NocturnalConfig] = None
        self._config_cache_time: Optional[datetime] = None
        
        # 設定ディレクトリの作成
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
    
    def load_config(self, reload: bool = False) -> NocturnalConfig:
        """設定を読み込む"""
        if self._config and not reload:
            # キャッシュから返す（ファイル更新チェック付き）
            if self._is_config_cache_valid():
                return self._config
        
        try:
            if self.config_path.exists():
                config_dict = self._load_yaml_config()
                config_dict = self._apply_env_overrides(config_dict)
                self._config = self._dict_to_config(config_dict)
            else:
                # デフォルト設定で初期化
                self._config = NocturnalConfig()
                self.save_config(self._config)
                self.logger.info(f"デフォルト設定ファイルを作成しました: {self.config_path}")
            
            self._config_cache_time = datetime.now()
            self._validate_config(self._config)
            
            return self._config
            
        except Exception as e:
            self.logger.error(f"設定読み込みエラー: {e}")
            # フォールバック: デフォルト設定を使用
            self._config = NocturnalConfig()
            return self._config
    
    def save_config(self, config: NocturnalConfig) -> bool:
        """設定をファイルに保存"""
        try:
            config_dict = asdict(config)
            config_dict = self._prepare_config_for_save(config_dict)
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.safe_dump(
                    config_dict,
                    f,
                    default_flow_style=False,
                    allow_unicode=True,
                    indent=2
                )
            
            self._config = config
            self._config_cache_time = datetime.now()
            self.logger.info(f"設定を保存しました: {self.config_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"設定保存エラー: {e}")
            return False
    
    def get_config(self) -> NocturnalConfig:
        """現在の設定を取得"""
        return self.load_config()
    
    def update_config(self, updates: Dict[str, Any]) -> bool:
        """設定を部分更新"""
        try:
            config = self.load_config()
            updated_dict = asdict(config)
            
            # ネストした辞書の更新
            self._deep_update(updated_dict, updates)
            
            updated_config = self._dict_to_config(updated_dict)
            return self.save_config(updated_config)
            
        except Exception as e:
            self.logger.error(f"設定更新エラー: {e}")
            return False
    
    def validate_config(self, config: Optional[NocturnalConfig] = None) -> List[str]:
        """設定の検証"""
        if config is None:
            config = self.load_config()
        
        errors = []
        
        try:
            # 基本検証
            if not config.project_name.strip():
                errors.append("project_name は必須です")
            
            # パス検証
            workspace_path = Path(config.workspace_path)
            if not workspace_path.exists():
                errors.append(f"workspace_path が存在しません: {workspace_path}")
            
            # コスト設定検証
            if config.cost_management.monthly_budget <= 0:
                errors.append("monthly_budget は正の値である必要があります")
            
            if not (0 < config.cost_management.free_tool_target_rate <= 1):
                errors.append("free_tool_target_rate は0-1の範囲である必要があります")
            
            # 品質閾値検証
            if not (0 < config.target_quality_threshold <= 1):
                errors.append("target_quality_threshold は0-1の範囲である必要があります")
            
            if config.minimum_quality_threshold >= config.target_quality_threshold:
                errors.append("minimum_quality_threshold は target_quality_threshold より小さい必要があります")
            
            # 並行実行設定検証
            if config.parallel_execution.max_parallel_executions < 1:
                errors.append("max_parallel_executions は1以上である必要があります")
            
            # スケジューラー設定検証
            if not (0 <= config.night_start_hour <= 23):
                errors.append("night_start_hour は0-23の範囲である必要があります")
            
            if not (0 <= config.night_end_hour <= 23):
                errors.append("night_end_hour は0-23の範囲である必要があります")
            
        except Exception as e:
            errors.append(f"設定検証中にエラーが発生しました: {e}")
        
        return errors
    
    def create_sample_config(self, output_path: Optional[str] = None) -> bool:
        """サンプル設定ファイルを作成"""
        try:
            sample_config = NocturnalConfig(
                project_name="サンプルプロジェクト",
                workspace_path="./workspace",
                agents=AgentConfig(
                    primary_agent=AgentType.LOCAL_LLM,
                    fallback_agents=[AgentType.CLAUDE_CODE]
                ),
                cost_management=CostConfig(
                    monthly_budget=15.0,
                    free_tool_target_rate=0.85
                ),
                safety=SafetyConfig(
                    backup_retention_days=14,
                    max_rollback_points=15
                ),
                parallel_execution=ParallelConfig(
                    max_parallel_executions=5,
                    high_quality_threshold=0.9
                ),
                target_quality_threshold=0.85
            )
            
            if output_path:
                original_path = self.config_path
                self.config_path = Path(output_path)
                result = self.save_config(sample_config)
                self.config_path = original_path
                return result
            else:
                return self.save_config(sample_config)
                
        except Exception as e:
            self.logger.error(f"サンプル設定作成エラー: {e}")
            return False
    
    def _load_yaml_config(self) -> Dict[str, Any]:
        """YAML設定ファイルを読み込む"""
        with open(self.config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    
    def _apply_env_overrides(self, config_dict: Dict[str, Any]) -> Dict[str, Any]:
        """環境変数による設定オーバーライド"""
        # 環境変数のプレフィックス
        prefix = "NOCTURNAL_"
        
        # 主要な設定項目の環境変数チェック
        env_mappings = {
            f"{prefix}PROJECT_NAME": "project_name",
            f"{prefix}WORKSPACE_PATH": "workspace_path",
            f"{prefix}MONTHLY_BUDGET": "cost_management.monthly_budget",
            f"{prefix}CLAUDE_API_KEY": "agents.claude_api_key",
            f"{prefix}OPENAI_API_KEY": "agents.openai_api_key",
            f"{prefix}LOG_LEVEL": "logging.level",
            f"{prefix}NIGHT_START_HOUR": "night_start_hour",
            f"{prefix}NIGHT_END_HOUR": "night_end_hour",
            f"{prefix}TARGET_QUALITY": "target_quality_threshold"
        }
        
        for env_var, config_path in env_mappings.items():
            env_value = os.getenv(env_var)
            if env_value is not None:
                self._set_nested_dict_value(config_dict, config_path, env_value)
        
        return config_dict
    
    def _dict_to_config(self, config_dict: Dict[str, Any]) -> NocturnalConfig:
        """辞書からConfigオブジェクトを作成（新旧両形式対応）"""
        # 新形式と旧形式の両方に対応
        try:
            # Enum型の変換処理
            if 'agents' in config_dict and isinstance(config_dict['agents'], dict):
                agents_dict = config_dict['agents']
                if 'primary_agent' in agents_dict:
                    if isinstance(agents_dict['primary_agent'], str):
                        agents_dict['primary_agent'] = AgentType(agents_dict['primary_agent'])
                if 'fallback_agents' in agents_dict:
                    agents_dict['fallback_agents'] = [
                        AgentType(agent) if isinstance(agent, str) else agent
                        for agent in agents_dict['fallback_agents']
                    ]
            
            # ネストした設定の処理（フィールド不足の場合はデフォルト値使用）
            database_config = self._safe_create_config(DatabaseConfig, config_dict.get('database', {}))
            agents_config = self._safe_create_config(AgentConfig, config_dict.get('agents', {}))
            
            # cost/cost_management の両方に対応
            cost_data = config_dict.get('cost', config_dict.get('cost_management', {}))
            cost_config = self._safe_create_config(CostConfig, cost_data)
            
            safety_config = self._safe_create_config(SafetyConfig, config_dict.get('safety', {}))
            parallel_config = self._safe_create_config(ParallelConfig, config_dict.get('parallel_execution', {}))
            logging_config = self._safe_create_config(LoggingConfig, config_dict.get('logging', {}))
            
            # メイン設定の作成（新形式の追加フィールドは無視）
            excluded_keys = {
                'database', 'agents', 'cost', 'cost_management', 'safety', 
                'parallel_execution', 'logging', 'execution', 'quality', 
                'notifications', 'integrations', 'development', 'advanced',
                'project_specific', 'project_type', 'created_at', 'llm'
            }
            main_config = {k: v for k, v in config_dict.items() if k not in excluded_keys}
            
            return NocturnalConfig(
                database=database_config,
                agents=agents_config,
                cost_management=cost_config,
                safety=safety_config,
                parallel_execution=parallel_config,
                logging=logging_config,
                **main_config
            )
            
        except Exception as e:
            self.logger.warning(f"新形式設定読み込み失敗、デフォルト設定使用: {e}")
            # フォールバック: デフォルト設定
            return NocturnalConfig()
    
    def _safe_create_config(self, config_class, config_data: Dict[str, Any]):
        """安全な設定オブジェクト作成（不明なフィールドは無視）"""
        if not isinstance(config_data, dict):
            return config_class()
            
        try:
            # dataclassの有効なフィールドのみを抽出
            valid_fields = {field.name for field in config_class.__dataclass_fields__.values()}
            filtered_data = {k: v for k, v in config_data.items() if k in valid_fields}
            return config_class(**filtered_data)
        except Exception as e:
            self.logger.warning(f"{config_class.__name__} 作成失敗、デフォルト使用: {e}")
            return config_class()
    
    def _prepare_config_for_save(self, config_dict: Dict[str, Any]) -> Dict[str, Any]:
        """保存用設定の準備"""
        # Enum型を文字列に変換
        if 'agents' in config_dict and isinstance(config_dict['agents'], dict):
            agents_dict = config_dict['agents']
            if 'primary_agent' in agents_dict:
                agents_dict['primary_agent'] = agents_dict['primary_agent'].value
            if 'fallback_agents' in agents_dict:
                agents_dict['fallback_agents'] = [
                    agent.value if hasattr(agent, 'value') else agent
                    for agent in agents_dict['fallback_agents']
                ]
        
        return config_dict
    
    def _validate_config(self, config: NocturnalConfig) -> None:
        """設定の検証（例外発生版）"""
        errors = self.validate_config(config)
        if errors:
            error_msg = "設定検証エラー:\n" + "\n".join(f"- {error}" for error in errors)
            raise ValueError(error_msg)
    
    def _is_config_cache_valid(self) -> bool:
        """設定キャッシュの有効性チェック"""
        if not self._config_cache_time:
            return False
        
        try:
            file_mtime = datetime.fromtimestamp(self.config_path.stat().st_mtime)
            return file_mtime <= self._config_cache_time
        except:
            return False
    
    def _deep_update(self, target_dict: Dict[str, Any], updates: Dict[str, Any]) -> None:
        """ネストした辞書の深いアップデート"""
        for key, value in updates.items():
            if key in target_dict and isinstance(target_dict[key], dict) and isinstance(value, dict):
                self._deep_update(target_dict[key], value)
            else:
                target_dict[key] = value
    
    def _set_nested_dict_value(self, target_dict: Dict[str, Any], path: str, value: Any) -> None:
        """ネストした辞書に値を設定"""
        keys = path.split('.')
        current_dict = target_dict
        
        # 最後のキー以外を辿る
        for key in keys[:-1]:
            if key not in current_dict:
                current_dict[key] = {}
            current_dict = current_dict[key]
        
        # 最後のキーに値を設定
        last_key = keys[-1]
        # 型変換の試行
        try:
            if value.lower() in ('true', 'false'):
                current_dict[last_key] = value.lower() == 'true'
            elif value.replace('.', '').replace('-', '').isdigit():
                current_dict[last_key] = float(value) if '.' in value else int(value)
            else:
                current_dict[last_key] = value
        except:
            current_dict[last_key] = value