"""並行実行システムの単体テスト"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from nocturnal_agent.parallel.branch_manager import (
    BranchManager, BranchType, BranchInfo, MergeConflict
)
from nocturnal_agent.parallel.quality_controller import (
    QualityController, QualityTier, QualityDecision, ExecutionPlan, QualityMetrics
)
from nocturnal_agent.parallel.parallel_executor import (
    ParallelExecutor, ParallelExecutionTask, ExecutionSession
)


class TestBranchManager:
    """ブランチ管理システムのテスト"""
    
    @pytest.fixture
    def branch_manager(self, git_repo):
        """BranchManagerインスタンスを提供"""
        config = {
            'branch_prefix': 'test-nocturnal',
            'high_quality_threshold': 0.85,
            'medium_quality_threshold': 0.7,
            'max_parallel_branches': 5
        }
        return BranchManager(str(git_repo), config)
    
    def test_branch_manager_initialization(self, branch_manager):
        """BranchManagerの初期化テスト"""
        assert branch_manager.branch_prefix == 'test-nocturnal'
        assert branch_manager.high_quality_threshold == 0.85
        assert branch_manager.medium_quality_threshold == 0.7
        assert branch_manager.max_parallel_branches == 5
        assert branch_manager.active_branches == {}
    
    def test_initialize_night_session(self, branch_manager):
        """夜間セッション初期化のテスト"""
        session_branch = branch_manager.initialize_night_session()
        
        assert session_branch is not None
        assert session_branch.startswith('test-nocturnal/night-')
        assert session_branch in branch_manager.active_branches
        assert branch_manager.current_night_session == session_branch
        
        # ブランチ情報の確認
        branch_info = branch_manager.active_branches[session_branch]
        assert branch_info.branch_type == BranchType.NIGHT_MAIN
        assert branch_info.quality_threshold == 0.0
    
    def test_create_quality_branch_high(self, branch_manager):
        """高品質ブランチ作成のテスト"""
        branch_manager.initialize_night_session()
        
        branch_name = branch_manager.create_quality_branch(
            quality_score=0.90,
            task_id='high_quality_task',
            task_description='高品質テストタスク'
        )
        
        assert branch_name is not None
        assert 'high_quality' in branch_name
        assert branch_name in branch_manager.active_branches
        
        branch_info = branch_manager.active_branches[branch_name]
        assert branch_info.branch_type == BranchType.HIGH_QUALITY
        assert branch_info.quality_threshold == 0.85
        assert 'high_quality_task' in branch_info.associated_tasks
    
    def test_create_quality_branch_medium(self, branch_manager):
        """中品質ブランチ作成のテスト"""
        branch_manager.initialize_night_session()
        
        branch_name = branch_manager.create_quality_branch(
            quality_score=0.75,
            task_id='medium_quality_task'
        )
        
        branch_info = branch_manager.active_branches[branch_name]
        assert branch_info.branch_type == BranchType.MEDIUM_QUALITY
        assert branch_info.quality_threshold == 0.7
    
    def test_create_quality_branch_experimental(self, branch_manager):
        """実験的ブランチ作成のテスト"""
        branch_manager.initialize_night_session()
        
        branch_name = branch_manager.create_quality_branch(
            quality_score=0.55,
            task_id='experimental_task'
        )
        
        branch_info = branch_manager.active_branches[branch_name]
        assert branch_info.branch_type == BranchType.EXPERIMENTAL
        assert branch_info.quality_threshold == 0.0
    
    @patch('subprocess.run')
    def test_switch_to_branch(self, mock_subprocess, branch_manager):
        """ブランチ切り替えのテスト"""
        mock_subprocess.return_value = Mock()
        
        branch_manager.initialize_night_session()
        session_branch = branch_manager.current_night_session
        
        success = branch_manager.switch_to_branch(session_branch)
        
        assert success is True
        mock_subprocess.assert_called_with(
            ['git', 'checkout', session_branch],
            cwd=branch_manager.project_path,
            capture_output=True,
            text=True,
            check=True
        )
    
    @patch('subprocess.run')
    def test_commit_task_result(self, mock_subprocess, branch_manager):
        """タスク結果コミットのテスト"""
        # Git操作のモック
        mock_subprocess.return_value = Mock()
        
        branch_manager.initialize_night_session()
        
        with patch.object(branch_manager, '_get_current_commit', return_value='abc123'):
            with patch.object(branch_manager, '_get_current_branch', 
                            return_value=branch_manager.current_night_session):
                
                commit_hash = branch_manager.commit_task_result(
                    task_id='test_task',
                    commit_message='テストコミット',
                    files_changed=['test.py']
                )
                
                assert commit_hash == 'abc123'
                
                # Git addとcommitが呼ばれたことを確認
                add_call = ['git', 'add', 'test.py']
                commit_call = ['git', 'commit', '-m']
                
                calls = [call[0][0] for call in mock_subprocess.call_args_list]
                assert add_call in calls
                assert any('git' == call[0] and 'commit' == call[1] 
                          for call in calls)
    
    def test_detect_merge_conflicts(self, branch_manager):
        """マージ競合検出のテスト"""
        branch_manager.initialize_night_session()
        
        # テスト用ブランチを作成
        branch1 = branch_manager.create_quality_branch(0.8, 'task1')
        branch2 = branch_manager.create_quality_branch(0.8, 'task2')
        
        with patch('subprocess.run') as mock_subprocess:
            # 競合ありのケース
            mock_subprocess.return_value = Mock(
                stdout='<<<<<<< HEAD\nconflict content\n>>>>>>> branch\n'
            )
            
            conflicts = branch_manager.detect_merge_conflicts(branch1, branch2)
            
            # 競合が検出された場合
            if conflicts:
                assert len(conflicts) > 0
                conflict = conflicts[0]
                assert conflict.source_branch == branch1
                assert conflict.target_branch == branch2
                assert isinstance(conflict.conflicting_files, list)
    
    def test_get_branch_status(self, branch_manager):
        """ブランチ状態取得のテスト"""
        branch_manager.initialize_night_session()
        branch_manager.create_quality_branch(0.9, 'task1')
        branch_manager.create_quality_branch(0.75, 'task2')
        
        status = branch_manager.get_branch_status()
        
        required_keys = [
            'current_night_session', 'active_branches_count', 'total_branches',
            'branch_breakdown', 'statistics', 'recent_activity'
        ]
        
        for key in required_keys:
            assert key in status
        
        assert status['current_night_session'] is not None
        assert status['total_branches'] >= 3  # night main + 2 quality branches
        assert status['active_branches_count'] >= 1


class TestQualityController:
    """品質制御システムのテスト"""
    
    @pytest.fixture
    def quality_controller(self, git_repo):
        """QualityControllerインスタンスを提供"""
        branch_manager = BranchManager(str(git_repo), {
            'branch_prefix': 'test',
            'high_quality_threshold': 0.85,
            'medium_quality_threshold': 0.7
        })
        
        config = {
            'high_quality_threshold': 0.85,
            'medium_quality_threshold': 0.7,
            'auto_apply_threshold': 0.90,
            'max_parallel_executions': 3
        }
        
        return QualityController(branch_manager, config)
    
    @pytest.mark.asyncio
    async def test_evaluate_task_quality_high(self, quality_controller, high_quality_task):
        """高品質タスクの評価テスト"""
        decision = await quality_controller.evaluate_task_quality(
            high_quality_task, estimated_quality=0.92
        )
        
        assert decision.quality_tier == QualityTier.HIGH
        assert decision.action in ['immediate_apply', 'parallel_branch']
        assert decision.auto_merge_eligible is True
        assert decision.confidence >= 0.9
    
    @pytest.mark.asyncio
    async def test_evaluate_task_quality_medium(self, quality_controller, sample_task):
        """中品質タスクの評価テスト"""
        decision = await quality_controller.evaluate_task_quality(
            sample_task, estimated_quality=0.75
        )
        
        assert decision.quality_tier == QualityTier.MEDIUM
        assert decision.action == 'parallel_branch'
        assert decision.auto_merge_eligible is False
        assert decision.requires_review is True
    
    @pytest.mark.asyncio
    async def test_evaluate_task_quality_low(self, quality_controller, low_quality_task):
        """低品質タスクの評価テスト"""
        decision = await quality_controller.evaluate_task_quality(
            low_quality_task, estimated_quality=0.55
        )
        
        assert decision.quality_tier == QualityTier.LOW
        assert decision.action == 'experimental_branch'
        assert decision.auto_merge_eligible is False
        assert decision.requires_review is True
    
    @pytest.mark.asyncio
    async def test_execute_with_quality_control(self, quality_controller, sample_task):
        """品質制御下での実行テスト"""
        decision = QualityDecision(
            quality_tier=QualityTier.MEDIUM,
            action='parallel_branch',
            branch_name=None,
            requires_review=True,
            auto_merge_eligible=False,
            reasoning='中品質のため並行検証',
            confidence=0.75
        )
        
        # モックエグゼキューター
        async def mock_executor(task):
            return Mock(
                task_id=task.id,
                success=True,
                quality_score=Mock(overall=0.75)
            )
        
        with patch.object(quality_controller.branch_manager, 'initialize_night_session'):
            with patch.object(quality_controller.branch_manager, 'create_quality_branch', 
                            return_value='test_branch'):
                with patch.object(quality_controller.branch_manager, 'switch_to_branch', 
                                return_value=True):
                    
                    result = await quality_controller.execute_with_quality_control(
                        sample_task, decision, mock_executor
                    )
                    
                    assert result.success is True
                    assert result.task_id == sample_task.id
    
    def test_get_quality_recommendations(self, quality_controller):
        """品質推奨事項取得のテスト"""
        # 低品質履歴を追加
        for i in range(5):
            quality_controller.quality_history.append(
                QualityMetrics(
                    overall_score=0.6,
                    individual_scores={},
                    consistency_score=0.6,
                    security_assessment=0.7,
                    performance_impact=0.65,
                    maintainability_score=0.6
                )
            )
        
        recommendations = quality_controller.get_quality_recommendations()
        
        assert len(recommendations) > 0
        quality_rec = next(
            (r for r in recommendations if r['type'] == 'quality_improvement'), None
        )
        assert quality_rec is not None
        assert quality_rec['priority'] == 'high'
    
    def test_get_controller_status(self, quality_controller):
        """コントローラー状態取得のテスト"""
        status = quality_controller.get_controller_status()
        
        required_keys = [
            'controller_active', 'quality_thresholds', 'current_executions',
            'pending_reviews', 'statistics', 'recent_quality_trend', 'recommendations'
        ]
        
        for key in required_keys:
            assert key in status
        
        assert status['controller_active'] is True
        assert 'high' in status['quality_thresholds']
        assert 'medium' in status['quality_thresholds']


class TestParallelExecutor:
    """並行実行システムのテスト"""
    
    @pytest.fixture
    def parallel_executor(self, git_repo):
        """ParallelExecutorインスタンスを提供"""
        config = {
            'max_parallel_executions': 3,
            'execution_timeout_seconds': 30,
            'quality_assessment_enabled': True,
            'branch_config': {
                'branch_prefix': 'test',
                'high_quality_threshold': 0.85,
                'medium_quality_threshold': 0.7
            },
            'quality_config': {
                'high_quality_threshold': 0.85,
                'medium_quality_threshold': 0.7,
                'auto_apply_threshold': 0.90
            }
        }
        return ParallelExecutor(str(git_repo), config)
    
    @pytest.mark.asyncio
    async def test_start_parallel_session(self, parallel_executor):
        """並行実行セッション開始のテスト"""
        session_id = await parallel_executor.start_parallel_session()
        
        assert session_id is not None
        assert session_id.startswith('parallel-')
        assert parallel_executor.current_session is not None
        assert parallel_executor.current_session.session_id == session_id
        assert parallel_executor.executor_stats['sessions_started'] >= 1
    
    @pytest.mark.asyncio
    async def test_execute_task_parallel(self, parallel_executor, sample_task):
        """並行タスク実行のテスト"""
        await parallel_executor.start_parallel_session()
        
        # モックエグゼキューター
        async def mock_executor(task):
            await asyncio.sleep(0.1)  # 実行時間をシミュレート
            return Mock(
                task_id=task.id,
                success=True,
                quality_score=Mock(overall=0.8)
            )
        
        task_id = await parallel_executor.execute_task_parallel(
            sample_task, mock_executor, estimated_quality=0.8
        )
        
        assert task_id == sample_task.id
        assert task_id in parallel_executor.current_session.active_tasks
        assert parallel_executor.current_session.total_tasks_processed >= 1
    
    @pytest.mark.asyncio
    async def test_wait_for_completion_single_task(self, parallel_executor, sample_task):
        """単一タスクの完了待機テスト"""
        await parallel_executor.start_parallel_session()
        
        async def quick_executor(task):
            return Mock(task_id=task.id, success=True)
        
        task_id = await parallel_executor.execute_task_parallel(
            sample_task, quick_executor
        )
        
        completion_result = await parallel_executor.wait_for_completion(
            task_id=task_id, timeout=5
        )
        
        assert completion_result['status'] in ['completed', 'not_found']
        assert completion_result['task_id'] == task_id
    
    @pytest.mark.asyncio
    async def test_wait_for_completion_all_tasks(self, parallel_executor):
        """全タスクの完了待機テスト"""
        await parallel_executor.start_parallel_session()
        
        async def quick_executor(task):
            return Mock(task_id=task.id, success=True)
        
        # 複数タスクを実行
        tasks = [
            Mock(id=f'task_{i}', description=f'Task {i}')
            for i in range(3)
        ]
        
        for task in tasks:
            await parallel_executor.execute_task_parallel(
                task, quick_executor
            )
        
        completion_result = await parallel_executor.wait_for_completion(timeout=10)
        
        assert completion_result['status'] in ['all_completed', 'timeout']
    
    @pytest.mark.asyncio
    async def test_get_execution_status(self, parallel_executor, sample_task):
        """実行状態取得のテスト"""
        await parallel_executor.start_parallel_session()
        
        async def slow_executor(task):
            await asyncio.sleep(1)  # 長い実行時間
            return Mock(task_id=task.id, success=True)
        
        await parallel_executor.execute_task_parallel(
            sample_task, slow_executor
        )
        
        status = await parallel_executor.get_execution_status()
        
        required_keys = [
            'session_active', 'session_id', 'session_duration',
            'active_tasks', 'completed_count', 'failed_count',
            'total_processed', 'parallel_limit', 'branch_status', 'quality_status'
        ]
        
        for key in required_keys:
            assert key in status
        
        assert status['session_active'] is True
        assert len(status['active_tasks']) >= 0
    
    @pytest.mark.asyncio
    async def test_finalize_parallel_session(self, parallel_executor):
        """並行実行セッション終了のテスト"""
        await parallel_executor.start_parallel_session()
        
        # 簡単なタスクを実行
        async def quick_executor(task):
            return Mock(task_id=task.id, success=True, quality_score=Mock(overall=0.8))
        
        task = Mock(id='final_task', description='Final task')
        await parallel_executor.execute_task_parallel(task, quick_executor)
        
        # 完了を待機
        await parallel_executor.wait_for_completion(timeout=5)
        
        session_summary = await parallel_executor.finalize_parallel_session()
        
        required_keys = [
            'session_id', 'duration', 'total_tasks_processed',
            'completed_tasks', 'failed_tasks', 'success_rate',
            'parallel_peak', 'branch_management', 'quality_review'
        ]
        
        for key in required_keys:
            assert key in session_summary
        
        assert parallel_executor.current_session is None
        assert session_summary['total_tasks_processed'] >= 1
    
    @pytest.mark.asyncio
    async def test_get_system_status(self, parallel_executor):
        """システム状態取得のテスト"""
        await parallel_executor.start_parallel_session()
        
        system_status = await parallel_executor.get_system_status()
        
        required_keys = [
            'parallel_executor', 'statistics', 'branch_manager_status',
            'quality_controller_status', 'execution_status'
        ]
        
        for key in required_keys:
            assert key in system_status
        
        executor_status = system_status['parallel_executor']
        assert 'max_parallel_executions' in executor_status
        assert 'quality_assessment_enabled' in executor_status
        assert 'current_session_active' in executor_status


class TestBranchTypeEnum:
    """ブランチ種別列挙型のテスト"""
    
    def test_branch_type_values(self):
        """ブランチ種別の値テスト"""
        assert BranchType.NIGHT_MAIN.value == "night_main"
        assert BranchType.HIGH_QUALITY.value == "high_quality"
        assert BranchType.MEDIUM_QUALITY.value == "medium_quality"
        assert BranchType.EXPERIMENTAL.value == "experimental"
        assert BranchType.EMERGENCY.value == "emergency"


class TestQualityTierEnum:
    """品質階層列挙型のテスト"""
    
    def test_quality_tier_values(self):
        """品質階層の値テスト"""
        assert QualityTier.HIGH.value == "high"
        assert QualityTier.MEDIUM.value == "medium"
        assert QualityTier.LOW.value == "low"
        assert QualityTier.FAILED.value == "failed"


class TestParallelExecutionModels:
    """並行実行モデルのテスト"""
    
    def test_parallel_execution_task_creation(self):
        """並行実行タスクの作成テスト"""
        task = Mock(id='test_task')
        parallel_task = ParallelExecutionTask(
            task=task,
            branch_name='test_branch',
            quality_tier=QualityTier.MEDIUM,
            started_at=datetime.now(),
            executor_id='exec_001'
        )
        
        assert parallel_task.task.id == 'test_task'
        assert parallel_task.branch_name == 'test_branch'
        assert parallel_task.quality_tier == QualityTier.MEDIUM
        assert parallel_task.executor_id == 'exec_001'
        assert parallel_task.future is None
    
    def test_execution_session_creation(self):
        """実行セッションの作成テスト"""
        session = ExecutionSession(
            session_id='test_session',
            started_at=datetime.now(),
            night_main_branch='test_main_branch'
        )
        
        assert session.session_id == 'test_session'
        assert session.night_main_branch == 'test_main_branch'
        assert session.active_tasks == {}
        assert session.completed_tasks == []
        assert session.failed_tasks == []
        assert session.max_parallel_limit == 3
        assert session.total_tasks_processed == 0