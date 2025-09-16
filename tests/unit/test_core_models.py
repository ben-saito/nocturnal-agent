"""コアモデルの単体テスト"""

import pytest
from datetime import datetime
from nocturnal_agent.core.models import (
    Task, QualityScore, ExecutionResult, TaskPriority, TaskStatus,
    AgentType, ProjectContext, DevelopmentHistory
)


class TestQualityScore:
    """品質スコアのテスト"""
    
    def test_quality_score_creation(self):
        """品質スコアの作成テスト"""
        score = QualityScore(
            overall=0.85,
            code_quality=0.90,
            consistency=0.85,
            test_coverage=0.75,
            security=0.95,
            performance=0.80
        )
        
        assert score.overall == 0.85
        assert score.code_quality == 0.90
        assert score.consistency == 0.85
        assert score.test_coverage == 0.75
        assert score.security == 0.95
        assert score.performance == 0.80
    
    def test_is_acceptable_default_threshold(self, sample_quality_score):
        """デフォルト閾値での許容性テスト"""
        assert sample_quality_score.is_acceptable()  # overall=0.85, threshold=0.85
        
        low_score = QualityScore(overall=0.75)
        assert not low_score.is_acceptable()  # overall=0.75 < 0.85
    
    def test_is_acceptable_custom_threshold(self, sample_quality_score):
        """カスタム閾値での許容性テスト"""
        assert sample_quality_score.is_acceptable(threshold=0.8)  # 0.85 > 0.8
        assert not sample_quality_score.is_acceptable(threshold=0.9)  # 0.85 < 0.9
    
    def test_quality_score_boundary_values(self):
        """境界値テスト"""
        # 最小値
        min_score = QualityScore(overall=0.0)
        assert not min_score.is_acceptable()
        
        # 最大値
        max_score = QualityScore(overall=1.0)
        assert max_score.is_acceptable()
        
        # 境界値
        boundary_score = QualityScore(overall=0.85)
        assert boundary_score.is_acceptable(threshold=0.85)


class TestTask:
    """タスクモデルのテスト"""
    
    def test_task_creation(self, sample_task):
        """タスクの作成テスト"""
        assert sample_task.id == "test_task_001"
        assert sample_task.description == "サンプルテストタスク"
        assert sample_task.priority == TaskPriority.MEDIUM
        assert sample_task.estimated_quality == 0.8
        assert sample_task.status == TaskStatus.PENDING
        assert len(sample_task.requirements) == 2
        assert len(sample_task.constraints) == 1
    
    def test_task_default_values(self):
        """タスクのデフォルト値テスト"""
        task = Task()
        
        assert task.id is not None  # UUIDが生成される
        assert task.description == ""
        assert task.priority == TaskPriority.MEDIUM
        assert task.estimated_quality == 0.0
        assert task.status == TaskStatus.PENDING
        assert task.requirements == []
        assert task.constraints == []
        assert task.minimum_quality_threshold == 0.85
        assert task.consistency_threshold == 0.85
    
    def test_task_execution_lifecycle(self, sample_task):
        """タスク実行ライフサイクルのテスト"""
        # 初期状態
        assert sample_task.status == TaskStatus.PENDING
        assert sample_task.started_at is None
        assert sample_task.completed_at is None
        
        # 実行開始
        sample_task.start_execution()
        assert sample_task.status == TaskStatus.IN_PROGRESS
        assert sample_task.started_at is not None
        assert sample_task.completed_at is None
        
        # 実行完了（成功）
        sample_task.complete_execution(success=True)
        assert sample_task.status == TaskStatus.COMPLETED
        assert sample_task.completed_at is not None
        
        # 新しいタスクで失敗テスト
        failed_task = Task(id="failed_task")
        failed_task.start_execution()
        failed_task.complete_execution(success=False)
        assert failed_task.status == TaskStatus.FAILED


class TestExecutionResult:
    """実行結果のテスト"""
    
    def test_execution_result_creation(self, sample_execution_result):
        """実行結果の作成テスト"""
        result = sample_execution_result
        
        assert result.task_id == "test_task_001"
        assert result.success is True
        assert result.quality_score.overall == 0.85
        assert result.generated_code == "def test_function():\n    return 'success'"
        assert result.agent_used == AgentType.LOCAL_LLM
        assert result.execution_time == 120.5
        assert len(result.files_modified) == 1
        assert len(result.files_created) == 1
        assert result.cost_incurred == 0.0
    
    def test_failed_execution_result(self, failed_execution_result):
        """失敗した実行結果のテスト"""
        result = failed_execution_result
        
        assert result.task_id == "test_task_001"
        assert result.success is False
        assert result.quality_score.overall == 0.0
        assert result.generated_code == ""
        assert len(result.errors) == 1
        assert "実行エラーが発生しました" in result.errors
    
    def test_execution_result_default_values(self):
        """実行結果のデフォルト値テスト"""
        result = ExecutionResult(
            task_id="test",
            success=True,
            quality_score=QualityScore(),
            generated_code="test"
        )
        
        assert result.agent_used == AgentType.LOCAL_LLM
        assert result.execution_time == 0.0
        assert result.improvements_made == []
        assert result.errors == []
        assert result.files_modified == []
        assert result.files_created == []
        assert result.files_deleted == []
        assert result.api_calls_made == 0
        assert result.cost_incurred == 0.0
        assert result.created_at is not None


class TestDevelopmentHistory:
    """開発履歴のテスト"""
    
    def test_development_history_creation(self):
        """開発履歴の作成テスト"""
        history = DevelopmentHistory(
            task_id="hist_001",
            task_description="テスト履歴項目",
            timestamp=datetime.now(),
            success=True,
            agent_used="LOCAL_LLM",
            execution_time=100.5,
            generated_code="test code",
            files_modified=["test.py"]
        )
        
        assert history.task_id == "hist_001"
        assert history.task_description == "テスト履歴項目"
        assert history.success is True
        assert history.agent_used == "LOCAL_LLM"
        assert history.execution_time == 100.5
        assert history.generated_code == "test code"
        assert len(history.files_modified) == 1
    
    def test_development_history_default_values(self):
        """開発履歴のデフォルト値テスト"""
        history = DevelopmentHistory(
            task_id="test",
            task_description="test",
            timestamp=datetime.now(),
            success=True,
            agent_used="test",
            execution_time=0.0
        )
        
        assert history.quality_score is None
        assert history.generated_code == ""
        assert history.result_summary is None
        assert history.files_modified == []
        assert history.metadata == {}


class TestProjectContext:
    """プロジェクトコンテキストのテスト"""
    
    def test_project_context_creation(self, project_context):
        """プロジェクトコンテキストの作成テスト"""
        assert project_context.project_name == "Test Project"
        assert project_context.root_path == "/test/path"
        assert project_context.main_language == "Python"
        assert project_context.framework == "pytest"
        assert len(project_context.development_history) == 1
        assert project_context.current_quality_level == 0.8
        assert project_context.target_quality_threshold == 0.85
    
    def test_project_context_default_values(self):
        """プロジェクトコンテキストのデフォルト値テスト"""
        context = ProjectContext(
            project_name="Test",
            root_path="/test"
        )
        
        assert context.main_language == ""
        assert context.framework == ""
        assert context.dependencies == []
        assert context.development_history == []
        assert context.current_quality_level == 0.0
        assert context.target_quality_threshold == 0.85
        assert context.coding_standards == {}
        assert context.test_requirements == []


class TestEnumValues:
    """列挙型の値テスト"""
    
    def test_task_priority_values(self):
        """タスク優先度の値テスト"""
        assert TaskPriority.LOW.value == "low"
        assert TaskPriority.MEDIUM.value == "medium"
        assert TaskPriority.HIGH.value == "high"
        assert TaskPriority.URGENT.value == "urgent"
    
    def test_task_status_values(self):
        """タスクステータスの値テスト"""
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.IN_PROGRESS.value == "in_progress"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.FAILED.value == "failed"
        assert TaskStatus.CANCELLED.value == "cancelled"
    
    def test_agent_type_values(self):
        """エージェント種類の値テスト"""
        assert AgentType.CLAUDE_CODE.value == "claude_code"
        assert AgentType.GITHUB_COPILOT.value == "github_copilot"
        assert AgentType.OPENAI_CODEX.value == "openai_codex"
        assert AgentType.LOCAL_LLM.value == "local_llm"
        assert AgentType.CURSOR.value == "cursor"