# Project Structure

## Root Directory Structure
```
nocturnal-agent/
├── src/nocturnal_agent/           # Main source code
├── tests/                         # Test suite
├── config/                        # Configuration files
├── docs/                          # Documentation (future)
├── knowledge-vault/               # Obsidian knowledge base
├── logs/                          # Log files and interaction reports
├── nocturnal_output/              # Generated output files
├── reports/                       # Generated reports
├── specs/                         # GitHub Spec Kit specifications
├── data/                          # Data files
├── .kiro/                         # Kiro tool configuration
├── .nocturnal/                    # Nocturnal internal files
├── .nocturnal_backups/            # Safety backups
├── .serena/                       # Serena tool configuration
├── .specstory/                    # Spec story configuration
├── pyproject.toml                 # Python project configuration
├── pytest.ini                    # Pytest configuration
├── run_tests.py                   # Test execution script
├── run_nocturnal_task.py          # Practical usage script
├── README.md                      # Project documentation
└── nocturnal                      # CLI entry point
```

## Source Code Structure (`src/nocturnal_agent/`)
```
src/nocturnal_agent/
├── __init__.py                    # Package initialization
├── main.py                        # Main NocturnalAgent class
├── cli.py                         # CLI entry point
├── core/                          # Core models and interfaces
│   ├── __init__.py
│   ├── config.py                  # Configuration classes
│   └── models.py                  # Data models and enums
├── agents/                        # Agent implementations
│   ├── __init__.py
│   ├── local_llm.py              # Local LLM agent
│   ├── claude_agent.py           # Claude Code integration
│   ├── cli_executor.py           # CLI agent executor
│   ├── agent_detector.py         # Agent detection and selection
│   └── future_agents.py          # Future agent implementations
├── engines/                       # Processing engines
│   ├── __init__.py
│   ├── consistency_engine.py     # Code consistency checking
│   ├── unified_consistency_engine.py  # Unified consistency system
│   ├── quality_evaluator.py      # Quality assessment
│   ├── pattern_extractor.py      # Pattern extraction
│   └── learning_engine.py        # Learning and improvement
├── scheduler/                     # Scheduling system
│   ├── __init__.py
│   ├── night_scheduler.py        # Main night scheduler
│   ├── time_controller.py        # Time management
│   ├── task_queue.py             # Task queue management
│   └── resource_monitor.py       # Resource monitoring
├── safety/                        # Safety mechanisms
│   ├── __init__.py
│   ├── safety_coordinator.py     # Main safety coordinator
│   ├── backup_manager.py         # Backup management
│   ├── rollback_manager.py       # Rollback functionality
│   └── danger_detector.py        # Dangerous operation detection
├── cost/                          # Cost management
│   ├── __init__.py
│   ├── cost_manager.py           # Cost tracking and limits
│   ├── usage_tracker.py          # API usage tracking
│   └── cost_optimizer.py         # Cost optimization
├── parallel/                      # Parallel execution
│   ├── __init__.py
│   ├── parallel_executor.py      # Parallel execution manager
│   ├── branch_manager.py         # Git branch management
│   └── quality_controller.py     # Quality-based control
├── quality/                       # Quality management
│   ├── __init__.py
│   ├── quality_manager.py        # Quality assessment manager
│   ├── improvement_cycle.py      # Quality improvement cycles
│   ├── approval_queue.py         # Manual approval queue
│   └── failure_analyzer.py       # Failure analysis
├── obsidian/                      # Obsidian integration
│   ├── __init__.py
│   ├── obsidian_integration.py   # Main Obsidian integration
│   ├── vault_manager.py          # Vault management
│   ├── knowledge_retriever.py    # Knowledge retrieval
│   └── context_manager.py        # Context management
├── reporting/                     # Report generation
│   ├── __init__.py
│   └── report_generator.py       # Report generation system
├── config/                        # Configuration management
│   ├── __init__.py
│   └── config_manager.py         # Configuration management
├── cli/                           # CLI components
│   ├── __init__.py
│   └── main.py                    # CLI implementation
├── design/                        # Design systems
│   ├── __init__.py
│   └── spec_kit_integration.py   # GitHub Spec Kit integration
├── execution/                     # Execution systems
│   ├── __init__.py
│   └── spec_driven_executor.py   # Spec-driven execution
└── logging/                       # Logging systems
    ├── __init__.py
    ├── structured_logger.py      # Structured logging
    └── interaction_logger.py     # Agent interaction logging
```

## Test Structure (`tests/`)
```
tests/
├── __init__.py                    # Test package initialization
├── conftest.py                    # Pytest configuration and fixtures
├── unit/                          # Unit tests
│   ├── test_core_models.py       # Core model tests
│   ├── test_config.py            # Configuration tests
│   ├── test_models.py            # Data model tests
│   ├── test_safety_systems.py    # Safety system tests
│   ├── test_parallel_execution.py # Parallel execution tests
│   └── test_cost_management.py   # Cost management tests
├── integration/                   # Integration tests
│   └── test_system_integration.py # System integration tests
└── fixtures/                      # Test fixtures and data
```

## Configuration Structure (`config/`)
```
config/
├── README.md                      # Configuration documentation
├── nocturnal-agent.yaml          # Main configuration template
├── nocturnal_config.yaml         # Runtime configuration
└── nocturnal_config.yaml.example # Example configuration
```

## Key File Relationships
- **Main entry point**: `src/nocturnal_agent/main.py` contains the `NocturnalAgent` class
- **CLI interface**: `nocturnal` script calls `src/nocturnal_agent/cli.py`
- **Configuration**: Managed by `src/nocturnal_agent/config/config_manager.py`
- **Models**: Core data structures in `src/nocturnal_agent/core/models.py`
- **Testing**: `run_tests.py` provides unified test execution
- **Practical usage**: `run_nocturnal_task.py` demonstrates real-world usage

## Generated Directories
- **logs/**: Contains execution logs and interaction reports
- **nocturnal_output/**: Generated code and output files
- **reports/**: HTML and other generated reports
- **knowledge-vault/**: Obsidian vault with project knowledge
- **.nocturnal_backups/**: Safety backups before major operations

## Special Files
- **pyproject.toml**: Python project configuration with dependencies and tools
- **pytest.ini**: Comprehensive pytest configuration with Japanese comments
- **.gitignore**: Standard Python gitignore with project-specific additions
- **README.md**: Bilingual (English/Japanese) project documentation