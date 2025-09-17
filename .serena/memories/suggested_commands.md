# Suggested Commands for Nocturnal Agent Development

## Development Setup Commands
```bash
# Install the project in development mode
pip install -e .

# Install development dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install
```

## Testing Commands
```bash
# Run all tests with coverage
python run_tests.py

# Run specific test types
python run_tests.py --type unit          # Unit tests only
python run_tests.py --type integration   # Integration tests only
python run_tests.py --type specific --test-path tests/unit/test_models.py

# Run tests with verbose output
python run_tests.py --verbose

# Check test requirements only
python run_tests.py --check-only

# Alternative pytest commands
pytest                                   # All tests
pytest tests/unit/ -m "unit"            # Unit tests
pytest tests/integration/ -m "integration"  # Integration tests
pytest --cov=src/nocturnal_agent --cov-report=html  # Coverage report
```

## Code Quality Commands
```bash
# Format code
black src/ tests/

# Sort imports
isort src/ tests/

# Run all formatting together
black src/ tests/ && isort src/ tests/

# Type checking
mypy src/

# Linting
flake8 src/ tests/
```

## Application Commands
```bash
# Nocturnal Agent CLI commands
nocturnal init                           # Initialize configuration
nocturnal status                         # Check system status
nocturnal config-check                   # Validate configuration

# Night execution
nocturnal start                          # Standard execution
nocturnal start --use-spec-kit --spec-type feature    # Spec Kit driven
nocturnal night-run --dry-run           # Test run
nocturnal night-run                     # Actual execution

# Task management
nocturnal add-task -t "Fix bug" -p high  # Add task
nocturnal add-task                       # Interactive task entry

# Spec Kit management
nocturnal spec create --type feature --title "User Auth"
nocturnal spec list
nocturnal spec show <spec-file>
nocturnal spec validate <spec-file>
```

## Practical Usage Command
```bash
# Run a practical test task
python run_nocturnal_task.py
```

## Git Commands (Darwin/macOS specific)
```bash
# Standard git operations
git status
git add .
git commit -m "commit message"
git push origin main

# Check git status and diff in parallel
git status & git diff

# Find files (use find on Darwin)
find . -name "*.py" -type f
find . -path "./src/*" -name "*.py"

# Grep for patterns (use grep on Darwin)
grep -r "pattern" src/
grep -n "TODO" src/**/*.py
```

## System Commands (Darwin/macOS)
```bash
# List directories and files
ls -la
ls -la src/

# Change directory
cd src/nocturnal_agent

# File operations
cat filename.py                         # View file contents
head -20 filename.py                    # First 20 lines
tail -20 filename.py                    # Last 20 lines
```

## Log Monitoring
```bash
# View execution logs
tail -f logs/nocturnal-agent.log

# View interaction logs
ls logs/interactions/
cat logs/interactions/interaction_report_*.md
```

## Configuration Commands
```bash
# Check configuration files
ls config/
cat config/nocturnal_config.yaml
cat config/nocturnal-agent.yaml

# Validate configuration
nocturnal config-check
```

## System Monitoring
```bash
# System resource monitoring
top                                      # Process monitoring
ps aux | grep python                    # Python processes
df -h                                    # Disk usage
free -h                                  # Memory usage (if available on Darwin)
```

## Package Management
```bash
# Install specific packages
pip install package_name

# List installed packages
pip list

# Check package versions
pip show package_name

# Update packages
pip install --upgrade package_name
```

## Clean-up Commands
```bash
# Remove Python cache files
find . -name "__pycache__" -type d -exec rm -rf {} +
find . -name "*.pyc" -delete

# Remove coverage reports
rm -rf htmlcov/
rm coverage.xml

# Clean test artifacts
rm -rf .pytest_cache/
```

## Development Workflow Commands
```bash
# Complete development cycle
black src/ tests/ && isort src/ tests/ && mypy src/ && python run_tests.py

# Quick check before commit
python run_tests.py --type unit && mypy src/

# Full validation before release
python run_tests.py && mypy src/ && flake8 src/ tests/
```