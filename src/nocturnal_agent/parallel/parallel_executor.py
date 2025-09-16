"""並行実行システムの統合コーディネーター"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Tuple
from dataclasses import dataclass, field
import concurrent.futures

from nocturnal_agent.parallel.branch_manager import BranchManager, BranchType
from nocturnal_agent.parallel.quality_controller import QualityController, QualityTier
from nocturnal_agent.core.models import Task, ExecutionResult

logger = logging.getLogger(__name__)


@dataclass
class ParallelExecutionTask:
    """並行実行タスク情報"""
    task: Task
    branch_name: str
    quality_tier: QualityTier
    started_at: datetime
    executor_id: str
    future: Optional[asyncio.Future] = None
    estimated_completion: Optional[datetime] = None


@dataclass
class ExecutionSession:
    """実行セッション情報"""
    session_id: str
    started_at: datetime
    night_main_branch: str
    active_tasks: Dict[str, ParallelExecutionTask] = field(default_factory=dict)
    completed_tasks: List[str] = field(default_factory=list)
    failed_tasks: List[str] = field(default_factory=list)
    max_parallel_limit: int = 3
    total_tasks_processed: int = 0


class ParallelExecutor:
    """並行実行システムの統合管理"""
    
    def __init__(self, project_path: str, config: Dict[str, Any]):
        """
        並行実行システムを初期化
        
        Args:
            project_path: プロジェクトパス
            config: 並行実行設定
        """
        self.project_path = project_path
        self.config = config
        
        # サブシステムを初期化
        self.branch_manager = BranchManager(project_path, config.get('branch_config', {}))
        self.quality_controller = QualityController(self.branch_manager, config.get('quality_config', {}))
        
        # 実行設定
        self.max_parallel_executions = config.get('max_parallel_executions', 3)
        self.execution_timeout = config.get('execution_timeout_seconds', 1800)  # 30分
        self.quality_assessment_enabled = config.get('quality_assessment_enabled', True)
        self.progressive_rollout_enabled = config.get('progressive_rollout_enabled', True)
        
        # セッション管理
        self.current_session: Optional[ExecutionSession] = None
        self.executor_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.max_parallel_executions
        )
        
        # コールバック
        self.execution_callbacks: List[Callable] = []
        self.completion_callbacks: List[Callable] = []
        
        # 統計
        self.executor_stats = {
            'sessions_started': 0,
            'total_tasks_executed': 0,
            'parallel_executions_peak': 0,
            'average_execution_time': 0.0,
            'success_rate': 0.0,
            'quality_improvement_rate': 0.0,
            'branch_merge_success_rate': 0.0
        }
    
    async def start_parallel_session(self) -> str:
        """
        並行実行セッションを開始
        
        Returns:
            セッションID
        """
        logger.info("並行実行セッション開始")
        
        try:
            # 夜間ブランチ環境を初期化
            night_main_branch = self.branch_manager.initialize_night_session()
            
            # セッション情報を作成
            session_id = f"parallel-{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            self.current_session = ExecutionSession(
                session_id=session_id,
                started_at=datetime.now(),
                night_main_branch=night_main_branch,
                max_parallel_limit=self.max_parallel_executions
            )
            
            self.executor_stats['sessions_started'] += 1
            
            logger.info(f"並行実行セッション開始完了: {session_id}")
            return session_id
            
        except Exception as e:
            logger.error(f"セッション開始エラー: {e}")
            raise
    
    async def execute_task_parallel(self, task: Task, executor_func: Callable,
                                  estimated_quality: float = 0.0) -> str:
        """
        タスクを並行実行キューに追加
        
        Args:
            task: 実行対象タスク
            executor_func: タスク実行関数
            estimated_quality: 推定品質スコア
            
        Returns:
            実行ID
        """
        if not self.current_session:
            raise RuntimeError("並行実行セッションが開始されていません")
        
        logger.debug(f"並行実行タスク追加: {task.id}")
        
        try:
            # 並行実行数の制限チェック
            if len(self.current_session.active_tasks) >= self.current_session.max_parallel_limit:
                # 完了待ち
                await self._wait_for_execution_slot()
            
            # 品質評価と実行方針決定
            if self.quality_assessment_enabled:
                quality_decision = await self.quality_controller.evaluate_task_quality(
                    task, estimated_quality
                )
                
                if quality_decision.action == "reject":
                    logger.warning(f"品質評価によりタスク拒否: {task.id}")
                    self.current_session.failed_tasks.append(task.id)
                    return task.id
            else:
                # 品質評価無効時はデフォルト設定
                quality_decision = None
            
            # 並行実行タスクを作成
            parallel_task = ParallelExecutionTask(
                task=task,
                branch_name="",  # 後で設定
                quality_tier=quality_decision.quality_tier if quality_decision else QualityTier.MEDIUM,
                started_at=datetime.now(),
                executor_id=f"exec-{task.id}-{int(datetime.now().timestamp())}",
                estimated_completion=datetime.now() + timedelta(seconds=self.execution_timeout)
            )
            
            # 非同期実行を開始
            future = asyncio.create_task(
                self._execute_task_with_quality_control(
                    parallel_task, executor_func, quality_decision
                )
            )
            parallel_task.future = future
            
            # アクティブタスクリストに追加
            self.current_session.active_tasks[task.id] = parallel_task
            self.current_session.total_tasks_processed += 1
            
            # 統計更新
            current_parallel = len(self.current_session.active_tasks)
            if current_parallel > self.executor_stats['parallel_executions_peak']:
                self.executor_stats['parallel_executions_peak'] = current_parallel
            
            # 実行コールバックを通知
            await self._notify_execution_callbacks('task_started', task, parallel_task)
            
            logger.debug(f"並行実行開始: {task.id} ({current_parallel}/{self.max_parallel_executions})")
            return task.id
            
        except Exception as e:
            logger.error(f"並行実行追加エラー ({task.id}): {e}")
            self.current_session.failed_tasks.append(task.id)
            raise
    
    async def wait_for_completion(self, task_id: Optional[str] = None,
                                timeout: Optional[float] = None) -> Dict[str, Any]:
        """
        タスク完了を待機
        
        Args:
            task_id: 特定のタスクID（Noneの場合は全タスク完了を待機）
            timeout: タイムアウト秒数
            
        Returns:
            完了結果
        """
        if not self.current_session:
            raise RuntimeError("並行実行セッションが開始されていません")
        
        try:
            if task_id:
                # 特定のタスクの完了を待機
                if task_id not in self.current_session.active_tasks:
                    if task_id in self.current_session.completed_tasks:
                        return {'status': 'completed', 'task_id': task_id}
                    elif task_id in self.current_session.failed_tasks:
                        return {'status': 'failed', 'task_id': task_id}
                    else:
                        return {'status': 'not_found', 'task_id': task_id}
                
                parallel_task = self.current_session.active_tasks[task_id]
                
                if timeout:
                    result = await asyncio.wait_for(parallel_task.future, timeout=timeout)
                else:
                    result = await parallel_task.future
                
                return {'status': 'completed', 'task_id': task_id, 'result': result}
                
            else:
                # 全タスクの完了を待機
                active_futures = [
                    task.future for task in self.current_session.active_tasks.values()
                    if task.future and not task.future.done()
                ]
                
                if not active_futures:
                    return {'status': 'all_completed', 'active_count': 0}
                
                logger.info(f"全タスク完了待機中: {len(active_futures)}個のタスク")
                
                if timeout:
                    done, pending = await asyncio.wait(
                        active_futures, timeout=timeout, return_when=asyncio.ALL_COMPLETED
                    )
                    
                    if pending:
                        logger.warning(f"タイムアウト: {len(pending)}個のタスクが未完了")
                        return {
                            'status': 'timeout',
                            'completed_count': len(done),
                            'pending_count': len(pending)
                        }
                else:
                    await asyncio.gather(*active_futures, return_exceptions=True)
                
                return {
                    'status': 'all_completed',
                    'completed_count': len(self.current_session.completed_tasks),
                    'failed_count': len(self.current_session.failed_tasks)
                }
                
        except Exception as e:
            logger.error(f"完了待機エラー: {e}")
            return {'status': 'error', 'error': str(e)}
    
    async def finalize_parallel_session(self) -> Dict[str, Any]:
        """
        並行実行セッションを終了
        
        Returns:
            セッション実行結果サマリー
        """
        if not self.current_session:
            raise RuntimeError("並行実行セッションが開始されていません")
        
        logger.info("並行実行セッション終了処理開始")
        
        try:
            # アクティブタスクの完了を待機（タイムアウト付き）
            if self.current_session.active_tasks:
                logger.info(f"残存タスク完了待機: {len(self.current_session.active_tasks)}個")
                completion_result = await self.wait_for_completion(timeout=300)  # 5分でタイムアウト
                
                if completion_result['status'] == 'timeout':
                    logger.warning("一部のタスクがタイムアウトしました")
            
            # ブランチレビューを実行
            if self.quality_assessment_enabled:
                review_results = await self.quality_controller.review_pending_branches()
                logger.info(f"ブランチレビュー完了: {review_results['branches_reviewed']}ブランチ")
            else:
                review_results = {'branches_reviewed': 0}
            
            # セッション統計を生成
            session_duration = datetime.now() - self.current_session.started_at
            
            session_summary = {
                'session_id': self.current_session.session_id,
                'duration': str(session_duration),
                'total_tasks_processed': self.current_session.total_tasks_processed,
                'completed_tasks': len(self.current_session.completed_tasks),
                'failed_tasks': len(self.current_session.failed_tasks),
                'success_rate': len(self.current_session.completed_tasks) / max(self.current_session.total_tasks_processed, 1),
                'parallel_peak': self.executor_stats['parallel_executions_peak'],
                'branch_management': self.branch_manager.finalize_night_session(),
                'quality_review': review_results,
                'recommendations': self.quality_controller.get_quality_recommendations()
            }
            
            # グローバル統計を更新
            self._update_global_stats(session_summary)
            
            # セッションをクリア
            self.current_session = None
            
            logger.info(f"並行実行セッション終了: 成功率{session_summary['success_rate']:.1%}")
            return session_summary
            
        except Exception as e:
            logger.error(f"セッション終了エラー: {e}")
            raise
    
    async def get_execution_status(self) -> Dict[str, Any]:
        """現在の実行状態を取得"""
        if not self.current_session:
            return {
                'session_active': False,
                'message': 'セッションが開始されていません'
            }
        
        active_tasks = []
        for task_id, parallel_task in self.current_session.active_tasks.items():
            status = "running"
            if parallel_task.future and parallel_task.future.done():
                status = "completed" if not parallel_task.future.exception() else "failed"
            
            active_tasks.append({
                'task_id': task_id,
                'branch': parallel_task.branch_name,
                'quality_tier': parallel_task.quality_tier.value,
                'status': status,
                'duration': str(datetime.now() - parallel_task.started_at),
                'executor_id': parallel_task.executor_id
            })
        
        return {
            'session_active': True,
            'session_id': self.current_session.session_id,
            'session_duration': str(datetime.now() - self.current_session.started_at),
            'active_tasks': active_tasks,
            'completed_count': len(self.current_session.completed_tasks),
            'failed_count': len(self.current_session.failed_tasks),
            'total_processed': self.current_session.total_tasks_processed,
            'parallel_limit': self.current_session.max_parallel_limit,
            'branch_status': self.branch_manager.get_branch_status(),
            'quality_status': self.quality_controller.get_controller_status()
        }
    
    async def _wait_for_execution_slot(self):
        """実行スロットが空くまで待機"""
        logger.debug("実行スロット待機中")
        
        while len(self.current_session.active_tasks) >= self.current_session.max_parallel_limit:
            # 完了したタスクをクリーンアップ
            await self._cleanup_completed_tasks()
            
            if len(self.current_session.active_tasks) >= self.current_session.max_parallel_limit:
                # まだ満杯の場合は少し待機
                await asyncio.sleep(1.0)
    
    async def _execute_task_with_quality_control(self, parallel_task: ParallelExecutionTask,
                                               executor_func: Callable,
                                               quality_decision) -> ExecutionResult:
        """品質制御下でタスクを実行"""
        task = parallel_task.task
        logger.debug(f"品質制御実行開始: {task.id}")
        
        try:
            if self.quality_assessment_enabled and quality_decision:
                # 品質コントローラー経由で実行
                result = await self.quality_controller.execute_with_quality_control(
                    task, quality_decision, executor_func
                )
            else:
                # 直接実行
                result = await executor_func(task)
            
            # 実行完了処理
            await self._handle_task_completion(parallel_task, result, success=True)
            
            return result
            
        except Exception as e:
            logger.error(f"品質制御実行エラー ({task.id}): {e}")
            
            # エラー結果を作成
            error_result = ExecutionResult(
                task_id=task.id,
                success=False,
                quality_score=None,
                generated_code="",
                errors=[str(e)]
            )
            
            # 実行完了処理
            await self._handle_task_completion(parallel_task, error_result, success=False)
            
            return error_result
    
    async def _handle_task_completion(self, parallel_task: ParallelExecutionTask,
                                    result: ExecutionResult, success: bool):
        """タスク完了処理"""
        task_id = parallel_task.task.id
        
        try:
            # セッションから移動
            if task_id in self.current_session.active_tasks:
                del self.current_session.active_tasks[task_id]
            
            if success:
                self.current_session.completed_tasks.append(task_id)
            else:
                self.current_session.failed_tasks.append(task_id)
            
            # 完了コールバックを通知
            await self._notify_completion_callbacks(parallel_task, result, success)
            
            logger.debug(f"タスク完了処理: {task_id} ({'成功' if success else '失敗'})")
            
        except Exception as e:
            logger.error(f"完了処理エラー ({task_id}): {e}")
    
    async def _cleanup_completed_tasks(self):
        """完了したタスクをクリーンアップ"""
        completed_task_ids = []
        
        for task_id, parallel_task in self.current_session.active_tasks.items():
            if parallel_task.future and parallel_task.future.done():
                completed_task_ids.append(task_id)
        
        for task_id in completed_task_ids:
            parallel_task = self.current_session.active_tasks[task_id]
            
            try:
                result = parallel_task.future.result()
                await self._handle_task_completion(parallel_task, result, success=True)
            except Exception as e:
                logger.error(f"タスク結果取得エラー ({task_id}): {e}")
                error_result = ExecutionResult(
                    task_id=task_id,
                    success=False,
                    quality_score=None,
                    generated_code="",
                    errors=[str(e)]
                )
                await self._handle_task_completion(parallel_task, error_result, success=False)
    
    async def _notify_execution_callbacks(self, event_type: str, task: Task,
                                        parallel_task: ParallelExecutionTask):
        """実行コールバックを通知"""
        for callback in self.execution_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event_type, task, parallel_task)
                else:
                    callback(event_type, task, parallel_task)
            except Exception as e:
                logger.error(f"実行コールバックエラー: {e}")
    
    async def _notify_completion_callbacks(self, parallel_task: ParallelExecutionTask,
                                         result: ExecutionResult, success: bool):
        """完了コールバックを通知"""
        for callback in self.completion_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(parallel_task, result, success)
                else:
                    callback(parallel_task, result, success)
            except Exception as e:
                logger.error(f"完了コールバックエラー: {e}")
    
    def _update_global_stats(self, session_summary: Dict[str, Any]):
        """グローバル統計を更新"""
        total_tasks = session_summary['total_tasks_processed']
        if total_tasks > 0:
            self.executor_stats['total_tasks_executed'] += total_tasks
            
            # 成功率の更新
            current_success_rate = self.executor_stats['success_rate']
            new_success_rate = session_summary['success_rate']
            
            # 加重平均で更新
            total_sessions = self.executor_stats['sessions_started']
            if total_sessions > 1:
                self.executor_stats['success_rate'] = (
                    (current_success_rate * (total_sessions - 1) + new_success_rate) / total_sessions
                )
            else:
                self.executor_stats['success_rate'] = new_success_rate
    
    def add_execution_callback(self, callback: Callable):
        """実行コールバックを追加"""
        self.execution_callbacks.append(callback)
    
    def add_completion_callback(self, callback: Callable):
        """完了コールバックを追加"""
        self.completion_callbacks.append(callback)
    
    async def get_system_status(self) -> Dict[str, Any]:
        """システム全体の状態を取得"""
        return {
            'parallel_executor': {
                'max_parallel_executions': self.max_parallel_executions,
                'execution_timeout': self.execution_timeout,
                'quality_assessment_enabled': self.quality_assessment_enabled,
                'current_session_active': self.current_session is not None
            },
            'statistics': self.executor_stats,
            'branch_manager_status': self.branch_manager.get_branch_status(),
            'quality_controller_status': self.quality_controller.get_controller_status(),
            'execution_status': await self.get_execution_status()
        }
    
    def __del__(self):
        """デストラクタ - リソースのクリーンアップ"""
        if hasattr(self, 'executor_pool'):
            self.executor_pool.shutdown(wait=False)