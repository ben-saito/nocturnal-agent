# Development Environment Setup

## System Requirements
- **Operating System**: Darwin (macOS) - primary support
- **Python Version**: 3.9+ (supports 3.9, 3.10, 3.11, 3.12)
- **Git**: Version control system
- **LM Studio**: For local LLM hosting (recommended: CodeLlama 13B)
- **Claude Code CLI**: Must be authenticated and available in PATH

## Initial Setup Commands
```bash
# 1. Clone and enter project directory
git clone <repository-url>
cd nocturnal-agent

# 2. Install project in development mode
pip install -e .

# 3. Install development dependencies
pip install -e ".[dev]"

# 4. Install pre-commit hooks
pre-commit install

# 5. Initialize configuration
nocturnal init

# 6. Verify system status
nocturnal status
nocturnal config-check
```

## Required External Tools
### LM Studio Setup
1. Download and install LM Studio from https://lmstudio.ai/
2. Download CodeLlama 13B model (or similar code model)
3. Configure API endpoint at `http://localhost:1234/v1`
4. Update `config/nocturnal-agent.yaml` with correct model path

### Claude Code CLI Setup
1. Install Claude Code CLI following official documentation
2. Authenticate with your Anthropic account
3. Verify with: `claude --version`
4. Ensure it's available in PATH

## Directory Structure Verification
After setup, verify these directories exist:
```bash
ls -la config/          # Configuration files
ls -la logs/            # Log directory (created automatically)
ls -la tests/           # Test suite
ls -la src/             # Source code
ls -la knowledge-vault/ # Obsidian vault (created automatically)
```

## Development Tools Configuration

### Code Formatting Tools
- **Black**: Pre-configured for 88-character line length
- **isort**: Configured for Black compatibility
- **Pre-commit**: Automatically runs formatting on commit

### Type Checking
- **mypy**: Configured for strict type checking
- **Target**: Python 3.9+ with `disallow_untyped_defs = true`

### Testing Framework
- **pytest**: Main testing framework
- **pytest-asyncio**: For async test support
- **pytest-cov**: For coverage reporting
- **Coverage target**: Minimum 80%

## Environment Variables (Optional)
```bash
# Override configuration via environment variables
export NOCTURNAL_LLM_API_URL="http://localhost:1234/v1"
export NOCTURNAL_PROJECT_NAME="my-project"
export NOCTURNAL_DEBUG_MODE="true"
```

## IDE Setup Recommendations

### VS Code Extensions
- Python extension pack
- Black formatter
- isort extension
- mypy type checker
- Pytest integration

### Configuration Files
- `.vscode/settings.json`: Configure formatting and linting
- `.vscode/launch.json`: Debug configuration for Python

## Common Development Commands
```bash
# Quick development cycle
black src/ tests/ && isort src/ tests/ && mypy src/ && python run_tests.py

# Run specific test categories
python run_tests.py --type unit
python run_tests.py --type integration

# Check code quality
flake8 src/ tests/

# View test coverage
python run_tests.py && open htmlcov/index.html
```

## Troubleshooting Common Issues

### Import Errors
- Ensure all directories have `__init__.py` files
- Check Python path includes project root
- Verify package installation with `pip list`

### Type Checking Errors
- Run `mypy src/` to see all type issues
- Add type hints to all function definitions
- Use `typing` module for complex types

### Test Failures
- Check test output for specific errors
- Verify async test setup with `pytest-asyncio`
- Check test fixtures in `tests/conftest.py`

### Configuration Issues
- Run `nocturnal config-check` to validate configuration
- Check YAML syntax in configuration files
- Verify file permissions on config directory

### External Tool Issues
- **LM Studio**: Ensure it's running and accessible at configured URL
- **Claude Code CLI**: Verify authentication with `claude status`
- **Git**: Ensure repository is properly initialized

## Performance Optimization

### Local Development
- Use local LLM for development to avoid API costs
- Enable debug mode for detailed logging
- Set lower quality thresholds for faster iteration

### Resource Monitoring
- Monitor CPU usage (limit: 80%)
- Monitor memory usage (limit: 8GB)
- Use `top` or Activity Monitor to track resource usage

## Safety Considerations

### Development Safety
- Always work in feature branches
- Enable backup systems during development
- Use dry-run mode for testing dangerous operations
- Verify dangerous command blocking is active

### Data Safety
- Regular backups of configuration and data
- Version control for all code changes
- Separate development and production configurations