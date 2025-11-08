"""
要件・設計のすり合わせ管理システム
ユーザーと対話的に要件と設計を確認・修正し、設計確定まで管理する
"""

import json
import yaml
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

from ..log_system.structured_logger import StructuredLogger, LogLevel, LogCategory
from .requirements_parser import RequirementsParser, RequirementAnalysis
from .design_generator import DesignFileGenerator


class CollaborationStatus(Enum):
    """すり合わせステータス"""
    REQUIREMENTS_DRAFT = "REQUIREMENTS_DRAFT"  # 要件草案
    REQUIREMENTS_REVIEW = "REQUIREMENTS_REVIEW"  # 要件レビュー中
    REQUIREMENTS_APPROVED = "REQUIREMENTS_APPROVED"  # 要件承認済み
    DESIGN_DRAFT = "DESIGN_DRAFT"  # 設計草案
    DESIGN_REVIEW = "DESIGN_REVIEW"  # 設計レビュー中
    DESIGN_APPROVED = "DESIGN_APPROVED"  # 設計承認済み（実装開始可能）
    IMPLEMENTATION_IN_PROGRESS = "IMPLEMENTATION_IN_PROGRESS"  # 実装中
    IMPLEMENTATION_COMPLETED = "IMPLEMENTATION_COMPLETED"  # 実装完了


@dataclass
class CollaborationSession:
    """すり合わせセッション"""
    session_id: str
    status: CollaborationStatus
    original_requirements: str
    current_requirements: str
    requirements_feedback: List[str]
    design_files: Dict[str, str]  # agent_name -> design_file_path
    design_feedback: Dict[str, List[str]]  # agent_name -> feedback list
    approved_at: Optional[datetime] = None
    created_at: datetime = None
    updated_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()


class CollaborationManager:
    """要件・設計のすり合わせ管理システム"""
    
    def __init__(self, workspace_path: str, logger: StructuredLogger):
        self.workspace_path = Path(workspace_path)
        self.logger = logger
        self.requirements_parser = RequirementsParser()
        self.design_generator = DesignFileGenerator()
        
        # セッション保存ディレクトリ
        self.sessions_dir = self.workspace_path / '.nocturnal' / 'collaboration_sessions'
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        
        # 現在のセッション
        self.current_session: Optional[CollaborationSession] = None
    
    def start_collaboration(self, requirements_text: str, project_name: str) -> CollaborationSession:
        """新しいすり合わせセッションを開始"""
        session_id = f"collab_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        session = CollaborationSession(
            session_id=session_id,
            status=CollaborationStatus.REQUIREMENTS_DRAFT,
            original_requirements=requirements_text,
            current_requirements=requirements_text,
            requirements_feedback=[],
            design_files={},
            design_feedback={}
        )
        
        self.current_session = session
        self._save_session(session)
        
        self.logger.log(LogLevel.INFO, LogCategory.SYSTEM,
                       f"📝 新しいすり合わせセッションを開始: {session_id}")
        
        return session
    
    def update_requirements(self, session_id: str, updated_requirements: str) -> CollaborationSession:
        """要件を更新"""
        session = self._load_session(session_id)
        if not session:
            raise ValueError(f"セッションが見つかりません: {session_id}")
        
        session.current_requirements = updated_requirements
        session.status = CollaborationStatus.REQUIREMENTS_DRAFT
        session.updated_at = datetime.now()
        
        self._save_session(session)
        self.logger.log(LogLevel.INFO, LogCategory.SYSTEM,
                       f"📝 要件を更新しました: {session_id}")
        
        return session
    
    def add_requirements_feedback(self, session_id: str, feedback: str) -> CollaborationSession:
        """要件へのフィードバックを追加"""
        session = self._load_session(session_id)
        if not session:
            raise ValueError(f"セッションが見つかりません: {session_id}")
        
        session.requirements_feedback.append({
            "timestamp": datetime.now().isoformat(),
            "feedback": feedback
        })
        session.status = CollaborationStatus.REQUIREMENTS_REVIEW
        session.updated_at = datetime.now()
        
        self._save_session(session)
        return session
    
    def approve_requirements(self, session_id: str) -> Tuple[CollaborationSession, RequirementAnalysis]:
        """要件を承認し、設計ファイルを生成"""
        session = self._load_session(session_id)
        if not session:
            raise ValueError(f"セッションが見つかりません: {session_id}")
        
        # 要件を解析
        analysis = self.requirements_parser.parse_requirements(session.current_requirements)
        
        # 設計ファイルを生成
        project_name = self._extract_project_name(session.current_requirements)
        design_files = self.design_generator.generate_design_files(
            analysis, str(self.workspace_path), project_name
        )
        
        session.design_files = design_files
        session.status = CollaborationStatus.DESIGN_DRAFT
        session.updated_at = datetime.now()
        
        self._save_session(session)
        self.logger.log(LogLevel.INFO, LogCategory.SYSTEM,
                       f"✅ 要件を承認し、設計ファイルを生成しました: {session_id}")
        
        return session, analysis
    
    def update_design(self, session_id: str, agent_name: str, design_file_path: str) -> CollaborationSession:
        """設計ファイルを更新"""
        session = self._load_session(session_id)
        if not session:
            raise ValueError(f"セッションが見つかりません: {session_id}")
        
        session.design_files[agent_name] = design_file_path
        session.status = CollaborationStatus.DESIGN_DRAFT
        session.updated_at = datetime.now()
        
        self._save_session(session)
        self.logger.log(LogLevel.INFO, LogCategory.SYSTEM,
                       f"📝 設計ファイルを更新しました: {agent_name} - {session_id}")
        
        return session
    
    def add_design_feedback(self, session_id: str, agent_name: str, feedback: str) -> CollaborationSession:
        """設計へのフィードバックを追加"""
        session = self._load_session(session_id)
        if not session:
            raise ValueError(f"セッションが見つかりません: {session_id}")
        
        if agent_name not in session.design_feedback:
            session.design_feedback[agent_name] = []
        
        session.design_feedback[agent_name].append({
            "timestamp": datetime.now().isoformat(),
            "feedback": feedback
        })
        session.status = CollaborationStatus.DESIGN_REVIEW
        session.updated_at = datetime.now()
        
        self._save_session(session)
        return session
    
    def approve_design(self, session_id: str) -> CollaborationSession:
        """設計を承認し、実装開始可能な状態にする"""
        session = self._load_session(session_id)
        if not session:
            raise ValueError(f"セッションが見つかりません: {session_id}")
        
        session.status = CollaborationStatus.DESIGN_APPROVED
        session.approved_at = datetime.now()
        session.updated_at = datetime.now()
        
        self._save_session(session)
        self.logger.log(LogLevel.INFO, LogCategory.SYSTEM,
                       f"✅ 設計を承認しました。実装を開始できます: {session_id}")
        
        return session
    
    def mark_implementation_started(self, session_id: str) -> CollaborationSession:
        """実装開始をマーク"""
        session = self._load_session(session_id)
        if not session:
            raise ValueError(f"セッションが見つかりません: {session_id}")
        
        if session.status != CollaborationStatus.DESIGN_APPROVED:
            raise ValueError(f"設計が承認されていません。現在のステータス: {session.status}")
        
        session.status = CollaborationStatus.IMPLEMENTATION_IN_PROGRESS
        session.updated_at = datetime.now()
        
        self._save_session(session)
        return session
    
    def mark_implementation_completed(self, session_id: str) -> CollaborationSession:
        """実装完了をマーク"""
        session = self._load_session(session_id)
        if not session:
            raise ValueError(f"セッションが見つかりません: {session_id}")
        
        session.status = CollaborationStatus.IMPLEMENTATION_COMPLETED
        session.updated_at = datetime.now()
        
        self._save_session(session)
        self.logger.log(LogLevel.INFO, LogCategory.SYSTEM,
                       f"🎉 実装が完了しました: {session_id}")
        
        return session
    
    def get_session(self, session_id: str) -> Optional[CollaborationSession]:
        """セッションを取得"""
        return self._load_session(session_id)
    
    def get_current_session(self) -> Optional[CollaborationSession]:
        """現在のセッションを取得"""
        if self.current_session:
            return self._load_session(self.current_session.session_id)
        return None
    
    def list_sessions(self) -> List[CollaborationSession]:
        """すべてのセッションをリストアップ"""
        sessions = []
        for session_file in self.sessions_dir.glob("session_*.json"):
            try:
                session = self._load_session_from_file(session_file)
                if session:
                    sessions.append(session)
            except Exception as e:
                self.logger.log(LogLevel.WARNING, LogCategory.SYSTEM,
                              f"セッションファイル読み込みエラー: {session_file} - {e}")
        
        return sorted(sessions, key=lambda s: s.created_at, reverse=True)
    
    def _load_session(self, session_id: str) -> Optional[CollaborationSession]:
        """セッションを読み込み"""
        session_file = self.sessions_dir / f"session_{session_id}.json"
        return self._load_session_from_file(session_file)
    
    def _load_session_from_file(self, session_file: Path) -> Optional[CollaborationSession]:
        """ファイルからセッションを読み込み"""
        if not session_file.exists():
            return None
        
        try:
            with open(session_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # datetimeフィールドを復元
            for field in ['created_at', 'updated_at', 'approved_at']:
                if data.get(field):
                    data[field] = datetime.fromisoformat(data[field])
            
            # Enumフィールドを復元
            data['status'] = CollaborationStatus(data['status'])
            
            return CollaborationSession(**data)
        except Exception as e:
            self.logger.log(LogLevel.ERROR, LogCategory.SYSTEM,
                          f"セッション読み込みエラー: {session_file} - {e}")
            return None
    
    def _save_session(self, session: CollaborationSession):
        """セッションを保存"""
        session_file = self.sessions_dir / f"session_{session.session_id}.json"
        
        # dataclassを辞書に変換
        data = asdict(session)
        
        # datetimeフィールドをISO形式に変換
        for field in ['created_at', 'updated_at', 'approved_at']:
            if data.get(field):
                data[field] = data[field].isoformat()
        
        # Enumフィールドを文字列に変換
        data['status'] = data['status'].value
        
        with open(session_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def _extract_project_name(self, requirements_text: str) -> str:
        """要件テキストからプロジェクト名を抽出"""
        # 簡単な抽出ロジック（必要に応じて改善可能）
        lines = requirements_text.split('\n')
        for line in lines[:5]:  # 最初の5行をチェック
            if 'プロジェクト名' in line or 'project name' in line.lower():
                parts = line.split(':')
                if len(parts) > 1:
                    return parts[1].strip()
        
        return "新規プロジェクト"
