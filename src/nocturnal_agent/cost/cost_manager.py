"""コスト管理システムの統合コーディネーター"""

import logging
import asyncio
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Any, Callable
from pathlib import Path

from nocturnal_agent.cost.usage_tracker import UsageTracker, ServiceType, UsageRecord
from nocturnal_agent.cost.cost_optimizer import CostOptimizer, PriorityLevel, CostEstimate
from nocturnal_agent.core.models import Task, ExecutionResult

logger = logging.getLogger(__name__)


class CostManager:
    """コスト管理システムの統合管理"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        コスト管理システムを初期化
        
        Args:
            config: コスト管理設定
                - monthly_budget: 月額予算（USD）
                - storage_path: データ保存パス
                - alert_settings: アラート設定
                - optimization_settings: 最適化設定
        """
        self.config = config
        self.monthly_budget = config.get('monthly_budget', 10.0)
        
        # 使用量追跡システムを初期化
        tracker_config = {
            'storage_path': config.get('storage_path', './data/cost'),
            'monthly_budget': self.monthly_budget,
            'alert_thresholds': config.get('alert_thresholds', [0.5, 0.8, 0.9, 0.95]),
            'free_tools': config.get('free_tools', [
                ServiceType.LOCAL_LLM.value,
                ServiceType.GITHUB_API.value
            ])
        }
        
        self.usage_tracker = UsageTracker(tracker_config)
        
        # コスト最適化システムを初期化
        optimizer_config = {
            'free_tool_target_rate': config.get('free_tool_target_rate', 0.9),
            'cost_thresholds': config.get('cost_thresholds', {
                'daily_warning': 0.5,
                'monthly_critical': 0.95
            }),
            'service_costs': config.get('service_costs', {}),
            'optimization_rules': config.get('optimization_rules', [])
        }
        
        self.cost_optimizer = CostOptimizer(self.usage_tracker, optimizer_config)
        
        # アラート設定
        self.alert_enabled = config.get('alert_enabled', True)
        self.alert_callbacks: List[Callable] = []
        
        # コスト管理状態
        self.cost_management_active = True
        self.emergency_mode = False  # 予算超過時の緊急モード
        
        # 統計
        self.manager_stats = {
            'session_start': datetime.now(),
            'tasks_optimized': 0,
            'cost_savings_achieved': 0.0,
            'emergency_activations': 0,
            'alerts_sent': 0
        }
        
        # アラートコールバックを設定
        if self.alert_enabled:
            self.usage_tracker.add_alert_callback(self._handle_usage_alert)
    
    async def optimize_task_execution(self, task: Task, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        タスク実行の最適化
        
        Args:
            task: 実行対象タスク
            context: 実行コンテキスト
            
        Returns:
            最適化結果とコスト情報
        """
        logger.debug(f"タスクコスト最適化開始: {task.id}")
        
        try:
            # 緊急モードチェック
            if self.emergency_mode:
                context['emergency_mode'] = True
                context['force_free_only'] = True
            
            # コスト最適化を実行
            optimization_result = self.cost_optimizer.optimize_task_execution(task, context)
            
            # 最適化統計を更新
            self.manager_stats['tasks_optimized'] += 1
            
            # 推定コスト節約を計算
            estimated_savings = self._calculate_potential_savings(optimization_result)
            if estimated_savings > 0:
                self.manager_stats['cost_savings_achieved'] += estimated_savings
            
            logger.debug(f"最適化完了 - 推定コスト: ${optimization_result['cost_estimate'].estimated_cost:.4f}")
            return optimization_result
            
        except Exception as e:
            logger.error(f"タスク最適化エラー: {e}")
            # エラー時は安全な設定にフォールバック
            return self._create_fallback_plan(task, context)
    
    async def record_task_execution(self, task: Task, result: ExecutionResult, 
                                  optimization_data: Optional[Dict[str, Any]] = None) -> bool:
        """
        タスク実行結果を記録
        
        Args:
            task: 実行されたタスク
            result: 実行結果
            optimization_data: 最適化時のデータ
            
        Returns:
            記録成功フラグ
        """
        try:
            # 実際のコストを算出（API使用量から）
            actual_cost = self._calculate_actual_cost(result, optimization_data)
            
            # サービス種別を決定
            service_type = self._determine_service_type(result, optimization_data)
            
            # 使用量を記録
            success = self.usage_tracker.record_usage(
                service_type=service_type,
                operation_type=self._get_operation_type(task, result),
                cost=actual_cost,
                tokens_used=getattr(result, 'tokens_used', 0),
                task_id=task.id,
                agent_type=result.agent_used.value if result.agent_used else None,
                metadata={
                    'task_description': task.description[:100],
                    'execution_time': result.execution_time,
                    'success': result.success,
                    'files_modified': len(result.files_modified),
                    'optimization_applied': optimization_data is not None
                }
            )
            
            # 緊急モードの状態をチェック
            await self._check_emergency_mode()
            
            logger.debug(f"実行結果記録完了: {task.id} - ${actual_cost:.4f}")
            return success
            
        except Exception as e:
            logger.error(f"実行結果記録エラー: {e}")
            return False
    
    def get_cost_dashboard(self) -> Dict[str, Any]:
        """コスト管理ダッシュボード情報を取得"""
        budget_status = self.usage_tracker.get_budget_status()
        current_month = self.usage_tracker.get_current_month_usage()
        optimizer_status = self.cost_optimizer.get_optimizer_status()
        
        # トレンド情報
        usage_trends = self.usage_tracker.get_usage_trends(days=30)
        service_breakdown = self.usage_tracker.get_service_breakdown(days=30)
        
        # 推奨事項
        recommendations = self.cost_optimizer.get_optimization_recommendations()
        
        return {
            'budget_overview': {
                'monthly_budget': self.monthly_budget,
                'current_spend': current_month.total_cost,
                'remaining_budget': budget_status['remaining_budget'],
                'utilization_percentage': budget_status['budget_utilization'] * 100,
                'days_remaining': budget_status['days_remaining'],
                'daily_budget_remaining': budget_status['daily_budget_remaining'],
                'on_track': budget_status['on_track']
            },
            'usage_summary': {
                'total_requests_this_month': current_month.total_requests,
                'total_tokens_this_month': current_month.total_tokens,
                'free_tool_usage_rate': current_month.free_tool_usage_rate * 100,
                'free_tool_target_rate': optimizer_status['free_tool_target_rate'] * 100,
                'alert_status': budget_status['alert_status']
            },
            'trends': {
                'daily_costs': usage_trends['costs'][-7:],  # 過去7日
                'daily_dates': usage_trends['dates'][-7:],
                'service_breakdown': service_breakdown,
                'cost_trend': self._calculate_cost_trend(usage_trends['costs'])
            },
            'optimization': {
                'tasks_optimized': self.manager_stats['tasks_optimized'],
                'cost_savings_achieved': self.manager_stats['cost_savings_achieved'],
                'free_tool_selections': optimizer_status['optimization_statistics']['free_tool_selections'],
                'paid_tool_selections': optimizer_status['optimization_statistics']['paid_tool_selections']
            },
            'recommendations': recommendations,
            'system_status': {
                'cost_management_active': self.cost_management_active,
                'emergency_mode': self.emergency_mode,
                'alerts_enabled': self.alert_enabled,
                'session_duration': str(datetime.now() - self.manager_stats['session_start'])
            }
        }
    
    def get_detailed_usage_report(self, days: int = 30) -> Dict[str, Any]:
        """詳細な使用量レポートを生成"""
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        
        usage_data = self.usage_tracker.get_usage_by_date_range(start_date, end_date)
        service_breakdown = self.usage_tracker.get_service_breakdown(days)
        
        # 詳細分析
        analysis = {
            'total_cost': sum(day.total_cost for day in usage_data.values()),
            'total_requests': sum(day.total_requests for day in usage_data.values()),
            'total_tokens': sum(day.total_tokens for day in usage_data.values()),
            'average_daily_cost': 0.0,
            'peak_usage_day': None,
            'service_efficiency': {},
            'cost_per_task': 0.0
        }
        
        if usage_data:
            analysis['average_daily_cost'] = analysis['total_cost'] / len(usage_data)
            
            # ピーク使用日を特定
            peak_day = max(usage_data.items(), key=lambda x: x[1].total_cost)
            analysis['peak_usage_day'] = {
                'date': peak_day[0],
                'cost': peak_day[1].total_cost,
                'requests': peak_day[1].total_requests
            }
            
            # サービス効率性分析
            for service, cost in service_breakdown.items():
                requests = sum(
                    len([r for r in day.records if r.service_type.value == service])
                    for day in usage_data.values()
                )
                analysis['service_efficiency'][service] = {
                    'total_cost': cost,
                    'total_requests': requests,
                    'cost_per_request': cost / requests if requests > 0 else 0.0
                }
            
            # タスクあたりのコスト
            if self.manager_stats['tasks_optimized'] > 0:
                analysis['cost_per_task'] = analysis['total_cost'] / self.manager_stats['tasks_optimized']
        
        return {
            'report_period': {'start': str(start_date), 'end': str(end_date)},
            'summary': analysis,
            'daily_breakdown': {
                date_str: {
                    'cost': day.total_cost,
                    'requests': day.total_requests,
                    'tokens': day.total_tokens,
                    'services': day.service_breakdown
                }
                for date_str, day in usage_data.items()
            },
            'service_breakdown': service_breakdown,
            'recommendations': self._generate_usage_recommendations(analysis, service_breakdown)
        }
    
    def add_alert_callback(self, callback: Callable):
        """アラートコールバックを追加"""
        self.alert_callbacks.append(callback)
    
    async def _handle_usage_alert(self, alert_data: Dict[str, Any]):
        """使用量アラートを処理"""
        logger.warning(f"コスト使用量アラート: {alert_data['threshold']*100:.0f}%到達")
        
        # 緊急モードの検討
        if alert_data['threshold'] >= 0.95:
            await self._activate_emergency_mode("予算95%超過のため緊急モードを有効化")
        
        # アラートコールバックを実行
        for callback in self.alert_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback('budget_alert', alert_data)
                else:
                    callback('budget_alert', alert_data)
            except Exception as e:
                logger.error(f"アラートコールバック実行エラー: {e}")
        
        self.manager_stats['alerts_sent'] += 1
    
    async def _check_emergency_mode(self):
        """緊急モードの必要性をチェック"""
        budget_status = self.usage_tracker.get_budget_status()
        
        if (budget_status['budget_utilization'] >= 0.98 and not self.emergency_mode):
            await self._activate_emergency_mode("予算98%超過")
        elif (budget_status['budget_utilization'] < 0.95 and self.emergency_mode):
            await self._deactivate_emergency_mode("予算使用量が95%を下回った")
    
    async def _activate_emergency_mode(self, reason: str):
        """緊急モードを有効化"""
        logger.critical(f"コスト管理緊急モード有効化: {reason}")
        
        self.emergency_mode = True
        self.manager_stats['emergency_activations'] += 1
        
        # 緊急モードアラートを送信
        alert_data = {
            'type': 'emergency_mode_activated',
            'reason': reason,
            'timestamp': datetime.now().isoformat(),
            'budget_status': self.usage_tracker.get_budget_status()
        }
        
        for callback in self.alert_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback('emergency_mode', alert_data)
                else:
                    callback('emergency_mode', alert_data)
            except Exception as e:
                logger.error(f"緊急モードアラートコールバック実行エラー: {e}")
    
    async def _deactivate_emergency_mode(self, reason: str):
        """緊急モードを無効化"""
        logger.info(f"コスト管理緊急モード解除: {reason}")
        
        self.emergency_mode = False
        
        # 緊急モード解除アラートを送信
        alert_data = {
            'type': 'emergency_mode_deactivated',
            'reason': reason,
            'timestamp': datetime.now().isoformat(),
            'budget_status': self.usage_tracker.get_budget_status()
        }
        
        for callback in self.alert_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback('emergency_mode_deactivated', alert_data)
                else:
                    callback('emergency_mode_deactivated', alert_data)
            except Exception as e:
                logger.error(f"緊急モード解除アラートコールバック実行エラー: {e}")
    
    def _calculate_actual_cost(self, result: ExecutionResult, 
                             optimization_data: Optional[Dict[str, Any]]) -> float:
        """実際のコストを算出"""
        # API呼び出し数とコストから実コストを算出
        api_cost = result.cost_incurred if hasattr(result, 'cost_incurred') else 0.0
        
        # 最適化データがある場合は、推定との差異を記録
        if optimization_data and 'cost_estimate' in optimization_data:
            estimated = optimization_data['cost_estimate'].estimated_cost
            if abs(api_cost - estimated) > 0.001:  # 差異が0.1セント以上の場合
                logger.debug(f"コスト見積もり差異: 推定${estimated:.4f} vs 実際${api_cost:.4f}")
        
        return api_cost
    
    def _determine_service_type(self, result: ExecutionResult, 
                               optimization_data: Optional[Dict[str, Any]]) -> ServiceType:
        """使用されたサービス種別を決定"""
        if optimization_data and 'optimized_plan' in optimization_data:
            selected_service = optimization_data['optimized_plan'].get('selected_service')
            if selected_service:
                return selected_service
        
        # ExecutionResultのagent_usedから推定
        if result.agent_used:
            agent_type = result.agent_used.value
            if 'local' in agent_type.lower():
                return ServiceType.LOCAL_LLM
            elif 'claude' in agent_type.lower():
                return ServiceType.CLAUDE_API
            elif 'openai' in agent_type.lower() or 'gpt' in agent_type.lower():
                return ServiceType.OPENAI_API
        
        # デフォルト
        return ServiceType.LOCAL_LLM
    
    def _get_operation_type(self, task: Task, result: ExecutionResult) -> str:
        """操作種別を決定"""
        if task.description:
            desc_lower = task.description.lower()
            if 'review' in desc_lower or 'analyze' in desc_lower:
                return 'code_analysis'
            elif 'generate' in desc_lower or 'create' in desc_lower:
                return 'code_generation'
            elif 'test' in desc_lower:
                return 'test_generation'
            elif 'refactor' in desc_lower:
                return 'code_refactoring'
        
        return 'general_task'
    
    def _calculate_potential_savings(self, optimization_result: Dict[str, Any]) -> float:
        """潜在的なコスト節約を計算"""
        selected_cost = optimization_result.get('cost_estimate', {}).estimated_cost or 0.0
        
        # 最も高価な代替案と比較
        alternatives = optimization_result.get('cost_estimate', {}).alternatives or []
        if alternatives:
            max_alternative_cost = max(alt.get('estimated_cost', 0.0) for alt in alternatives)
            return max(0.0, max_alternative_cost - selected_cost)
        
        return 0.0
    
    def _create_fallback_plan(self, task: Task, context: Dict[str, Any]) -> Dict[str, Any]:
        """エラー時のフォールバックプランを作成"""
        return {
            'optimized_plan': {
                'selected_service': ServiceType.LOCAL_LLM,
                'selected_agent': 'LOCAL_LLM',
                'fallback': True
            },
            'cost_estimate': CostEstimate(
                estimated_cost=0.0,
                confidence=1.0  # 無料なので確実
            ),
            'priority_level': PriorityLevel.FREE_ONLY.value,
            'budget_status': self.usage_tracker.get_budget_status(),
            'recommendations': ['エラーによりローカルLLMにフォールバック']
        }
    
    def _calculate_cost_trend(self, costs: List[float]) -> str:
        """コストトレンドを計算"""
        if len(costs) < 7:
            return "insufficient_data"
        
        recent_avg = sum(costs[-3:]) / 3  # 直近3日平均
        previous_avg = sum(costs[-7:-3]) / 4  # その前4日平均
        
        if recent_avg > previous_avg * 1.2:
            return "increasing"
        elif recent_avg < previous_avg * 0.8:
            return "decreasing"
        else:
            return "stable"
    
    def _generate_usage_recommendations(self, analysis: Dict[str, Any], 
                                      service_breakdown: Dict[str, float]) -> List[str]:
        """使用量分析に基づく推奨事項を生成"""
        recommendations = []
        
        # 高コストサービスの特定
        total_cost = analysis['total_cost']
        if total_cost > 0:
            high_cost_services = [
                service for service, cost in service_breakdown.items()
                if cost / total_cost > 0.3  # 30%以上のコスト占有
            ]
            
            if high_cost_services:
                recommendations.append(
                    f"高コストサービス（{', '.join(high_cost_services)}）の使用量削減を検討"
                )
        
        # サービス効率性の分析
        inefficient_services = []
        for service, metrics in analysis.get('service_efficiency', {}).items():
            if metrics['cost_per_request'] > 0.01:  # 1リクエスト1セント以上
                inefficient_services.append(service)
        
        if inefficient_services:
            recommendations.append(
                f"コスト効率の低いサービス（{', '.join(inefficient_services)}）の最適化を検討"
            )
        
        # タスクあたりコストの評価
        cost_per_task = analysis.get('cost_per_task', 0.0)
        if cost_per_task > 0.1:  # タスクあたり10セント以上
            recommendations.append("タスクあたりのコストが高め - バッチ処理や効率化を検討")
        
        return recommendations
    
    def get_manager_status(self) -> Dict[str, Any]:
        """コスト管理システムの状態を取得"""
        return {
            'cost_management_active': self.cost_management_active,
            'emergency_mode': self.emergency_mode,
            'monthly_budget': self.monthly_budget,
            'alert_enabled': self.alert_enabled,
            'session_info': {
                'start_time': self.manager_stats['session_start'].isoformat(),
                'tasks_optimized': self.manager_stats['tasks_optimized'],
                'cost_savings_achieved': self.manager_stats['cost_savings_achieved'],
                'emergency_activations': self.manager_stats['emergency_activations'],
                'alerts_sent': self.manager_stats['alerts_sent']
            },
            'usage_tracker_status': self.usage_tracker.get_tracker_status(),
            'optimizer_status': self.cost_optimizer.get_optimizer_status()
        }