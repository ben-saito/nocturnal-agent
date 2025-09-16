"""品質別実行制御システム - 品質レベルに応じたタスク実行管理"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum

from nocturnal_agent.parallel.branch_manager import BranchManager, BranchType
import subprocess
from nocturnal_agent.core.models import Task, ExecutionResult, QualityScore

logger = logging.getLogger(__name__)


class QualityTier(Enum):
    """品質階層"""
    HIGH = "high"           # 0.85+ 即座に適用
    MEDIUM = "medium"       # 0.7-0.84 並行ブランチで検証
    LOW = "low"             # 0.7未満 実験ブランチで分離
    FAILED = "failed"       # 実行失敗


@dataclass
class QualityDecision:
    """品質に基づく実行決定"""
    quality_tier: QualityTier
    action: str  # immediate_apply, parallel_branch, experimental_branch, reject
    branch_name: Optional[str]
    requires_review: bool
    auto_merge_eligible: bool
    reasoning: str
    confidence: float


@dataclass
class ExecutionPlan:
    """実行プラン"""
    task: Task
    target_branch: str
    expected_quality: float
    execution_strategy: str
    post_execution_action: str
    review_criteria: List[str] = field(default_factory=list)
    rollback_strategy: Optional[str] = None


@dataclass
class QualityMetrics:
    """品質メトリクス"""
    overall_score: float
    individual_scores: Dict[str, float]
    consistency_score: float
    security_assessment: float
    performance_impact: float
    maintainability_score: float
    test_coverage: float = 0.0


class QualityController:
    """品質別実行制御システム"""
    
    def __init__(self, branch_manager: BranchManager, config: Dict[str, Any]):
        """
        品質制御システムを初期化
        
        Args:
            branch_manager: ブランチ管理システム
            config: 品質制御設定
        """
        self.branch_manager = branch_manager
        self.config = config
        
        # 品質閾値設定
        self.high_quality_threshold = config.get('high_quality_threshold', 0.85)
        self.medium_quality_threshold = config.get('medium_quality_threshold', 0.7)
        self.auto_apply_threshold = config.get('auto_apply_threshold', 0.90)
        
        # 実行制御設定
        self.max_parallel_executions = config.get('max_parallel_executions', 3)
        self.quality_assessment_timeout = config.get('quality_assessment_timeout', 300)  # 5分
        self.enable_progressive_rollout = config.get('enable_progressive_rollout', True)
        
        # 実行状態管理
        self.active_executions: Dict[str, ExecutionPlan] = {}
        self.pending_reviews: List[str] = []
        self.quality_history: List[QualityMetrics] = []
        
        # コールバック
        self.quality_callbacks: List[Callable] = []
        self.decision_callbacks: List[Callable] = []
        
        # 統計
        self.controller_stats = {
            'session_start': datetime.now(),
            'tasks_processed': 0,
            'high_quality_auto_applied': 0,
            'medium_quality_parallel': 0,
            'low_quality_experimental': 0,
            'failed_tasks': 0,
            'reviews_completed': 0,
            'auto_merges_performed': 0
        }
    
    async def evaluate_task_quality(self, task: Task, estimated_quality: float = 0.0) -> QualityDecision:
        """
        タスクの品質を評価し実行方針を決定
        
        Args:
            task: 評価対象タスク
            estimated_quality: 事前品質推定値
            
        Returns:
            品質に基づく実行決定
        """
        logger.debug(f"タスク品質評価開始: {task.id}")
        
        try:
            # 品質階層を決定
            quality_tier = self._determine_quality_tier(estimated_quality, task)
            
            # 実行方針を決定
            decision = await self._make_execution_decision(quality_tier, task, estimated_quality)
            
            # 決定コールバックを実行
            await self._notify_decision_callbacks(decision, task)
            
            logger.debug(f"品質評価完了: {task.id} -> {decision.action}")
            return decision
            
        except Exception as e:
            logger.error(f"品質評価エラー ({task.id}): {e}")
            # フォールバック決定
            return QualityDecision(
                quality_tier=QualityTier.LOW,
                action="experimental_branch",
                branch_name=None,
                requires_review=True,
                auto_merge_eligible=False,
                reasoning=f"評価エラーによる安全策: {str(e)}",
                confidence=0.0
            )
    
    async def execute_with_quality_control(self, task: Task, decision: QualityDecision,
                                         executor: Callable) -> ExecutionResult:
        """
        品質制御下でタスクを実行
        
        Args:
            task: 実行対象タスク
            decision: 品質決定
            executor: タスク実行関数
            
        Returns:
            実行結果
        """
        logger.info(f"品質制御実行開始: {task.id} ({decision.action})")
        
        # 実行プランを作成
        execution_plan = await self._create_execution_plan(task, decision)
        self.active_executions[task.id] = execution_plan
        
        try:
            # ブランチ準備
            await self._prepare_execution_branch(execution_plan, decision)
            
            # タスク実行
            execution_result = await self._execute_task_with_monitoring(
                task, execution_plan, executor
            )
            
            # 実行後品質評価
            quality_metrics = await self._assess_execution_quality(
                task, execution_result, execution_plan
            )
            
            # 品質に基づく後処理
            post_execution_result = await self._handle_post_execution(
                task, execution_result, quality_metrics, execution_plan
            )
            
            # 統計更新
            self._update_controller_stats(decision.quality_tier, execution_result.success)
            
            return execution_result
            
        except Exception as e:
            logger.error(f"品質制御実行エラー ({task.id}): {e}")
            # エラー処理
            await self._handle_execution_error(task, execution_plan, str(e))
            raise
        
        finally:
            # クリーンアップ
            if task.id in self.active_executions:
                del self.active_executions[task.id]
    
    async def review_pending_branches(self) -> Dict[str, Any]:
        """保留中のブランチをレビュー"""
        logger.info("保留ブランチのレビュー開始")
        
        review_results = {
            'branches_reviewed': 0,
            'approved_for_merge': [],
            'requires_manual_review': [],
            'rejected': [],
            'errors': []
        }
        
        branch_status = self.branch_manager.get_branch_status()
        
        for branch_info in branch_status.get('recent_activity', []):
            if branch_info['name'] in self.pending_reviews:
                try:
                    review_result = await self._review_branch(branch_info)
                    
                    if review_result['approved']:
                        review_results['approved_for_merge'].append({
                            'branch': branch_info['name'],
                            'reason': review_result['reason']
                        })
                        
                        # 自動マージを試行
                        if review_result.get('auto_merge_eligible', False):
                            merge_result = self.branch_manager.attempt_auto_merge(
                                branch_info['name'],
                                self.branch_manager.current_night_session,
                                review_result.get('quality_score', 0.7)
                            )
                            
                            if merge_result['success']:
                                self.controller_stats['auto_merges_performed'] += 1
                    
                    elif review_result['requires_manual_review']:
                        review_results['requires_manual_review'].append({
                            'branch': branch_info['name'],
                            'issues': review_result['issues']
                        })
                    
                    else:
                        review_results['rejected'].append({
                            'branch': branch_info['name'],
                            'reason': review_result['reason']
                        })
                    
                    review_results['branches_reviewed'] += 1
                    self.controller_stats['reviews_completed'] += 1
                    
                except Exception as e:
                    logger.error(f"ブランチレビューエラー ({branch_info['name']}): {e}")
                    review_results['errors'].append({
                        'branch': branch_info['name'],
                        'error': str(e)
                    })
        
        # 保留リストを更新
        self.pending_reviews = [
            branch for branch in self.pending_reviews
            if branch not in [b['branch'] for b in review_results['approved_for_merge']]
            and branch not in [b['branch'] for b in review_results['rejected']]
        ]
        
        logger.info(f"レビュー完了: {review_results['branches_reviewed']}ブランチ処理")
        return review_results
    
    def get_quality_recommendations(self) -> List[Dict[str, Any]]:
        """品質向上の推奨事項を取得"""
        recommendations = []
        
        # 品質履歴分析
        if len(self.quality_history) >= 5:
            recent_scores = [q.overall_score for q in self.quality_history[-10:]]
            avg_score = sum(recent_scores) / len(recent_scores)
            
            if avg_score < self.medium_quality_threshold:
                recommendations.append({
                    'type': 'quality_improvement',
                    'priority': 'high',
                    'title': '品質スコアの改善が必要',
                    'description': f'直近の平均品質: {avg_score:.2f}',
                    'actions': [
                        'タスクの事前品質チェックの強化',
                        'コード生成プロンプトの改善',
                        'レビュー基準の見直し'
                    ]
                })
        
        # 実行パターン分析
        stats = self.controller_stats
        total_tasks = stats['tasks_processed']
        
        if total_tasks > 0:
            high_quality_rate = stats['high_quality_auto_applied'] / total_tasks
            
            if high_quality_rate < 0.3:  # 30%未満
                recommendations.append({
                    'type': 'execution_strategy',
                    'priority': 'medium',
                    'title': '高品質タスクの比率が低い',
                    'description': f'自動適用率: {high_quality_rate:.1%}',
                    'actions': [
                        'タスク選択基準の見直し',
                        '品質予測モデルの調整',
                        'エージェント設定の最適化'
                    ]
                })
        
        # ブランチ管理分析
        branch_status = self.branch_manager.get_branch_status()
        active_branches = branch_status.get('active_branches_count', 0)
        
        if active_branches > self.max_parallel_executions * 1.5:
            recommendations.append({
                'type': 'branch_management',
                'priority': 'medium',
                'title': 'アクティブブランチ数が多すぎる',
                'description': f'現在: {active_branches}ブランチ',
                'actions': [
                    '古いブランチのクリーンアップ',
                    '並行実行数の制限',
                    'マージ頻度の向上'
                ]
            })
        
        return recommendations
    
    def _determine_quality_tier(self, estimated_quality: float, task: Task) -> QualityTier:
        """品質階層を決定"""
        if estimated_quality >= self.high_quality_threshold:
            return QualityTier.HIGH
        elif estimated_quality >= self.medium_quality_threshold:
            return QualityTier.MEDIUM
        elif estimated_quality > 0:
            return QualityTier.LOW
        else:
            return QualityTier.FAILED
    
    async def _make_execution_decision(self, quality_tier: QualityTier, task: Task,
                                     estimated_quality: float) -> QualityDecision:
        """実行決定を作成"""
        
        if quality_tier == QualityTier.HIGH:
            # 高品質: 即座適用またはメインブランチへの並行実行
            if estimated_quality >= self.auto_apply_threshold:
                action = "immediate_apply"
                branch_name = self.branch_manager.current_night_session
                auto_merge_eligible = True
                requires_review = False
                reasoning = f"高品質スコア ({estimated_quality:.2f}) により即座適用"
            else:
                action = "parallel_branch"
                branch_name = None  # 後で作成
                auto_merge_eligible = True
                requires_review = False
                reasoning = f"高品質 ({estimated_quality:.2f}) だが慎重に並行実行"
        
        elif quality_tier == QualityTier.MEDIUM:
            # 中品質: 並行ブランチで検証
            action = "parallel_branch"
            branch_name = None
            auto_merge_eligible = False
            requires_review = True
            reasoning = f"中品質 ({estimated_quality:.2f}) のため並行検証"
        
        elif quality_tier == QualityTier.LOW:
            # 低品質: 実験ブランチで分離
            action = "experimental_branch"
            branch_name = None
            auto_merge_eligible = False
            requires_review = True
            reasoning = f"低品質 ({estimated_quality:.2f}) のため実験的実行"
        
        else:
            # 失敗予想: 拒否
            action = "reject"
            branch_name = None
            auto_merge_eligible = False
            requires_review = True
            reasoning = "実行失敗が予想されるため拒否"
        
        return QualityDecision(
            quality_tier=quality_tier,
            action=action,
            branch_name=branch_name,
            requires_review=requires_review,
            auto_merge_eligible=auto_merge_eligible,
            reasoning=reasoning,
            confidence=min(estimated_quality, 1.0) if estimated_quality > 0 else 0.0
        )
    
    async def _create_execution_plan(self, task: Task, decision: QualityDecision) -> ExecutionPlan:
        """実行プランを作成"""
        
        # ターゲットブランチを決定
        if decision.action == "immediate_apply":
            target_branch = self.branch_manager.current_night_session
        else:
            # 新しいブランチを作成
            target_branch = self.branch_manager.create_quality_branch(
                quality_score=decision.confidence,
                task_id=task.id,
                task_description=task.description
            )
            decision.branch_name = target_branch
        
        # 実行戦略を決定
        if decision.quality_tier == QualityTier.HIGH:
            execution_strategy = "standard_execution"
            post_execution_action = "auto_merge_if_successful"
        elif decision.quality_tier == QualityTier.MEDIUM:
            execution_strategy = "monitored_execution"
            post_execution_action = "queue_for_review"
        else:
            execution_strategy = "sandboxed_execution"
            post_execution_action = "manual_review_required"
        
        return ExecutionPlan(
            task=task,
            target_branch=target_branch,
            expected_quality=decision.confidence,
            execution_strategy=execution_strategy,
            post_execution_action=post_execution_action,
            review_criteria=[
                "コードの正常動作",
                "既存機能への影響なし",
                "セキュリティ問題なし",
                "品質基準の達成"
            ],
            rollback_strategy="branch_deletion" if decision.quality_tier == QualityTier.LOW else "revert_commit"
        )
    
    async def _prepare_execution_branch(self, plan: ExecutionPlan, decision: QualityDecision):
        """実行用ブランチを準備"""
        # ブランチに切り替え
        if not self.branch_manager.switch_to_branch(plan.target_branch):
            raise RuntimeError(f"ブランチ切り替え失敗: {plan.target_branch}")
        
        logger.debug(f"実行ブランチ準備完了: {plan.target_branch}")
    
    async def _execute_task_with_monitoring(self, task: Task, plan: ExecutionPlan,
                                          executor: Callable) -> ExecutionResult:
        """監視下でタスクを実行"""
        logger.debug(f"監視実行開始: {task.id}")
        
        # タスク実行（タイムアウト付き）
        try:
            result = await asyncio.wait_for(
                executor(task),
                timeout=self.quality_assessment_timeout
            )
            
            logger.debug(f"タスク実行完了: {task.id} ({'成功' if result.success else '失敗'})")
            return result
            
        except asyncio.TimeoutError:
            logger.warning(f"タスク実行タイムアウト: {task.id}")
            # タイムアウト用のExecutionResultを作成
            return ExecutionResult(
                task_id=task.id,
                success=False,
                quality_score=QualityScore(overall=0.0),
                generated_code="",
                errors=["実行タイムアウト"]
            )
    
    async def _assess_execution_quality(self, task: Task, result: ExecutionResult,
                                      plan: ExecutionPlan) -> QualityMetrics:
        """実行結果の品質を評価"""
        
        # 基本品質メトリクスを抽出
        quality_score = result.quality_score if result.quality_score else QualityScore()
        
        metrics = QualityMetrics(
            overall_score=quality_score.overall,
            individual_scores={
                'code_quality': quality_score.code_quality,
                'consistency': quality_score.consistency,
                'security': quality_score.security,
                'performance': quality_score.performance
            },
            consistency_score=quality_score.consistency,
            security_assessment=quality_score.security,
            performance_impact=quality_score.performance,
            maintainability_score=quality_score.code_quality,
            test_coverage=quality_score.test_coverage
        )
        
        # 品質履歴に追加
        self.quality_history.append(metrics)
        
        # 古い履歴を削除（最新100件のみ保持）
        if len(self.quality_history) > 100:
            self.quality_history = self.quality_history[-100:]
        
        return metrics
    
    async def _handle_post_execution(self, task: Task, result: ExecutionResult,
                                   metrics: QualityMetrics, plan: ExecutionPlan) -> Dict[str, Any]:
        """実行後の処理を実行"""
        
        post_result = {
            'action_taken': None,
            'merge_attempted': False,
            'merge_successful': False,
            'review_queued': False
        }
        
        if not result.success:
            # 実行失敗の場合
            post_result['action_taken'] = 'execution_failed'
            logger.warning(f"タスク実行失敗: {task.id}")
            return post_result
        
        # 実行成功の場合の後処理
        if plan.post_execution_action == "auto_merge_if_successful":
            if metrics.overall_score >= self.high_quality_threshold:
                # 自動マージを試行
                merge_result = self.branch_manager.attempt_auto_merge(
                    plan.target_branch,
                    self.branch_manager.current_night_session,
                    metrics.overall_score
                )
                
                post_result['merge_attempted'] = True
                post_result['merge_successful'] = merge_result['success']
                post_result['action_taken'] = 'auto_merged' if merge_result['success'] else 'merge_failed'
                
                if not merge_result['success']:
                    # マージ失敗時はレビューキューに追加
                    self.pending_reviews.append(plan.target_branch)
                    post_result['review_queued'] = True
            else:
                # 品質が不十分な場合はレビューキューに追加
                self.pending_reviews.append(plan.target_branch)
                post_result['review_queued'] = True
                post_result['action_taken'] = 'quality_insufficient_queued'
        
        elif plan.post_execution_action == "queue_for_review":
            # レビューキューに追加
            self.pending_reviews.append(plan.target_branch)
            post_result['review_queued'] = True
            post_result['action_taken'] = 'queued_for_review'
        
        else:
            # 手動レビューが必要
            post_result['action_taken'] = 'manual_review_required'
        
        return post_result
    
    async def _handle_execution_error(self, task: Task, plan: ExecutionPlan, error: str):
        """実行エラーの処理"""
        logger.error(f"実行エラー処理: {task.id} - {error}")
        
        # エラー時のロールバック戦略を実行
        if plan.rollback_strategy == "branch_deletion":
            try:
                # ブランチを削除（危険な変更を含む可能性があるため）
                subprocess.run([
                    'git', 'checkout', self.branch_manager.current_night_session
                ], cwd=self.branch_manager.project_path, check=True)
                
                subprocess.run([
                    'git', 'branch', '-D', plan.target_branch
                ], cwd=self.branch_manager.project_path, check=True)
                
                logger.info(f"エラーブランチ削除: {plan.target_branch}")
            except Exception as e:
                logger.error(f"ブランチ削除エラー: {e}")
        
        self.controller_stats['failed_tasks'] += 1
    
    async def _review_branch(self, branch_info: Dict[str, Any]) -> Dict[str, Any]:
        """ブランチのレビューを実行"""
        
        # 簡略化されたレビューロジック
        # 実際の実装では、より詳細な品質チェックが必要
        
        review_result = {
            'approved': False,
            'requires_manual_review': False,
            'auto_merge_eligible': False,
            'quality_score': 0.7,  # デフォルト値
            'reason': '',
            'issues': []
        }
        
        # ブランチの活動レベルをチェック
        if branch_info['task_count'] > 0:
            # タスクが関連付けられている場合は承認
            review_result['approved'] = True
            review_result['reason'] = f"{branch_info['task_count']}個のタスクが正常完了"
            
            # ブランチタイプに基づく判定
            if branch_info['type'] == 'high_quality':
                review_result['auto_merge_eligible'] = True
                review_result['quality_score'] = 0.85
            elif branch_info['type'] == 'medium_quality':
                review_result['quality_score'] = 0.75
            else:
                review_result['requires_manual_review'] = True
                review_result['issues'].append('実験的ブランチのため手動確認が必要')
        
        else:
            review_result['reason'] = 'タスクの関連付けなし、または活動なし'
            review_result['issues'].append('空のブランチ')
        
        return review_result
    
    async def _notify_decision_callbacks(self, decision: QualityDecision, task: Task):
        """決定コールバックを通知"""
        for callback in self.decision_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(decision, task)
                else:
                    callback(decision, task)
            except Exception as e:
                logger.error(f"決定コールバックエラー: {e}")
    
    def _update_controller_stats(self, quality_tier: QualityTier, success: bool):
        """コントローラー統計を更新"""
        self.controller_stats['tasks_processed'] += 1
        
        if success:
            if quality_tier == QualityTier.HIGH:
                self.controller_stats['high_quality_auto_applied'] += 1
            elif quality_tier == QualityTier.MEDIUM:
                self.controller_stats['medium_quality_parallel'] += 1
            elif quality_tier == QualityTier.LOW:
                self.controller_stats['low_quality_experimental'] += 1
        else:
            self.controller_stats['failed_tasks'] += 1
    
    def add_quality_callback(self, callback: Callable):
        """品質コールバックを追加"""
        self.quality_callbacks.append(callback)
    
    def add_decision_callback(self, callback: Callable):
        """決定コールバックを追加"""
        self.decision_callbacks.append(callback)
    
    def get_controller_status(self) -> Dict[str, Any]:
        """コントローラーの状態を取得"""
        recent_quality = []
        if len(self.quality_history) > 0:
            recent_quality = [q.overall_score for q in self.quality_history[-10:]]
        
        return {
            'controller_active': True,
            'quality_thresholds': {
                'high': self.high_quality_threshold,
                'medium': self.medium_quality_threshold,
                'auto_apply': self.auto_apply_threshold
            },
            'current_executions': len(self.active_executions),
            'pending_reviews': len(self.pending_reviews),
            'statistics': self.controller_stats,
            'recent_quality_trend': {
                'scores': recent_quality,
                'average': sum(recent_quality) / len(recent_quality) if recent_quality else 0.0,
                'improving': len(recent_quality) >= 5 and recent_quality[-1] > recent_quality[0]
            },
            'recommendations': self.get_quality_recommendations()
        }