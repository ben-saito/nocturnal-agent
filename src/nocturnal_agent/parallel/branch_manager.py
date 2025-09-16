"""ブランチ管理システム - 夜間並行実行のためのGitブランチ管理"""

import logging
import subprocess
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class BranchType(Enum):
    """ブランチ種別"""
    NIGHT_MAIN = "night_main"           # 夜間メインブランチ
    HIGH_QUALITY = "high_quality"       # 高品質タスク用ブランチ
    MEDIUM_QUALITY = "medium_quality"   # 中品質タスク用ブランチ
    EXPERIMENTAL = "experimental"       # 実験用ブランチ
    EMERGENCY = "emergency"             # 緊急用ブランチ


@dataclass
class BranchInfo:
    """ブランチ情報"""
    name: str
    branch_type: BranchType
    base_commit: str
    created_at: datetime
    last_activity: datetime
    quality_threshold: float
    associated_tasks: List[str] = field(default_factory=list)
    merge_candidates: List[str] = field(default_factory=list)
    conflict_count: int = 0
    status: str = "active"  # active, merged, abandoned
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MergeConflict:
    """マージ競合情報"""
    source_branch: str
    target_branch: str
    conflicting_files: List[str]
    conflict_type: str  # content, rename, delete, etc.
    severity: str       # low, medium, high
    resolution_strategy: Optional[str] = None
    auto_resolvable: bool = False


class BranchManager:
    """並行実行用ブランチ管理システム"""
    
    def __init__(self, project_path: str, config: Dict[str, Any]):
        """
        ブランチ管理システムを初期化
        
        Args:
            project_path: プロジェクトのパス
            config: ブランチ管理設定
        """
        self.project_path = Path(project_path)
        self.config = config
        
        # ブランチ命名設定
        self.branch_prefix = config.get('branch_prefix', 'nocturnal')
        self.date_format = config.get('date_format', '%Y%m%d')
        
        # 品質閾値設定
        self.high_quality_threshold = config.get('high_quality_threshold', 0.85)
        self.medium_quality_threshold = config.get('medium_quality_threshold', 0.7)
        
        # ブランチ管理設定
        self.max_parallel_branches = config.get('max_parallel_branches', 5)
        self.auto_merge_high_quality = config.get('auto_merge_high_quality', True)
        self.conflict_detection_enabled = config.get('conflict_detection_enabled', True)
        
        # 現在のブランチ状態
        self.active_branches: Dict[str, BranchInfo] = {}
        self.current_night_session: Optional[str] = None
        
        # 統計
        self.branch_stats = {
            'session_start': datetime.now(),
            'branches_created': 0,
            'branches_merged': 0,
            'conflicts_detected': 0,
            'conflicts_resolved': 0,
            'auto_merges_successful': 0,
            'manual_interventions': 0
        }
    
    def initialize_night_session(self) -> str:
        """
        夜間セッション用のブランチ環境を初期化
        
        Returns:
            夜間メインブランチ名
        """
        logger.info("夜間セッション用ブランチ環境を初期化中")
        
        try:
            # 現在のブランチとコミットを取得
            current_branch = self._get_current_branch()
            current_commit = self._get_current_commit()
            
            # 夜間セッション名を生成
            session_id = datetime.now().strftime(self.date_format)
            night_main_branch = f"{self.branch_prefix}/night-{session_id}"
            
            # 夜間メインブランチを作成
            self._create_branch(night_main_branch, current_commit)
            
            # ブランチ情報を記録
            self.active_branches[night_main_branch] = BranchInfo(
                name=night_main_branch,
                branch_type=BranchType.NIGHT_MAIN,
                base_commit=current_commit,
                created_at=datetime.now(),
                last_activity=datetime.now(),
                quality_threshold=0.0,  # メインブランチは品質制限なし
                metadata={
                    'original_branch': current_branch,
                    'session_id': session_id
                }
            )
            
            self.current_night_session = night_main_branch
            self.branch_stats['branches_created'] += 1
            
            logger.info(f"夜間メインブランチ作成完了: {night_main_branch}")
            return night_main_branch
            
        except Exception as e:
            logger.error(f"夜間セッション初期化エラー: {e}")
            raise
    
    def create_quality_branch(self, quality_score: float, task_id: str, 
                            task_description: str = "") -> str:
        """
        品質レベルに応じたブランチを作成
        
        Args:
            quality_score: 品質スコア
            task_id: タスクID
            task_description: タスク説明
            
        Returns:
            作成されたブランチ名
        """
        logger.debug(f"品質別ブランチ作成: タスク {task_id}, 品質 {quality_score:.2f}")
        
        try:
            # 品質レベルに基づいてブランチタイプを決定
            branch_type = self._determine_branch_type(quality_score)
            
            # ブランチ名を生成
            timestamp = datetime.now().strftime('%H%M%S')
            branch_name = f"{self.branch_prefix}/{branch_type.value}-{task_id}-{timestamp}"
            
            # ベースコミットを決定
            if branch_type == BranchType.HIGH_QUALITY:
                # 高品質タスクは夜間メインブランチをベースに
                base_branch = self.current_night_session
            else:
                # 中・低品質タスクは現在のコミットをベースに
                base_branch = None
            
            base_commit = self._get_branch_commit(base_branch) if base_branch else self._get_current_commit()
            
            # ブランチを作成
            self._create_branch(branch_name, base_commit)
            
            # ブランチ情報を記録
            self.active_branches[branch_name] = BranchInfo(
                name=branch_name,
                branch_type=branch_type,
                base_commit=base_commit,
                created_at=datetime.now(),
                last_activity=datetime.now(),
                quality_threshold=self._get_quality_threshold(branch_type),
                associated_tasks=[task_id],
                metadata={
                    'task_description': task_description[:100],
                    'expected_quality': quality_score
                }
            )
            
            self.branch_stats['branches_created'] += 1
            
            logger.info(f"品質別ブランチ作成完了: {branch_name} (品質: {quality_score:.2f})")
            return branch_name
            
        except Exception as e:
            logger.error(f"品質別ブランチ作成エラー: {e}")
            raise
    
    def switch_to_branch(self, branch_name: str) -> bool:
        """
        指定されたブランチに切り替え
        
        Args:
            branch_name: 切り替え先ブランチ名
            
        Returns:
            切り替え成功フラグ
        """
        try:
            result = subprocess.run([
                'git', 'checkout', branch_name
            ], cwd=self.project_path, capture_output=True, text=True, check=True)
            
            # ブランチ情報の最終活動時刻を更新
            if branch_name in self.active_branches:
                self.active_branches[branch_name].last_activity = datetime.now()
            
            logger.debug(f"ブランチ切り替え完了: {branch_name}")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"ブランチ切り替えエラー ({branch_name}): {e.stderr}")
            return False
    
    def commit_task_result(self, task_id: str, commit_message: str, 
                          files_changed: List[str]) -> Optional[str]:
        """
        タスク結果をコミット
        
        Args:
            task_id: タスクID
            commit_message: コミットメッセージ
            files_changed: 変更されたファイル一覧
            
        Returns:
            コミットハッシュ
        """
        try:
            # 変更されたファイルをステージング
            if files_changed:
                subprocess.run([
                    'git', 'add'
                ] + files_changed, cwd=self.project_path, check=True)
            else:
                # すべての変更をステージング
                subprocess.run([
                    'git', 'add', '-A'
                ], cwd=self.project_path, check=True)
            
            # コミット実行
            full_commit_message = f"{commit_message}\n\nTask-ID: {task_id}\nNocturnal-Agent: automated-commit"
            
            result = subprocess.run([
                'git', 'commit', '-m', full_commit_message
            ], cwd=self.project_path, capture_output=True, text=True, check=True)
            
            # コミットハッシュを取得
            commit_hash = self._get_current_commit()
            
            # 現在のブランチの情報を更新
            current_branch = self._get_current_branch()
            if current_branch in self.active_branches:
                branch_info = self.active_branches[current_branch]
                branch_info.last_activity = datetime.now()
                if task_id not in branch_info.associated_tasks:
                    branch_info.associated_tasks.append(task_id)
            
            logger.debug(f"タスク結果コミット完了: {task_id} -> {commit_hash[:8]}")
            return commit_hash
            
        except subprocess.CalledProcessError as e:
            logger.error(f"コミットエラー ({task_id}): {e.stderr}")
            return None
    
    def detect_merge_conflicts(self, source_branch: str, target_branch: str) -> List[MergeConflict]:
        """
        マージ競合を検出
        
        Args:
            source_branch: ソースブランチ
            target_branch: ターゲットブランチ
            
        Returns:
            検出された競合のリスト
        """
        conflicts = []
        
        if not self.conflict_detection_enabled:
            return conflicts
        
        try:
            # マージの試行（dry-run）
            result = subprocess.run([
                'git', 'merge-tree', 
                self._get_branch_commit(target_branch),
                self._get_branch_commit(source_branch)
            ], cwd=self.project_path, capture_output=True, text=True)
            
            if result.stdout.strip():
                # 競合が検出された場合
                conflicting_files = self._parse_conflict_output(result.stdout)
                
                conflict = MergeConflict(
                    source_branch=source_branch,
                    target_branch=target_branch,
                    conflicting_files=conflicting_files,
                    conflict_type="content",  # 詳細な分析が必要
                    severity=self._assess_conflict_severity(conflicting_files),
                    auto_resolvable=len(conflicting_files) <= 2  # 簡単な判定
                )
                
                conflicts.append(conflict)
                self.branch_stats['conflicts_detected'] += 1
                
                logger.warning(f"マージ競合検出: {source_branch} -> {target_branch} ({len(conflicting_files)}ファイル)")
        
        except Exception as e:
            logger.error(f"競合検出エラー: {e}")
        
        return conflicts
    
    def attempt_auto_merge(self, source_branch: str, target_branch: str, 
                          quality_score: float) -> Dict[str, Any]:
        """
        自動マージを試行
        
        Args:
            source_branch: ソースブランチ
            target_branch: ターゲットブランチ
            quality_score: 品質スコア
            
        Returns:
            マージ結果
        """
        logger.debug(f"自動マージ試行: {source_branch} -> {target_branch}")
        
        merge_result = {
            'success': False,
            'commit_hash': None,
            'conflicts': [],
            'strategy_used': None,
            'manual_intervention_required': False
        }
        
        try:
            # 品質チェック
            if quality_score < self.high_quality_threshold and target_branch == self.current_night_session:
                merge_result['manual_intervention_required'] = True
                merge_result['strategy_used'] = 'quality_gate_rejected'
                logger.warning(f"品質ゲートによりマージ拒否: 品質 {quality_score:.2f}")
                return merge_result
            
            # 競合検出
            conflicts = self.detect_merge_conflicts(source_branch, target_branch)
            merge_result['conflicts'] = conflicts
            
            if conflicts:
                # 競合がある場合
                if all(conflict.auto_resolvable for conflict in conflicts):
                    # 自動解決可能な競合
                    merge_result['strategy_used'] = 'auto_resolve'
                    # 実際の自動解決ロジックは複雑なため、今回は簡略化
                    logger.info("自動解決可能な競合を検出（実装省略）")
                else:
                    # 手動介入が必要
                    merge_result['manual_intervention_required'] = True
                    merge_result['strategy_used'] = 'manual_intervention_required'
                    self.branch_stats['manual_interventions'] += 1
                    return merge_result
            
            # 実際のマージ実行
            current_branch = self._get_current_branch()
            
            # ターゲットブランチに切り替え
            self.switch_to_branch(target_branch)
            
            try:
                # マージ実行
                result = subprocess.run([
                    'git', 'merge', '--no-ff', source_branch,
                    '-m', f"Auto-merge: {source_branch} (quality: {quality_score:.2f})"
                ], cwd=self.project_path, capture_output=True, text=True, check=True)
                
                merge_result['success'] = True
                merge_result['commit_hash'] = self._get_current_commit()
                merge_result['strategy_used'] = 'fast_forward_merge'
                
                # 統計更新
                self.branch_stats['branches_merged'] += 1
                self.branch_stats['auto_merges_successful'] += 1
                
                # ブランチ情報更新
                if source_branch in self.active_branches:
                    self.active_branches[source_branch].status = 'merged'
                
                logger.info(f"自動マージ完了: {source_branch} -> {target_branch}")
                
            except subprocess.CalledProcessError as e:
                logger.error(f"マージ実行エラー: {e.stderr}")
                merge_result['strategy_used'] = 'merge_failed'
                
            finally:
                # 元のブランチに戻る
                self.switch_to_branch(current_branch)
        
        except Exception as e:
            logger.error(f"自動マージエラー: {e}")
            merge_result['strategy_used'] = 'exception_occurred'
        
        return merge_result
    
    def cleanup_inactive_branches(self, max_age_hours: int = 24) -> List[str]:
        """
        非アクティブなブランチをクリーンアップ
        
        Args:
            max_age_hours: 最大経過時間
            
        Returns:
            削除されたブランチのリスト
        """
        deleted_branches = []
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        
        for branch_name, branch_info in list(self.active_branches.items()):
            if (branch_info.status in ['merged', 'abandoned'] and
                branch_info.last_activity < cutoff_time and
                branch_info.branch_type != BranchType.NIGHT_MAIN):
                
                try:
                    # ブランチ削除
                    subprocess.run([
                        'git', 'branch', '-D', branch_name
                    ], cwd=self.project_path, capture_output=True, text=True, check=True)
                    
                    del self.active_branches[branch_name]
                    deleted_branches.append(branch_name)
                    
                    logger.debug(f"非アクティブブランチ削除: {branch_name}")
                    
                except subprocess.CalledProcessError as e:
                    logger.warning(f"ブランチ削除エラー ({branch_name}): {e.stderr}")
        
        return deleted_branches
    
    def get_branch_status(self) -> Dict[str, Any]:
        """ブランチ管理の状態を取得"""
        return {
            'current_night_session': self.current_night_session,
            'active_branches_count': len([b for b in self.active_branches.values() if b.status == 'active']),
            'total_branches': len(self.active_branches),
            'branch_breakdown': {
                branch_type.value: len([b for b in self.active_branches.values() if b.branch_type == branch_type])
                for branch_type in BranchType
            },
            'statistics': self.branch_stats,
            'recent_activity': [
                {
                    'name': info.name,
                    'type': info.branch_type.value,
                    'last_activity': info.last_activity.isoformat(),
                    'task_count': len(info.associated_tasks)
                }
                for info in sorted(self.active_branches.values(), key=lambda x: x.last_activity, reverse=True)[:5]
            ]
        }
    
    def _get_current_branch(self) -> str:
        """現在のブランチ名を取得"""
        result = subprocess.run([
            'git', 'branch', '--show-current'
        ], cwd=self.project_path, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    
    def _get_current_commit(self) -> str:
        """現在のコミットハッシュを取得"""
        result = subprocess.run([
            'git', 'rev-parse', 'HEAD'
        ], cwd=self.project_path, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    
    def _get_branch_commit(self, branch_name: str) -> str:
        """指定ブランチのコミットハッシュを取得"""
        result = subprocess.run([
            'git', 'rev-parse', branch_name
        ], cwd=self.project_path, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    
    def _create_branch(self, branch_name: str, base_commit: str):
        """新しいブランチを作成"""
        subprocess.run([
            'git', 'checkout', '-b', branch_name, base_commit
        ], cwd=self.project_path, capture_output=True, text=True, check=True)
    
    def _determine_branch_type(self, quality_score: float) -> BranchType:
        """品質スコアに基づいてブランチタイプを決定"""
        if quality_score >= self.high_quality_threshold:
            return BranchType.HIGH_QUALITY
        elif quality_score >= self.medium_quality_threshold:
            return BranchType.MEDIUM_QUALITY
        else:
            return BranchType.EXPERIMENTAL
    
    def _get_quality_threshold(self, branch_type: BranchType) -> float:
        """ブランチタイプに対応する品質閾値を取得"""
        thresholds = {
            BranchType.HIGH_QUALITY: self.high_quality_threshold,
            BranchType.MEDIUM_QUALITY: self.medium_quality_threshold,
            BranchType.EXPERIMENTAL: 0.0,
            BranchType.NIGHT_MAIN: 0.0,
            BranchType.EMERGENCY: 0.0
        }
        return thresholds.get(branch_type, 0.0)
    
    def _parse_conflict_output(self, output: str) -> List[str]:
        """Git merge-tree出力から競合ファイルを解析"""
        files = []
        # 実際の実装では、より詳細な解析が必要
        # 簡略化版として、出力からファイル名を抽出
        lines = output.split('\n')
        for line in lines:
            if line.startswith('<<<<<<< ') or 'conflicts in' in line:
                # 競合を含む行から推測
                match = re.search(r'(\S+\.py|\S+\.js|\S+\.ts)', line)
                if match:
                    files.append(match.group(1))
        return list(set(files))  # 重複除去
    
    def _assess_conflict_severity(self, conflicting_files: List[str]) -> str:
        """競合の深刻度を評価"""
        if len(conflicting_files) == 0:
            return "low"
        elif len(conflicting_files) <= 2:
            return "medium"
        else:
            return "high"
    
    def finalize_night_session(self) -> Dict[str, Any]:
        """夜間セッションを終了し、結果をまとめる"""
        logger.info("夜間セッションを終了中")
        
        session_summary = {
            'session_id': self.current_night_session,
            'duration': str(datetime.now() - self.branch_stats['session_start']),
            'branches_created': self.branch_stats['branches_created'],
            'branches_merged': self.branch_stats['branches_merged'],
            'conflicts_handled': self.branch_stats['conflicts_resolved'],
            'pending_branches': [
                {
                    'name': info.name,
                    'type': info.branch_type.value,
                    'tasks': info.associated_tasks,
                    'requires_review': info.status == 'active' and info.branch_type != BranchType.HIGH_QUALITY
                }
                for info in self.active_branches.values()
                if info.status == 'active'
            ],
            'cleanup_performed': self.cleanup_inactive_branches()
        }
        
        logger.info(f"夜間セッション終了: {len(session_summary['pending_branches'])}個のブランチがレビュー待ち")
        return session_summary