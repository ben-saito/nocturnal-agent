"""
設計確定後の自動実行継続システム
設計が確定したら、すべての実装が完了するまで自動的に実行を継続する
"""

import asyncio
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
import json

from ..log_system.structured_logger import StructuredLogger, LogLevel, LogCategory
from ..execution.implementation_task_manager import ImplementationTaskManager, TaskStatus
from ..execution.spec_driven_executor import SpecDrivenExecutor
from .collaboration_manager import CollaborationManager, CollaborationStatus


class AutoExecutionStatus(Enum):
    """自動実行ステータス"""
    IDLE = "IDLE"  # 待機中
    RUNNING = "RUNNING"  # 実行中
    PAUSED = "PAUSED"  # 一時停止
    COMPLETED = "COMPLETED"  # 完了
    FAILED = "FAILED"  # 失敗


@dataclass
class AutoExecutionSession:
    """自動実行セッション"""
    session_id: str
    collaboration_session_id: str
    status: AutoExecutionStatus
    design_files: Dict[str, str]  # agent_name -> design_file_path
    current_agent_index: int
    total_tasks: int
    completed_tasks: int
    failed_tasks: int
    started_at: datetime
    last_update_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    
    def __post_init__(self):
        if self.last_update_at is None:
            self.last_update_at = datetime.now()


class ContinuousExecutionManager:
    """設計確定後の自動実行継続管理システム"""
    
    def __init__(self, workspace_path: str, logger: StructuredLogger, config: Any):
        self.workspace_path = Path(workspace_path)
        self.logger = logger
        self.config = config
        
        self.collaboration_manager = CollaborationManager(workspace_path, logger)
        self.task_manager = ImplementationTaskManager(workspace_path, logger)
        # executorは必要に応じて初期化（設計ファイル実行時に使用）
        
        # 自動実行セッション保存ディレクトリ
        self.sessions_dir = self.workspace_path / '.nocturnal' / 'auto_execution_sessions'
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        
        # 現在の実行セッション
        self.current_session: Optional[AutoExecutionSession] = None
        self.is_running = False
    
    async def start_continuous_execution(self, collaboration_session_id: str) -> AutoExecutionSession:
        """設計確定後の自動実行を開始"""
        # すり合わせセッションを確認
        collab_session = self.collaboration_manager.get_session(collaboration_session_id)
        if not collab_session:
            raise ValueError(f"すり合わせセッションが見つかりません: {collaboration_session_id}")
        
        if collab_session.status != CollaborationStatus.DESIGN_APPROVED:
            raise ValueError(f"設計が承認されていません。現在のステータス: {collab_session.status}")
        
        # 実装開始をマーク
        self.collaboration_manager.mark_implementation_started(collaboration_session_id)
        
        # 自動実行セッションを作成
        session_id = f"auto_exec_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        session = AutoExecutionSession(
            session_id=session_id,
            collaboration_session_id=collaboration_session_id,
            status=AutoExecutionStatus.RUNNING,
            design_files=collab_session.design_files,
            current_agent_index=0,
            total_tasks=0,
            completed_tasks=0,
            failed_tasks=0,
            started_at=datetime.now(),
            last_update_at=datetime.now()
        )
        
        self.current_session = session
        self._save_session(session)
        
        self.logger.log(LogLevel.INFO, LogCategory.SYSTEM,
                       f"🚀 自動実行を開始しました: {session_id}")
        
        # バックグラウンドで実行開始
        self.is_running = True
        asyncio.create_task(self._run_continuous_execution(session))
        
        return session
    
    async def _run_continuous_execution(self, session: AutoExecutionSession):
        """自動実行のメインループ"""
        try:
            agent_names = list(session.design_files.keys())
            
            # 各エージェントの設計ファイルを順次実行
            for agent_index, agent_name in enumerate(agent_names):
                if not self.is_running:
                    session.status = AutoExecutionStatus.PAUSED
                    self._save_session(session)
                    self.logger.log(LogLevel.INFO, LogCategory.SYSTEM,
                                   f"⏸️ 自動実行が一時停止されました: {session.session_id}")
                    return
                
                design_file_path = session.design_files[agent_name]
                session.current_agent_index = agent_index
                self._save_session(session)
                
                self.logger.log(LogLevel.INFO, LogCategory.SYSTEM,
                               f"📋 エージェント '{agent_name}' の実装を開始: {design_file_path}")
                
                # 設計ファイルからタスクを実行
                await self._execute_design_file(session, agent_name, design_file_path)
                
                # タスク完了をチェック
                if await self._check_all_tasks_completed():
                    session.status = AutoExecutionStatus.COMPLETED
                    session.completed_at = datetime.now()
                    self.collaboration_manager.mark_implementation_completed(
                        session.collaboration_session_id
                    )
                    self._save_session(session)
                    self.logger.log(LogLevel.INFO, LogCategory.SYSTEM,
                                   f"🎉 すべての実装が完了しました: {session.session_id}")
                    return
            
            # すべてのエージェントの実行が完了
            # 再度タスク完了をチェック
            if await self._check_all_tasks_completed():
                session.status = AutoExecutionStatus.COMPLETED
                session.completed_at = datetime.now()
                self.collaboration_manager.mark_implementation_completed(
                    session.collaboration_session_id
                )
                self._save_session(session)
                self.logger.log(LogLevel.INFO, LogCategory.SYSTEM,
                               f"🎉 すべての実装が完了しました: {session.session_id}")
            else:
                # 未完了タスクがある場合は再実行
                self.logger.log(LogLevel.INFO, LogCategory.SYSTEM,
                               f"🔄 未完了タスクがあるため、再実行を開始します: {session.session_id}")
                await self._retry_failed_tasks(session)
        
        except Exception as e:
            session.status = AutoExecutionStatus.FAILED
            session.error_message = str(e)
            session.last_update_at = datetime.now()
            self._save_session(session)
            self.logger.log(LogLevel.ERROR, LogCategory.SYSTEM,
                          f"❌ 自動実行エラー: {session.session_id} - {e}")
            raise
    
    async def _execute_design_file(self, session: AutoExecutionSession, 
                                  agent_name: str, design_file_path: str):
        """設計ファイルを実行"""
        try:
            from ..design.design_file_manager import DistributedDesignGenerator
            from ..execution.implementation_task_manager import ImplementationTaskManager
            
            # 設計ファイル管理システムを初期化
            design_generator = DistributedDesignGenerator(self.logger)
            
            # 設計ファイルを検証・準備
            design = design_generator.validate_and_prepare_design(design_file_path)
            if not design:
                raise ValueError(f"設計ファイルの検証に失敗しました: {design_file_path}")
            
            # ワークスペースパスを取得
            workspace_path = design.get('project_info', {}).get('workspace_path', '')
            if not workspace_path:
                workspace_path = str(self.workspace_path)
            
            # タスクを実装タスク管理システムに登録
            generated_tasks = design.get('generated_tasks', [])
            created_task_ids = []
            task_id_mapping = {}
            
            self.logger.log(LogLevel.INFO, LogCategory.SYSTEM,
                           f"📝 タスク登録開始: {len(generated_tasks)}個のタスク ({agent_name})")
            
            # 第1パス: 依存関係なしでタスクを作成
            for task_data in generated_tasks:
                original_task_id = task_data.get('task_id', f"task_{len(created_task_ids)}")
                
                # タスクデータを実装タスク用に変換
                task_spec = {
                    'title': task_data.get('title', 'Unknown Task'),
                    'description': task_data.get('description', ''),
                    'priority': task_data.get('priority', 'MEDIUM'),
                    'estimated_hours': task_data.get('estimated_hours', 2.0),
                    'technical_requirements': task_data.get('technical_requirements', []),
                    'acceptance_criteria': task_data.get('acceptance_criteria', []),
                    'dependencies': []
                }
                
                task_id = self.task_manager.create_task_from_specification(task_spec)
                created_task_ids.append(task_id)
                task_id_mapping[original_task_id] = task_id
                
                # 作成されたタスクを承認状態にする
                self.task_manager.approve_task(task_id, f"design_file_execution_{agent_name}")
            
            # 第2パス: 依存関係を設定
            for i, task_data in enumerate(generated_tasks):
                if 'dependencies' in task_data and task_data['dependencies']:
                    task_id = created_task_ids[i]
                    valid_dependencies = []
                    for dep_id in task_data['dependencies']:
                        if dep_id in task_id_mapping:
                            valid_dependencies.append(task_id_mapping[dep_id])
                    
                    if task_id in self.task_manager.tasks:
                        self.task_manager.tasks[task_id].dependencies = valid_dependencies
            
            self.logger.log(LogLevel.INFO, LogCategory.SYSTEM,
                           f"✅ {len(created_task_ids)}個のタスクを登録・承認完了 ({agent_name})")
            
            # タスクを実行
            from ..execution.implementation_task_manager import NightlyTaskExecutor
            executor = NightlyTaskExecutor(
                workspace_path=str(workspace_path),
                logger=self.logger,
                config=self.config
            )
            
            # すべてのタスクを実行
            pending_tasks = [
                t for t in self.task_manager.get_all_tasks().values()
                if t.status == TaskStatus.APPROVED and t.task_id in created_task_ids
            ]
            
            self.logger.log(LogLevel.INFO, LogCategory.SYSTEM,
                           f"🚀 {len(pending_tasks)}個のタスクを実行開始 ({agent_name})")
            
            for task in pending_tasks:
                try:
                    await executor.execute_task(task)
                except Exception as e:
                    self.logger.log(LogLevel.ERROR, LogCategory.SYSTEM,
                                  f"❌ タスク実行エラー ({task.task_id}): {e}")
            
            # タスク統計を更新
            all_tasks = self.task_manager.get_all_tasks()
            session.total_tasks = len(all_tasks)
            session.completed_tasks = len([
                t for t in all_tasks.values() 
                if t.status == TaskStatus.COMPLETED
            ])
            session.failed_tasks = len([
                t for t in all_tasks.values() 
                if t.status == TaskStatus.FAILED
            ])
            session.last_update_at = datetime.now()
            self._save_session(session)
            
            self.logger.log(LogLevel.INFO, LogCategory.SYSTEM,
                           f"✅ エージェント '{agent_name}' の実行完了: "
                           f"完了={session.completed_tasks}, 失敗={session.failed_tasks}, "
                           f"合計={session.total_tasks}")
        
        except Exception as e:
            self.logger.log(LogLevel.ERROR, LogCategory.SYSTEM,
                          f"❌ 設計ファイル実行エラー ({agent_name}): {e}")
            raise
    
    async def _check_all_tasks_completed(self) -> bool:
        """すべてのタスクが完了したかチェック"""
        all_tasks = self.task_manager.get_all_tasks()
        
        if not all_tasks:
            return False
        
        for task in all_tasks.values():
            if task.status not in [TaskStatus.COMPLETED, TaskStatus.SKIPPED]:
                return False
        
        return True
    
    async def _retry_failed_tasks(self, session: AutoExecutionSession):
        """失敗したタスクを再実行"""
        failed_tasks = [
            t for t in self.task_manager.get_all_tasks().values()
            if t.status == TaskStatus.FAILED
        ]
        
        if not failed_tasks:
            return
        
        self.logger.log(LogLevel.INFO, LogCategory.SYSTEM,
                       f"🔄 {len(failed_tasks)}個の失敗タスクを再実行します")
        
        # 失敗したタスクを再実行
        for task in failed_tasks:
            try:
                # タスクを再実行可能な状態にリセット
                task.status = TaskStatus.PENDING
                self.task_manager.update_task(task.task_id, task)
                
                # タスクを再実行（簡易実装）
                # 実際には、SpecDrivenExecutorの再実行機能を使用する必要がある
                self.logger.log(LogLevel.INFO, LogCategory.SYSTEM,
                               f"🔄 タスクを再実行: {task.task_id} - {task.title}")
            
            except Exception as e:
                self.logger.log(LogLevel.ERROR, LogCategory.SYSTEM,
                              f"❌ タスク再実行エラー ({task.task_id}): {e}")
        
        # 再実行後、再度完了チェック
        await asyncio.sleep(5)  # 少し待機
        if await self._check_all_tasks_completed():
            session.status = AutoExecutionStatus.COMPLETED
            session.completed_at = datetime.now()
            self.collaboration_manager.mark_implementation_completed(
                session.collaboration_session_id
            )
            self._save_session(session)
    
    def pause_execution(self, session_id: str):
        """実行を一時停止"""
        session = self._load_session(session_id)
        if not session:
            raise ValueError(f"セッションが見つかりません: {session_id}")
        
        self.is_running = False
        session.status = AutoExecutionStatus.PAUSED
        session.last_update_at = datetime.now()
        self._save_session(session)
        
        self.logger.log(LogLevel.INFO, LogCategory.SYSTEM,
                       f"⏸️ 実行を一時停止しました: {session_id}")
    
    def resume_execution(self, session_id: str):
        """実行を再開"""
        session = self._load_session(session_id)
        if not session:
            raise ValueError(f"セッションが見つかりません: {session_id}")
        
        if session.status != AutoExecutionStatus.PAUSED:
            raise ValueError(f"実行が一時停止されていません。現在のステータス: {session.status}")
        
        self.is_running = True
        session.status = AutoExecutionStatus.RUNNING
        session.last_update_at = datetime.now()
        self._save_session(session)
        
        # バックグラウンドで実行再開
        asyncio.create_task(self._run_continuous_execution(session))
        
        self.logger.log(LogLevel.INFO, LogCategory.SYSTEM,
                       f"▶️ 実行を再開しました: {session_id}")
    
    def stop_execution(self, session_id: str):
        """実行を停止"""
        session = self._load_session(session_id)
        if not session:
            raise ValueError(f"セッションが見つかりません: {session_id}")
        
        self.is_running = False
        session.status = AutoExecutionStatus.IDLE
        session.last_update_at = datetime.now()
        self._save_session(session)
        
        self.logger.log(LogLevel.INFO, LogCategory.SYSTEM,
                       f"⏹️ 実行を停止しました: {session_id}")
    
    def get_session(self, session_id: str) -> Optional[AutoExecutionSession]:
        """セッションを取得"""
        return self._load_session(session_id)
    
    def get_current_session(self) -> Optional[AutoExecutionSession]:
        """現在の実行セッションを取得"""
        return self.current_session
    
    def get_status(self, session_id: str) -> Dict[str, Any]:
        """実行ステータスを取得"""
        session = self._load_session(session_id)
        if not session:
            return {"error": "セッションが見つかりません"}
        
        all_tasks = self.task_manager.get_all_tasks()
        
        return {
            "session_id": session.session_id,
            "status": session.status.value,
            "total_tasks": len(all_tasks),
            "completed_tasks": session.completed_tasks,
            "failed_tasks": session.failed_tasks,
            "progress_percentage": (
                (session.completed_tasks / session.total_tasks * 100)
                if session.total_tasks > 0 else 0
            ),
            "started_at": session.started_at.isoformat(),
            "last_update_at": session.last_update_at.isoformat(),
            "completed_at": session.completed_at.isoformat() if session.completed_at else None
        }
    
    def _load_session(self, session_id: str) -> Optional[AutoExecutionSession]:
        """セッションを読み込み"""
        session_file = self.sessions_dir / f"session_{session_id}.json"
        if not session_file.exists():
            return None
        
        try:
            with open(session_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # datetimeフィールドを復元
            for field in ['started_at', 'last_update_at', 'completed_at']:
                if data.get(field):
                    data[field] = datetime.fromisoformat(data[field])
            
            # Enumフィールドを復元
            data['status'] = AutoExecutionStatus(data['status'])
            
            return AutoExecutionSession(**data)
        except Exception as e:
            self.logger.log(LogLevel.ERROR, LogCategory.SYSTEM,
                          f"セッション読み込みエラー: {session_file} - {e}")
            return None
    
    def _save_session(self, session: AutoExecutionSession):
        """セッションを保存"""
        session_file = self.sessions_dir / f"session_{session.session_id}.json"
        
        # dataclassを辞書に変換
        data = asdict(session)
        
        # datetimeフィールドをISO形式に変換
        for field in ['started_at', 'last_update_at', 'completed_at']:
            if data.get(field):
                data[field] = data[field].isoformat()
        
        # Enumフィールドを文字列に変換
        data['status'] = data['status'].value
        
        with open(session_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
