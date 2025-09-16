"""Core data models for the Nocturnal Agent system."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from uuid import uuid4

from pydantic import BaseModel, Field


class TaskPriority(Enum):
    """Task priority levels."""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class TaskStatus(Enum):
    """Task execution status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentType(Enum):
    """Types of coding agents."""
    CLAUDE_CODE = "claude_code"
    GITHUB_COPILOT = "github_copilot"
    OPENAI_CODEX = "openai_codex"
    LOCAL_LLM = "local_llm"
    CURSOR = "cursor"


@dataclass
class QualityScore:
    """Quality assessment score for generated code."""
    overall: float = 0.0  # 0.0-1.0
    code_quality: float = 0.0
    consistency: float = 0.0
    test_coverage: float = 0.0
    security: float = 0.0
    performance: float = 0.0
    
    def is_acceptable(self, threshold: float = 0.85) -> bool:
        """Check if quality score meets threshold."""
        return self.overall >= threshold


@dataclass
class CodePattern:
    """Represents a code pattern extracted from the codebase."""
    name: str
    pattern_type: str  # naming, structure, architecture, etc.
    description: str
    examples: List[str] = field(default_factory=list)
    confidence: float = 0.0
    usage_count: int = 0
    project_specific: bool = True


@dataclass
class ConsistencyRule:
    """Rules for maintaining code consistency."""
    rule_id: str
    name: str
    description: str
    pattern: str  # regex or other pattern
    severity: str  # error, warning, info
    auto_fixable: bool = False
    fix_suggestion: Optional[str] = None


@dataclass
class HistoryEntry:
    """Development history entry."""
    timestamp: datetime
    action: str
    description: str
    success: bool
    quality_score: Optional[QualityScore] = None
    agent_used: Optional[AgentType] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Lesson:
    """Learning from success or failure."""
    lesson_id: str
    title: str
    description: str
    category: str  # success_pattern, failure_analysis, improvement
    applicable_patterns: List[str] = field(default_factory=list)
    confidence: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)
    usage_count: int = 0


@dataclass
class SuccessPattern:
    """Pattern of successful implementations."""
    pattern_id: str
    name: str
    description: str
    implementation_steps: List[str] = field(default_factory=list)
    quality_metrics: Dict[str, float] = field(default_factory=dict)
    applicable_contexts: List[str] = field(default_factory=list)
    success_rate: float = 0.0


@dataclass
class ProjectContext:
    """Context information for a specific project."""
    project_name: str
    patterns: List[CodePattern] = field(default_factory=list)
    consistency_rules: List[ConsistencyRule] = field(default_factory=list)
    development_history: List[HistoryEntry] = field(default_factory=list)
    lessons_learned: List[Lesson] = field(default_factory=list)
    success_patterns: List[SuccessPattern] = field(default_factory=list)
    
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def update_timestamp(self) -> None:
        """Update the last modified timestamp."""
        self.updated_at = datetime.now()


@dataclass
class Task:
    """Represents a development task to be executed."""
    id: str = field(default_factory=lambda: str(uuid4()))
    description: str = ""
    priority: TaskPriority = TaskPriority.MEDIUM
    estimated_quality: float = 0.0
    project_context: Optional[ProjectContext] = None
    requirements: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Execution context
    working_directory: Optional[str] = None
    target_files: List[str] = field(default_factory=list)
    branch_name: Optional[str] = None
    
    # Quality requirements
    minimum_quality_threshold: float = 0.85
    consistency_threshold: float = 0.85
    
    def start_execution(self) -> None:
        """Mark task as started."""
        self.status = TaskStatus.IN_PROGRESS
        self.started_at = datetime.now()
    
    def complete_execution(self, success: bool = True) -> None:
        """Mark task as completed or failed."""
        self.status = TaskStatus.COMPLETED if success else TaskStatus.FAILED
        self.completed_at = datetime.now()


@dataclass
class ExecutionResult:
    """Result of task execution."""
    task_id: str
    success: bool
    quality_score: QualityScore
    generated_code: str = ""
    agent_used: AgentType = AgentType.LOCAL_LLM
    execution_time: float = 0.0
    improvements_made: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    
    # File changes
    files_modified: List[str] = field(default_factory=list)
    files_created: List[str] = field(default_factory=list)
    files_deleted: List[str] = field(default_factory=list)
    
    # Git information
    commit_hash: Optional[str] = None
    branch_name: Optional[str] = None
    
    # Cost tracking
    api_calls_made: int = 0
    cost_incurred: float = 0.0
    
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class ConsistencyScore:
    """Score for code consistency evaluation."""
    overall: float = 0.0  # 0.0-1.0
    naming_conventions: float = 0.0
    code_structure: float = 0.0
    documentation: float = 0.0
    architecture_alignment: float = 0.0
    
    violations: List[Dict[str, Any]] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    
    def is_acceptable(self, threshold: float = 0.85) -> bool:
        """Check if consistency score meets threshold."""
        return self.overall >= threshold


@dataclass
class Violation:
    """Represents a consistency or quality violation."""
    violation_id: str
    rule_id: str
    severity: str
    message: str
    file_path: str
    line_number: Optional[int] = None
    suggestion: Optional[str] = None
    auto_fixable: bool = False


@dataclass
class Correction:
    """Represents a suggested correction for a violation."""
    violation_id: str
    original_code: str
    corrected_code: str
    explanation: str
    confidence: float = 0.0


class TaskAnalysis(BaseModel):
    """Analysis result for a task before execution."""
    task_id: str
    complexity_score: float = Field(ge=0.0, le=1.0)
    estimated_duration: float  # in minutes
    risk_level: str = Field(pattern="^(low|medium|high|critical)$")
    required_agent_capabilities: List[str] = Field(default_factory=list)
    dependencies: List[str] = Field(default_factory=list)
    success_probability: float = Field(ge=0.0, le=1.0)
    recommended_agent: AgentType = AgentType.LOCAL_LLM
    execution_strategy: str = ""
    
    class Config:
        """Pydantic config."""
        use_enum_values = True


class FailureInfo(BaseModel):
    """Information about a failed execution."""
    task_id: str
    agent_used: AgentType
    error_type: str
    error_message: str
    stack_trace: Optional[str] = None
    failed_at: datetime = Field(default_factory=datetime.now)
    retry_count: int = 0
    context: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        """Pydantic config."""
        use_enum_values = True


class ImprovementPlan(BaseModel):
    """Plan for improving failed execution."""
    task_id: str
    failure_analysis: str
    root_cause: str
    improvement_steps: List[str] = Field(default_factory=list)
    estimated_success_probability: float = Field(ge=0.0, le=1.0)
    recommended_changes: Dict[str, Any] = Field(default_factory=dict)
    should_retry: bool = True
    alternative_approach: Optional[str] = None