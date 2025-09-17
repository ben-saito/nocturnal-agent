# System Design Patterns and Guidelines

## Core Design Patterns

### 1. Async-First Architecture
- **Pattern**: All I/O operations use async/await
- **Implementation**: Core classes have async methods for main operations
- **Example**: `async def start_autonomous_session()`, `async def execute_task()`
- **Rationale**: Enables concurrent operations and better resource utilization

### 2. Component Initialization Pattern
```python
def _initialize_components(self):
    """コンポーネント初期化"""
    # Initialize in dependency order
    self.logger = StructuredLogger(config)
    self.scheduler = NightScheduler(workspace, config, main_agent=self)
    self.cost_manager = CostManager(config)
    # ... etc
```

### 3. Session-Based State Management
- **Pattern**: All operations within a session context
- **Implementation**: `session_id`, `session_stats`, `session_settings`
- **Benefits**: Enables tracking, logging, and cleanup
- **Example**: Each autonomous session has unique ID and isolated state

### 4. Multi-Agent Orchestration Pattern
```python
# Agent selection and coordination
if self.session_settings['use_spec_kit']:
    result = await self.spec_executor.execute_task_with_spec(task, executor_func, spec_type)
else:
    result = await self.direct_executor.execute_task(task, executor_func)
```

### 5. Quality-Driven Execution
- **Pattern**: Quality thresholds determine automatic vs manual approval
- **Implementation**: 0.85+ threshold for auto-approval, improvement cycles for lower scores
- **Quality gates**: Multiple validation points throughout execution

### 6. Safety-First Design
- **Pattern**: Safety checks at every major operation
- **Implementation**: `SafetyCoordinator` validates all operations
- **Backup strategy**: Automatic backups before any destructive operation
- **Resource limits**: CPU, memory, and file change limits enforced

## Configuration Management Patterns

### 1. Hierarchical Configuration
```yaml
# Main config with nested sections
project_name: "nocturnal-agent"
llm:
  model_path: "models/codellama-13b"
  api_url: "http://localhost:1234/v1"
scheduler:
  start_time: "22:00"
  end_time: "06:00"
```

### 2. Pydantic Validation Pattern
```python
class ConfigSection(BaseModel):
    """Configuration section with validation"""
    field: str = Field(..., description="Required field")
    optional_field: Optional[int] = None
    
    @validator('field')
    def validate_field(cls, v):
        # Custom validation logic
        return v
```

### 3. Environment Override Pattern
- Configuration values can be overridden by environment variables
- Format: `NOCTURNAL_SECTION_FIELD` (e.g., `NOCTURNAL_LLM_API_URL`)

## Error Handling Patterns

### 1. Structured Error Logging
```python
try:
    await operation()
except Exception as e:
    self.logger.log_error(
        "operation_error",
        f"操作エラー: {e}",
        session_id=self.session_id,
        exc_info=True
    )
    raise
```

### 2. Graceful Degradation
- System continues operation when non-critical components fail
- Fallback mechanisms for external service failures
- Quality-based decision making when uncertain

### 3. Recovery Patterns
```python
for attempt in range(max_retries):
    try:
        result = await operation()
        break
    except RetryableError as e:
        if attempt == max_retries - 1:
            raise
        await asyncio.sleep(backoff_delay * (2 ** attempt))
```

## Logging and Monitoring Patterns

### 1. Structured Logging with Context
```python
self.logger.log(
    LogLevel.INFO,
    LogCategory.SYSTEM,
    "操作完了",
    session_id=self.session_id,
    task_id=task.id,
    extra_data={
        'duration': duration,
        'quality_score': score
    }
)
```

### 2. Interaction Logging Pattern
```python
# Log all agent interactions
self.interaction_logger.log_instruction(session_id, task_id, agent_type, instruction)
self.interaction_logger.log_response(session_id, task_id, agent_type, response, quality_score)
self.interaction_logger.log_approval(session_id, task_id, agent_type, response, reason)
```

### 3. Metrics Collection Pattern
- Session statistics tracking
- Quality score history
- Cost tracking and budget management
- Resource usage monitoring

## Parallel Execution Patterns

### 1. Branch-Based Parallelism
```python
# Create isolated branches for parallel work
branch_configs = [
    {'branch_name': f'parallel-{i}', 'quality_threshold': threshold}
    for i in range(max_parallel_branches)
]
```

### 2. Quality-Based Merge Strategy
- High quality (0.85+): Automatic merge
- Medium quality (0.70-0.85): Manual review
- Low quality (<0.70): Reject or improve

### 3. Resource-Aware Execution
- Monitor CPU and memory usage
- Limit concurrent operations based on available resources
- Dynamic scaling based on system load

## Integration Patterns

### 1. Plugin Architecture for Agents
```python
class AgentInterface:
    async def execute_task(self, task: Task) -> ExecutionResult:
        raise NotImplementedError
    
    def get_capabilities(self) -> List[str]:
        raise NotImplementedError
```

### 2. Spec Kit Integration Pattern
```python
if use_spec_kit:
    spec = self.spec_generator.create_spec(task, spec_type)
    validated_spec = self.spec_validator.validate(spec)
    result = await self.spec_executor.execute_with_spec(task, validated_spec)
```

### 3. Knowledge Base Integration
- Obsidian vault for persistent knowledge
- Pattern extraction and learning
- Context-aware decision making

## Testing Patterns

### 1. Async Test Pattern
```python
@pytest.mark.asyncio
async def test_async_operation():
    agent = NocturnalAgent(workspace_path)
    result = await agent.start_autonomous_session()
    assert result is not None
```

### 2. Fixture-Based Test Setup
```python
@pytest.fixture
async def nocturnal_agent():
    agent = NocturnalAgent("test_workspace")
    yield agent
    await agent.cleanup()
```

### 3. Integration Test Pattern
- Test end-to-end workflows
- Mock external dependencies
- Validate system integration points

## Security and Safety Patterns

### 1. Command Validation Pattern
```python
dangerous_commands = ["rm", "del", "format", "sudo rm"]
if any(cmd in operation for cmd in dangerous_commands):
    raise SecurityError("危険なコマンドが検出されました")
```

### 2. Resource Limit Pattern
```python
@resource_limit(cpu_percent=80, memory_gb=8)
async def execute_operation():
    # Operation with resource monitoring
    pass
```

### 3. Backup Before Modify Pattern
```python
async def modify_files(files):
    backup_id = await self.backup_manager.create_backup()
    try:
        await perform_modifications(files)
    except Exception:
        await self.backup_manager.restore_backup(backup_id)
        raise
```

## Performance Optimization Patterns

### 1. Lazy Loading Pattern
- Load components only when needed
- Defer expensive operations until required
- Cache frequently accessed data

### 2. Batch Processing Pattern
- Group similar operations together
- Minimize I/O operations
- Optimize network calls

### 3. Cost Optimization Pattern
- Prefer local LLM over API calls
- Use free tools when possible (90%+ preference)
- Track and limit API usage costs