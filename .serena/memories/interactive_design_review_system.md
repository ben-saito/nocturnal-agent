# Interactive Design Review System Implementation Plan

## User Request
"ユーザーからタスクを取得したら設計書をそのタイミングで作成し、レビューしてもらい、対和式インターフェースでやり取りでフィードバック、修正を行なった上で、タスク実行を夜中に実行する様な動きにしたいです。"

Translation: Create design documents immediately when task is received, have user review them, enable interactive dialogue-based feedback and modifications, then execute the task at nighttime.

## System Design

### 1. Interactive Design Review Workflow
- **Immediate Design Generation**: Upon task receipt, immediately generate comprehensive design documents
- **Interactive Review Interface**: Present design to user with structured feedback options
- **Dialogue-Based Modifications**: Enable real-time conversation about design changes
- **Approval Gate**: Require explicit user approval before scheduling execution
- **Nighttime Execution**: Schedule approved tasks for automated nighttime execution

### 2. Key Components

**Interactive Review Manager** (`src/nocturnal_agent/review/interactive_review_manager.py`)
- Manages the entire review workflow
- Coordinates between design generation and user interaction
- Tracks review status and approval states

**Design Document Generator** (`src/nocturnal_agent/design/design_document_generator.py`)
- Creates comprehensive design documents immediately upon task receipt
- Utilizes existing AI collaboration system for high-quality design generation
- Formats designs for interactive review

**Dialogue Interface** (`src/nocturnal_agent/interface/dialogue_interface.py`)
- Provides conversational interface for design feedback
- Handles structured feedback collection
- Enables iterative design modifications

**Task Scheduler** (`src/nocturnal_agent/scheduler/task_scheduler.py`)
- Manages task scheduling for nighttime execution
- Integrates with system cron/scheduling capabilities
- Provides execution status tracking

### 3. Workflow States
1. **DESIGN_PENDING**: Task received, design generation in progress
2. **REVIEW_READY**: Design complete, awaiting user review
3. **REVIEW_IN_PROGRESS**: User actively reviewing and providing feedback
4. **MODIFICATIONS_NEEDED**: User requested changes, design being updated
5. **APPROVED**: Design approved by user, ready for scheduling
6. **SCHEDULED**: Task scheduled for nighttime execution
7. **EXECUTING**: Task currently being executed
8. **COMPLETED**: Task execution finished

### 4. Integration Points
- Extends existing SpecDrivenExecutor with review workflow
- Utilizes AI Collaborative Spec Generator for design creation
- Integrates with existing quality assurance system
- Maintains compatibility with current command structure

## Implementation Strategy
1. Create core review workflow infrastructure
2. Implement interactive dialogue interface
3. Build task scheduling system
4. Integrate with existing execution pipeline
5. Add comprehensive logging and status tracking