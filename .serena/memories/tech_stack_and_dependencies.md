# Tech Stack and Dependencies

## Core Technology Stack
- **Python**: 3.9+ (supports 3.9, 3.10, 3.11, 3.12)
- **Build System**: setuptools with wheel
- **Package Management**: pip with pyproject.toml configuration

## Core Dependencies
- **pydantic**: >=2.0.0 - Data validation and modeling
- **pyyaml**: >=6.0 - YAML configuration file handling
- **aiofiles**: >=23.0.0 - Asynchronous file operations
- **asyncio-tools**: >=0.4.0 - Enhanced asyncio utilities
- **click**: >=8.0.0 - Command-line interface framework
- **python-dateutil**: >=2.8.0 - Date and time manipulation
- **psutil**: >=5.9.0 - System and process monitoring
- **structlog**: >=23.0.0 - Structured logging
- **rich**: >=13.0.0 - Terminal output formatting and display
- **gitpython**: >=3.1.0 - Git repository manipulation

## Development Dependencies
- **pytest**: >=7.0.0 - Testing framework
- **pytest-asyncio**: >=0.21.0 - Async testing support
- **pytest-cov**: >=4.0.0 - Code coverage reporting
- **black**: >=23.0.0 - Code formatting
- **isort**: >=5.12.0 - Import sorting
- **flake8**: >=6.0.0 - Code linting
- **mypy**: >=1.0.0 - Static type checking
- **pre-commit**: >=3.0.0 - Pre-commit hooks

## External Tools Integration
- **LM Studio**: Local LLM hosting (recommended: CodeLlama 13B)
- **Claude Code CLI**: AI coding assistance
- **GitHub Copilot**: Code completion (future integration)
- **Obsidian**: Knowledge base management
- **Git**: Version control system

## Static Analysis Tools
- **pylint**: Python code analysis
- **flake8**: Style and error checking
- **mypy**: Type checking

## Configuration Tools
- **black**: Line length 88, target Python 3.9
- **isort**: Black-compatible profile, multi-line output 3
- **mypy**: Python 3.9 target, strict type checking enabled
- **pytest**: Coverage reporting, async mode auto

## Operating System Support
- **Primary**: Darwin (macOS) 
- **Secondary**: Linux, Windows (via WSL recommended)

## Key Features of Dependencies
- **Async-first design**: Heavy use of asyncio, aiofiles, asyncio-tools
- **Type safety**: pydantic for runtime validation, mypy for static checking
- **Structured logging**: structlog for machine-readable logs
- **CLI excellence**: click for command-line interfaces, rich for beautiful terminal output
- **Git integration**: GitPython for repository operations
- **System monitoring**: psutil for resource tracking and safety limits