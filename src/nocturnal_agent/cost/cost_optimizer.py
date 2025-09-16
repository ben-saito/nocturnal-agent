"""無料優先戦略とコスト最適化システムの実装"""

import logging
from datetime import datetime, date
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum

from nocturnal_agent.cost.usage_tracker import UsageTracker, ServiceType
from nocturnal_agent.core.models import Task, AgentType

logger = logging.getLogger(__name__)


class PriorityLevel(Enum):
    """優先度レベル"""
    FREE_ONLY = "free_only"          # 無料ツールのみ使用
    FREE_PREFERRED = "free_preferred" # 無料ツール優先、必要時に有料
    BALANCED = "balanced"             # バランス重視
    PERFORMANCE = "performance"       # パフォーマンス重視
    UNLIMITED = "unlimited"           # 制限なし


@dataclass
class CostEstimate:
    """コスト見積もり"""
    estimated_cost: float
    confidence: float  # 0.0-1.0
    service_breakdown: Dict[str, float] = field(default_factory=dict)
    token_estimate: int = 0
    time_estimate: float = 0.0  # seconds
    alternatives: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class OptimizationRule:
    """最適化ルール"""
    rule_id: str
    name: str
    description: str
    condition: Callable[[Dict[str, Any]], bool]
    action: Callable[[Dict[str, Any]], Dict[str, Any]]
    priority: int = 0
    enabled: bool = True


class CostOptimizer:
    """コスト最適化システム"""
    
    def __init__(self, usage_tracker: UsageTracker, config: Dict[str, Any]):
        """
        コスト最適化システムを初期化
        
        Args:
            usage_tracker: 使用量追跡システム
            config: 最適化設定
                - free_tool_target_rate: 無料ツール目標使用率（デフォルト0.9）
                - cost_thresholds: コスト閾値設定
                - optimization_rules: カスタム最適化ルール
        """
        self.usage_tracker = usage_tracker
        self.free_tool_target_rate = config.get('free_tool_target_rate', 0.9)
        self.cost_thresholds = config.get('cost_thresholds', {
            'daily_warning': 0.5,    # 日次予算の50%で警告
            'monthly_critical': 0.95  # 月次予算の95%で緊急モード
        })
        
        # サービス別コスト単価（概算値、実際のAPIによって調整が必要）
        self.service_costs = config.get('service_costs', {
            ServiceType.OPENAI_API.value: {
                'chat_completion_per_1k_tokens': 0.002,  # GPT-4o基準
                'embedding_per_1k_tokens': 0.0001
            },
            ServiceType.CLAUDE_API.value: {
                'chat_completion_per_1k_tokens': 0.003,  # Claude-3 Opus基準
                'analysis_per_1k_tokens': 0.003
            },
            ServiceType.LOCAL_LLM.value: {
                'chat_completion_per_1k_tokens': 0.0,  # ローカル実行なので無料
                'analysis_per_1k_tokens': 0.0
            },
            ServiceType.GITHUB_API.value: {
                'api_request': 0.0,  # 基本使用量は無料
                'search_request': 0.0
            }
        })
        
        # 最適化ルール
        self.optimization_rules: List[OptimizationRule] = []
        self._initialize_default_rules()
        self._load_custom_rules(config.get('optimization_rules', []))
        
        # 統計
        self.optimizer_stats = {
            'optimizations_performed': 0,
            'cost_saved': 0.0,
            'free_tool_selections': 0,
            'paid_tool_selections': 0,
            'rules_applied': {}
        }
    
    def optimize_task_execution(self, task: Task, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        タスク実行の最適化を行う
        
        Args:
            task: 実行対象タスク
            context: 実行コンテキスト（予定されるオペレーション、データサイズなど）
            
        Returns:
            最適化された実行プラン
        """
        logger.debug(f"タスクの実行最適化開始: {task.id}")
        
        # 現在の予算状況を確認
        budget_status = self.usage_tracker.get_budget_status()
        
        # 優先度レベルを決定
        priority_level = self._determine_priority_level(budget_status, context)
        
        # 利用可能なサービスオプションを評価
        service_options = self._evaluate_service_options(task, context, priority_level)
        
        # 最適化ルールを適用
        optimized_plan = self._apply_optimization_rules({
            'task': task,
            'context': context,
            'budget_status': budget_status,
            'priority_level': priority_level,
            'service_options': service_options
        })
        
        # selected_serviceが設定されていない場合は、デフォルトを選択
        if not optimized_plan.get('selected_service') and service_options:
            # 優先度レベルに応じてデフォルト選択
            if priority_level in [PriorityLevel.FREE_ONLY, PriorityLevel.FREE_PREFERRED]:
                free_options = [opt for opt in service_options if opt['cost_estimate'] == 0.0]
                if free_options:
                    optimized_plan['selected_service'] = free_options[0]['service']
                    optimized_plan['selected_agent'] = free_options[0]['agent_type']
                else:
                    optimized_plan['selected_service'] = service_options[0]['service']
                    optimized_plan['selected_agent'] = service_options[0]['agent_type']
            else:
                # パフォーマンス重視の場合は最高性能を選択
                best_option = max(service_options, key=lambda x: x['performance_score'])
                optimized_plan['selected_service'] = best_option['service']
                optimized_plan['selected_agent'] = best_option['agent_type']
        
        # コスト見積もりを生成
        cost_estimate = self._generate_cost_estimate(optimized_plan)
        
        # 統計を更新
        self._update_optimizer_stats(optimized_plan, cost_estimate)
        
        result = {
            'optimized_plan': optimized_plan,
            'cost_estimate': cost_estimate,
            'priority_level': priority_level.value,
            'budget_status': budget_status,
            'recommendations': self._generate_recommendations(
                optimized_plan, budget_status, priority_level
            )
        }
        
        logger.debug(f"最適化完了 - 推定コスト: ${cost_estimate.estimated_cost:.4f}")
        return result
    
    def suggest_alternatives(self, current_plan: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        現在のプランに対する代替案を提案
        
        Args:
            current_plan: 現在の実行プラン
            
        Returns:
            代替案のリスト
        """
        alternatives = []
        
        # 無料ツール優先の代替案
        if current_plan.get('primary_service') != ServiceType.LOCAL_LLM:
            free_alternative = self._create_free_alternative(current_plan)
            if free_alternative:
                alternatives.append(free_alternative)
        
        # パフォーマンス重視の代替案
        performance_alternative = self._create_performance_alternative(current_plan)
        if performance_alternative:
            alternatives.append(performance_alternative)
        
        # バランス重視の代替案
        balanced_alternative = self._create_balanced_alternative(current_plan)
        if balanced_alternative:
            alternatives.append(balanced_alternative)
        
        return alternatives
    
    def get_optimization_recommendations(self) -> List[Dict[str, Any]]:
        """最適化推奨事項を取得"""
        recommendations = []
        
        # 予算状況に基づく推奨
        budget_status = self.usage_tracker.get_budget_status()
        
        if budget_status['budget_utilization'] > 0.8:
            recommendations.append({
                'type': 'budget_warning',
                'priority': 'high',
                'title': '予算使用量が80%を超過',
                'description': '無料ツールの使用を優先してください',
                'actions': ['無料ツール使用率の向上', 'コスト効率の高いオペレーションの選択']
            })
        
        # 無料ツール使用率に基づく推奨
        current_month = self.usage_tracker.get_current_month_usage()
        if current_month.free_tool_usage_rate < self.free_tool_target_rate:
            gap = self.free_tool_target_rate - current_month.free_tool_usage_rate
            recommendations.append({
                'type': 'free_tool_usage',
                'priority': 'medium',
                'title': f'無料ツール使用率が目標を下回る',
                'description': f'現在: {current_month.free_tool_usage_rate:.1%}, 目標: {self.free_tool_target_rate:.1%}',
                'actions': [
                    'ローカルLLMの活用を増やす',
                    'GitHub APIやローカルツールの優先使用'
                ]
            })
        
        # サービス別使用量に基づく推奨
        service_breakdown = self.usage_tracker.get_service_breakdown()
        high_cost_services = [(k, v) for k, v in service_breakdown.items() if v > 1.0]
        
        if high_cost_services:
            recommendations.append({
                'type': 'service_optimization',
                'priority': 'medium',
                'title': 'コストの高いサービス使用を検出',
                'description': f'高コストサービス: {", ".join([s[0] for s in high_cost_services])}',
                'actions': [
                    '代替サービスの検討',
                    'バッチ処理による効率化'
                ]
            })
        
        return recommendations
    
    def _determine_priority_level(self, budget_status: Dict[str, Any], context: Dict[str, Any]) -> PriorityLevel:
        """優先度レベルを決定"""
        budget_util = budget_status['budget_utilization']
        free_rate = budget_status['free_tool_usage_rate']
        
        # 予算が95%以上使用済みの場合は無料のみ
        if budget_util >= 0.95:
            return PriorityLevel.FREE_ONLY
        
        # 予算が80%以上使用済みの場合は無料優先
        if budget_util >= 0.8:
            return PriorityLevel.FREE_PREFERRED
        
        # 無料ツール使用率が目標を大幅に下回る場合
        if free_rate < self.free_tool_target_rate - 0.1:
            return PriorityLevel.FREE_PREFERRED
        
        # タスクが緊急性を持つ場合
        if context.get('urgency') == 'high' or context.get('quality_requirement') == 'high':
            return PriorityLevel.PERFORMANCE
        
        # デフォルトはバランス
        return PriorityLevel.BALANCED
    
    def _evaluate_service_options(self, task: Task, context: Dict[str, Any], 
                                priority_level: PriorityLevel) -> List[Dict[str, Any]]:
        """利用可能なサービスオプションを評価"""
        options = []
        
        # ローカルLLMオプション（無料）
        local_option = {
            'service': ServiceType.LOCAL_LLM,
            'agent_type': AgentType.LOCAL_LLM,
            'cost_estimate': 0.0,
            'performance_score': 0.7,  # 一般的にクラウドLLMより劣る
            'availability_score': 0.9,
            'suitable_for': ['code_generation', 'text_analysis', 'simple_tasks']
        }
        options.append(local_option)
        
        # 有料オプションは優先度レベルに応じて追加
        if priority_level not in [PriorityLevel.FREE_ONLY]:
            # Claude APIオプション
            claude_option = {
                'service': ServiceType.CLAUDE_API,
                'agent_type': AgentType.CLAUDE_CODE,
                'cost_estimate': self._estimate_api_cost(ServiceType.CLAUDE_API, context),
                'performance_score': 0.95,
                'availability_score': 0.95,
                'suitable_for': ['complex_analysis', 'code_review', 'architecture_design']
            }
            options.append(claude_option)
            
            # OpenAI APIオプション
            openai_option = {
                'service': ServiceType.OPENAI_API,
                'agent_type': AgentType.OPENAI_CODEX,
                'cost_estimate': self._estimate_api_cost(ServiceType.OPENAI_API, context),
                'performance_score': 0.92,
                'availability_score': 0.98,
                'suitable_for': ['chat_completion', 'embedding', 'fine_tuning_tasks']
            }
            options.append(openai_option)
        
        # 優先度レベルに基づいてオプションをフィルタリング
        if priority_level == PriorityLevel.FREE_ONLY:
            options = [opt for opt in options if opt['cost_estimate'] == 0.0]
        elif priority_level == PriorityLevel.FREE_PREFERRED:
            # 無料オプションを先頭に移動
            options.sort(key=lambda x: (x['cost_estimate'] > 0, x['cost_estimate']))
        
        return options
    
    def _estimate_api_cost(self, service: ServiceType, context: Dict[str, Any]) -> float:
        """API使用コストを見積もり"""
        estimated_tokens = context.get('estimated_tokens', 1000)  # デフォルト1000トークン
        operation_type = context.get('operation_type', 'chat_completion')
        
        service_config = self.service_costs.get(service.value, {})
        cost_per_1k = service_config.get(f'{operation_type}_per_1k_tokens', 0.002)
        
        return (estimated_tokens / 1000) * cost_per_1k
    
    def _apply_optimization_rules(self, optimization_context: Dict[str, Any]) -> Dict[str, Any]:
        """最適化ルールを適用"""
        context = optimization_context.copy()
        
        # 有効なルールを優先度順でソート
        active_rules = [rule for rule in self.optimization_rules if rule.enabled]
        active_rules.sort(key=lambda x: x.priority, reverse=True)
        
        for rule in active_rules:
            try:
                if rule.condition(context):
                    logger.debug(f"最適化ルール適用: {rule.name}")
                    context = rule.action(context)
                    
                    # 統計を更新
                    rule_name = rule.rule_id
                    self.optimizer_stats['rules_applied'][rule_name] = (
                        self.optimizer_stats['rules_applied'].get(rule_name, 0) + 1
                    )
                    
            except Exception as e:
                logger.warning(f"最適化ルール実行エラー ({rule.name}): {e}")
        
        return context
    
    def _generate_cost_estimate(self, optimized_plan: Dict[str, Any]) -> CostEstimate:
        """コスト見積もりを生成"""
        service_options = optimized_plan.get('service_options', [])
        selected_service = optimized_plan.get('selected_service')
        
        if not selected_service:
            return CostEstimate(estimated_cost=0.0, confidence=0.0)
        
        # 選択されたサービスのコスト見積もりを取得
        for option in service_options:
            if option['service'] == selected_service:
                return CostEstimate(
                    estimated_cost=option['cost_estimate'],
                    confidence=0.8,  # 見積もり精度
                    service_breakdown={selected_service.value: option['cost_estimate']},
                    token_estimate=optimized_plan.get('context', {}).get('estimated_tokens', 0),
                    time_estimate=optimized_plan.get('estimated_time', 0.0)
                )
        
        return CostEstimate(estimated_cost=0.0, confidence=0.0)
    
    def _initialize_default_rules(self):
        """デフォルト最適化ルールを初期化"""
        
        # ルール1: 予算制限時は無料ツール強制
        def budget_limit_condition(context: Dict[str, Any]) -> bool:
            budget_status = context.get('budget_status', {})
            return budget_status.get('budget_utilization', 0) >= 0.95
        
        def budget_limit_action(context: Dict[str, Any]) -> Dict[str, Any]:
            # 無料サービスのみを選択
            service_options = context.get('service_options', [])
            free_options = [opt for opt in service_options if opt['cost_estimate'] == 0.0]
            
            if free_options:
                context['selected_service'] = free_options[0]['service']
                context['selected_agent'] = free_options[0]['agent_type']
            
            return context
        
        self.optimization_rules.append(OptimizationRule(
            rule_id="budget_limit_free_only",
            name="予算制限時無料ツール強制",
            description="予算使用量が95%を超えた場合、無料ツールのみ使用",
            condition=budget_limit_condition,
            action=budget_limit_action,
            priority=100
        ))
        
        # ルール2: 無料ツール使用率向上
        def free_rate_condition(context: Dict[str, Any]) -> bool:
            budget_status = context.get('budget_status', {})
            return budget_status.get('free_tool_usage_rate', 1.0) < self.free_tool_target_rate
        
        def free_rate_action(context: Dict[str, Any]) -> Dict[str, Any]:
            service_options = context.get('service_options', [])
            free_options = [opt for opt in service_options if opt['cost_estimate'] == 0.0]
            
            if free_options and context.get('priority_level') != PriorityLevel.PERFORMANCE:
                context['selected_service'] = free_options[0]['service']
                context['selected_agent'] = free_options[0]['agent_type']
            
            return context
        
        self.optimization_rules.append(OptimizationRule(
            rule_id="improve_free_rate",
            name="無料ツール使用率向上",
            description="無料ツール使用率が目標を下回る場合、無料ツールを優先選択",
            condition=free_rate_condition,
            action=free_rate_action,
            priority=80
        ))
        
        # ルール3: パフォーマンス重視時の最適化
        def performance_condition(context: Dict[str, Any]) -> bool:
            return context.get('priority_level') == PriorityLevel.PERFORMANCE
        
        def performance_action(context: Dict[str, Any]) -> Dict[str, Any]:
            service_options = context.get('service_options', [])
            # パフォーマンススコアで選択
            best_option = max(service_options, key=lambda x: x['performance_score'])
            context['selected_service'] = best_option['service']
            context['selected_agent'] = best_option['agent_type']
            return context
        
        self.optimization_rules.append(OptimizationRule(
            rule_id="performance_optimization",
            name="パフォーマンス最適化",
            description="パフォーマンス重視時は最高性能のサービスを選択",
            condition=performance_condition,
            action=performance_action,
            priority=90
        ))
    
    def _load_custom_rules(self, custom_rules: List[Dict[str, Any]]):
        """カスタム最適化ルールを読み込み"""
        # 実装は将来の拡張のためのプレースホルダー
        logger.debug(f"カスタムルール {len(custom_rules)} 件をスキップ（未実装）")
    
    def _generate_recommendations(self, plan: Dict[str, Any], 
                                budget_status: Dict[str, Any], 
                                priority_level: PriorityLevel) -> List[str]:
        """推奨事項を生成"""
        recommendations = []
        
        selected_service = plan.get('selected_service')
        
        if selected_service == ServiceType.LOCAL_LLM:
            recommendations.append("ローカルLLMを使用してコストを節約")
        elif budget_status.get('budget_utilization', 0) > 0.5:
            recommendations.append("予算の50%以上を使用済み - 無料ツールの活用を検討")
        
        if priority_level == PriorityLevel.FREE_ONLY:
            recommendations.append("予算制限により無料ツールのみ使用可能")
        
        return recommendations
    
    def _create_free_alternative(self, current_plan: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """無料代替案を作成"""
        return {
            'name': '無料ツール代替案',
            'service': ServiceType.LOCAL_LLM,
            'estimated_cost': 0.0,
            'trade_offs': ['処理性能の低下', '実行時間の増加'],
            'benefits': ['コスト削減', '予算枠の節約']
        }
    
    def _create_performance_alternative(self, current_plan: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """パフォーマンス代替案を作成"""
        return {
            'name': 'パフォーマンス重視代替案', 
            'service': ServiceType.CLAUDE_API,
            'estimated_cost': 0.05,  # 概算
            'trade_offs': ['コスト増加'],
            'benefits': ['高品質な結果', '実行時間の短縮', '高い成功率']
        }
    
    def _create_balanced_alternative(self, current_plan: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """バランス代替案を作成"""
        return {
            'name': 'バランス重視代替案',
            'service': ServiceType.OPENAI_API,
            'estimated_cost': 0.03,  # 概算
            'trade_offs': ['中程度のコスト'],
            'benefits': ['良好なパフォーマンス', '適度なコスト', '安定した可用性']
        }
    
    def _update_optimizer_stats(self, plan: Dict[str, Any], estimate: CostEstimate):
        """最適化統計を更新"""
        self.optimizer_stats['optimizations_performed'] += 1
        
        selected_service = plan.get('selected_service')
        if selected_service == ServiceType.LOCAL_LLM:
            self.optimizer_stats['free_tool_selections'] += 1
        else:
            self.optimizer_stats['paid_tool_selections'] += 1
    
    def get_optimizer_status(self) -> Dict[str, Any]:
        """最適化システムの状態を取得"""
        budget_status = self.usage_tracker.get_budget_status()
        current_month = self.usage_tracker.get_current_month_usage()
        
        return {
            'optimizer_active': True,
            'free_tool_target_rate': self.free_tool_target_rate,
            'current_free_tool_rate': current_month.free_tool_usage_rate,
            'budget_status': budget_status,
            'optimization_statistics': self.optimizer_stats,
            'active_rules': len([r for r in self.optimization_rules if r.enabled]),
            'cost_thresholds': self.cost_thresholds,
            'recommendations': self.get_optimization_recommendations()
        }