# Task Completion Workflow

## Standard Development Workflow

### 1. Before Starting Development
```bash
# Check system status
nocturnal status

# Validate configuration
nocturnal config-check

# Ensure development environment is ready
pip install -e ".[dev]"
```

### 2. Code Development Process
```bash
# Create/switch to feature branch
git checkout -b feature/new-feature

# Write code following project conventions
# - Use Japanese docstrings
# - Follow type hints requirements
# - Use async/await patterns where appropriate
# - Follow naming conventions (snake_case, PascalCase)
```

### 3. Code Quality Checks (MANDATORY)
```bash
# Format code
black src/ tests/

# Sort imports
isort src/ tests/

# Type checking (REQUIRED - must pass)
mypy src/

# Linting
flake8 src/ tests/
```

### 4. Testing (REQUIRED)
```bash
# Run all tests with coverage
python run_tests.py

# Ensure minimum 80% coverage
# Tests must pass before proceeding

# For specific test types:
python run_tests.py --type unit
python run_tests.py --type integration
```

### 5. Pre-commit Validation
```bash
# Run the complete validation cycle
black src/ tests/ && isort src/ tests/ && mypy src/ && python run_tests.py

# This must complete successfully before commit
```

### 6. Commit Process
```bash
# Add changes
git add .

# Commit with descriptive message (bilingual preferred)
git commit -m "feat: add new feature / 新機能追加"

# Push to feature branch
git push origin feature/new-feature
```

## Quality Assurance Requirements

### Mandatory Checks
1. **Type checking**: `mypy src/` must pass with no errors
2. **Code formatting**: `black` and `isort` must be applied
3. **Test coverage**: Minimum 80% coverage required
4. **All tests**: Must pass unit and integration tests
5. **Linting**: `flake8` should show minimal warnings

### Quality Standards
- **Overall quality threshold**: 0.85+ (85%)
- **Consistency threshold**: 0.85+ (85%)
- **Maximum improvement cycles**: 3 attempts
- **Static analysis**: pylint, flake8, mypy must all pass

## When Task is Complete

### 1. Final Validation
```bash
# Complete quality check cycle
python run_tests.py && mypy src/ && flake8 src/ tests/

# Verify all tests pass
python run_tests.py --verbose

# Check test coverage report
# HTML report available at htmlcov/index.html
```

### 2. System Integration Test
```bash
# Test the actual system if applicable
python run_nocturnal_task.py

# Check logs for any issues
tail -f logs/nocturnal-agent.log
```

### 3. Documentation Updates
- Update relevant docstrings if public API changed
- Update configuration documentation if config changed
- Update README.md if major features added

### 4. Safety Validation
- Ensure no dangerous commands introduced
- Verify resource limits respected
- Check backup mechanisms work
- Validate error handling is robust

## Spec Kit Integration Workflow

### When Using GitHub Spec Kit
```bash
# Create specification first
nocturnal spec create --type feature --title "Feature Name"

# Validate specification
nocturnal spec validate <spec-file>

# Execute with Spec Kit (default enabled)
nocturnal start --use-spec-kit --spec-type feature

# Review generated specifications
nocturnal spec list
nocturnal spec show <spec-file>
```

## Debugging and Troubleshooting

### Log Analysis
```bash
# Check main system logs
cat logs/nocturnal-agent.log

# Check interaction logs
ls logs/interactions/
cat logs/interactions/interaction_report_*.md

# Monitor real-time logs
tail -f logs/nocturnal-agent.log
```

### Common Issues Resolution
1. **Import errors**: Check `__init__.py` files exist
2. **Type errors**: Run `mypy src/` and fix all issues
3. **Test failures**: Check test output and fix root causes
4. **Configuration errors**: Run `nocturnal config-check`

## Release Preparation

### Before Release
```bash
# Full validation suite
python run_tests.py --verbose
mypy src/
flake8 src/ tests/
black --check src/ tests/
isort --check src/ tests/

# Integration test
python run_nocturnal_task.py

# System status check
nocturnal status
```

### Performance Considerations
- Verify resource limits are respected (CPU 80%, Memory 8GB)
- Check parallel execution limits (max 5 branches)
- Validate cost management thresholds
- Ensure backup mechanisms are working

## Emergency Procedures

### If Quality Check Fails
1. Review error messages carefully
2. Fix issues one by one
3. Re-run quality checks after each fix
4. Use improvement cycles (max 3) if automated

### If Tests Fail
1. Run specific failing test: `python run_tests.py --type specific --test-path <test-file>`
2. Check fixtures and test data
3. Verify async test setup is correct
4. Check for race conditions in parallel tests

### If System Integration Fails
1. Check configuration files in `config/`
2. Verify external dependencies (LM Studio, Claude Code CLI)
3. Check file permissions and directory structure
4. Review safety coordinator logs