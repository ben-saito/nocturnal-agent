"""Unit tests for core data models."""

import pytest
from datetime import datetime
from uuid import UUID

from nocturnal_agent.core.models import (
    Task, TaskPriority, TaskStatus, QualityScore, ExecutionResult,
    ProjectContext, CodePattern, ConsistencyRule, AgentType
)


class TestQualityScore:
    """Test QualityScore model."""
    
    def test_quality_score_creation(self):
        """Test creating a QualityScore instance."""
        score = QualityScore(
            overall=0.85,
            code_quality=0.8,
            consistency=0.9,
            test_coverage=0.7,
            security=0.95,
            performance=0.8
        )
        
        assert score.overall == 0.85
        assert score.code_quality == 0.8
        assert score.consistency == 0.9
        assert score.test_coverage == 0.7
        assert score.security == 0.95
        assert score.performance == 0.8
    
    def test_quality_score_acceptable(self):
        """Test quality score acceptance logic."""
        good_score = QualityScore(overall=0.85)
        bad_score = QualityScore(overall=0.70)
        
        assert good_score.is_acceptable()
        assert not bad_score.is_acceptable()
        assert bad_score.is_acceptable(threshold=0.65)


class TestTask:
    """Test Task model."""
    
    def test_task_creation(self):
        """Test creating a Task instance."""
        task = Task(
            description="Test task",
            priority=TaskPriority.HIGH,
            requirements=["Python", "Git"],
            constraints=["No external dependencies"]
        )
        
        assert task.description == "Test task"
        assert task.priority == TaskPriority.HIGH
        assert task.status == TaskStatus.PENDING
        assert task.requirements == ["Python", "Git"]
        assert task.constraints == ["No external dependencies"]
        assert isinstance(UUID(task.id), UUID)  # Valid UUID
    
    def test_task_execution_lifecycle(self):
        """Test task execution state changes."""
        task = Task(description="Test task")
        
        # Initial state
        assert task.status == TaskStatus.PENDING
        assert task.started_at is None
        assert task.completed_at is None
        
        # Start execution
        task.start_execution()
        assert task.status == TaskStatus.IN_PROGRESS
        assert task.started_at is not None
        assert isinstance(task.started_at, datetime)
        
        # Complete execution successfully
        task.complete_execution(success=True)
        assert task.status == TaskStatus.COMPLETED
        assert task.completed_at is not None
        assert isinstance(task.completed_at, datetime)
    
    def test_task_execution_failure(self):
        """Test task execution failure."""
        task = Task(description="Test task")
        task.start_execution()
        task.complete_execution(success=False)
        
        assert task.status == TaskStatus.FAILED
        assert task.completed_at is not None


class TestExecutionResult:
    """Test ExecutionResult model."""
    
    def test_execution_result_creation(self):
        """Test creating an ExecutionResult instance."""
        quality_score = QualityScore(overall=0.85)
        
        result = ExecutionResult(
            task_id="test-task-123",
            success=True,
            quality_score=quality_score,
            generated_code="print('Hello, World!')",
            agent_used=AgentType.CLAUDE_CODE,
            execution_time=45.5,
            improvements_made=["Added type hints", "Improved documentation"],
            files_modified=["main.py", "utils.py"]
        )
        
        assert result.task_id == "test-task-123"
        assert result.success is True
        assert result.quality_score == quality_score
        assert result.generated_code == "print('Hello, World!')"
        assert result.agent_used == AgentType.CLAUDE_CODE
        assert result.execution_time == 45.5
        assert len(result.improvements_made) == 2
        assert len(result.files_modified) == 2
        assert isinstance(result.created_at, datetime)


class TestProjectContext:
    """Test ProjectContext model."""
    
    def test_project_context_creation(self):
        """Test creating a ProjectContext instance."""
        pattern = CodePattern(
            name="Function naming",
            pattern_type="naming",
            description="Use snake_case for functions",
            examples=["def my_function():", "def process_data():"],
            confidence=0.9
        )
        
        rule = ConsistencyRule(
            rule_id="naming-001",
            name="Function naming rule",
            description="Functions must use snake_case",
            pattern=r"^[a-z_][a-z0-9_]*$",
            severity="error",
            auto_fixable=True
        )
        
        context = ProjectContext(
            project_name="test-project",
            patterns=[pattern],
            consistency_rules=[rule]
        )
        
        assert context.project_name == "test-project"
        assert len(context.patterns) == 1
        assert len(context.consistency_rules) == 1
        assert context.patterns[0] == pattern
        assert context.consistency_rules[0] == rule
        assert isinstance(context.created_at, datetime)
        assert isinstance(context.updated_at, datetime)
    
    def test_project_context_update_timestamp(self):
        """Test timestamp update functionality."""
        context = ProjectContext(project_name="test")
        original_time = context.updated_at
        
        # Small delay to ensure timestamp difference
        import time
        time.sleep(0.01)
        
        context.update_timestamp()
        assert context.updated_at > original_time


class TestCodePattern:
    """Test CodePattern model."""
    
    def test_code_pattern_creation(self):
        """Test creating a CodePattern instance."""
        pattern = CodePattern(
            name="Class naming",
            pattern_type="naming",
            description="Use PascalCase for classes",
            examples=["class MyClass:", "class DataProcessor:"],
            confidence=0.95,
            usage_count=10,
            project_specific=True
        )
        
        assert pattern.name == "Class naming"
        assert pattern.pattern_type == "naming"
        assert pattern.description == "Use PascalCase for classes"
        assert len(pattern.examples) == 2
        assert pattern.confidence == 0.95
        assert pattern.usage_count == 10
        assert pattern.project_specific is True


class TestConsistencyRule:
    """Test ConsistencyRule model."""
    
    def test_consistency_rule_creation(self):
        """Test creating a ConsistencyRule instance."""
        rule = ConsistencyRule(
            rule_id="import-001",
            name="Import organization",
            description="Imports should be organized by type",
            pattern=r"^import\s+\w+",
            severity="warning",
            auto_fixable=True,
            fix_suggestion="Organize imports using isort"
        )
        
        assert rule.rule_id == "import-001"
        assert rule.name == "Import organization"
        assert rule.description == "Imports should be organized by type"
        assert rule.pattern == r"^import\s+\w+"
        assert rule.severity == "warning"
        assert rule.auto_fixable is True
        assert rule.fix_suggestion == "Organize imports using isort"


if __name__ == "__main__":
    pytest.main([__file__])