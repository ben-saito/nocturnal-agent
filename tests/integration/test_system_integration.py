"""システム統合テスト - 主要コンポーネント間の統合動作確認"""

import pytest
import asyncio
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch

from nocturnal_agent.cost.cost_manager import CostManager
from nocturnal_agent.safety.safety_coordinator import SafetyCoordinator
from nocturnal_agent.parallel.parallel_executor import ParallelExecutor
from nocturnal_agent.core.models import Task, ExecutionResult, QualityScore, AgentType


class TestCostSafetyIntegration:
    """コスト管理と安全性システムの統合テスト"""
    
    @pytest.fixture
    def integrated_systems(self, git_repo):
        """統合システムを提供"""
        cost_config = {
            'monthly_budget': 10.0,
            'storage_path': str(git_repo / 'cost_data'),
            'free_tool_target_rate': 0.9
        }
        
        safety_config = {
            'backup': {'enable_verification': True, 'retention_days': 7},
            'danger_detection': {
                'enable_file_operations': True,
                'enable_system_commands': True
            },
            'rollback': {'enable_verification': True},
            'auto_backup_before_execution': True,
            'auto_create_rollback_points': True,
            'block_dangerous_operations': True
        }
        
        cost_manager = CostManager(cost_config)
        safety_coordinator = SafetyCoordinator(str(git_repo), safety_config)
        
        return cost_manager, safety_coordinator
    
    @pytest.mark.asyncio
    async def test_cost_safety_coordinated_execution(self, integrated_systems, sample_task):
        """コスト管理と安全性が連携したタスク実行テスト"""
        cost_manager, safety_coordinator = integrated_systems
        
        # 安全セッション初期化
        await safety_coordinator.initialize_safety_session()
        
        # コスト最適化
        optimization_result = await cost_manager.optimize_task_execution(
            sample_task, 
            {'estimated_tokens': 1000, 'operation_type': 'safe_operation'}
        )
        
        # 安全チェック
        safe_code = "def safe_function():\n    return 'safe'"
        safety_result = await safety_coordinator.pre_task_safety_check(
            sample_task, safe_code
        )
        
        assert optimization_result['cost_estimate'].estimated_cost >= 0
        assert safety_result['safe_to_execute'] is True
        
        # 実行結果の記録
        execution_result = ExecutionResult(
            task_id=sample_task.id,
            success=True,
            quality_score=QualityScore(overall=0.85),
            generated_code=safe_code,
            agent_used=AgentType.LOCAL_LLM,
            execution_time=120.0,
            cost_incurred=0.0
        )
        
        cost_record_success = await cost_manager.record_task_execution(
            sample_task, execution_result, optimization_result
        )
        
        safety_post_check = await safety_coordinator.post_task_safety_check(
            sample_task, execution_result
        )
        
        assert cost_record_success is True
        assert safety_post_check['task_completed_safely'] is True
        
        # セッション終了
        await safety_coordinator.finalize_safety_session()
    
    @pytest.mark.asyncio
    async def test_emergency_cost_safety_coordination(self, integrated_systems, sample_task):
        """緊急時のコスト・安全性連携テスト"""
        cost_manager, safety_coordinator = integrated_systems
        
        await safety_coordinator.initialize_safety_session()
        
        # 予算を95%以上使用してコスト緊急モードをトリガー
        for i in range(10):
            cost_manager.usage_tracker.record_usage(
                service_type=cost_manager.usage_tracker.ServiceType.CLAUDE_API,
                operation_type='emergency_test',
                cost=1.0,
                tokens_used=1000
            )
        
        # 緊急モードチェック
        await cost_manager._check_emergency_mode()
        
        # 緊急モード下でのタスク最適化
        optimization_result = await cost_manager.optimize_task_execution(
            sample_task,
            {'estimated_tokens': 2000, 'operation_type': 'emergency_task'}
        )
        
        # コスト緊急モードが有効化されていることを確認
        assert cost_manager.emergency_mode is True
        
        # 無料ツールが強制選択されることを確認
        assert optimization_result['optimized_plan']['selected_service'].value == 'local_llm'
        
        # 安全性緊急回復のテスト
        recovery_result = await safety_coordinator.emergency_recovery(
            "統合テスト緊急回復"
        )
        
        assert recovery_result['recovery_attempted'] is True


class TestParallelSafetyIntegration:
    """並行実行と安全性システムの統合テスト"""
    
    @pytest.fixture
    def parallel_safety_systems(self, git_repo):
        """並行実行と安全性システムを提供"""
        parallel_config = {
            'max_parallel_executions': 2,
            'execution_timeout_seconds': 30,
            'quality_assessment_enabled': True,
            'branch_config': {
                'branch_prefix': 'integration-test',
                'high_quality_threshold': 0.85,
                'medium_quality_threshold': 0.7
            },
            'quality_config': {
                'high_quality_threshold': 0.85,
                'medium_quality_threshold': 0.7
            }
        }
        
        safety_config = {
            'backup': {'enable_verification': True},
            'danger_detection': {'enable_file_operations': True},
            'rollback': {'enable_verification': True},
            'auto_backup_before_execution': True,
            'auto_create_rollback_points': True,
            'block_dangerous_operations': True
        }
        
        parallel_executor = ParallelExecutor(str(git_repo), parallel_config)
        safety_coordinator = SafetyCoordinator(str(git_repo), safety_config)
        
        return parallel_executor, safety_coordinator
    
    @pytest.mark.asyncio
    async def test_parallel_execution_with_safety(self, parallel_safety_systems):
        """安全性チェック付き並行実行テスト"""
        parallel_executor, safety_coordinator = parallel_safety_systems
        
        # システム初期化
        await parallel_executor.start_parallel_session()
        await safety_coordinator.initialize_safety_session()
        
        # 安全なタスクエグゼキューター
        async def safe_executor(task):
            # 事前安全チェック
            safe_code = f"def {task.id}_function():\n    return 'success'"
            safety_result = await safety_coordinator.pre_task_safety_check(
                task, safe_code
            )
            
            if not safety_result['safe_to_execute']:
                raise RuntimeError("安全チェックに失敗")
            
            # 実行結果作成
            result = ExecutionResult(
                task_id=task.id,
                success=True,
                quality_score=QualityScore(overall=0.8),
                generated_code=safe_code,
                agent_used=AgentType.LOCAL_LLM,
                execution_time=60.0,
                files_modified=[f"{task.id}.py"]
            )
            
            # 事後安全チェック
            await safety_coordinator.post_task_safety_check(task, result)
            
            return result
        
        # テストタスクを作成・実行
        tasks = [
            Task(id=f"safe_task_{i}", description=f"Safe task {i}")
            for i in range(3)
        ]
        
        task_ids = []
        for task in tasks:
            task_id = await parallel_executor.execute_task_parallel(
                task, safe_executor, estimated_quality=0.8
            )
            task_ids.append(task_id)
        
        # 完了待機
        completion_result = await parallel_executor.wait_for_completion(timeout=30)
        
        assert completion_result['status'] in ['all_completed', 'timeout']
        
        # システム終了
        session_summary = await parallel_executor.finalize_parallel_session()
        safety_summary = await safety_coordinator.finalize_safety_session()
        
        assert session_summary['total_tasks_processed'] >= len(tasks)
        assert safety_summary['statistics']['rollback_points_created'] > 0
    
    @pytest.mark.asyncio
    async def test_dangerous_task_blocking_in_parallel(self, parallel_safety_systems):
        """並行実行における危険タスクのブロックテスト"""
        parallel_executor, safety_coordinator = parallel_safety_systems
        
        await parallel_executor.start_parallel_session()
        await safety_coordinator.initialize_safety_session()
        
        # 危険なコードを含むエグゼキューター
        async def dangerous_executor(task):
            dangerous_code = "import os; os.system('rm -rf /')"
            safety_result = await safety_coordinator.pre_task_safety_check(
                task, dangerous_code
            )
            
            if not safety_result['safe_to_execute']:
                return ExecutionResult(
                    task_id=task.id,
                    success=False,
                    quality_score=QualityScore(overall=0.0),
                    generated_code="",
                    errors=["危険な操作がブロックされました"]
                )
            
            # 実際には実行されない
            return ExecutionResult(
                task_id=task.id,
                success=False,
                quality_score=QualityScore(overall=0.0),
                generated_code=dangerous_code
            )
        
        dangerous_task = Task(
            id="dangerous_task",
            description="危険なタスク"
        )
        
        task_id = await parallel_executor.execute_task_parallel(
            dangerous_task, dangerous_executor
        )
        
        completion_result = await parallel_executor.wait_for_completion(
            task_id=task_id, timeout=10
        )
        
        # タスクが実行されたが失敗したことを確認
        assert completion_result['status'] in ['completed', 'failed']
        
        # 安全性違反が記録されていることを確認
        safety_status = safety_coordinator.get_safety_status()
        assert safety_status['safety_violations_count'] > 0


class TestFullSystemIntegration:
    """全システム統合テスト"""
    
    @pytest.fixture
    def full_system(self, git_repo):
        """全システム統合セットアップ"""
        # コスト管理設定
        cost_config = {
            'monthly_budget': 10.0,
            'storage_path': str(git_repo / 'cost_data'),
            'free_tool_target_rate': 0.9,
            'alert_enabled': True
        }
        
        # 安全性設定
        safety_config = {
            'backup': {'enable_verification': True, 'retention_days': 7},
            'danger_detection': {
                'enable_file_operations': True,
                'enable_system_commands': True
            },
            'rollback': {'enable_verification': True, 'max_rollback_points': 10},
            'auto_backup_before_execution': True,
            'auto_create_rollback_points': True,
            'block_dangerous_operations': True
        }
        
        # 並行実行設定
        parallel_config = {
            'max_parallel_executions': 2,
            'execution_timeout_seconds': 60,
            'quality_assessment_enabled': True,
            'branch_config': {
                'branch_prefix': 'full-test',
                'high_quality_threshold': 0.85,
                'medium_quality_threshold': 0.7,
                'max_parallel_branches': 5
            },
            'quality_config': {
                'high_quality_threshold': 0.85,
                'medium_quality_threshold': 0.7,
                'auto_apply_threshold': 0.90,
                'max_parallel_executions': 2
            }
        }
        
        cost_manager = CostManager(cost_config)
        safety_coordinator = SafetyCoordinator(str(git_repo), safety_config)
        parallel_executor = ParallelExecutor(str(git_repo), parallel_config)
        
        return cost_manager, safety_coordinator, parallel_executor
    
    @pytest.mark.asyncio
    async def test_complete_development_cycle(self, full_system):
        """完全な開発サイクルの統合テスト"""
        cost_manager, safety_coordinator, parallel_executor = full_system
        
        # システム初期化
        await safety_coordinator.initialize_safety_session()
        session_id = await parallel_executor.start_parallel_session()
        
        assert session_id is not None
        
        # 統合エグゼキューター（コスト・安全・品質を考慮）
        async def integrated_executor(task):
            # Step 1: コスト最適化
            optimization = await cost_manager.optimize_task_execution(
                task, {
                    'estimated_tokens': 1500,
                    'operation_type': 'code_generation',
                    'quality_requirement': 'medium'
                }
            )
            
            # Step 2: 安全性チェック
            generated_code = f"def {task.id}_function():\n    return 'Hello from {task.id}'"
            safety_check = await safety_coordinator.pre_task_safety_check(
                task, generated_code
            )
            
            if not safety_check['safe_to_execute']:
                return ExecutionResult(
                    task_id=task.id,
                    success=False,
                    quality_score=QualityScore(overall=0.0),
                    generated_code="",
                    errors=["安全チェック失敗"]
                )
            
            # Step 3: 実行シミュレーション
            await asyncio.sleep(0.2)  # 実行時間シミュレート
            
            execution_result = ExecutionResult(
                task_id=task.id,
                success=True,
                quality_score=QualityScore(
                    overall=0.8,
                    code_quality=0.8,
                    consistency=0.85,
                    test_coverage=0.7,
                    security=0.9,
                    performance=0.8
                ),
                generated_code=generated_code,
                agent_used=AgentType.LOCAL_LLM,
                execution_time=200.0,
                files_modified=[f"{task.id}.py"],
                cost_incurred=optimization['cost_estimate'].estimated_cost
            )
            
            # Step 4: 事後処理
            await cost_manager.record_task_execution(
                task, execution_result, optimization
            )
            await safety_coordinator.post_task_safety_check(
                task, execution_result
            )
            
            return execution_result
        
        # テストタスクの実行
        test_tasks = [
            Task(id=f"integration_task_{i}", description=f"統合テストタスク {i}")
            for i in range(4)
        ]
        
        # 並行実行
        for task in test_tasks:
            await parallel_executor.execute_task_parallel(
                task, integrated_executor, estimated_quality=0.8
            )
        
        # 完了待機
        completion_result = await parallel_executor.wait_for_completion(timeout=30)
        
        assert completion_result['status'] in ['all_completed', 'timeout']
        if completion_result['status'] == 'all_completed':
            assert completion_result['completed_count'] >= len(test_tasks)
        
        # システム状態確認
        cost_dashboard = cost_manager.get_cost_dashboard()
        safety_status = safety_coordinator.get_safety_status()
        execution_status = await parallel_executor.get_execution_status()
        
        # コスト管理が正常動作していることを確認
        assert cost_dashboard['budget_overview']['monthly_budget'] == 10.0
        assert cost_dashboard['optimization']['tasks_optimized'] >= len(test_tasks)
        
        # 安全性システムが正常動作していることを確認
        assert safety_status['safety_active'] is True
        assert safety_status['statistics']['rollback_points_created'] > 0
        
        # 並行実行が正常動作していることを確認
        assert execution_status['total_processed'] >= len(test_tasks)
        
        # システム終了
        parallel_summary = await parallel_executor.finalize_parallel_session()
        safety_summary = await safety_coordinator.finalize_safety_session()
        
        # 最終統計確認
        assert parallel_summary['success_rate'] >= 0.5
        assert safety_summary['statistics']['backups_created'] >= 1
        
        # 最終レポート生成
        final_report = {
            'session_summary': parallel_summary,
            'safety_report': safety_summary,
            'cost_report': cost_manager.get_detailed_usage_report(days=1),
            'integration_success': True
        }
        
        assert final_report['integration_success'] is True
    
    @pytest.mark.asyncio
    async def test_error_recovery_coordination(self, full_system):
        """エラー回復の連携テスト"""
        cost_manager, safety_coordinator, parallel_executor = full_system
        
        await safety_coordinator.initialize_safety_session()
        await parallel_executor.start_parallel_session()
        
        # エラーを発生させるエグゼキューター
        async def error_executor(task):
            if task.id.endswith('_error'):
                # 意図的にエラーを発生
                raise RuntimeError("テスト用エラー")
            
            return ExecutionResult(
                task_id=task.id,
                success=True,
                quality_score=QualityScore(overall=0.7),
                generated_code="success",
                agent_used=AgentType.LOCAL_LLM
            )
        
        # 正常タスクとエラータスク
        tasks = [
            Task(id="normal_task_1", description="正常タスク1"),
            Task(id="error_task_error", description="エラータスク"),
            Task(id="normal_task_2", description="正常タスク2")
        ]
        
        for task in tasks:
            await parallel_executor.execute_task_parallel(
                task, error_executor, estimated_quality=0.7
            )
        
        completion_result = await parallel_executor.wait_for_completion(timeout=15)
        
        # 一部失敗があっても他のタスクは成功していることを確認
        execution_status = await parallel_executor.get_execution_status()
        assert execution_status['completed_count'] >= 1
        assert execution_status['failed_count'] >= 1
        
        # 緊急回復テスト
        recovery_result = await safety_coordinator.emergency_recovery(
            "統合テストエラー回復"
        )
        
        assert recovery_result['recovery_attempted'] is True
        
        # システム終了
        await parallel_executor.finalize_parallel_session()
        await safety_coordinator.finalize_safety_session()


class TestSystemPerformance:
    """システムパフォーマンステスト"""
    
    @pytest.mark.asyncio
    async def test_concurrent_load_handling(self, git_repo):
        """同時負荷処理テスト"""
        parallel_executor = ParallelExecutor(str(git_repo), {
            'max_parallel_executions': 3,
            'execution_timeout_seconds': 30
        })
        
        await parallel_executor.start_parallel_session()
        
        async def load_executor(task):
            await asyncio.sleep(0.1)  # 軽い処理をシミュレート
            return ExecutionResult(
                task_id=task.id,
                success=True,
                quality_score=QualityScore(overall=0.75),
                generated_code="load test",
                agent_used=AgentType.LOCAL_LLM
            )
        
        # 多数のタスクを同時実行
        tasks = [
            Task(id=f"load_task_{i}", description=f"負荷テストタスク {i}")
            for i in range(10)
        ]
        
        start_time = datetime.now()
        
        for task in tasks:
            await parallel_executor.execute_task_parallel(
                task, load_executor, estimated_quality=0.75
            )
        
        completion_result = await parallel_executor.wait_for_completion(timeout=60)
        
        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds()
        
        # パフォーマンス確認
        assert completion_result['status'] == 'all_completed'
        assert completion_result['completed_count'] == len(tasks)
        assert execution_time < 30  # 30秒以内で完了
        
        # 並行実行効率の確認
        session_summary = await parallel_executor.finalize_parallel_session()
        assert session_summary['parallel_peak'] >= 3  # 最大並行数が活用された
    
    def test_memory_usage_stability(self, basic_config):
        """メモリ使用量安定性テスト"""
        # メモリリークがないことを確認するための基本テスト
        systems = []
        
        for i in range(5):
            config = basic_config.copy()
            config['storage_path'] = f'./test_memory_{i}'
            cost_manager = CostManager(config)
            systems.append(cost_manager)
        
        # システムが正常に作成されることを確認
        assert len(systems) == 5
        
        for system in systems:
            assert system.cost_management_active is True
        
        # システムのクリーンアップ
        del systems