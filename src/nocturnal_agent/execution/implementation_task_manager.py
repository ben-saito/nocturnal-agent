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
    started_at: Optional[datetime] = None  # 実行開始時刻を追加
    
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
                    # started_atがNoneでない場合のみiso形式から復元
                    if task_data.get('started_at'):
                        task_data['started_at'] = datetime.fromisoformat(task_data['started_at'])
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
                # started_atもiso形式に変換（Noneの場合はそのまま）
                if task.started_at:
                    task_dict['started_at'] = task.started_at.isoformat()
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
        task.started_at = datetime.now()  # 実行開始時刻を記録
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

    def _detect_and_reset_stalled_tasks(self) -> int:
        """停止したタスクを検出してリセットする
        
        Returns:
            int: リセットしたタスクの数
        """
        reset_count = 0
        current_time = datetime.now()
        stall_threshold = timedelta(minutes=45)  # 45分を超えたら停止と判断
        
        for task in self.tasks.values():  # .values()を追加
            if task.status == TaskStatus.IN_PROGRESS:  # 正しいenum値を使用
                # タスクが実行開始された時刻を確認
                if hasattr(task, 'started_at') and task.started_at:
                    elapsed_time = current_time - task.started_at
                    if elapsed_time > stall_threshold:
                        self.logger.log(LogLevel.WARNING, LogCategory.SYSTEM, 
                                      f"停止したタスクを検出: {task.task_id} (実行時間: {elapsed_time})")
                        task.status = TaskStatus.APPROVED  # 正しいenum値を使用
                        task.started_at = None
                        if hasattr(task, 'assigned_agent'):
                            task.assigned_agent = None
                        reset_count += 1
                        self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, 
                                      f"タスク {task.task_id} をリセットしました")
                else:
                    # started_atが設定されていない古いrunningタスクもリセット
                    self.logger.log(LogLevel.WARNING, LogCategory.SYSTEM, 
                                  f"実行時刻不明のタスクを検出: {task.task_id}")
                    task.status = TaskStatus.APPROVED  # 正しいenum値を使用
                    task.started_at = None
                    if hasattr(task, 'assigned_agent'):
                        task.assigned_agent = None
                    reset_count += 1
                    self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, 
                                  f"タスク {task.task_id} をリセットしました")
        
        if reset_count > 0:
            self._save_tasks()
            self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, 
                          f"合計 {reset_count} 個のタスクをリセットしました")
        
        return reset_count


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
        # タスク種別を判定
        is_design_task = task.title.endswith("- 設計")
        is_implementation_task = task.title.endswith("- 実装") 
        is_test_task = task.title.endswith("- テスト")
        
        instruction = f"""# 実装タスク実行指示

## タスク情報
- **タスクID**: {task.task_id}
- **タスクタイプ**: {"設計" if is_design_task else "実装" if is_implementation_task else "テスト" if is_test_task else "その他"}
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
        
        # タスク種別に応じた具体的な指示を生成
        if is_design_task:
            instruction += f"""
## 【重要】ファイル作成必須タスク

**このタスクの成功条件は実際のファイル作成です。レポートのみでは失敗扱いとなります。**

### 【必須実行手順】(この順序で実行):

#### STEP 1: ディレクトリ作成（必須）
```bash
mkdir -p docs/design
mkdir -p docs/api
mkdir -p src/components
```

#### STEP 2: 設計書ファイル作成（必須）
**以下のファイルを必ず作成してください:**
1. **メイン設計書**: `docs/design/{task.task_id.replace('impl_', '').replace('_', '-')}-design.md`
2. **API仕様書**: `docs/api/{task.task_id.replace('impl_', '').replace('_', '-')}-api.md`
3. **コンポーネント設計**: `src/components/{task.task_id.replace('impl_', '').replace('_', '-')}-components.md`

#### STEP 3: 各ファイルの必須内容
**メイン設計書の必須セクション:**
```markdown
# {task.title} - 詳細設計書

## 1. システム概要
## 2. 技術仕様
## 3. アーキテクチャ設計
## 4. データフロー設計
## 5. コンポーネント設計
## 6. API設計
## 7. パフォーマンス要件
## 8. セキュリティ設計
## 9. 実装計画
## 10. 受け入れ基準
```

### 【重要な警告】:
- **Write**または**Edit**ツールを使用してファイルを作成してください
- **必ずファイルパスを明示**してファイル作成を実行してください
- **レポートだけの提出は受け入れられません**
- **"ファイル作成権限が必要"等の言い訳は禁止**です
- **files_modified配列に作成したファイルが記録される**ことを確認してください

### 【成功の確認方法】:
1. 実際にファイルが存在すること
2. ファイルに適切な内容が含まれていること
3. 最低1500文字以上の詳細な設計書であること
"""
        elif is_implementation_task:
            instruction += f"""
## 【重要】ソースコード作成必須タスク

**このタスクの成功条件は実際のソースコード作成です。レポートのみでは失敗扱いとなります。**

### 【必須実行手順】(この順序で実行):

#### STEP 1: ディレクトリ構造作成（必須）
```bash
mkdir -p src/components
mkdir -p src/api
mkdir -p src/utils
mkdir -p src/types
mkdir -p src/hooks
```

#### STEP 2: ソースファイル作成（必須）
**以下のファイルを必ず作成してください:**
1. **メインコンポーネント**: `src/components/{task.task_id.replace('impl_', '').replace('_', '-')}.tsx`
2. **API層**: `src/api/{task.task_id.replace('impl_', '').replace('_', '-')}-api.ts`
3. **型定義**: `src/types/{task.task_id.replace('impl_', '').replace('_', '-')}-types.ts`
4. **ユーティリティ**: `src/utils/{task.task_id.replace('impl_', '').replace('_', '-')}-utils.ts`

#### STEP 3: 設定・依存関係ファイル作成
```bash
package.json (必要に応じて更新)
tsconfig.json (必要に応じて更新)
.env.example (必要に応じて作成)
```

### 【重要な警告】:
- **Write**または**Edit**ツールを使用してファイルを作成してください
- **必ず動作するコードを記述**してください
- **import/export文、型定義を正しく記述**してください
- **レポートだけの提出は受け入れられません**
- **files_modified配列に作成したファイルが記録される**ことを確認してください

### 【成功の確認方法】:
1. 実際にソースファイルが存在すること
2. TypeScript/JavaScript構文が正しいこと
3. 適切なimport/export構造であること
4. 最低500行以上の実装コードであること
"""
        elif is_test_task:
            instruction += f"""
## 【重要】テストコード作成必須タスク

**このタスクの成功条件は実際のテストコード作成です。レポートのみでは失敗扱いとなります。**

### 【必須実行手順】(この順序で実行):

#### STEP 1: テストディレクトリ作成（必須）
```bash
mkdir -p tests/unit
mkdir -p tests/integration
mkdir -p tests/e2e
mkdir -p tests/fixtures
```

#### STEP 2: テストファイル作成（必須）
**以下のファイルを必ず作成してください:**
1. **ユニットテスト**: `tests/unit/test-{task.task_id.replace('impl_', '').replace('_', '-')}.spec.ts`
2. **統合テスト**: `tests/integration/test-{task.task_id.replace('impl_', '').replace('_', '-')}.spec.ts`
3. **E2Eテスト**: `tests/e2e/{task.task_id.replace('impl_', '').replace('_', '-')}.e2e.spec.ts`
4. **テストヘルパー**: `tests/helpers/{task.task_id.replace('impl_', '').replace('_', '-')}-helpers.ts`

#### STEP 3: テスト設定ファイル作成
```bash
jest.config.js (または jest.config.ts)
vitest.config.ts (必要に応じて)
playwright.config.ts (E2E用)
```

### 【重要な警告】:
- **Write**または**Edit**ツールを使用してファイルを作成してください
- **実際に実行可能なテストコードを記述**してください
- **テストカバレッジ80%以上を目指す**テストケースを記述してください
- **レポートだけの提出は受け入れられません**
- **files_modified配列に作成したファイルが記録される**ことを確認してください

### 【成功の確認方法】:
1. 実際にテストファイルが存在すること
2. テストが実行可能であること（構文エラーなし）
3. 適切なアサーション文が含まれていること
4. 最低20個以上のテストケースが含まれていること
"""
        else:
            instruction += """
## 実行指示
このタスクを以下の手順で実装してください：

1. **コード実装**: 技術要件に基づいてコードを実装
2. **ファイル作成**: 適切なディレクトリ構造でファイルを配置
3. **ドキュメント作成**: 必要な設計書・説明書を作成
4. **受け入れ基準確認**: すべての受け入れ基準が満たされていることを確認
"""

        # 共通の重要指示を追加
        instruction += """
## 【最重要】ファイル作成チェックリスト

### 【必須確認事項】(作業完了前に必ずチェック):
・Write/Editツールを使用してファイルを作成したか
・作成したファイルが実際に存在するか  
・ファイル内容が空ではないか(最低限の内容が含まれているか)
・適切なディレクトリに配置されているか
・files_modified配列に記録されているか

### 【警告】絶対に避けるべき行動:
・レポートのみの提出
・ファイル作成権限が必要等の言い訳
・承認待ち等の理由でファイル作成を回避
・設計書の代わりにレポートで済ませる
・ファイル作成をスキップしてコメントのみ

### 【成功の定義】:
このタスクは以下の条件を満たした時のみ成功です:
1. 具体的なファイルが実際に作成されている
2. ファイル内容が要件を満たしている
3. 後続タスクで利用可能な品質である
4. files_modified配列に正しく記録されている

### 【作業完了レポート要件】:
作業完了後、必ず以下の形式でレポートしてください:

## 作業完了レポート

### 作成・更新したファイル一覧:
1. [ファイルパス1] - [説明]
2. [ファイルパス2] - [説明]

### 各ファイルの内容概要:
- [ファイル名]: [内容の説明、行数、主要機能等]

### 技術要件達成状況:
- [要件1]: [OK/NG] [達成状況の説明]

### 受け入れ基準達成状況:
- [基準1]: [OK/NG] [達成状況の説明]
"""
        return instruction
    
    def _verify_files_created(self, task: ImplementationTask, claude_output: str) -> List[str]:
        """実際にファイルが作成されたかを検証する"""
        created_files = []
        
        # タスクタイプに応じた期待ファイルパスを生成
        is_design_task = task.title.endswith("- 設計")
        is_implementation_task = task.title.endswith("- 実装") 
        is_test_task = task.title.endswith("- テスト")
        
        expected_paths = []
        
        if is_design_task:
            base_name = task.task_id.replace('impl_', '').replace('_', '-')
            expected_paths = [
                f"docs/design/{base_name}-design.md",
                f"docs/api/{base_name}-api.md",
                f"src/components/{base_name}-components.md"
            ]
        elif is_implementation_task:
            base_name = task.task_id.replace('impl_', '').replace('_', '-')
            expected_paths = [
                f"src/components/{base_name}.tsx",
                f"src/api/{base_name}-api.ts",
                f"src/types/{base_name}-types.ts"
            ]
        elif is_test_task:
            base_name = task.task_id.replace('impl_', '').replace('_', '-')
            expected_paths = [
                f"tests/unit/test-{base_name}.spec.ts",
                f"tests/integration/test-{base_name}.spec.ts"
            ]
        
        # 実際のファイル存在を確認
        for expected_path in expected_paths:
            full_path = self.workspace_path / expected_path
            if full_path.exists() and full_path.is_file():
                # ファイルが空でないことも確認
                if full_path.stat().st_size > 100:  # 最低100バイト
                    created_files.append(str(expected_path))
                    self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, 
                                  f"✓ ファイル確認: {expected_path} ({full_path.stat().st_size} bytes)")
                else:
                    self.logger.log(LogLevel.WARNING, LogCategory.SYSTEM, 
                                  f"⚠ ファイルが空または小さすぎます: {expected_path}")
            else:
                self.logger.log(LogLevel.WARNING, LogCategory.SYSTEM, 
                              f"✗ ファイルが見つかりません: {expected_path}")
        
        # Claudeの出力からファイル作成を検出する追加ロジック
        claude_mentioned_files = self._extract_files_from_output(claude_output)
        for file_path in claude_mentioned_files:
            full_path = self.workspace_path / file_path
            if full_path.exists() and full_path.is_file() and full_path.stat().st_size > 100:
                if file_path not in created_files:
                    created_files.append(file_path)
                    self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, 
                                  f"✓ 追加ファイル確認: {file_path}")
        
        return created_files
    
    def _extract_files_from_output(self, output: str) -> List[str]:
        """Claude出力からファイルパスを抽出する"""
        import re
        
        # ファイルパスパターンを検索
        patterns = [
            r'(?:created|wrote|saved|generated).*?([a-zA-Z0-9_/-]+\.(?:md|ts|tsx|js|jsx|py|json))',
            r'File created.*?([a-zA-Z0-9_/-]+\.(?:md|ts|tsx|js|jsx|py|json))',
            r'`([a-zA-Z0-9_/-]+\.(?:md|ts|tsx|js|jsx|py|json))`',
        ]
        
        files = []
        for pattern in patterns:
            matches = re.findall(pattern, output, re.IGNORECASE)
            files.extend(matches)
        
        # 重複除去と正規化
        return list(set(files))
    
    def _generate_strict_retry_instruction(self, task: ImplementationTask) -> str:
        """ファイル作成を強制する厳格な指示を生成"""
        is_design_task = task.title.endswith("- 設計")
        base_name = task.task_id.replace('impl_', '').replace('_', '-')
        
        instruction = f"""# 🚨 緊急：ファイル作成必須タスク - 再実行 🚨

## 前回の実行でファイルが作成されませんでした。今回は絶対にファイル作成してください。

### タスク情報
- **タスクID**: {task.task_id}
- **タイトル**: {task.title}
- **説明**: {task.description}

### 🚨 絶対要件：以下のファイルを必ず作成してください 🚨

"""
        
        if is_design_task:
            instruction += f"""
#### 必須作成ファイル:
1. `docs/design/{base_name}-design.md` - メイン設計書（最低2000文字）
2. `docs/api/{base_name}-api.md` - API仕様書（最低1000文字）  
3. `src/components/{base_name}-components.md` - コンポーネント設計（最低1000文字）

#### 実行手順（この通りに実行）:
```
1. mkdir -p docs/design docs/api src/components
2. Write ツールで docs/design/{base_name}-design.md を作成
3. Write ツールで docs/api/{base_name}-api.md を作成
4. Write ツールで src/components/{base_name}-components.md を作成
5. 各ファイルが作成されたことを確認
```
"""
        
        instruction += """
### ❌ 絶対に禁止されている行為:
- レポートだけの提出
- "ファイルを作成しました"と言うだけ
- 実際にファイルを作成しないこと
- 権限がない等の言い訳

### ✅ 成功の証明:
- Write ツールを実際に使用する
- ファイルが物理的に存在する
- ファイル内容が要件を満たす

## 最終確認：
このタスクは実際のファイル作成のみで成功と判定されます。
レポートや説明は不要です。ファイル作成だけしてください。
"""
        
        return instruction
    
    async def _execute_with_strict_mode(self, task: ImplementationTask, instruction: str) -> Dict:
        """厳格モードでタスクを実行"""
        import subprocess
        import os
        
        try:
            # 指示ファイルを作成
            strict_instruction_path = self.execution_dir / f"{task.task_id}_strict_retry.md"
            with open(strict_instruction_path, 'w', encoding='utf-8') as f:
                f.write(instruction)
            
            # より厳格なコマンドで実行
            cmd = [
                'claude',
                '--file', str(strict_instruction_path),
                '--workspace', str(self.workspace_path),
                '--force-write',  # 強制書き込みモード
                '--verbose'       # 詳細出力
            ]
            
            self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, 
                          f"🚨 厳格モードで再実行: {task.task_id}")
            
            env = dict(os.environ)
            env.update({
                'CLAUDE_FORCE_WRITE': '1',
                'CLAUDE_STRICT_MODE': '1',
                'PWD': str(self.workspace_path)
            })
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                timeout=600,  # 10分タイムアウト（短縮）
                cwd=self.workspace_path,
                env=env
            )
            
            # ファイル作成確認
            files_created = self._verify_files_created(task, result.stdout)
            
            return {
                'status': 'success' if files_created else 'failed',
                'task_id': task.task_id,
                'execution_time': datetime.now().isoformat(),
                'claude_output': result.stdout,
                'claude_stderr': result.stderr,
                'files_created': files_created,
                'retry_mode': 'strict',
                'message': f'厳格モード再実行: {"成功" if files_created else "失敗"}'
            }
            
        except Exception as e:
            self.logger.log(LogLevel.ERROR, LogCategory.SYSTEM, 
                          f"厳格モード実行エラー: {e}")
            return {
                'status': 'error',
                'task_id': task.task_id,
                'error': str(e),
                'files_created': [],
                'retry_mode': 'strict'
            }
    
    def _create_instruction_file(self, task: ImplementationTask, instruction: str) -> Path:
        """実行指示ファイルを作成"""
        instruction_file = self.execution_dir / f"{task.task_id}_instruction.md"
        
        with open(instruction_file, 'w', encoding='utf-8') as f:
            f.write(instruction)
        
        return instruction_file
    
    def _generate_claude_command(self, instruction_file: Path, log_file: Path) -> str:
        """ClaudeCode実行コマンドを生成"""
        # 実際の実装では claude コマンドを使用
        # ワークスペース内での読み書き権限を明示的に付与
        return f"""cd "{self.workspace_path}" && claude --file "{instruction_file}" --allow-write --allow-read --workspace "{self.workspace_path}" > "{log_file}" 2>&1"""
    
    async def _simulate_claude_execution(self, task: ImplementationTask, instruction: str) -> Dict:
        """ClaudeCodeを実際に実行してタスクを処理"""
        import subprocess
        import tempfile
        import psutil
        import signal
        import time
        import os
        
        try:
            self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, 
                          f"🔄 ClaudeCode実行開始: {task.title}")
            
            # 既存の長時間実行中のClaudeプロセスをクリーンアップ
            self._cleanup_stale_claude_processes()
            
            # 指示ファイルを一時作成
            with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
                f.write(instruction)
                instruction_file = f.name
            
            # 指示ファイルを作成
            instruction_file_path = self.execution_dir / f"{task.task_id}_instruction.md"
            with open(instruction_file_path, 'w', encoding='utf-8') as f:
                f.write(instruction)
            
            # ClaudeCodeコマンドを修正版で実行 (標準入力を使用)
            cmd = [
                'claude', 
                '--print',  # 非対話モードで出力
                '--add-dir', str(self.workspace_path),  # ディレクトリアクセス許可
                '--dangerously-skip-permissions'  # 権限チェックをスキップ
            ]
            
            self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, 
                          f"💬 ClaudeCode実行中（ワークスペース: {self.workspace_path}）...")
            self.logger.log(LogLevel.DEBUG, LogCategory.SYSTEM, 
                          f"実行コマンド: {' '.join(cmd)}")
            
            # プロセス開始時刻を記録
            start_time = time.time()
            
            # 環境変数を設定
            env = dict(os.environ)
            env.update({
                'PWD': str(self.workspace_path),
                'CLAUDE_WORKSPACE': str(self.workspace_path),
                'CLAUDE_ALLOW_WRITE': '1'
            })
            
            # 指示を標準入力として渡す
            result = subprocess.run(
                cmd,
                input=instruction,  # 指示を標準入力として渡す
                capture_output=True,
                text=True,
                encoding='utf-8',
                timeout=1800,  # 30分タイムアウト
                cwd=self.workspace_path,
                env=env
            )
            
            # 一時ファイル削除
            Path(instruction_file).unlink()
            
            if result.returncode == 0:
                execution_time = time.time() - start_time
                
                # ファイル生成を検証
                files_created = self._verify_files_created(task, result.stdout)
                
                if files_created:
                    self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, 
                                  f"✅ ClaudeCode実行成功: {task.title} ({execution_time:.1f}秒)")
                    self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, 
                                  f"📁 作成されたファイル: {len(files_created)}個")
                    for file_path in files_created:
                        self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, 
                                      f"  - {file_path}")
                else:
                    self.logger.log(LogLevel.WARNING, LogCategory.SYSTEM, 
                                  f"⚠️  ClaudeCode実行完了だが、ファイルが作成されていません: {task.title}")
                
                # 実行結果の内容を表示（最初の500文字）
                output_preview = result.stdout[:500]
                if len(result.stdout) > 500:
                    output_preview += "..."
                
                self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, 
                              f"📝 ClaudeCode出力プレビュー:\n{output_preview}")
                
                # ファイルが作成されていない場合の自動再実行
                if not files_created:
                    self.logger.log(LogLevel.WARNING, LogCategory.SYSTEM, 
                                  f"🔄 ファイル作成失敗のため、より強力な指示で再実行します")
                    
                    # より厳しい指示で再実行
                    retry_instruction = self._generate_strict_retry_instruction(task)
                    retry_result = await self._execute_with_strict_mode(task, retry_instruction)
                    
                    if retry_result['files_created']:
                        self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, 
                                      f"✅ 再実行成功: ファイル作成確認")
                        return retry_result
                
                return {
                    'status': 'success' if files_created else 'partial_success',
                    'task_id': task.task_id,
                    'execution_time': datetime.now().isoformat(),
                    'claude_output': result.stdout,
                    'claude_stderr': result.stderr,
                    'files_modified': files_created,
                    'files_created_count': len(files_created),
                    'message': f'タスク「{task.title}」がClaudeCodeにより{"正常に実装" if files_created else "実行されましたが、ファイル作成に問題があります"}されました'
                }
            else:
                self.logger.log(LogLevel.ERROR, LogCategory.SYSTEM, 
                              f"❌ ClaudeCode実行エラー: {result.stderr}")
                
                return {
                    'status': 'error',
                    'task_id': task.task_id,
                    'execution_time': datetime.now().isoformat(),
                    'error': result.stderr,
                    'claude_output': result.stdout,
                    'message': f'タスク「{task.title}」のClaudeCode実行でエラーが発生しました'
                }
                
        except subprocess.TimeoutExpired as e:
            # タイムアウト時にプロセスを強制終了
            if hasattr(e, 'process') and e.process:
                try:
                    # プロセスグループを終了
                    process = psutil.Process(e.process.pid)
                    for child in process.children(recursive=True):
                        child.kill()
                    process.kill()
                    self.logger.log(LogLevel.WARNING, LogCategory.SYSTEM, 
                                  f"🔪 タイムアウトによりClaudeプロセス(PID: {e.process.pid})を強制終了")
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            
            # 追加のクリーンアップ
            self._cleanup_stale_claude_processes()
            
            self.logger.log(LogLevel.ERROR, LogCategory.SYSTEM, 
                          f"⏰ ClaudeCode実行タイムアウト: {task.title}")
            return {
                'status': 'error',
                'task_id': task.task_id,
                'error': 'ClaudeCode実行がタイムアウトしました（30分）',
                'message': f'タスク「{task.title}」の実行がタイムアウトしました'
            }
            
        except FileNotFoundError:
            self.logger.log(LogLevel.ERROR, LogCategory.SYSTEM, 
                          "❌ ClaudeCodeが見つかりません")
            return {
                'status': 'error',
                'task_id': task.task_id,
                'error': 'ClaudeCodeコマンドが見つかりません',
                'message': 'ClaudeCode CLIがインストールされているか確認してください'
            }
            
        except Exception as e:
            self.logger.log(LogLevel.ERROR, LogCategory.SYSTEM, 
                          f"❌ ClaudeCode実行中に予期しないエラー: {e}")
            return {
                'status': 'error',
                'task_id': task.task_id,
                'error': str(e),
                'message': f'ClaudeCode実行中に予期しないエラーが発生しました: {e}'
            }

    def _extract_modified_files(self, claude_output: str) -> List[str]:
        """ClaudeCode出力から変更されたファイル一覧を抽出"""
        modified_files = []
        
        # ClaudeCodeの出力からファイル変更パターンを検索
        import re
        
        # 一般的なファイル変更パターン
        patterns = [
            r'(?:Created|Modified|Updated|Wrote|Edited)[\s:]+([^\s\n]+\.[a-zA-Z]+)',
            r'File[\s:]+([^\s\n]+\.[a-zA-Z]+)[\s]+(?:created|modified|updated)',
            r'```[a-zA-Z]*\n# ([^\s\n]+\.[a-zA-Z]+)',
            r'Writing to ([^\s\n]+\.[a-zA-Z]+)',
            r'Saved ([^\s\n]+\.[a-zA-Z]+)'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, claude_output, re.IGNORECASE)
            modified_files.extend(matches)
        
        # 重複を除去し、相対パスに正規化
        unique_files = []
        for file_path in modified_files:
            # パスを正規化
            normalized_path = file_path.strip().replace('\\', '/')
            if normalized_path not in unique_files:
                unique_files.append(normalized_path)
        
        return unique_files[:10]  # 最大10ファイルまで

    def _cleanup_stale_claude_processes(self):
        """長時間実行中のClaudeプロセスをクリーンアップ"""
        try:
            import psutil
            import time
            
            current_time = time.time()
            max_age_seconds = 45 * 60  # 45分
            terminated_count = 0
            
            for proc in psutil.process_iter(['pid', 'name', 'create_time', 'cmdline']):
                try:
                    # Claudeプロセスかチェック
                    if proc.info['name'] == 'claude' or (
                        proc.info['cmdline'] and 
                        any('claude' in str(arg) for arg in proc.info['cmdline'])
                    ):
                        # プロセスの実行時間をチェック
                        process_age = current_time - proc.info['create_time']
                        
                        if process_age > max_age_seconds:
                            self.logger.log(LogLevel.WARNING, LogCategory.SYSTEM, 
                                          f"🔪 長時間実行中のClaudeプロセスを終了: PID {proc.info['pid']} (実行時間: {process_age/60:.1f}分)")
                            
                            # プロセスとその子プロセスを終了
                            try:
                                parent = psutil.Process(proc.info['pid'])
                                for child in parent.children(recursive=True):
                                    child.terminate()
                                parent.terminate()
                                
                                # 3秒待って強制終了
                                time.sleep(3)
                                if parent.is_running():
                                    for child in parent.children(recursive=True):
                                        child.kill()
                                    parent.kill()
                                
                                terminated_count += 1
                                
                            except (psutil.NoSuchProcess, psutil.AccessDenied):
                                # プロセスが既に終了している場合は無視
                                pass
                                
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    # プロセス情報取得に失敗した場合は無視
                    continue
            
            if terminated_count > 0:
                self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, 
                              f"🧹 {terminated_count}個の長時間実行Claudeプロセスを終了しました")
                
        except Exception as e:
            self.logger.log(LogLevel.WARNING, LogCategory.SYSTEM, 
                          f"⚠️ プロセスクリーンアップ中にエラー: {e}")
    
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

    async def _detect_and_reset_stalled_tasks(self) -> int:
        """停止したタスクを検出してリセットする
        
        Returns:
            int: リセットしたタスクの数
        """
        return self.task_manager._detect_and_reset_stalled_tasks()
    
    async def execute_nightly_tasks(self, max_tasks: int = 5) -> Dict:
        """夜間タスク実行メイン処理"""
        self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, 
                      f"🌙 夜間タスク実行開始 (最大{max_tasks}タスク)")
        
        execution_summary = {
            'start_time': datetime.now().isoformat(),
            'executed_tasks': [],
            'failed_tasks': [],
            'skipped_tasks': [],
            'reset_tasks': [],
            'total_execution_time': 0
        }
        
        try:
            # 🔄 途中停止タスクの検出と自動リセット
            reset_count = await self._detect_and_reset_stalled_tasks()
            if reset_count > 0:
                execution_summary['reset_tasks_count'] = reset_count
                self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, 
                              f"🔄 {reset_count}個の途中停止タスクをリセットしました")
            
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

    async def execute_continuous_tasks(self, max_concurrent: int = 3, check_interval: int = 300) -> Dict:
        """継続的なタスク実行（自動再開機能付き）
        
        Args:
            max_concurrent: 最大同時実行タスク数
            check_interval: チェック間隔（秒）
        """
        self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, 
                      f"🔄 継続的タスク実行開始 (最大同時{max_concurrent}タスク)")
        
        total_summary = {
            'start_time': datetime.now().isoformat(),
            'total_executed': 0,
            'total_failed': 0,
            'total_reset': 0,
            'execution_cycles': 0
        }
        
        try:
            while True:
                cycle_start = datetime.now()
                
                # 🧹 停止タスクのリセット + プロセスクリーンアップ
                reset_count = await self._detect_and_reset_stalled_tasks()
                if reset_count > 0:
                    total_summary['total_reset'] += reset_count
                    self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, 
                                  f"🔄 {reset_count}個のタスクをリセットしました")
                
                # 実行可能タスクをチェック
                ready_tasks = self.task_manager.get_ready_tasks()
                
                if not ready_tasks:
                    self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, 
                                  f"✅ 全タスク完了または実行可能タスクなし。{check_interval}秒後に再チェック...")
                    
                    # 完了率をチェック
                    task_summary = self.task_manager.get_task_summary()
                    if task_summary['completion_rate'] >= 1.0:
                        self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, 
                                      "🎉 全タスクが完了しました！")
                        break
                    
                    await asyncio.sleep(check_interval)
                    continue
                
                # 実行するタスクを選択
                tasks_to_execute = ready_tasks[:max_concurrent]
                
                self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, 
                              f"🎯 サイクル#{total_summary['execution_cycles'] + 1}: "
                              f"{len(tasks_to_execute)}個のタスクを実行開始")
                
                # タスク実行
                cycle_result = await self.execute_nightly_tasks(max_tasks=max_concurrent)
                
                # サマリー更新
                total_summary['total_executed'] += len(cycle_result.get('executed_tasks', []))
                total_summary['total_failed'] += len(cycle_result.get('failed_tasks', []))
                total_summary['execution_cycles'] += 1
                
                # 進捗状況を表示
                task_summary = self.task_manager.get_task_summary()
                self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, 
                              f"📊 現在の進捗: {task_summary['completion_rate']:.1%} "
                              f"(完了: {task_summary['completed']}, "
                              f"実行中: {task_summary['in_progress']}, "
                              f"待機中: {task_summary['pending']})")
                
                # 次のサイクルまで待機
                if ready_tasks:  # まだタスクがある場合は短い間隔
                    await asyncio.sleep(30)
                else:
                    await asyncio.sleep(check_interval)
                    
        except KeyboardInterrupt:
            self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, 
                          "⏹️ ユーザーにより継続実行が停止されました")
        except Exception as e:
            self.logger.log(LogLevel.ERROR, LogCategory.SYSTEM, 
                          f"❌ 継続実行中にエラー: {e}")
        
        total_summary['end_time'] = datetime.now().isoformat()
        self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, 
                      f"🏁 継続実行完了: "
                      f"実行 {total_summary['total_executed']}タスク, "
                      f"失敗 {total_summary['total_failed']}タスク, "
                      f"リセット {total_summary['total_reset']}タスク")
        
        return total_summary
