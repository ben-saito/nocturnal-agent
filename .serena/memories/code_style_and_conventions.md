# Code Style and Conventions

## Code Formatting
- **Black**: Line length 88 characters, target Python 3.9+
- **isort**: Black-compatible profile with multi-line output style 3
- **File encoding**: UTF-8 with Japanese comments and docstrings supported

## Type Hints and Validation
- **Required**: All function definitions must have type hints (`mypy` with `disallow_untyped_defs = true`)
- **Runtime validation**: Use `pydantic` models for data validation
- **Type checking**: `mypy` targeting Python 3.9 with strict configuration
- **Return types**: Always specify return types, use `-> None` for functions without return

## Documentation Style
- **Docstrings**: Japanese language docstrings are used throughout the codebase
- **Class documentation**: Brief Japanese description of class purpose
- **Method documentation**: Japanese descriptions of method functionality
- **Example**: `"""夜間自律開発システム メインクラス"""`

## Naming Conventions
- **Classes**: PascalCase (e.g., `NocturnalAgent`, `TaskPriority`)
- **Functions/Methods**: snake_case (e.g., `start_autonomous_session`, `_initialize_components`)
- **Variables**: snake_case (e.g., `session_id`, `workspace_path`)
- **Constants**: UPPER_SNAKE_CASE (e.g., `DEFAULT_QUALITY_THRESHOLD`)
- **Private methods**: Leading underscore (e.g., `_finalize_session`)

## Code Organization
- **Package structure**: Follows `src/` layout with `src/nocturnal_agent/` as main package
- **Module organization**: Feature-based modules (agents, engines, scheduler, safety, etc.)
- **Import style**: Absolute imports preferred, relative imports for internal module references

## Async/Await Patterns
- **Async-first design**: Core functionality uses async/await patterns
- **Method signatures**: `async def` for I/O bound operations
- **Error handling**: Try/except blocks with proper async exception handling
- **Example**: `async def start_autonomous_session(...) -> str:`

## Error Handling
- **Structured logging**: Use `structlog` for all logging with Japanese messages
- **Exception patterns**: Catch specific exceptions, log with context
- **Error messages**: Japanese error messages in logs with English technical details in code
- **Example**: `self.logger.log_error("session_execution_error", f"セッション実行エラー: {e}")`

## Configuration Management
- **Pydantic models**: All configuration classes inherit from `BaseModel`
- **YAML configuration**: Configuration files in YAML format with validation
- **Environment variables**: Support for environment variable overrides
- **Type safety**: Full type checking for configuration values

## Data Models
- **Enums**: Use Python enums for status and type definitions (e.g., `TaskStatus`, `AgentType`)
- **Pydantic models**: All data classes use Pydantic for validation
- **Immutability**: Prefer immutable data structures where possible
- **Example structures**: `Task`, `ExecutionResult`, `QualityScore`, `ProjectContext`

## Testing Conventions
- **Test organization**: Separate `unit/` and `integration/` test directories
- **Test markers**: Use pytest markers (unit, integration, slow, asyncio, safety, cost, parallel, quality)
- **Coverage requirements**: 80% minimum coverage (`--cov-fail-under=80`)
- **Async testing**: Use `pytest-asyncio` with `asyncio_mode = auto`

## Logging Standards
- **Structured logging**: Use `StructuredLogger` class with Japanese messages
- **Log levels**: INFO for normal operations, WARNING for issues, ERROR for failures
- **Session tracking**: Include `session_id` in all relevant log entries
- **Extra data**: Include contextual information in `extra_data` parameter

## Git and Version Control
- **Branch isolation**: All work done in dedicated branches
- **Commit messages**: Include both English and Japanese descriptions
- **Safety commits**: Automatic backups before significant operations
- **Quality gates**: 0.85+ quality threshold for automatic merging

## Performance Considerations
- **Resource limits**: CPU 80%, Memory 8GB limits enforced
- **Async operations**: Use async file I/O with `aiofiles`
- **Parallel execution**: Support up to 5 concurrent branches
- **Monitoring**: Use `psutil` for system resource monitoring