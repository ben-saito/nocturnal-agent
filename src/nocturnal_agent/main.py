"""Nocturnal Agent メイン統合システム"""

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
import uuid

from .config.config_manager import ConfigManager, NocturnalConfig
from .log_system.structured_logger import StructuredLogger, LogLevel, LogCategory
from .log_system.interaction_logger import InteractionLogger, InteractionType, AgentType as InteractionAgentType
from .scheduler.night_scheduler import NightScheduler
from .cost.cost_manager import CostManager
from .safety.safety_coordinator import SafetyCoordinator
from .parallel.parallel_executor import ParallelExecutor
from .reporting.report_generator import ReportGenerator
from .core.models import Task, ExecutionResult
from .execution.spec_driven_executor import SpecDrivenExecutor
from .design.spec_kit_integration import SpecType


class NocturnalAgent:
    """夜間自律開発システム メインクラス"""
    
    def __init__(self, workspace_path: str):
        """Nocturnal Agent初期化"""
        # 設定管理システム
        self.config_manager = ConfigManager()
        self.config = self.config_manager.load_config()
        
        # 基本設定
        self.workspace_path = Path(workspace_path)
        self.session_id = None
        self.is_running = False
        
        # セッション統計
        self.session_stats = {
            'session_start': None,
            'session_end': None,
            'total_tasks': 0,
            'completed_tasks': 0,
            'failed_tasks': 0,
            'total_cost': 0.0,
            'quality_scores': []
        }
        
        # セッション設定（ユーザー指示による動的設定）
        self.session_settings = {
            'use_spec_kit': True,  # デフォルトでSpec Kit使用する
            'spec_type': 'feature',
            'quality_threshold': self.config.minimum_quality_threshold
        }
        
        # コンポーネント初期化
        self._initialize_components()
    
    def _initialize_components(self):
        """コンポーネント初期化"""
        # ログシステム
        self.logger = StructuredLogger({
            'level': self.config.logging.level,
            'output_path': self.config.logging.output_path,
            'console_output': self.config.logging.console_output,
            'file_output': self.config.logging.file_output,
            'retention_days': self.config.logging.retention_days,
            'max_file_size_mb': self.config.logging.max_file_size_mb
        })
        
        # スケジューラー（メインエージェントの参照を渡す）
        scheduler_config = {
            'time_control': {},
            'task_queue': {},
            'resource_monitoring': {},
            'quality_management': {}
        }
        self.scheduler = NightScheduler(
            str(self.workspace_path), 
            scheduler_config,
            main_agent=self  # セッション設定へのアクセス用
        )
        
        # コスト管理
        self.cost_manager = CostManager(self.config.cost_management.__dict__)
        
        # 安全性コーディネーター
        self.safety_coordinator = SafetyCoordinator(
            str(self.workspace_path), 
            self.config.safety.__dict__
        )
        
        # 並行実行マネージャー
        self.parallel_executor = ParallelExecutor(
            str(self.workspace_path), 
            self.config.parallel_execution.__dict__
        )
        
        # レポートジェネレーター
        self.report_generator = ReportGenerator(self.logger)
        
        # 対話ログシステム
        self.interaction_logger = InteractionLogger(str(self.workspace_path / "logs" / "interactions"))
        
        # Spec Kit駆動実行システム
        self.spec_executor = SpecDrivenExecutor(str(self.workspace_path), self.logger)
        
        self.logger.log(
            LogLevel.INFO,
            LogCategory.SYSTEM,
            "Nocturnal Agent システム初期化完了",
            extra_data={
                'workspace_path': str(self.workspace_path),
                'project_name': self.config.project_name
            }
        )
    
    async def start_autonomous_session(self, 
                                     immediate: bool = False,
                                     duration_minutes: Optional[int] = None,
                                     task_limit: Optional[int] = None,
                                     quality_threshold: Optional[float] = None,
                                     use_spec_kit: bool = False,
                                     spec_type: str = "feature") -> str:
        """自律セッション開始"""
        if self.is_running:
            raise RuntimeError("セッションが既に実行中です")
        
        self.session_id = f"nocturnal_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        self.is_running = True
        self.session_stats['start_time'] = datetime.now()
        
        self.logger.log(
            LogLevel.INFO,
            LogCategory.SYSTEM,
            f"自律セッション開始: {self.session_id}",
            session_id=self.session_id,
            extra_data={
                'immediate': immediate,
                'duration_minutes': duration_minutes,
                'task_limit': task_limit,
                'quality_threshold': quality_threshold,
                'use_spec_kit': use_spec_kit,
                'spec_type': spec_type if use_spec_kit else None
            }
        )
        
        # セッション設定を保存
        self.session_settings = {
            'use_spec_kit': use_spec_kit,
            'spec_type': spec_type,
            'quality_threshold': quality_threshold or self.config.minimum_quality_threshold
        }
        
        try:
            # 安全性セッション初期化
            await self.safety_coordinator.initialize_safety_session()
            
            # 並行実行セッション開始
            await self.parallel_executor.start_parallel_session()
            
            # メインセッション実行
            await self._run_autonomous_session(
                immediate=immediate,
                duration_minutes=duration_minutes,
                task_limit=task_limit,
                quality_threshold=quality_threshold or self.config.minimum_quality_threshold
            )
            
        except Exception as e:
            self.logger.log_error(
                "session_execution_error",
                f"セッション実行エラー: {e}",
                session_id=self.session_id,
                exc_info=True
            )
            raise
        finally:
            await self._finalize_session()
        
        return self.session_id
    
    async def _run_autonomous_session(self,
                                    immediate: bool = False,
                                    duration_minutes: Optional[int] = None,
                                    task_limit: Optional[int] = None,
                                    quality_threshold: float = 0.6) -> None:
        """メイン自律セッション実行"""
        
        # スケジューラーでセッション実行
        session_config = {
            'immediate_start': immediate,
            'duration_minutes': duration_minutes,
            'task_limit': task_limit,
            'quality_threshold': quality_threshold,
            'session_id': self.session_id
        }
        
        await self.scheduler.start_night_session(**session_config)
        
        # セッション監視とタスク処理のメインループ
        await self._main_execution_loop()
    
    async def _main_execution_loop(self) -> None:
        """メイン実行ループ"""
        while self.is_running:
            try:
                # システム状態チェック
                scheduler_status = await self.scheduler.get_system_status()
                
                if not scheduler_status.get('active_session'):
                    self.logger.log(
                        LogLevel.INFO,
                        LogCategory.SYSTEM,
                        "スケジューラーセッションが終了しました",
                        session_id=self.session_id
                    )
                    break
                
                # コスト状況チェック
                cost_status = await self.cost_manager.get_usage_status()
                if cost_status.get('emergency_mode'):
                    self.logger.log(
                        LogLevel.WARNING,
                        LogCategory.COST_MANAGEMENT,
                        "緊急モードが発動しました。セッションを安全に終了します",
                        session_id=self.session_id
                    )
                    break
                
                # 安全性チェック
                safety_status = self.safety_coordinator.get_safety_status()
                violations = safety_status.get('safety_violations_count', 0)
                if violations > 10:  # 安全性違反が多い場合
                    self.logger.log(
                        LogLevel.WARNING,
                        LogCategory.SAFETY,
                        f"安全性違反が多数発生しています（{violations}件）",
                        session_id=self.session_id
                    )
                
                # 進行状況の更新
                await self._update_session_stats(scheduler_status)
                
                # 定期的な待機
                await asyncio.sleep(30)  # 30秒間隔
                
            except asyncio.CancelledError:
                self.logger.log(
                    LogLevel.INFO,
                    LogCategory.SYSTEM,
                    "セッションがキャンセルされました",
                    session_id=self.session_id
                )
                break
            except Exception as e:
                self.logger.log_error(
                    "execution_loop_error",
                    f"実行ループエラー: {e}",
                    session_id=self.session_id
                )
                await asyncio.sleep(5)  # エラー時は短い待機
    
    async def _update_session_stats(self, scheduler_status: Dict[str, Any]) -> None:
        """セッション統計更新"""
        if 'session_info' in scheduler_status:
            session_info = scheduler_status['session_info']
            
            self.session_stats.update({
                'total_tasks': session_info.get('total_tasks', 0),
                'completed_tasks': session_info.get('completed_tasks', 0),
                'failed_tasks': session_info.get('failed_tasks', 0)
            })
    
    async def stop_session(self, force: bool = False) -> bool:
        """セッション停止"""
        if not self.is_running:
            return True
        
        self.logger.log(
            LogLevel.INFO,
            LogCategory.SYSTEM,
            f"セッション停止要求: force={force}",
            session_id=self.session_id
        )
        
        self.is_running = False
        
        try:
            # スケジューラー停止
            await self.scheduler.stop_night_session(force=force)
            
            return True
        except Exception as e:
            self.logger.log_error(
                "session_stop_error",
                f"セッション停止エラー: {e}",
                session_id=self.session_id
            )
            return False
    
    async def _finalize_session(self) -> None:
        """セッション終了処理"""
        self.session_stats['end_time'] = datetime.now()
        self.is_running = False
        
        try:
            # 並行実行セッション終了
            parallel_summary = await self.parallel_executor.finalize_parallel_session()
            
            # 安全性セッション終了
            safety_summary = await self.safety_coordinator.finalize_safety_session()
            
            # 最終レポート生成
            final_report = await self.report_generator.generate_session_report(
                self.session_id
            )
            
            # レポート保存
            report_path = self.report_generator.save_report_html(final_report)
            
            self.logger.log(
                LogLevel.INFO,
                LogCategory.SYSTEM,
                f"セッション終了: {self.session_id}",
                session_id=self.session_id,
                extra_data={
                    'session_duration_minutes': self._calculate_session_duration(),
                    'total_tasks': self.session_stats['total_tasks'],
                    'completed_tasks': self.session_stats['completed_tasks'],
                    'failed_tasks': self.session_stats['failed_tasks'],
                    'success_rate': self._calculate_success_rate(),
                    'final_report_path': str(report_path)
                }
            )
            
        except Exception as e:
            self.logger.log_error(
                "session_finalization_error",
                f"セッション終了処理エラー: {e}",
                session_id=self.session_id
            )
    
    def _calculate_session_duration(self) -> float:
        """セッション期間計算（分）"""
        if self.session_stats['start_time'] and self.session_stats['end_time']:
            duration = self.session_stats['end_time'] - self.session_stats['start_time']
            return duration.total_seconds() / 60
        return 0.0
    
    def _calculate_success_rate(self) -> float:
        """成功率計算"""
        total = self.session_stats['completed_tasks'] + self.session_stats['failed_tasks']
        if total > 0:
            return self.session_stats['completed_tasks'] / total
        return 0.0
    
    async def get_system_status(self) -> Dict[str, Any]:
        """システム状況取得"""
        status = {
            'system_info': {
                'session_active': self.is_running,
                'session_id': self.session_id,
                'project_name': self.config.project_name,
                'workspace_path': str(self.workspace_path)
            }
        }
        
        if self.is_running and self.session_id:
            # アクティブセッション情報
            status['session_stats'] = self.session_stats.copy()
            status['session_stats']['duration_minutes'] = self._calculate_session_duration()
        
        # 各システムの状況
        try:
            status['scheduler'] = await self.scheduler.get_system_status()
        except:
            status['scheduler'] = {'error': 'スケジューラー状況取得失敗'}
        
        try:
            status['cost_management'] = self.cost_manager.get_cost_dashboard()
        except:
            status['cost_management'] = {'error': 'コスト状況取得失敗'}
        
        try:
            status['safety'] = self.safety_coordinator.get_safety_status()
        except:
            status['safety'] = {'error': '安全性状況取得失敗'}
        
        try:
            status['parallel_execution'] = await self.parallel_executor.get_execution_status()
        except:
            status['parallel_execution'] = {'error': '並行実行状況取得失敗'}
        
        return status
    
    async def generate_current_report(self, report_type: str = "session") -> str:
        """現在のセッションのレポート生成"""
        if not self.session_id:
            raise ValueError("アクティブなセッションがありません")
        
        if report_type == "session":
            report = self.report_generator.generate_session_report(self.session_id)
        elif report_type == "daily":
            report = self.report_generator.generate_daily_report()
        else:
            raise ValueError(f"サポートされていないレポートタイプ: {report_type}")
        
        # レポート保存
        html_path = self.report_generator.save_report_html(report)
        return str(html_path)
    
    def update_configuration(self, updates: Dict[str, Any]) -> bool:
        """設定更新"""
        success = self.config_manager.update_config(updates)
        
        if success:
            # 設定を再読み込み
            self.config = self.config_manager.load_config()
            
            self.logger.log(
                LogLevel.INFO,
                LogCategory.SYSTEM,
                "設定が更新されました",
                session_id=self.session_id,
                extra_data={'updates': updates}
            )
        
        return success
    
    async def execute_task_with_spec_design(self, task: Task, 
                                           executor_func,
                                           spec_type: SpecType = SpecType.FEATURE) -> ExecutionResult:
        """Spec Kit仕様駆動タスク実行（対話ログ付き）"""
        
        # 対話ログ: 指示送信
        self.interaction_logger.log_instruction(
            session_id=self.session_id or "unknown",
            task_id=task.id,
            agent_type=InteractionAgentType.CLAUDE_CODE,
            instruction=f"Spec Kit駆動でタスク実行: {task.description}",
            metadata={
                'spec_type': spec_type.value,
                'estimated_quality': task.estimated_quality,
                'requirements': task.requirements
            }
        )
        
        self.logger.log(
            LogLevel.INFO,
            LogCategory.SYSTEM,
            f"Spec Kit駆動実行開始: {task.description}",
            task_id=task.id,
            extra_data={
                'spec_type': spec_type.value,
                'estimated_quality': task.estimated_quality
            }
        )
        
        try:
            # Spec Kit駆動実行
            result = await self.spec_executor.execute_task_with_spec(
                task, executor_func, spec_type
            )
            
            # 対話ログ: レスポンス受信
            self.interaction_logger.log_response(
                session_id=self.session_id or "unknown",
                task_id=task.id,
                agent_type=InteractionAgentType.CLAUDE_CODE,
                response=f"Spec Kit駆動実行完了。生成コード: {len(result.generated_code.split())}語",
                quality_score=result.quality_score.overall if result.quality_score else None,
                execution_time=result.execution_time,
                metadata={
                    'success': result.success,
                    'agent_used': result.agent_used.value if result.agent_used else None,
                    'files_created': getattr(result, 'files_created', [])
                }
            )
            
            # 品質に基づく承認/拒否の判定
            quality_threshold = 0.85
            if result.success and (not result.quality_score or result.quality_score.overall >= quality_threshold):
                # 承認
                self.interaction_logger.log_approval(
                    session_id=self.session_id or "unknown",
                    task_id=task.id,
                    agent_type=InteractionAgentType.CLAUDE_CODE,
                    response=result.generated_code[:200] + "...",
                    reason=f"品質スコア {result.quality_score.overall:.2f} が閾値 {quality_threshold} を超過",
                    metadata={'auto_approval': True}
                )
            elif not result.success or (result.quality_score and result.quality_score.overall < quality_threshold):
                # 拒否
                rejection_reason = "実行失敗" if not result.success else f"品質スコア {result.quality_score.overall:.2f} が閾値 {quality_threshold} を下回る"
                self.interaction_logger.log_rejection(
                    session_id=self.session_id or "unknown",
                    task_id=task.id,
                    agent_type=InteractionAgentType.CLAUDE_CODE,
                    response=result.generated_code[:200] + "..." if result.generated_code else "実行失敗",
                    rejection_reason=rejection_reason,
                    metadata={'auto_rejection': True}
                )
            
            self.logger.log(
                LogLevel.INFO,
                LogCategory.SYSTEM,
                f"Spec Kit駆動実行完了: 成功={result.success}",
                task_id=task.id,
                extra_data={
                    'quality_achieved': result.quality_score.overall if result.quality_score else 0,
                    'spec_driven': True
                }
            )
            
            return result
            
        except Exception as e:
            # 対話ログ: エラー
            self.interaction_logger.log_rejection(
                session_id=self.session_id or "unknown",
                task_id=task.id,
                agent_type=InteractionAgentType.CLAUDE_CODE,
                response="実行エラー",
                rejection_reason=f"例外発生: {str(e)}",
                metadata={'error_type': type(e).__name__}
            )
            
            self.logger.log_error(
                "spec_driven_execution_error",
                f"Spec Kit駆動実行エラー: {e}",
                task_id=task.id
            )
            raise
    
    async def generate_spec_report(self) -> Dict[str, Any]:
        """Spec Kit仕様レポート生成"""
        return self.spec_executor.generate_spec_report()
    
    async def cleanup_old_specs(self, days_old: int = 30) -> int:
        """古いSpec Kit仕様のクリーンアップ"""
        return await self.spec_executor.cleanup_old_specs(days_old)
    
    def validate_system(self) -> Dict[str, Any]:
        """システム検証"""
        validation_result = {
            'overall_healthy': True,
            'issues': [],
            'warnings': [],
            'config_validation': []
        }
        
        # 設定検証
        config_errors = self.config_manager.validate_config()
        validation_result['config_validation'] = config_errors
        
        if config_errors:
            validation_result['overall_healthy'] = False
            validation_result['issues'].extend(config_errors)
        
        # ワークスペース検証
        if not self.workspace_path.exists():
            validation_result['overall_healthy'] = False
            validation_result['issues'].append(f"ワークスペースが存在しません: {self.workspace_path}")
        
        # データディレクトリ検証
        data_dir = Path(self.config.data_directory)
        if not data_dir.exists():
            validation_result['warnings'].append(f"データディレクトリが存在しません: {data_dir}")
        
        # ログディレクトリ検証
        log_dir = Path(self.config.log_directory)
        if not log_dir.exists():
            validation_result['warnings'].append(f"ログディレクトリが存在しません: {log_dir}")
        
        return validation_result


# 便利な関数
async def create_and_start_session(config_path: Optional[str] = None,
                                 workspace_path: Optional[str] = None,
                                 immediate: bool = False,
                                 duration_minutes: Optional[int] = None) -> NocturnalAgent:
    """簡単セッション作成・開始"""
    agent = NocturnalAgent(config_path, workspace_path)
    
    session_id = await agent.start_autonomous_session(
        immediate=immediate,
        duration_minutes=duration_minutes
    )
    
    return agent


def create_agent(config_path: Optional[str] = None,
                workspace_path: Optional[str] = None) -> NocturnalAgent:
    """エージェント作成（セッション開始なし）"""
    return NocturnalAgent(config_path, workspace_path)