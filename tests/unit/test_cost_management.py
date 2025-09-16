"""コスト管理システムの単体テスト"""

import pytest
import tempfile
import json
from datetime import date, datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch

from nocturnal_agent.cost.usage_tracker import (
    UsageTracker, ServiceType, UsageRecord, DayUsage, MonthUsage
)
from nocturnal_agent.cost.cost_optimizer import (
    CostOptimizer, PriorityLevel, CostEstimate
)
from nocturnal_agent.cost.cost_manager import CostManager


class TestUsageTracker:
    """使用量追跡システムのテスト"""
    
    @pytest.fixture
    def usage_tracker(self, temp_dir):
        """UsageTrackerインスタンスを提供"""
        config = {
            'storage_path': str(temp_dir / 'usage'),
            'monthly_budget': 10.0,
            'alert_thresholds': [0.5, 0.8, 0.9, 0.95],
            'free_tools': ['local_llm', 'github_api']
        }
        return UsageTracker(config)
    
    def test_usage_tracker_initialization(self, usage_tracker):
        """UsageTrackerの初期化テスト"""
        assert usage_tracker.monthly_budget == 10.0
        assert len(usage_tracker.alert_thresholds) == 4
        assert 'local_llm' in usage_tracker.free_tools
        assert usage_tracker.storage_path.exists()
    
    def test_record_usage_success(self, usage_tracker):
        """使用量記録の成功テスト"""
        success = usage_tracker.record_usage(
            service_type=ServiceType.LOCAL_LLM,
            operation_type='test_operation',
            cost=0.0,
            tokens_used=100,
            task_id='test_task_1'
        )
        
        assert success is True
        assert usage_tracker.tracker_stats['total_records'] == 1
        assert usage_tracker.tracker_stats['total_cost_tracked'] == 0.0
    
    def test_record_usage_with_cost(self, usage_tracker):
        """コスト付き使用量記録のテスト"""
        success = usage_tracker.record_usage(
            service_type=ServiceType.CLAUDE_API,
            operation_type='chat_completion',
            cost=0.05,
            tokens_used=500,
            task_id='test_task_2'
        )
        
        assert success is True
        assert usage_tracker.tracker_stats['total_cost_tracked'] == 0.05
    
    def test_get_current_month_usage(self, usage_tracker):
        """現在の月の使用量取得テスト"""
        # 使用量を記録
        usage_tracker.record_usage(
            ServiceType.LOCAL_LLM, 'test', 0.0, 100
        )
        
        month_usage = usage_tracker.get_current_month_usage()
        
        assert month_usage.year == datetime.now().year
        assert month_usage.month == datetime.now().month
        assert month_usage.total_requests >= 1
    
    def test_get_budget_status(self, usage_tracker):
        """予算状況取得のテスト"""
        # コスト付き使用量を記録
        usage_tracker.record_usage(
            ServiceType.CLAUDE_API, 'test', 2.5, 1000
        )
        
        budget_status = usage_tracker.get_budget_status()
        
        assert budget_status['monthly_budget'] == 10.0
        assert budget_status['current_spend'] == 2.5
        assert budget_status['remaining_budget'] == 7.5
        assert budget_status['budget_utilization'] == 0.25
        assert 'days_remaining' in budget_status
        assert 'alert_status' in budget_status
    
    def test_service_breakdown(self, usage_tracker):
        """サービス別使用量内訳のテスト"""
        # 複数サービスの使用量を記録
        usage_tracker.record_usage(ServiceType.LOCAL_LLM, 'test1', 0.0, 100)
        usage_tracker.record_usage(ServiceType.CLAUDE_API, 'test2', 0.05, 200)
        usage_tracker.record_usage(ServiceType.OPENAI_API, 'test3', 0.03, 150)
        
        breakdown = usage_tracker.get_service_breakdown(days=1)
        
        assert 'local_llm' in breakdown
        assert 'claude_api' in breakdown
        assert 'openai_api' in breakdown
        assert breakdown['local_llm'] == 0.0
        assert breakdown['claude_api'] == 0.05
        assert breakdown['openai_api'] == 0.03


class TestCostOptimizer:
    """コスト最適化システムのテスト"""
    
    @pytest.fixture
    def cost_optimizer(self, temp_dir):
        """CostOptimizerインスタンスを提供"""
        usage_tracker = UsageTracker({
            'storage_path': str(temp_dir / 'usage'),
            'monthly_budget': 10.0,
            'free_tools': ['local_llm']
        })
        
        config = {
            'free_tool_target_rate': 0.9,
            'cost_thresholds': {
                'daily_warning': 0.5,
                'monthly_critical': 0.95
            }
        }
        
        return CostOptimizer(usage_tracker, config)
    
    @pytest.mark.asyncio
    async def test_optimize_task_execution(self, cost_optimizer, sample_task):
        """タスク実行最適化のテスト"""
        context = {
            'estimated_tokens': 1000,
            'operation_type': 'code_generation',
            'urgency': 'medium'
        }
        
        result = cost_optimizer.optimize_task_execution(sample_task, context)
        
        assert 'optimized_plan' in result
        assert 'cost_estimate' in result
        assert 'priority_level' in result
        assert 'budget_status' in result
        assert 'recommendations' in result
        
        # コスト見積もりの確認
        cost_estimate = result['cost_estimate']
        assert hasattr(cost_estimate, 'estimated_cost')
        assert hasattr(cost_estimate, 'confidence')
    
    def test_suggest_alternatives(self, cost_optimizer):
        """代替案提案のテスト"""
        current_plan = {
            'primary_service': ServiceType.CLAUDE_API,
            'estimated_cost': 0.05
        }
        
        alternatives = cost_optimizer.suggest_alternatives(current_plan)
        
        assert len(alternatives) >= 1
        assert any(alt['name'] == '無料ツール代替案' for alt in alternatives)
        
        free_alt = next(alt for alt in alternatives if alt['name'] == '無料ツール代替案')
        assert free_alt['estimated_cost'] == 0.0
        assert 'trade_offs' in free_alt
        assert 'benefits' in free_alt
    
    def test_get_optimization_recommendations(self, cost_optimizer):
        """最適化推奨事項取得のテスト"""
        # 予算状況をシミュレート（80%使用）
        cost_optimizer.usage_tracker.record_usage(
            ServiceType.CLAUDE_API, 'test', 8.0, 5000
        )
        
        recommendations = cost_optimizer.get_optimization_recommendations()
        
        assert len(recommendations) > 0
        budget_warning = next(
            (r for r in recommendations if r['type'] == 'budget_warning'), None
        )
        assert budget_warning is not None
        assert budget_warning['priority'] == 'high'


class TestCostManager:
    """コスト管理統合システムのテスト"""
    
    @pytest.fixture
    def cost_manager(self, temp_dir):
        """CostManagerインスタンスを提供"""
        config = {
            'monthly_budget': 10.0,
            'storage_path': str(temp_dir / 'cost'),
            'free_tool_target_rate': 0.9,
            'alert_enabled': True
        }
        return CostManager(config)
    
    @pytest.mark.asyncio
    async def test_optimize_task_execution(self, cost_manager, sample_task):
        """統合されたタスク最適化のテスト"""
        context = {
            'estimated_tokens': 1500,
            'operation_type': 'code_analysis',
            'quality_requirement': 'medium'
        }
        
        result = await cost_manager.optimize_task_execution(sample_task, context)
        
        assert 'optimized_plan' in result
        assert 'cost_estimate' in result
        assert result['cost_estimate'].estimated_cost >= 0
        assert cost_manager.manager_stats['tasks_optimized'] == 1
    
    @pytest.mark.asyncio
    async def test_record_task_execution(self, cost_manager, sample_task, sample_execution_result):
        """タスク実行結果記録のテスト"""
        success = await cost_manager.record_task_execution(
            sample_task, sample_execution_result
        )
        
        assert success is True
    
    def test_get_cost_dashboard(self, cost_manager):
        """コストダッシュボード取得のテスト"""
        dashboard = cost_manager.get_cost_dashboard()
        
        required_keys = [
            'budget_overview', 'usage_summary', 'trends', 
            'optimization', 'recommendations', 'system_status'
        ]
        
        for key in required_keys:
            assert key in dashboard
        
        # 予算概要の確認
        budget_overview = dashboard['budget_overview']
        assert budget_overview['monthly_budget'] == 10.0
        assert 'current_spend' in budget_overview
        assert 'remaining_budget' in budget_overview
        assert 'utilization_percentage' in budget_overview
    
    def test_get_detailed_usage_report(self, cost_manager):
        """詳細使用量レポートのテスト"""
        # テストデータを追加
        cost_manager.usage_tracker.record_usage(
            ServiceType.LOCAL_LLM, 'test', 0.0, 100
        )
        
        report = cost_manager.get_detailed_usage_report(days=7)
        
        assert 'report_period' in report
        assert 'summary' in report
        assert 'daily_breakdown' in report
        assert 'service_breakdown' in report
        assert 'recommendations' in report
        
        # サマリーの確認
        summary = report['summary']
        assert 'total_cost' in summary
        assert 'total_requests' in summary
        assert 'average_daily_cost' in summary
    
    @pytest.mark.asyncio
    async def test_emergency_mode_activation(self, cost_manager):
        """緊急モード有効化のテスト"""
        # 予算を95%以上使用してアラートトリガー
        cost_manager.usage_tracker.record_usage(
            ServiceType.CLAUDE_API, 'test', 9.7, 10000
        )
        
        # 緊急モードチェック
        await cost_manager._check_emergency_mode()
        
        assert cost_manager.emergency_mode is True
        assert cost_manager.manager_stats['emergency_activations'] >= 1
    
    def test_alert_callback_registration(self, cost_manager):
        """アラートコールバック登録のテスト"""
        callback_called = []
        
        def test_callback(alert_type, data):
            callback_called.append((alert_type, data))
        
        cost_manager.add_alert_callback(test_callback)
        
        # コールバックが登録されたことを確認
        assert len(cost_manager.alert_callbacks) == 1


class TestServiceTypeEnum:
    """サービス種類列挙型のテスト"""
    
    def test_service_type_values(self):
        """サービス種類の値テスト"""
        assert ServiceType.OPENAI_API.value == "openai_api"
        assert ServiceType.CLAUDE_API.value == "claude_api"
        assert ServiceType.LOCAL_LLM.value == "local_llm"
        assert ServiceType.GITHUB_API.value == "github_api"
        assert ServiceType.OBSIDIAN_API.value == "obsidian_api"
        assert ServiceType.OTHER.value == "other"


class TestPriorityLevelEnum:
    """優先度レベル列挙型のテスト"""
    
    def test_priority_level_values(self):
        """優先度レベルの値テスト"""
        assert PriorityLevel.FREE_ONLY.value == "free_only"
        assert PriorityLevel.FREE_PREFERRED.value == "free_preferred"
        assert PriorityLevel.BALANCED.value == "balanced"
        assert PriorityLevel.PERFORMANCE.value == "performance"
        assert PriorityLevel.UNLIMITED.value == "unlimited"


class TestDataPersistence:
    """データ永続化のテスト"""
    
    def test_usage_record_serialization(self, usage_tracker):
        """使用量記録のシリアライゼーションテスト"""
        # 使用量を記録
        usage_tracker.record_usage(
            ServiceType.LOCAL_LLM,
            'test_operation',
            0.0,
            100,
            task_id='test_task'
        )
        
        # データが保存されることを確認
        today = date.today()
        daily_file = usage_tracker.storage_path / f"daily_{today}.json"
        
        assert daily_file.exists()
        
        # ファイル内容の確認
        with open(daily_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        assert data['total_requests'] >= 1
        assert len(data['records']) >= 1
        
        record = data['records'][0]
        assert record['service_type'] == 'local_llm'
        assert record['operation_type'] == 'test_operation'
        assert record['cost'] == 0.0
        assert record['tokens_used'] == 100
    
    def test_monthly_usage_aggregation(self, usage_tracker):
        """月次使用量集計のテスト"""
        # 複数の使用量を記録
        usage_tracker.record_usage(ServiceType.LOCAL_LLM, 'op1', 0.0, 100)
        usage_tracker.record_usage(ServiceType.CLAUDE_API, 'op2', 0.05, 200)
        usage_tracker.record_usage(ServiceType.OPENAI_API, 'op3', 0.03, 150)
        
        month_usage = usage_tracker.get_current_month_usage()
        
        assert month_usage.total_cost == 0.08  # 0.0 + 0.05 + 0.03
        assert month_usage.total_tokens == 450  # 100 + 200 + 150
        assert month_usage.total_requests == 3
        assert len(month_usage.service_breakdown) == 3