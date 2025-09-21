"""
実装タスク管理システム
仕様書から分割された実装タスクを管理し、夜間実行で順次実行する
"""

import json
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum

from ..log_system.structured_logger import StructuredLogger, LogLevel, LogCategory


class TaskStatus(Enum):
    """実装タスクのステータス"""
    PENDING = "PENDING"           # 未実行
    APPROVED = "APPROVED"         # 承認済み
    IN_PROGRESS = "IN_PROGRESS"   # 実行中
    COMPLETED = "COMPLETED"       # 完了
    FAILED = "FAILED"             # 失敗
    SKIPPED = "SKIPPED"           # スキップ


class TaskPriority(Enum):
    """実装タスクの優先度"""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class ImplementationTask:
    """実装タスクの定義"""
    task_id: str
    title: str
    description: str
    priority: TaskPriority
    status: TaskStatus
    dependencies: List[str]  # 依存する他のタスクのID
    estimated_hours: float
    technical_requirements: List[str]
    acceptance_criteria: List[str]
    created_at: datetime
    updated_at: datetime
    assigned_to: Optional[str] = None
    execution_log: List[Dict] = None
    
    def __post_init__(self):
        if self.execution_log is None:
            self.execution_log = []


class ImplementationTaskManager:
    """実装タスク管理システム"""
    
    def __init__(self, workspace_path: str, logger: StructuredLogger):
        self.workspace_path = Path(workspace_path)
        self.logger = logger
        self.tasks: Dict[str, ImplementationTask] = {}
        
        # タスク保存ディレクトリを設定
        self.tasks_dir = self.workspace_path / '.nocturnal' / 'implementation_tasks'
        self.tasks_dir.mkdir(parents=True, exist_ok=True)
        
        # 既存のタスクを読み込み
        self._load_tasks()
    
    def _load_tasks(self):
        """既存のタスクファイルを読み込み"""
        try:
            tasks_file = self.tasks_dir / 'tasks.json'
            if tasks_file.exists():
                with open(tasks_file, 'r', encoding='utf-8') as f:
                    tasks_data = json.load(f)
                
                for task_id, task_data in tasks_data.items():
                    # datetime フィールドを復元
                    task_data['created_at'] = datetime.fromisoformat(task_data['created_at'])
                    task_data['updated_at'] = datetime.fromisoformat(task_data['updated_at'])
                    task_data['priority'] = TaskPriority(task_data['priority'])
                    task_data['status'] = TaskStatus(task_data['status'])
                    
                    self.tasks[task_id] = ImplementationTask(**task_data)
                
                self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, 
                              f"📋 {len(self.tasks)}個の実装タスクを読み込み完了")
            else:
                self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, "📋 新規タスク管理システムを初期化")
        except Exception as e:
            self.logger.log(LogLevel.ERROR, LogCategory.SYSTEM, f"タスク読み込みエラー: {e}")
            self.tasks = {}
    
    def _save_tasks(self):
        """タスクをファイルに保存"""
        try:
            tasks_file = self.tasks_dir / 'tasks.json'
            
            # シリアライズ可能な形式に変換
            tasks_data = {}
            for task_id, task in self.tasks.items():
                task_dict = asdict(task)
                task_dict['created_at'] = task.created_at.isoformat()
                task_dict['updated_at'] = task.updated_at.isoformat()
                task_dict['priority'] = task.priority.value
                task_dict['status'] = task.status.value
                tasks_data[task_id] = task_dict
            
            with open(tasks_file, 'w', encoding='utf-8') as f:
                json.dump(tasks_data, f, ensure_ascii=False, indent=2)
            
            self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, 
                          f"💾 {len(self.tasks)}個のタスクを保存完了")
        except Exception as e:
            self.logger.log(LogLevel.ERROR, LogCategory.SYSTEM, f"タスク保存エラー: {e}")
    
    def create_task_from_specification(self, spec_section: Dict, parent_task_id: Optional[str] = None) -> str:
        """仕様書のセクションから実装タスクを作成"""
        task_id = f"impl_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{len(self.tasks):03d}"
        
        task = ImplementationTask(
            task_id=task_id,
            title=spec_section.get('title', 'Implementation Task'),
            description=spec_section.get('description', ''),
            priority=TaskPriority(spec_section.get('priority', 'MEDIUM')),
            status=TaskStatus.PENDING,
            dependencies=spec_section.get('dependencies', []),
            estimated_hours=spec_section.get('estimated_hours', 1.0),
            technical_requirements=spec_section.get('technical_requirements', []),
            acceptance_criteria=spec_section.get('acceptance_criteria', []),
            created_at=datetime.now(),
            updated_at=datetime.now(),
            assigned_to=spec_section.get('assigned_to')
        )
        
        self.tasks[task_id] = task
        self._save_tasks()
        
        self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, 
                      f"📝 新規実装タスク作成: {task_id} - {task.title}")
        
        return task_id
    
    def break_down_specification_into_tasks(self, design_document: Dict) -> List[str]:
        """設計書を実装タスクに分割"""
        self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, "🔧 仕様書からタスク分割を開始...")
        
        created_task_ids = []
        
        # 実装計画から段階的タスクを作成
        impl_plan = design_document.get('implementation_plan', {})
        phases = impl_plan.get('phases', ['設計', '実装', 'テスト', 'デプロイ'])
        priority_components = impl_plan.get('priority_components', ['コア機能', 'UI', 'データ層'])
        
        # 各コンポーネントに対して各フェーズのタスクを作成
        for component in priority_components:
            for phase in phases:
                task_spec = {
                    'title': f"{component} - {phase}",
                    'description': f"{component}の{phase}フェーズを実装する",
                    'priority': 'HIGH' if component == priority_components[0] else 'MEDIUM',
                    'estimated_hours': 2.0,
                    'technical_requirements': [
                        f"{component}の{phase}を完了する",
                        "コーディング規約に準拠する",
                        "適切なテストを実装する"
                    ],
                    'acceptance_criteria': [
                        f"{component}の{phase}が正常に動作する",
                        "エラーハンドリングが適切に実装されている",
                        "ドキュメントが更新されている"
                    ]
                }
                
                task_id = self.create_task_from_specification(task_spec)
                created_task_ids.append(task_id)
        
        # アーキテクチャ設計から追加タスクを作成
        arch_overview = design_document.get('architecture_overview', {})
        interfaces = arch_overview.get('key_interfaces', [])
        
        for interface in interfaces:
            task_spec = {
                'title': f"{interface}インターフェース実装",
                'description': f"{interface}との連携機能を実装する",
                'priority': 'HIGH',
                'estimated_hours': 3.0,
                'technical_requirements': [
                    f"{interface}との通信を実装する",
                    "エラーハンドリングを実装する",
                    "ログ出力を実装する"
                ],
                'acceptance_criteria': [
                    f"{interface}との通信が正常に動作する",
                    "エラー時の適切な処理が実装されている",
                    "パフォーマンス要件を満たしている"
                ]
            }
            
            task_id = self.create_task_from_specification(task_spec)
            created_task_ids.append(task_id)
        
        self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, 
                      f"✅ {len(created_task_ids)}個のタスクに分割完了")
        
        return created_task_ids
    
    def get_ready_tasks(self) -> List[ImplementationTask]:
        """実行可能なタスクを取得（依存関係を考慮）"""
        ready_tasks = []
        
        for task in self.tasks.values():
            if task.status in [TaskStatus.APPROVED] and self._are_dependencies_completed(task):
                ready_tasks.append(task)
        
        # 優先度順にソート
        priority_order = {TaskPriority.CRITICAL: 0, TaskPriority.HIGH: 1, 
                         TaskPriority.MEDIUM: 2, TaskPriority.LOW: 3}
        ready_tasks.sort(key=lambda t: (priority_order[t.priority], t.created_at))
        
        return ready_tasks
    
    def _are_dependencies_completed(self, task: ImplementationTask) -> bool:
        """タスクの依存関係が完了しているかチェック"""
        for dep_id in task.dependencies:
            if dep_id in self.tasks:
                if self.tasks[dep_id].status != TaskStatus.COMPLETED:
                    return False
            else:
                # 依存タスクが存在しない場合は警告
                self.logger.log(LogLevel.WARNING, LogCategory.SYSTEM, 
                              f"依存タスクが見つかりません: {dep_id}")
        return True
    
    def approve_task(self, task_id: str, approver: str = "system") -> bool:
        """タスクを承認"""
        if task_id not in self.tasks:
            return False
        
        task = self.tasks[task_id]
        task.status = TaskStatus.APPROVED
        task.updated_at = datetime.now()
        task.execution_log.append({
            'action': 'approved',
            'timestamp': datetime.now().isoformat(),
            'approver': approver
        })
        
        self._save_tasks()
        
        self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, 
                      f"✅ タスク承認: {task_id} - {task.title}")
        
        return True
    
    def start_task_execution(self, task_id: str) -> bool:
        """タスクの実行を開始"""
        if task_id not in self.tasks:
            return False
        
        task = self.tasks[task_id]
        task.status = TaskStatus.IN_PROGRESS
        task.updated_at = datetime.now()
        task.execution_log.append({
            'action': 'started',
            'timestamp': datetime.now().isoformat()
        })
        
        self._save_tasks()
        
        self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, 
                      f"🚀 タスク実行開始: {task_id} - {task.title}")
        
        return True
    
    def complete_task(self, task_id: str, execution_result: Dict) -> bool:
        """タスクを完了"""
        if task_id not in self.tasks:
            return False
        
        task = self.tasks[task_id]
        task.status = TaskStatus.COMPLETED
        task.updated_at = datetime.now()
        task.execution_log.append({
            'action': 'completed',
            'timestamp': datetime.now().isoformat(),
            'result': execution_result
        })
        
        self._save_tasks()
        
        self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, 
                      f"✅ タスク完了: {task_id} - {task.title}")
        
        return True
    
    def fail_task(self, task_id: str, error_info: Dict) -> bool:
        """タスクを失敗として記録"""
        if task_id not in self.tasks:
            return False
        
        task = self.tasks[task_id]
        task.status = TaskStatus.FAILED
        task.updated_at = datetime.now()
        task.execution_log.append({
            'action': 'failed',
            'timestamp': datetime.now().isoformat(),
            'error': error_info
        })
        
        self._save_tasks()
        
        self.logger.log(LogLevel.ERROR, LogCategory.SYSTEM, 
                      f"❌ タスク失敗: {task_id} - {task.title}")
        
        return True
    
    def get_task_summary(self) -> Dict[str, Any]:
        """タスクの統計情報を取得"""
        status_counts = {}
        for status in TaskStatus:
            status_counts[status.value] = sum(1 for t in self.tasks.values() if t.status == status)
        
        total_estimated_hours = sum(t.estimated_hours for t in self.tasks.values())
        completed_hours = sum(t.estimated_hours for t in self.tasks.values() if t.status == TaskStatus.COMPLETED)
        
        return {
            'total_tasks': len(self.tasks),
            'status_counts': status_counts,
            'total_estimated_hours': total_estimated_hours,
            'completed_hours': completed_hours,
            'completion_rate': completed_hours / total_estimated_hours if total_estimated_hours > 0 else 0
        }


class ClaudeCodeExecutor:
    """ClaudeCodeへの実行指示システム"""
    
    def __init__(self, workspace_path: str, logger):
        self.workspace_path = Path(workspace_path)
        self.logger = logger
        
        # Claude Code実行履歴を保存するディレクトリ
        self.execution_dir = self.workspace_path / '.nocturnal' / 'claude_executions'
        self.execution_dir.mkdir(parents=True, exist_ok=True)
    
    async def execute_task_via_claude_code(self, task: ImplementationTask) -> Dict:
        """ClaudeCodeを通じてタスクを実行"""
        try:
            self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, 
                          f"🤖 ClaudeCodeでタスク実行開始: {task.title}")
            
            # タスク実行指示を生成
            execution_instruction = self._generate_execution_instruction(task)
            
            # ClaudeCodeへの実行指示ファイルを作成
            instruction_file = self._create_instruction_file(task, execution_instruction)
            
            # 実行ログファイルのパス
            log_file = self.execution_dir / f"{task.task_id}_execution.log"
            
            # ClaudeCode実行コマンドを生成
            claude_command = self._generate_claude_command(instruction_file, log_file)
            
            self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, 
                          f"📝 ClaudeCode実行指示: {instruction_file}")
            
            # 実行結果をシミュレート（実際の実装では subprocess で Claude Code を実行）
            execution_result = await self._simulate_claude_execution(task, execution_instruction)
            
            # 実行結果を保存
            self._save_execution_result(task, execution_result)
            
            return execution_result
            
        except Exception as e:
            self.logger.log(LogLevel.ERROR, LogCategory.SYSTEM, 
                          f"❌ ClaudeCode実行エラー: {task.task_id} - {e}")
            return {
                'status': 'error',
                'task_id': task.task_id,
                'error': str(e),
                'message': f'ClaudeCode実行中にエラーが発生: {e}'
            }
    
    def _generate_execution_instruction(self, task: ImplementationTask) -> str:
        """タスク実行指示を生成"""
        instruction = f"""# 実装タスク実行指示

## タスク情報
- **タスクID**: {task.task_id}
- **タイトル**: {task.title}
- **説明**: {task.description}
- **優先度**: {task.priority.value}
- **推定時間**: {task.estimated_hours}時間

## 技術要件
"""
        for i, req in enumerate(task.technical_requirements, 1):
            instruction += f"{i}. {req}\n"
        
        instruction += f"""
## 受け入れ基準
"""
        for i, criteria in enumerate(task.acceptance_criteria, 1):
            instruction += f"{i}. {criteria}\n"
        
        instruction += f"""
## 実行指示
このタスクを以下の手順で実装してください：

1. **コード実装**: 技術要件に基づいてコードを実装
2. **テスト作成**: 実装したコードのテストを作成
3. **ドキュメント更新**: 必要に応じてドキュメントを更新
4. **受け入れ基準確認**: すべての受け入れ基準が満たされていることを確認

## 注意事項
- PEP 8に準拠したコードを書いてください
- 適切なエラーハンドリングを実装してください
- 型ヒントを使用してください
- 必要に応じてログ出力を追加してください

作業完了後、実装内容と結果をレポートしてください。
"""
        return instruction
    
    def _create_instruction_file(self, task: ImplementationTask, instruction: str) -> Path:
        """実行指示ファイルを作成"""
        instruction_file = self.execution_dir / f"{task.task_id}_instruction.md"
        
        with open(instruction_file, 'w', encoding='utf-8') as f:
            f.write(instruction)
        
        return instruction_file
    
    def _generate_claude_command(self, instruction_file: Path, log_file: Path) -> str:
        """ClaudeCode実行コマンドを生成"""
        # 実際の実装では claude コマンドを使用
        return f"""claude --file "{instruction_file}" --workspace "{self.workspace_path}" --output "{log_file}" """
    
    async def _simulate_claude_execution(self, task: ImplementationTask, instruction: str) -> Dict:
        """ClaudeCode実行をシミュレート（開発用）"""
        # 実際の実装では subprocess を使ってClaudeCodeを実行
        import asyncio
        await asyncio.sleep(1)  # 実行時間をシミュレート
        
        return {
            'status': 'success',
            'task_id': task.task_id,
            'execution_time': datetime.now().isoformat(),
            'files_modified': [
                f"src/{task.title.lower().replace(' ', '_')}.py",
                f"tests/test_{task.title.lower().replace(' ', '_')}.py"
            ],
            'test_results': {
                'passed': 5,
                'failed': 0,
                'skipped': 0
            },
            'message': f'タスク「{task.title}」がClaudeCodeにより正常に実装されました'
        }
    
    def _save_execution_result(self, task: ImplementationTask, result: Dict):
        """実行結果を保存"""
        result_file = self.execution_dir / f"{task.task_id}_result.json"
        
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, 
                      f"💾 実行結果保存: {result_file}")


class NightlyTaskExecutor:
    """夜間タスク実行システム（ローカルLLM → ClaudeCode）"""
    
    def __init__(self, workspace_path: str, logger):
        self.workspace_path = workspace_path
        self.logger = logger
        self.task_manager = ImplementationTaskManager(workspace_path, logger)
        self.claude_executor = ClaudeCodeExecutor(workspace_path, logger)
    
    async def execute_nightly_tasks(self, max_tasks: int = 5) -> Dict:
        """夜間タスク実行メイン処理"""
        self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, 
                      f"🌙 夜間タスク実行開始 (最大{max_tasks}タスク)")
        
        execution_summary = {
            'start_time': datetime.now().isoformat(),
            'executed_tasks': [],
            'failed_tasks': [],
            'skipped_tasks': [],
            'total_execution_time': 0
        }
        
        try:
            # 実行可能なタスクを取得
            ready_tasks = self.task_manager.get_ready_tasks()
            
            if not ready_tasks:
                self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, 
                              "📋 実行可能なタスクがありません")
                execution_summary['message'] = '実行可能なタスクがありません'
                return execution_summary
            
            # 実行するタスクを制限
            tasks_to_execute = ready_tasks[:max_tasks]
            
            self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, 
                          f"🎯 {len(tasks_to_execute)}個のタスクを実行開始")
            
            for task in tasks_to_execute:
                execution_start = datetime.now()
                
                try:
                    # ローカルLLMがClaudeCodeに実行指示を送信
                    self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, 
                                  f"🤖 ローカルLLM → ClaudeCode: {task.title}")
                    
                    # タスク実行開始をマーク
                    self.task_manager.start_task_execution(task.task_id)
                    
                    # ClaudeCodeでタスク実行
                    execution_result = await self.claude_executor.execute_task_via_claude_code(task)
                    
                    execution_time = (datetime.now() - execution_start).total_seconds()
                    
                    if execution_result['status'] == 'success':
                        # タスク完了をマーク
                        self.task_manager.complete_task(task.task_id, execution_result)
                        execution_summary['executed_tasks'].append({
                            'task_id': task.task_id,
                            'title': task.title,
                            'execution_time': execution_time,
                            'result': execution_result
                        })
                        
                        self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, 
                                      f"✅ タスク完了: {task.title} ({execution_time:.1f}秒)")
                    else:
                        # タスク失敗をマーク
                        self.task_manager.fail_task(task.task_id, execution_result)
                        execution_summary['failed_tasks'].append({
                            'task_id': task.task_id,
                            'title': task.title,
                            'execution_time': execution_time,
                            'error': execution_result.get('error', 'Unknown error')
                        })
                        
                        self.logger.log(LogLevel.ERROR, LogCategory.SYSTEM, 
                                      f"❌ タスク失敗: {task.title}")
                
                except Exception as e:
                    execution_time = (datetime.now() - execution_start).total_seconds()
                    error_info = {'error': str(e), 'type': 'execution_error'}
                    self.task_manager.fail_task(task.task_id, error_info)
                    
                    execution_summary['failed_tasks'].append({
                        'task_id': task.task_id,
                        'title': task.title,
                        'execution_time': execution_time,
                        'error': str(e)
                    })
                    
                    self.logger.log(LogLevel.ERROR, LogCategory.SYSTEM, 
                                  f"❌ タスク実行エラー: {task.title} - {e}")
                
                execution_summary['total_execution_time'] += execution_time
            
            # 実行結果サマリー
            task_summary = self.task_manager.get_task_summary()
            execution_summary['end_time'] = datetime.now().isoformat()
            execution_summary['task_summary'] = task_summary
            
            success_count = len(execution_summary['executed_tasks'])
            failure_count = len(execution_summary['failed_tasks'])
            
            self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, 
                          f"🎉 夜間タスク実行完了: 成功{success_count}件、失敗{failure_count}件")
            self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, 
                          f"📊 全体進捗: {task_summary['completion_rate']:.1%}")
            
            return execution_summary
            
        except Exception as e:
            execution_summary['end_time'] = datetime.now().isoformat()
            execution_summary['error'] = str(e)
            self.logger.log(LogLevel.ERROR, LogCategory.SYSTEM, 
                          f"夜間タスク実行システムエラー: {e}")
            return execution_summary
