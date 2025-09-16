"""pytest設定とフィクスチャの定義"""

import pytest
import tempfile
import shutil
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Dict, Any
import sys
import os

# srcディレクトリをPythonパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from nocturnal_agent.core.models import (
    Task, ExecutionResult, QualityScore, TaskPriority, 
    TaskStatus, AgentType, ProjectContext, DevelopmentHistory
)


@pytest.fixture
def temp_dir():
    """テスト用の一時ディレクトリを提供"""
    temp_path = tempfile.mkdtemp()
    yield Path(temp_path)
    shutil.rmtree(temp_path)


@pytest.fixture
def git_repo(temp_dir):
    """Git初期化済みの一時ディレクトリを提供"""
    os.system(f"cd {temp_dir} && git init && git config user.email 'test@test.com' && git config user.name 'Test User'")
    
    # 初期ファイルを作成
    test_file = temp_dir / "test.py"
    test_file.write_text("# Test file")
    
    os.system(f"cd {temp_dir} && git add . && git commit -m 'Initial commit'")
    return temp_dir


@pytest.fixture
def sample_task():
    """サンプルタスクを提供"""
    return Task(
        id="test_task_001",
        description="サンプルテストタスク",
        priority=TaskPriority.MEDIUM,
        estimated_quality=0.8,
        requirements=["要件1", "要件2"],
        constraints=["制約1"]
    )


@pytest.fixture
def high_quality_task():
    """高品質タスクを提供"""
    return Task(
        id="high_quality_task",
        description="高品質テストタスク",
        priority=TaskPriority.HIGH,
        estimated_quality=0.92,
        minimum_quality_threshold=0.85
    )


@pytest.fixture
def low_quality_task():
    """低品質タスクを提供"""
    return Task(
        id="low_quality_task", 
        description="低品質テストタスク",
        priority=TaskPriority.LOW,
        estimated_quality=0.5,
        minimum_quality_threshold=0.7
    )


@pytest.fixture
def sample_quality_score():
    """サンプル品質スコアを提供"""
    return QualityScore(
        overall=0.85,
        code_quality=0.85,
        consistency=0.90,
        test_coverage=0.75,
        security=0.95,
        performance=0.80
    )


@pytest.fixture
def high_quality_score():
    """高品質スコアを提供"""
    return QualityScore(
        overall=0.92,
        code_quality=0.95,
        consistency=0.95,
        test_coverage=0.85,
        security=0.98,
        performance=0.88
    )


@pytest.fixture
def low_quality_score():
    """低品質スコアを提供"""
    return QualityScore(
        overall=0.55,
        code_quality=0.60,
        consistency=0.65,
        test_coverage=0.30,
        security=0.70,
        performance=0.45
    )


@pytest.fixture
def sample_execution_result(sample_task, sample_quality_score):
    """サンプル実行結果を提供"""
    return ExecutionResult(
        task_id=sample_task.id,
        success=True,
        quality_score=sample_quality_score,
        generated_code="def test_function():\n    return 'success'",
        agent_used=AgentType.LOCAL_LLM,
        execution_time=120.5,
        files_modified=["test.py"],
        files_created=["new_test.py"],
        cost_incurred=0.0
    )


@pytest.fixture
def failed_execution_result(sample_task):
    """失敗した実行結果を提供"""
    return ExecutionResult(
        task_id=sample_task.id,
        success=False,
        quality_score=QualityScore(overall=0.0),
        generated_code="",
        agent_used=AgentType.LOCAL_LLM,
        execution_time=45.0,
        errors=["実行エラーが発生しました"],
        cost_incurred=0.0
    )


@pytest.fixture
def project_context():
    """プロジェクトコンテキストを提供"""
    return ProjectContext(
        project_name="Test Project",
        root_path="/test/path",
        main_language="Python",
        framework="pytest",
        development_history=[
            DevelopmentHistory(
                task_id="hist_001",
                task_description="テスト履歴1",
                timestamp=datetime.now(),
                success=True,
                agent_used="LOCAL_LLM",
                execution_time=100.0,
                generated_code="test code",
                files_modified=["test1.py"]
            )
        ],
        current_quality_level=0.8,
        target_quality_threshold=0.85
    )


@pytest.fixture
def basic_config():
    """基本設定を提供"""
    return {
        'monthly_budget': 10.0,
        'free_tool_target_rate': 0.9,
        'high_quality_threshold': 0.85,
        'medium_quality_threshold': 0.7,
        'max_parallel_executions': 3,
        'safety_enabled': True,
        'backup_enabled': True,
        'cost_tracking_enabled': True
    }


@pytest.fixture
def cost_config():
    """コスト管理設定を提供"""
    return {
        'monthly_budget': 10.0,
        'storage_path': './test_cost_data',
        'alert_thresholds': [0.5, 0.8, 0.9, 0.95],
        'free_tool_target_rate': 0.9,
        'free_tools': ['local_llm', 'github_api']
    }


@pytest.fixture
def safety_config():
    """安全性設定を提供"""
    return {
        'backup': {
            'enable_verification': True,
            'retention_days': 7
        },
        'danger_detection': {
            'enable_file_operations': True,
            'enable_system_commands': True
        },
        'rollback': {
            'enable_verification': True,
            'max_rollback_points': 10
        }
    }


@pytest.fixture
def parallel_config():
    """並行実行設定を提供"""
    return {
        'max_parallel_executions': 3,
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


@pytest.fixture
def mock_claude_response():
    """Claude APIレスポンスのモックデータ"""
    return {
        'choices': [{
            'message': {
                'content': 'def hello_world():\n    """テスト関数"""\n    return "Hello, World!"'
            }
        }],
        'usage': {
            'total_tokens': 150,
            'prompt_tokens': 100,
            'completion_tokens': 50
        }
    }


@pytest.fixture
def mock_obsidian_data():
    """Obsidian連携用のモックデータ"""
    return {
        'notes': [
            {
                'title': 'Test Note 1',
                'content': '# Test Note 1\n\nThis is a test note.',
                'path': 'test1.md',
                'created': datetime.now().isoformat(),
                'modified': datetime.now().isoformat()
            }
        ],
        'project_info': {
            'name': 'Test Project',
            'path': '/test/vault',
            'file_count': 10
        }
    }


# pytest-asyncio設定
@pytest.fixture(scope="session")
def event_loop():
    """イベントループを提供"""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


# テストデータのクリーンアップ
@pytest.fixture(autouse=True)
def cleanup_test_files():
    """テスト後のファイルクリーンアップ"""
    yield
    # テスト用に作成されたファイルを削除
    test_dirs = ['./test_cost_data', './test_backups', './test_logs']
    for test_dir in test_dirs:
        if os.path.exists(test_dir):
            shutil.rmtree(test_dir)