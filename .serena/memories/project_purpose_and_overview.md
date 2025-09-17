# Nocturnal Agent - Project Purpose and Overview

## Project Purpose
Nocturnal Agent is an autonomous night development system that performs coding tasks automatically during nighttime hours (22:00-06:00). It's designed to let developers' code write itself while they sleep, using local LLM orchestration with multi-agent coordination for cost-effective and safe automated coding.

## Key Features
- **Night Automation**: Automatic execution during 22:00-06:00 window
- **Multi-Agent Orchestration**: Coordinates Claude Code, GitHub Copilot, and other coding agents
- **Local LLM Intelligence**: Uses LM Studio for cost-effective task planning and quality assessment
- **Quality Assurance**: Maintains 0.85+ quality threshold with 3-cycle improvement system
- **Safety First**: Automatic backups, dangerous command blocking, resource limits
- **Learning System**: Obsidian-based knowledge accumulation for project-specific patterns
- **Cost Control**: $10/month budget with 90%+ free tool preference
- **Parallel Execution**: Up to 5 concurrent branches based on quality confidence
- **GitHub Spec Kit Integration**: Optional spec-driven development when explicitly requested

## System Architecture
The system consists of several key components:
- **Night Scheduler**: Manages timing and execution windows
- **Local LLM Agent**: Provides intelligence for task planning and quality assessment
- **Multi-Agent Coordination**: Integrates with Claude Code, GitHub Copilot and other agents
- **Consistency Engine**: Ensures code consistency and quality
- **Quality Assessment**: Evaluates and improves code quality
- **Obsidian Knowledge Base**: Accumulates project-specific patterns and learning
- **Git Management & Backup**: Handles version control and safety backups
- **Safety Coordinator**: Manages security and resource limits
- **Cost Manager**: Tracks and optimizes API usage costs
- **Parallel Executor**: Manages concurrent development branches

## Current Implementation Status
The system has completed 12 major tasks including:
1. Project foundation and core interfaces
2. Local LLM Agent implementation
3. CLI coding agent integration system
4. Consistency engine implementation
5. Obsidian integration system
6. Quality improvement cycle implementation
7. Night scheduler implementation
8. Safety and backup system implementation
9. Cost management system implementation
10. Parallel execution features
11. Test suite implementation
12. Configuration and documentation

## Technology Stack
- Python 3.9+
- LM Studio for local LLM hosting
- Claude Code CLI for intelligent coding assistance
- Obsidian for knowledge management
- GitHub Spec Kit for structured technical specifications
- Git for version control and branching
- Various static analysis tools (pylint, flake8, mypy)

## Safety Features
- Automatic backups before execution
- Resource limits (CPU 80%, Memory 8GB)
- Dangerous command blocking
- File change limits (20 files per task)
- Git branch isolation
- Quality gates (0.85+ threshold for automatic application)