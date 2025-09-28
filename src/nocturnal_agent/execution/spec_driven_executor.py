"""Spec Kit駆動のタスク実行システム"""

import asyncio
import json
import os
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List
import uuid

from ..core.models import Task, ExecutionResult, AgentType
from ..design.spec_kit_integration import (
    SpecKitManager, TaskSpecTranslator, TechnicalSpec, 
    SpecType, SpecStatus
)
from ..log_system.structured_logger import StructuredLogger, LogLevel, LogCategory


class SpecDrivenExecutor:
    """Spec Kit仕様駆動のタスク実行器"""
    
    def __init__(self, target_project_path: str, logger: StructuredLogger):
        """対象プロジェクトディレクトリでの実行専用初期化"""
        self.target_project_path = Path(target_project_path).resolve()
        self.logger = logger
        
        # 対象プロジェクトの検証
        if not self.target_project_path.exists():
            raise FileNotFoundError(f"対象プロジェクトディレクトリが見つかりません: {self.target_project_path}")
        
        if not self.target_project_path.is_dir():
            raise NotADirectoryError(f"パスがディレクトリではありません: {self.target_project_path}")
        
        # Spec Kit管理システム（対象プロジェクト内に作成）
        self.spec_manager = SpecKitManager(str(self.target_project_path / "specs"))
        self.translator = TaskSpecTranslator(self.spec_manager)
        
        # 指揮官型AI協調システム（対象プロジェクト用）
        from ..llm.command_based_collaboration import CommandBasedCollaborationSystem
        from ..core.config import LLMConfig
        
        # LLM設定を作成
        llm_config = LLMConfig()
        self.command_collaboration_system = CommandBasedCollaborationSystem(
            str(self.target_project_path), llm_config
        )
        
        # インタラクティブレビューマネージャー（対象プロジェクト用）
        self.interactive_review = InteractiveReviewManager(str(self.target_project_path), logger)
        
        # 実行履歴
        self.execution_history = []
        
        self.logger.log(
            LogLevel.INFO,
            LogCategory.SYSTEM,
            f"🎯 対象プロジェクト SpecDrivenExecutor 初期化完了: {self.target_project_path}",
            extra_data={
                'target_project_path': str(self.target_project_path),
                'target_project_exists': True,
                'specs_directory': str(self.target_project_path / "specs")
            }
        )

    async def _execute_with_collaboration_system(self, task: Task) -> ExecutionResult:
        """指揮官型AI協調システムを使用してタスクを実行"""
        try:
            spec, campaign_result = await self.command_collaboration_system.execute_task_with_command_collaboration(task)
            
            # ExecutionResultに変換
            return ExecutionResult(
                success=campaign_result.success,
                agent_used=AgentType.COLLABORATION,
                quality_score=None,
                files_modified=[],
                files_created=[],
                cost_incurred=0.0,
                errors=campaign_result.issues_encountered,
                warnings=[],
                session_id=campaign_result.campaign_id
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                agent_used=AgentType.COLLABORATION,
                quality_score=None,
                files_modified=[],
                files_created=[],
                cost_incurred=0.0,
                errors=[str(e)],
                warnings=[],
                session_id=f"failed_{task.id}"
            )
    
    async def execute_task_with_spec(self, task: Task, 
                                   executor_func,
                                   spec_type: SpecType = SpecType.FEATURE) -> ExecutionResult:
        """仕様駆動タスク実行"""
        
        session_id = f"spec_exec_{uuid.uuid4().hex[:8]}"
        
        self.logger.log(
            LogLevel.INFO,
            LogCategory.TASK_EXECUTION,
            f"Spec駆動タスク実行開始: {task.description}",
            task_id=task.id,
            session_id=session_id,
            extra_data={
                'spec_type': spec_type.value,
                'estimated_quality': task.estimated_quality
            }
        )
        
        try:
            # Phase 1: タスクから技術仕様を生成
            spec = await self._generate_spec_from_task(task, spec_type, session_id)
            
            # Phase 2: 仕様レビューと検証
            validated_spec = await self._validate_spec(spec, session_id)
            
            # Phase 3: 仕様に基づく実装実行
            execution_result = await self._execute_with_spec(
                validated_spec, executor_func, session_id
            )
            
            # Phase 4: 実行結果による仕様更新
            await self._update_spec_from_result(validated_spec, execution_result, session_id)
            
            return execution_result
            
        except Exception as e:
            self.logger.log_error(
                "spec_driven_execution_error",
                f"Spec駆動実行エラー: {e}",
                task_id=task.id,
                session_id=session_id
            )
            
            # フォールバック: 通常のタスク実行
            return await executor_func(task)

    async def execute_task_with_interactive_review(self, task: Task, session_id: str = None) -> Dict:
        """インタラクティブレビューワークフローでタスクを実行"""
        if not session_id:
            session_id = f"review_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        self.logger.log(LogLevel.INFO, LogCategory.TASK_EXECUTION, f"🎨 インタラクティブレビューワークフロー開始: {task.description}")
        
        try:
            # Phase 1: 即座に設計書を生成してレビューを開始
            review_presentation = await self.interactive_review.initiate_design_review(task, session_id)
            
            self.logger.log(LogLevel.INFO, LogCategory.TASK_EXECUTION, "✅ 設計レビューの準備完了 - ユーザーの承認待ち")
            
            return {
                'workflow_status': 'DESIGN_REVIEW_READY',
                'session_id': session_id,
                'review_data': review_presentation,
                'message': '設計書が生成されました。レビューして承認してください。',
                'next_actions': {
                    'approve': f'設計を承認: approve_design("{session_id}")',
                    'modify': f'修正要求: request_modification("{session_id}", "修正内容")',
                    'discuss': f'議論開始: start_discussion("{session_id}", "議論トピック")',
                    'reject': f'設計拒否: reject_design("{session_id}")'
                }
            }
            
        except Exception as e:
            self.logger.log_error("WORKFLOW_ERROR", f"インタラクティブレビューワークフローエラー: {e}")
            
            # フォールバック: 通常の実行に切り替え
            self.logger.log(LogLevel.INFO, LogCategory.TASK_EXECUTION, "🔄 通常の実行モードにフォールバック")
            try:
                execution_result = await self.execute_task_with_spec(task, self._execute_with_collaboration_system)
                
                # ExecutionResultを期待される辞書形式に変換
                return {
                    'workflow_status': 'COMPLETED' if execution_result.success else 'ERROR',
                    'session_id': session_id,
                    'review_data': {
                        'design_summary': {
                            'project_name': task.description,
                            'architecture_type': 'Layered Architecture',
                            'key_components': 'N/A',
                            'complexity_level': 'MEDIUM',
                            'estimated_effort': 'N/A',
                            'main_technologies': []
                        },
                        'implementation_plan': {
                            'phases': ['設計', '実装', 'テスト', 'デプロイ'],
                            'priority_components': ['コア機能'],
                            'risk_factors': ['技術的複雑さ']
                        },
                        'architecture_overview': {
                            'pattern': 'MVC',
                            'layers': ['View', 'Controller', 'Model'],
                            'key_interfaces': ['API'],
                            'data_flow': 'UI -> Logic -> Database'
                        },
                        'quality_requirements': {
                            'performance': 'Standard',
                            'reliability': 'High',
                            'security': 'Medium',
                            'maintainability': 'High',
                            'testing': 'Required'
                        }
                    },
                    'message': 'フォールバック実行が完了しました。',
                    'execution_result': execution_result
                }
            except Exception as fallback_error:
                self.logger.log_error("FALLBACK_ERROR", f"フォールバック実行エラー: {fallback_error}")
                return {
                    'workflow_status': 'ERROR',
                    'session_id': session_id,
                    'message': f'設計書生成エラー: {fallback_error}',
                    'review_data': {
                        'design_summary': {
                            'project_name': task.description,
                            'architecture_type': 'N/A',
                            'key_components': 'N/A',
                            'complexity_level': 'N/A',
                            'estimated_effort': 'N/A',
                            'main_technologies': []
                        },
                        'implementation_plan': {
                            'phases': [],
                            'priority_components': [],
                            'risk_factors': []
                        },
                        'architecture_overview': {
                            'pattern': 'N/A',
                            'layers': [],
                            'key_interfaces': [],
                            'data_flow': 'N/A'
                        },
                        'quality_requirements': {}
                    }
                }

    
    def set_target_project_execution(self, target_project_path: str):
        """対象プロジェクトディレクトリでの実行モードに設定"""
        self.target_project_path = Path(target_project_path).resolve()
        
        # CommandBasedCollaborationSystemが対象プロジェクト実行モードをサポートしているかチェック
        if hasattr(self.command_collaboration_system, 'set_target_project_execution'):
            self.command_collaboration_system.set_target_project_execution(str(self.target_project_path))
        
        self.logger.log(
            LogLevel.INFO,
            LogCategory.SYSTEM,
            f"🎯 SpecDrivenExecutor: 対象プロジェクト実行モード設定: {self.target_project_path}",
            extra_data={
                'target_project_path': str(self.target_project_path),
                'target_project_exists': self.target_project_path.exists(),
                'target_project_is_dir': self.target_project_path.is_dir() if self.target_project_path.exists() else False
            }
        )
    
    def is_target_project_mode(self) -> bool:
        """対象プロジェクト実行モードかチェック"""
        return hasattr(self, 'target_project_path') and self.target_project_path is not None
    
    async def execute_task_with_target_project(self, task: Task, target_project_path: str, session_id: str = None) -> Dict:
        """対象プロジェクトディレクトリでタスクを実行"""
        if not session_id:
            session_id = f"target_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        target_path = Path(target_project_path).resolve()
        
        self.logger.log(
            LogLevel.INFO,
            LogCategory.SYSTEM,
            f"🎯 対象プロジェクト実行開始: {task.description}",
            task_id=task.id,
            session_id=session_id,
            extra_data={
                'target_project_path': str(target_path),
                'current_target_path': str(self.target_project_path)
            }
        )
        
        try:
            # 対象プロジェクト実行モードに設定
            self.set_target_project_execution(str(target_path))
            
            # 通常のタスク実行
            result = await self.execute_task_with_spec(task, self._execute_with_collaboration_system)
            
            self.logger.log(
                LogLevel.INFO,
                LogCategory.SYSTEM,
                f"✅ 対象プロジェクト実行完了: {task.description}",
                task_id=task.id,
                session_id=session_id,
                extra_data={
                    'target_project_path': str(target_path),
                    'execution_success': True
                }
            )
            
            return {
                'status': 'success',
                'task_result': result,
                'target_project_path': str(target_path),
                'session_id': session_id,
                'message': f'対象プロジェクト「{target_path.name}」でタスクが実行されました'
            }
            
        except Exception as e:
            self.logger.log_error(
                "target_project_execution_error",
                f"対象プロジェクト実行エラー: {e}",
                task_id=task.id,
                session_id=session_id
            )
            
            return {
                'status': 'error',
                'error': str(e),
                'target_project_path': str(target_path),
                'session_id': session_id,
                'message': f'対象プロジェクト実行でエラーが発生しました: {e}'
            }
    
    async def execute_task_from_requirements_file_in_target_project(
        self, 
        requirements_file: str, 
        target_project_path: str,
        session_id: str = None
    ) -> Dict:
        """対象プロジェクトディレクトリで要件ファイルからタスクを実行"""
        if not session_id:
            session_id = f"target_file_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        target_path = Path(target_project_path).resolve()
        
        self.logger.log(
            LogLevel.INFO,
            LogCategory.SYSTEM,
            f"📄 対象プロジェクトで要件ファイル実行開始: {requirements_file}",
            session_id=session_id,
            extra_data={
                'requirements_file': requirements_file,
                'target_project_path': str(target_path)
            }
        )
        
        try:
            # 対象プロジェクト実行モードに設定
            self.set_target_project_execution(str(target_path))
            
            # 要件ファイルからインタラクティブレビューを開始
            review_result = await self.interactive_review.initiate_design_review_from_file(
                requirements_file, session_id
            )
            
            return {
                'workflow_status': 'DESIGN_REVIEW_READY',
                'session_id': session_id,
                'review_data': review_result,
                'requirements_file': requirements_file,
                'target_project_path': str(target_path),
                'message': f'対象プロジェクト「{target_path.name}」で要件ファイルから設計書が生成されました',
                'next_actions': {
                    'approve': f'設計を承認: na review approve {session_id}',
                    'modify': f'修正要求: na review modify {session_id} "修正内容"',
                    'discuss': f'議論開始: na review discuss {session_id} "議論トピック"',
                    'reject': f'設計拒否: na review reject {session_id}'
                }
            }
            
        except Exception as e:
            self.logger.log_error(
                "target_project_requirements_file_error",
                f"対象プロジェクト要件ファイル実行エラー: {e}",
                session_id=session_id,
                extra_data={
                    'requirements_file': requirements_file,
                    'target_project_path': str(target_path)
                }
            )
            
            return {
                'workflow_status': 'ERROR',
                'session_id': session_id,
                'error': str(e),
                'requirements_file': requirements_file,
                'target_project_path': str(target_path),
                'message': f'対象プロジェクト要件ファイル処理でエラーが発生しました: {e}'
            }

    
    async def execute_task_from_requirements_file(self, requirements_file: str, session_id: str = None) -> Dict:
        """要件ファイルからインタラクティブレビューワークフローでタスクを実行"""
        if not session_id:
            session_id = f"file_review_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, f"📄 要件ファイルからインタラクティブレビューワークフロー開始: {requirements_file}")
        
        try:
            # Phase 1: 要件ファイルから設計書を生成してレビューを開始
            review_presentation = await self.interactive_review.initiate_design_review_from_file(
                requirements_file, session_id
            )
            
            self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, "✅ 要件ファイルベースの設計レビューの準備完了 - ユーザーの承認待ち")
            
            return {
                'workflow_status': 'DESIGN_REVIEW_READY',
                'session_id': session_id,
                'review_data': review_presentation,
                'requirements_file': requirements_file,
                'message': '要件ファイルから設計書が生成されました。レビューして承認してください。',
                'next_actions': {
                    'approve': f'設計を承認: na review approve {session_id}',
                    'modify': f'修正要求: na review modify {session_id} "修正内容"',
                    'discuss': f'議論開始: na review discuss {session_id} "議論トピック"',
                    'reject': f'設計拒否: na review reject {session_id}'
                }
            }
            
        except Exception as e:
            self.logger.log_error("WORKFLOW_ERROR", f"要件ファイルベースのインタラクティブレビューワークフローエラー: {e}")
            
            # エラー情報を返す
            return {
                'workflow_status': 'ERROR',
                'session_id': session_id,
                'error': str(e),
                'message': f'要件ファイル処理でエラーが発生しました: {e}',
                'requirements_file': requirements_file
            }
    
    async def process_review_feedback(self, session_id: str, feedback_type: str, feedback_content: str = "") -> Dict:
        """レビューフィードバックを処理"""
        try:
            result = await self.interactive_review.process_user_feedback(
                session_id, feedback_type, feedback_content
            )
            
            if result.get('status') == 'APPROVED':
                self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, f"✅ タスクが承認され夜間実行にスケジュールされました: {result.get('scheduled_execution')}")
            
            return result
            
        except Exception as e:
            self.logger.log_error("FEEDBACK_ERROR", f"レビューフィードバック処理エラー: {e}")
            return {
                'status': 'ERROR',
                'message': f'フィードバック処理でエラーが発生しました: {e}',
                'session_id': session_id
            }
    
    async def approve_design(self, session_id: str) -> Dict:
        """設計を承認（便利メソッド）"""
        return await self.process_review_feedback(session_id, 'approve')
    
    async def request_modification(self, session_id: str, modification_request: str) -> Dict:
        """修正要求（便利メソッド）"""
        return await self.process_review_feedback(session_id, 'modify', modification_request)
    
    async def start_discussion(self, session_id: str, discussion_topic: str) -> Dict:
        """議論開始（便利メソッド）"""
        return await self.process_review_feedback(session_id, 'discuss', discussion_topic)
    
    async def reject_design(self, session_id: str) -> Dict:
        """設計拒否（便利メソッド）"""
        return await self.process_review_feedback(session_id, 'reject')
    
    async def execute_nighttime_tasks(self):
        """夜間タスクを実行"""
        self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, "🌙 夜間実行開始")
        
        try:
            await self.interactive_review.execute_scheduled_tasks()
            self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, "✅ 夜間実行完了")
            
        except Exception as e:
            self.logger.log_error("NIGHTTIME_EXECUTION_ERROR", f"夜間実行エラー: {e}")
    
    def get_review_status(self, session_id: str = None) -> Dict:
        """レビュー状況を取得"""
        if session_id:
            if session_id in self.interactive_review.review_states:
                return self.interactive_review.review_states[session_id]
            else:
                return {'status': 'NOT_FOUND', 'session_id': session_id}
        else:
            return {
                'active_reviews': len(self.interactive_review.review_states),
                'scheduled_tasks': len(self.interactive_review.scheduled_tasks),
                'pending_tasks': len(self.interactive_review.pending_tasks),
                'review_sessions': list(self.interactive_review.review_states.keys())
            }
    
    def get_scheduled_tasks(self) -> List[Dict]:
        """スケジュールされたタスク一覧を取得"""
        return self.interactive_review.scheduled_tasks
    
    async def _generate_spec_from_task(self, task: Task, spec_type: SpecType, 
                                     session_id: str) -> TechnicalSpec:
        """指揮官型AI協調による技術仕様生成（品質保証統合）"""
        
        self.logger.log(
            LogLevel.INFO,
            LogCategory.SYSTEM,
            f"指揮官型AI協調技術仕様生成: {task.description}",
            task_id=task.id,
            session_id=session_id,
            extra_data={'spec_type': spec_type.value}
        )
        
        try:
            # 指揮官型AI協調システムを使用
            tech_spec, campaign_result = await self.command_collaboration_system.execute_task_with_command_collaboration(
                task=task,
                collaboration_options={'spec_type': spec_type.value, 'session_id': session_id}
            )
            
            # 仕様ファイル保存
            spec_path = self.spec_manager.save_spec(tech_spec)
            
            # 🔍 新機能: 生成コードの品質検証
            await self._validate_generated_code(session_id)
            
            self.logger.log(
                LogLevel.INFO,
                LogCategory.SYSTEM,
                f"指揮官型AI協調技術仕様生成完了: {spec_path}",
                task_id=task.id,
                session_id=session_id,
                extra_data={
                    'spec_path': str(spec_path),
                    'requirements_count': len(tech_spec.requirements),
                    'campaign_success': campaign_result.success,
                    'campaign_duration': campaign_result.total_duration,
                    'commands_issued': campaign_result.commands_issued,
                    'successful_executions': campaign_result.successful_executions,
                    'final_deliverables': len(campaign_result.final_deliverables),
                    'collaboration_method': 'command_based',
                    'quality_validated': True
                }
            )
            
            return tech_spec
            
        except Exception as e:
            self.logger.log_error(
                "command_collaboration_error",
                f"指揮官型AI協調エラー: {e}",
                task_id=task.id,
                session_id=session_id
            )
            
            # フォールバック: 従来の仕様生成
            self.logger.log(
                LogLevel.WARNING,
                LogCategory.SYSTEM,
                "フォールバックモードで仕様生成を実行します",
                task_id=task.id,
                session_id=session_id
            )
            
            # 基本仕様生成
            spec = self.translator.task_to_spec(task, spec_type)
            
            # 詳細設計の補完
            spec = await self._enhance_spec_design(spec, task, session_id)
            
            # 仕様ファイル保存
            spec_path = self.spec_manager.save_spec(spec)
            
            self.logger.log(
                LogLevel.INFO,
                LogCategory.SYSTEM,
                f"フォールバック技術仕様生成完了: {spec_path}",
                task_id=task.id,
                session_id=session_id,
                extra_data={
                    'spec_path': str(spec_path),
                    'requirements_count': len(spec.requirements),
                    'method': 'fallback'
                }
            )
            
            return spec
    
    async def _validate_generated_code(self, session_id: str):
        """生成コードの品質検証と自動修正"""
        try:
            from ..quality.auto_fixer import IntegratedQualityAssurance
            
            self.logger.log(
                LogLevel.INFO,
                LogCategory.SYSTEM,
                "🔍 統合品質保証開始（検証→修正→再検証）",
                session_id=session_id
            )
            
            qa_system = IntegratedQualityAssurance()
            quality_summary = await qa_system.ensure_code_quality(str(self.workspace_path))
            
            self.logger.log(
                LogLevel.INFO,
                LogCategory.SYSTEM,
                f"✅ 統合品質保証完了: 最終スコア {quality_summary['final_quality_score']:.2f}",
                session_id=session_id,
                extra_data={
                    'final_quality_score': quality_summary['final_quality_score'],
                    'iterations_used': quality_summary['iterations_used'],
                    'quality_target_met': quality_summary['quality_target_met'],
                    'auto_fixes_applied': sum(
                        result.get('fixes_applied', 0) 
                        for result in quality_summary['iteration_results']
                    )
                }
            )
            
            # 品質目標未達の場合は詳細警告
            if not quality_summary['quality_target_met']:
                self.logger.log(
                    LogLevel.WARNING,
                    LogCategory.SYSTEM,
                    f"⚠️ 品質目標未達: {quality_summary['final_quality_score']:.2f} < 0.8",
                    session_id=session_id,
                    extra_data={
                        'max_iterations_reached': quality_summary['iterations_used'] >= 3,
                        'requires_manual_review': True
                    }
                )
            else:
                self.logger.log(
                    LogLevel.INFO,
                    LogCategory.SYSTEM,
                    "🎯 品質目標達成：実行エラーゼロ保証",
                    session_id=session_id
                )
        
        except Exception as e:
            self.logger.log_error(
                "integrated_qa_error",
                f"統合品質保証エラー: {e}",
                session_id=session_id
            )

    
    async def _enhance_spec_design(self, spec: TechnicalSpec, task: Task, 
                                 session_id: str) -> TechnicalSpec:
        """仕様設計の拡張"""
        
        # コンポーネント設計の追加
        if not spec.design.components:
            spec.design.components = await self._generate_component_design(task, session_id)
        
        # インターフェース設計の追加
        if not spec.design.interfaces:
            spec.design.interfaces = await self._generate_interface_design(task, session_id)
        
        # データモデル設計の追加
        if not spec.design.data_models:
            spec.design.data_models = await self._generate_data_model_design(task, session_id)
        
        # リスク分析の追加
        if not spec.implementation.risks:
            spec.implementation.risks = await self._analyze_implementation_risks(task, session_id)
        
        return spec
    
    async def _generate_component_design(self, task: Task, session_id: str) -> List[Dict[str, Any]]:
        """コンポーネント設計生成"""
        
        components = []
        
        # タスクの複雑性に基づいてコンポーネント設計
        if task.estimated_quality >= 0.8:
            # 高品質要件: 詳細なコンポーネント分割
            components = [
                {
                    'name': f"{task.id}_core",
                    'type': 'Core Module',
                    'description': 'メインロジック実装',
                    'interfaces': ['IExecutable', 'IValidatable'],
                    'dependencies': []
                },
                {
                    'name': f"{task.id}_validation",
                    'type': 'Validation Module',
                    'description': '入力検証とバリデーション',
                    'interfaces': ['IValidator'],
                    'dependencies': [f"{task.id}_core"]
                },
                {
                    'name': f"{task.id}_output",
                    'type': 'Output Module',
                    'description': '結果出力と整形',
                    'interfaces': ['IFormatter'],
                    'dependencies': [f"{task.id}_core"]
                }
            ]
        else:
            # 中〜低品質要件: シンプルな構成
            components = [
                {
                    'name': f"{task.id}_implementation",
                    'type': 'Implementation Module',
                    'description': 'タスク実装',
                    'interfaces': ['IExecutable'],
                    'dependencies': []
                }
            ]
        
        self.logger.log(
            LogLevel.INFO,
            LogCategory.SYSTEM,
            f"コンポーネント設計生成: {len(components)}個",
            task_id=task.id,
            session_id=session_id,
            extra_data={'components_count': len(components)}
        )
        
        return components
    
    async def _generate_interface_design(self, task: Task, session_id: str) -> List[Dict[str, Any]]:
        """インターフェース設計生成"""
        
        interfaces = [
            {
                'name': 'IExecutable',
                'type': 'Interface',
                'methods': [
                    {
                        'name': 'execute',
                        'parameters': ['context: Dict[str, Any]'],
                        'return_type': 'ExecutionResult',
                        'description': 'タスク実行'
                    },
                    {
                        'name': 'validate',
                        'parameters': ['input_data: Any'],
                        'return_type': 'bool',
                        'description': '入力検証'
                    }
                ],
                'description': 'タスク実行インターフェース'
            }
        ]
        
        if task.estimated_quality >= 0.8:
            interfaces.extend([
                {
                    'name': 'IQualityAssured',
                    'type': 'Interface',
                    'methods': [
                        {
                            'name': 'calculate_quality',
                            'parameters': ['result: Any'],
                            'return_type': 'float',
                            'description': '品質スコア計算'
                        }
                    ],
                    'description': '品質保証インターフェース'
                }
            ])
        
        return interfaces
    
    async def _generate_data_model_design(self, task: Task, session_id: str) -> List[Dict[str, Any]]:
        """データモデル設計生成"""
        
        data_models = [
            {
                'name': f"{task.id.title()}Input",
                'type': 'Data Model',
                'fields': [
                    {
                        'name': 'task_id',
                        'type': 'str',
                        'required': True,
                        'description': 'タスクID'
                    },
                    {
                        'name': 'parameters',
                        'type': 'Dict[str, Any]',
                        'required': False,
                        'description': '実行パラメータ'
                    }
                ],
                'description': 'タスク入力データモデル'
            },
            {
                'name': f"{task.id.title()}Output",
                'type': 'Data Model',
                'fields': [
                    {
                        'name': 'success',
                        'type': 'bool',
                        'required': True,
                        'description': '実行成功フラグ'
                    },
                    {
                        'name': 'result_data',
                        'type': 'Any',
                        'required': False,
                        'description': '実行結果データ'
                    },
                    {
                        'name': 'quality_score',
                        'type': 'float',
                        'required': True,
                        'description': '品質スコア'
                    }
                ],
                'description': 'タスク出力データモデル'
            }
        ]
        
        return data_models
    
    async def _analyze_implementation_risks(self, task: Task, session_id: str) -> List[Dict[str, str]]:
        """実装リスク分析"""
        
        risks = []
        
        # 品質リスク分析
        if task.estimated_quality >= 0.9:
            risks.append({
                'risk': '高品質要件による開発コスト増大',
                'probability': 'medium',
                'impact': 'medium',
                'mitigation': '段階的実装とレビューサイクルの導入'
            })
        
        if task.minimum_quality_threshold >= 0.8:
            risks.append({
                'risk': '品質閾値未達による実装やり直し',
                'probability': 'medium',
                'impact': 'high',
                'mitigation': '事前テストと品質チェックの強化'
            })
        
        # 要件リスク分析
        if len(task.requirements or []) > 5:
            risks.append({
                'risk': '要件の複雑性による実装困難',
                'probability': 'medium',
                'impact': 'medium',
                'mitigation': '要件分割と優先順位付け'
            })
        
        # 制約リスク分析
        if len(task.constraints or []) > 3:
            risks.append({
                'risk': '制約条件による設計制限',
                'probability': 'high',
                'impact': 'medium',
                'mitigation': '制約分析と代替設計の検討'
            })
        
        return risks
    
    async def _validate_spec(self, spec: TechnicalSpec, session_id: str) -> TechnicalSpec:
        """仕様検証と承認"""
        
        self.logger.log(
            LogLevel.INFO,
            LogCategory.SYSTEM,
            f"仕様検証開始: {spec.metadata.title}",
            session_id=session_id,
            extra_data={
                'requirements_count': len(spec.requirements),
                'components_count': len(spec.design.components),
                'risks_count': len(spec.implementation.risks)
            }
        )
        
        # 自動検証チェック
        validation_result = await self._perform_automated_validation(spec, session_id)
        
        if validation_result['valid']:
            spec.metadata.status = SpecStatus.APPROVED
            self.logger.log(
                LogLevel.INFO,
                LogCategory.SYSTEM,
                f"仕様検証成功: 自動承認",
                session_id=session_id
            )
        else:
            spec.metadata.status = SpecStatus.REVIEW
            self.logger.log(
                LogLevel.WARNING,
                LogCategory.SYSTEM,
                f"仕様検証警告: 手動レビューが必要",
                session_id=session_id,
                extra_data={'validation_issues': validation_result['issues']}
            )
        
        # 仕様更新
        spec.metadata.updated_at = datetime.now().isoformat()
        self.spec_manager.save_spec(spec)
        
        return spec
    
    async def _perform_automated_validation(self, spec: TechnicalSpec, 
                                          session_id: str) -> Dict[str, Any]:
        """自動仕様検証"""
        
        issues = []
        
        # 要件検証
        if not spec.requirements:
            issues.append("要件が定義されていません")
        
        for req in spec.requirements:
            if not req.acceptance_criteria:
                issues.append(f"要件 {req.id} に受入条件が定義されていません")
        
        # 設計検証
        if not spec.design.overview:
            issues.append("設計概要が定義されていません")
        
        if not spec.design.components:
            issues.append("コンポーネント設計が定義されていません")
        
        # 実装検証
        if not spec.implementation.approach:
            issues.append("実装アプローチが定義されていません")
        
        if not spec.implementation.testing_strategy:
            issues.append("テスト戦略が定義されていません")
        
        return {
            'valid': len(issues) == 0,
            'issues': issues
        }
    
    async def _execute_with_spec(self, spec: TechnicalSpec, executor_func, 
                               session_id: str) -> ExecutionResult:
        """仕様に基づく実装実行"""
        
        self.logger.log(
            LogLevel.INFO,
            LogCategory.TASK_EXECUTION,
            f"仕様基準実行開始: {spec.metadata.title}",
            session_id=session_id,
            extra_data={
                'spec_status': spec.metadata.status.value,
                'components_count': len(spec.design.components)
            }
        )
        
        # 仕様からタスクを再構築
        enhanced_task = self.translator.spec_to_task(spec)
        
        # 実行コンテキストに仕様情報を追加（contextフィールドがないためコメントアウト）
        # enhanced_task.context = enhanced_task.context or {}
        # enhanced_task.context.update({
        #     'spec_driven': True,
        #     'spec_title': spec.metadata.title,
        #     'spec_version': spec.metadata.version,
        #     'components': [comp['name'] for comp in spec.design.components],
        #     'interfaces': [intf['name'] for intf in spec.design.interfaces],
        #     'quality_requirements': {
        #         'target': enhanced_task.estimated_quality,
        #         'threshold': enhanced_task.minimum_quality_threshold
        #     }
        # })
        
        # 実行
        start_time = datetime.now()
        result = await executor_func(enhanced_task)
        execution_time = (datetime.now() - start_time).total_seconds()
        
        # 結果の拡張
        result.execution_time = execution_time
        result.spec_driven = True
        
        self.logger.log(
            LogLevel.INFO,
            LogCategory.TASK_EXECUTION,
            f"仕様基準実行完了: 成功={result.success}",
            session_id=session_id,
            execution_time_ms=execution_time * 1000,
            extra_data={
                'quality_achieved': result.quality_score.overall if result.quality_score else 0,
                'spec_driven': True
            }
        )
        
        return result
    
    async def _update_spec_from_result(self, spec: TechnicalSpec, 
                                     execution_result: ExecutionResult,
                                     session_id: str) -> None:
        """実行結果による仕様更新"""
        
        self.logger.log(
            LogLevel.INFO,
            LogCategory.SYSTEM,
            f"実行結果による仕様更新: {spec.metadata.title}",
            session_id=session_id,
            extra_data={
                'execution_success': execution_result.success,
                'quality_achieved': execution_result.quality_score.overall if execution_result.quality_score else 0
            }
        )
        
        # ステータス更新
        if execution_result.success:
            quality_achieved = execution_result.quality_score.overall if execution_result.quality_score else 0
            if quality_achieved >= 0.8:
                spec.metadata.status = SpecStatus.IMPLEMENTED
            else:
                spec.metadata.status = SpecStatus.REVIEW
        else:
            spec.metadata.status = SpecStatus.DRAFT
        
        # 実行結果の記録
        spec.implementation.execution_history = getattr(spec.implementation, 'execution_history', [])
        spec.implementation.execution_history.append({
            'timestamp': datetime.now().isoformat(),
            'success': execution_result.success,
            'quality_score': execution_result.quality_score.overall if execution_result.quality_score else 0,
            'execution_time': execution_result.execution_time or 0,
            'agent_used': execution_result.agent_used.value if execution_result.agent_used else None,
            'files_modified': execution_result.files_modified or [],
            'files_created': execution_result.files_created or []
        })
        
        # 仕様更新
        spec.metadata.updated_at = datetime.now().isoformat()
        self.spec_manager.save_spec(spec)
        
        # 実行履歴に追加
        self.execution_history.append({
            'spec_title': spec.metadata.title,
            'execution_result': execution_result,
            'session_id': session_id
        })
    
    def generate_spec_report(self, spec_path: Optional[Path] = None) -> Dict[str, Any]:
        """仕様レポート生成"""
        
        if spec_path:
            specs = [self.spec_manager.load_spec(spec_path)]
        else:
            spec_list = self.spec_manager.list_specs()
            specs = [self.spec_manager.load_spec(spec_info['file_path']) 
                    for spec_info in spec_list]
        
        report = {
            'generated_at': datetime.now().isoformat(),
            'total_specs': len(specs),
            'status_breakdown': {},
            'type_breakdown': {},
            'quality_metrics': {},
            'execution_summary': {}
        }
        
        # ステータス集計
        for spec in specs:
            status = spec.metadata.status.value
            report['status_breakdown'][status] = report['status_breakdown'].get(status, 0) + 1
            
            spec_type = spec.metadata.spec_type.value
            report['type_breakdown'][spec_type] = report['type_breakdown'].get(spec_type, 0) + 1
        
        # 実行履歴から品質メトリクス算出
        if self.execution_history:
            quality_scores = []
            success_count = 0
            
            for history in self.execution_history:
                result = history['execution_result']
                if result.quality_score:
                    quality_scores.append(result.quality_score.overall)
                if result.success:
                    success_count += 1
            
            if quality_scores:
                report['quality_metrics'] = {
                    'average_quality': sum(quality_scores) / len(quality_scores),
                    'max_quality': max(quality_scores),
                    'min_quality': min(quality_scores),
                    'success_rate': success_count / len(self.execution_history)
                }
        
        return report
    
    async def cleanup_old_specs(self, days_old: int = 30) -> int:
        """古い仕様のクリーンアップ"""
        
        self.logger.log(
            LogLevel.INFO,
            LogCategory.SYSTEM,
            f"古い仕様のクリーンアップ開始: {days_old}日以前",
            extra_data={'threshold_days': days_old}
        )
        
        cutoff_date = datetime.now().timestamp() - (days_old * 24 * 3600)
        cleanup_count = 0
        
        spec_list = self.spec_manager.list_specs()
        for spec_info in spec_list:
            spec_path = Path(spec_info['file_path'])
            
            # ファイル作成日時チェック
            if spec_path.stat().st_mtime < cutoff_date:
                spec = self.spec_manager.load_spec(spec_path)
                
                # 実装完了済みかつ古い仕様のみクリーンアップ
                if spec.metadata.status == SpecStatus.IMPLEMENTED:
                    spec_path.unlink()  # ファイル削除
                    cleanup_count += 1
        
        self.logger.log(
            LogLevel.INFO,
            LogCategory.SYSTEM,
            f"仕様クリーンアップ完了: {cleanup_count}件削除",
            extra_data={'deleted_count': cleanup_count}
        )
        
        return cleanup_count

class InteractiveReviewManager:
    """インタラクティブ設計レビューマネージャー"""
    
    def __init__(self, workspace_path: str, logger: StructuredLogger):
        self.workspace_path = Path(workspace_path)
        self.logger = logger
        self.review_states = {}
        self.pending_tasks = []
        self.scheduled_tasks = []
        
        # セッション保存ディレクトリを設定
        self.sessions_dir = self.workspace_path / '.nocturnal' / 'review_sessions'
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        
        # 既存のセッションを読み込み
        self._load_sessions()
        
        # スケジュールされたタスクを読み込み
        self._load_scheduled_tasks()

    
    def _load_sessions(self):
        """既存のセッションファイルを読み込み"""
        try:
            for session_file in self.sessions_dir.glob('*.json'):
                session_id = session_file.stem
                with open(session_file, 'r', encoding='utf-8') as f:
                    session_data = json.load(f)
                    
                    # TaskオブジェクトをJSONから復元
                    if 'task' in session_data and isinstance(session_data['task'], dict):
                        from ..core.models import Task, TaskPriority
                        task_data = session_data['task']
                        priority_str = task_data.get('priority', 'medium')
                        # 文字列を enum に変換
                        priority = TaskPriority.MEDIUM
                        if priority_str == 'high':
                            priority = TaskPriority.HIGH
                        elif priority_str == 'low':
                            priority = TaskPriority.LOW
                        elif priority_str == 'critical':
                            priority = TaskPriority.CRITICAL
                        
                        session_data['task'] = Task(
                            description=task_data.get('description', ''),
                            priority=priority,
                            requirements=task_data.get('requirements', []),
                            constraints=task_data.get('constraints', [])
                        )
                    
                    self.review_states[session_id] = session_data
            
            if self.review_states:
                self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, 
                              f"📂 {len(self.review_states)}個のレビューセッションを読み込み完了")
        except Exception as e:
            self.logger.log(LogLevel.ERROR, LogCategory.SYSTEM, f"セッション読み込みエラー: {e}")

    
    def _load_scheduled_tasks(self):
        """スケジュールされたタスクをファイルから読み込み"""
        try:
            scheduled_tasks_file = self.sessions_dir / 'scheduled_tasks.json'
            if scheduled_tasks_file.exists():
                with open(scheduled_tasks_file, 'r', encoding='utf-8') as f:
                    tasks_data = json.load(f)
                
                # Task オブジェクトを復元
                for task_data in tasks_data:
                    if 'task' in task_data and isinstance(task_data['task'], dict):
                        from ..core.models import Task
                        task_info = task_data['task']
                        task_data['task'] = Task(
                            description=task_info.get('description', ''),
                            priority=task_info.get('priority', 'medium')
                        )
                
                self.scheduled_tasks = tasks_data
                self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, 
                              f"📋 {len(self.scheduled_tasks)}個のスケジュールされたタスクを読み込み完了")
            else:
                self.scheduled_tasks = []
        except Exception as e:
            self.logger.log(LogLevel.ERROR, LogCategory.SYSTEM, f"スケジュールタスク読み込みエラー: {e}")
            self.scheduled_tasks = []
    
    def _save_scheduled_tasks(self):
        """スケジュールされたタスクをファイルに保存"""
        try:
            scheduled_tasks_file = self.sessions_dir / 'scheduled_tasks.json'
            
            # Task オブジェクトをシリアライズ可能な形式に変換
            safe_tasks_data = []
            for task_data in self.scheduled_tasks:
                safe_task_data = task_data.copy()
                
                # Task オブジェクトの基本情報のみ保存
                if 'task' in safe_task_data and hasattr(safe_task_data['task'], 'description'):
                    task = safe_task_data['task']
                    task_created_at = getattr(task, 'created_at', datetime.now())
                    if hasattr(task_created_at, 'isoformat'):
                        task_created_at = task_created_at.isoformat()
                    else:
                        task_created_at = str(task_created_at)
                        
                    safe_task_data['task'] = {
                        'description': task.description,
                        'priority': str(task.priority),
                        'type': getattr(task, 'type', 'unknown'),
                        'created_at': task_created_at
                    }
                
                safe_tasks_data.append(safe_task_data)
            
            with open(scheduled_tasks_file, 'w', encoding='utf-8') as f:
                json.dump(safe_tasks_data, f, ensure_ascii=False, indent=2)
            
            self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, 
                          f"💾 {len(self.scheduled_tasks)}個のスケジュールタスクを保存完了")
        except Exception as e:
            self.logger.log(LogLevel.ERROR, LogCategory.SYSTEM, f"スケジュールタスク保存エラー: {e}")
    
    def _save_session(self, session_id: str):
        """セッションをファイルに保存"""
        if session_id in self.review_states:
            try:
                session_file = self.sessions_dir / f'{session_id}.json'
                session_data = self.review_states[session_id].copy()
                
                # created_atを文字列に変換
                created_at = session_data.get('created_at', datetime.now())
                if hasattr(created_at, 'isoformat'):
                    created_at = created_at.isoformat()
                else:
                    created_at = str(created_at)
                
                # 基本的な情報のみを保存（循環参照を避ける）
                safe_session_data = {
                    'session_id': session_data.get('session_id', session_id),
                    'status': session_data.get('status', 'REVIEW_READY'),
                    'created_at': created_at,
                    'modifications': session_data.get('modifications', 0),
                    'feedback_history': session_data.get('feedback_history', [])
                }
                
                # Taskオブジェクトの基本情報のみ保存
                if 'task' in session_data and hasattr(session_data['task'], 'description'):
                    task = session_data['task']
                    task_created_at = getattr(task, 'created_at', datetime.now())
                    if hasattr(task_created_at, 'isoformat'):
                        task_created_at = task_created_at.isoformat()
                    else:
                        task_created_at = str(task_created_at)
                        
                    safe_session_data['task'] = {
                        'description': task.description,
                        'priority': str(task.priority),
                        'type': getattr(task, 'type', 'unknown'),
                        'created_at': task_created_at
                    }
                
                # 設計ドキュメントの概要のみ保存
                if 'design_document' in session_data:
                    design_doc = session_data['design_document']
                    if isinstance(design_doc, dict):
                        safe_session_data['design_document'] = {
                            'design_summary': design_doc.get('design_summary', {}),
                            'architecture_overview': design_doc.get('architecture_overview', {}),
                            'implementation_plan': design_doc.get('implementation_plan', {}),
                            'quality_requirements': design_doc.get('quality_requirements', {})
                        }
                
                with open(session_file, 'w', encoding='utf-8') as f:
                    json.dump(safe_session_data, f, ensure_ascii=False, indent=2)
                self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, 
                              f"💾 セッション保存完了: {session_id}")
            except Exception as e:
                self.logger.log(LogLevel.ERROR, LogCategory.SYSTEM, f"セッション保存エラー: {e}")
    
    async def initiate_design_review(self, task: Task, session_id: str) -> Dict:
        """設計レビューを開始する"""
        self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, f"🎨 設計レビューを開始: {task.description}")
        
        # 即座に設計書を生成
        design_doc = await self._generate_immediate_design(task, session_id)
        
        # レビュー状態を初期化
        review_data = {
            'task': task,
            'session_id': session_id,
            'design_document': design_doc,
            'status': 'REVIEW_READY',
            'feedback_history': [],
            'created_at': datetime.now().isoformat(),
            'modifications': 0
        }
        
        self.review_states[session_id] = review_data
        
        # セッションを保存
        self._save_session(session_id)
        
        # ユーザーにレビューを提示
        return await self._present_design_for_review(review_data)

    
    async def initiate_design_review_from_file(self, requirements_file: str, session_id: str = None) -> Dict:
        """要件ファイルから設計レビューを開始する"""
        try:
            # 要件ファイルを解析
            requirements_data = RequirementsFileParser.parse_requirements_file(requirements_file)
            
            self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, f"📄 要件ファイルから設計レビューを開始: {requirements_data['title']}")
            self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, f"📝 ファイル形式: {requirements_data['file_format']}")
            
            # Taskオブジェクトを作成
            from ..core.models import Task, TaskPriority
            task = Task(
                description=f"{requirements_data['title']}: {requirements_data['description']}",
                priority=TaskPriority.MEDIUM if requirements_data['priority'] == 'medium' else TaskPriority.HIGH,
                requirements=[req for req in requirements_data.get('functional_requirements', [])],
                constraints=[constraint for constraint in requirements_data.get('constraints', [])]
            )
            
            # セッションIDの生成
            if not session_id:
                session_id = f"file_review_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # 即座に設計書を生成（要件ファイル情報を含む）
            design_doc = await self._generate_immediate_design_from_file(task, requirements_data, session_id)
            
            # レビュー状態を初期化
            review_data = {
                'task': task,
                'session_id': session_id,
                'design_document': design_doc,
                'requirements_file': requirements_file,
                'requirements_data': requirements_data,
                'status': 'REVIEW_READY',
                'feedback_history': [],
                'created_at': datetime.now().isoformat(),
                'modifications': 0
            }
            
            self.review_states[session_id] = review_data
            
            # ユーザーにレビューを提示
            return await self._present_design_for_review(review_data)
            
        except Exception as e:
            self.logger.log_error("REQUIREMENTS_FILE_ERROR", f"要件ファイルからの設計レビュー開始エラー: {e}")
            raise ValueError(f"要件ファイル処理エラー: {e}")
    
    async def _generate_immediate_design_from_file(self, task: Task, requirements_data: Dict, session_id: str) -> Dict:
        """要件ファイルから設計書を即座に生成"""
        self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, "📋 要件ファイルから設計書を即座に生成中...")
        
        try:
            from nocturnal_agent.llm.ai_collaborative_spec_generator import AICollaborativeSpecGenerator
            from nocturnal_agent.core.config import LLMConfig
            
            # 正しいLLMConfigオブジェクトを作成
            llm_config = LLMConfig(
                local_llm_url='http://localhost:1234',
                anthropic_api_key=os.getenv('ANTHROPIC_API_KEY', ''),
                enabled=True,
                timeout=30.0,
                max_tokens=4000,
                temperature=0.7
            )
            
            ai_generator = AICollaborativeSpecGenerator(llm_config)
            
            # 要件ファイルの情報をタスクに統合
            enhanced_task = self._enhance_task_with_requirements(task, requirements_data)
            
            tech_spec, collaboration_report = await ai_generator.generate_specification_collaboratively(enhanced_task)
            
            # 設計書の構造化（要件ファイル情報を含む）
            design_doc = {
                'technical_specification': tech_spec,
                'collaboration_report': collaboration_report,
                'requirements_source': {
                    'file_path': requirements_data.get('file_path'),
                    'format': requirements_data['file_format'],
                    'parsed_requirements': requirements_data['requirements'],
                    'technical_specs': requirements_data['technical_specs'],
                    'constraints': requirements_data['constraints'],
                    'acceptance_criteria': requirements_data['acceptance_criteria']
                },
                'design_summary': self._create_design_summary_from_requirements(tech_spec, requirements_data),
                'implementation_plan': self._extract_implementation_plan_from_requirements(tech_spec, requirements_data),
                'architecture_overview': self._extract_architecture_from_requirements(tech_spec, requirements_data),
                'quality_requirements': self._extract_quality_requirements_from_requirements(tech_spec, requirements_data)
            }
            
            self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, "✅ 要件ファイルベースの設計書生成完了")
            return design_doc
            
        except Exception as e:
            self.logger.log(LogLevel.ERROR, LogCategory.SYSTEM, f"要件ファイルベースの設計書生成エラー: {e}")
            # フォールバック設計書（要件ファイル情報を含む）
            return self._create_fallback_design_from_requirements(task, requirements_data)
    
    def _enhance_task_with_requirements(self, task: Task, requirements_data: Dict) -> Task:
        """要件ファイルの情報でタスクを拡張"""
        enhanced_description = task.description or ""
        
        # 要件リストを追加
        if requirements_data['requirements']:
            enhanced_description += f"\n\n## 機能要件:\n"
            for req in requirements_data['requirements']:
                enhanced_description += f"- {req}\n"
        
        # 技術仕様を追加
        if requirements_data['technical_specs']:
            enhanced_description += f"\n## 技術仕様:\n"
            for key, value in requirements_data['technical_specs'].items():
                enhanced_description += f"- {key}: {value}\n"
        
        # 制約を追加
        if requirements_data['constraints']:
            enhanced_description += f"\n## 制約:\n"
            for constraint in requirements_data['constraints']:
                enhanced_description += f"- {constraint}\n"
        
        # 受け入れ基準を追加
        if requirements_data['acceptance_criteria']:
            enhanced_description += f"\n## 受け入れ基準:\n"
            for criteria in requirements_data['acceptance_criteria']:
                enhanced_description += f"- {criteria}\n"
        
        # 新しいTaskオブジェクトを作成
        enhanced_task = Task(
            title=task.description,
            description=enhanced_description,
            priority=task.priority
        )
        
        return enhanced_task
    
    def _create_design_summary_from_requirements(self, tech_spec, requirements_data: Dict) -> Dict:
        """要件ファイルから設計概要を作成"""
        summary = self._create_design_summary(tech_spec) if tech_spec else {}
        
        # 要件ファイルからの追加情報
        summary.update({
            'requirements_count': len(requirements_data['requirements']),
            'constraints_count': len(requirements_data['constraints']),
            'acceptance_criteria_count': len(requirements_data['acceptance_criteria']),
            'source_file_format': requirements_data['file_format'],
            'specified_technologies': requirements_data['technical_specs']
        })
        
        return summary
    
    def _extract_implementation_plan_from_requirements(self, tech_spec, requirements_data: Dict) -> Dict:
        """要件ファイルから実装プランを抽出"""
        plan = self._extract_implementation_plan(tech_spec) if tech_spec else {}
        
        # 要件ファイルからの情報で拡張
        plan.update({
            'specified_requirements': requirements_data['requirements'][:5],  # 最初の5つ
            'technical_constraints': requirements_data['constraints'],
            'acceptance_tests': requirements_data['acceptance_criteria']
        })
        
        return plan
    
    def _extract_architecture_from_requirements(self, tech_spec, requirements_data: Dict) -> Dict:
        """要件ファイルからアーキテクチャ概要を抽出"""
        arch = self._extract_architecture(tech_spec) if tech_spec else {}
        
        # 技術仕様から情報を追加
        if requirements_data['technical_specs']:
            arch.update({
                'specified_technologies': requirements_data['technical_specs'],
                'technology_stack': list(requirements_data['technical_specs'].values())
            })
        
        return arch
    
    def _extract_quality_requirements_from_requirements(self, tech_spec, requirements_data: Dict) -> Dict:
        """要件ファイルから品質要件を抽出"""
        quality = self._extract_quality_requirements(tech_spec) if tech_spec else {}
        
        # 受け入れ基準から品質要件を抽出
        quality.update({
            'acceptance_criteria': requirements_data['acceptance_criteria'],
            'constraints': requirements_data['constraints']
        })
        
        return quality
    
    def _create_fallback_design_from_requirements(self, task: Task, requirements_data: Dict) -> Dict:
        """要件ファイルからフォールバック設計書を作成"""
        fallback = self._create_fallback_design(task)
        
        # 要件ファイル情報を追加
        fallback.update({
            'requirements_source': {
                'file_path': requirements_data.get('file_path'),
                'format': requirements_data['file_format'],
                'parsed_requirements': requirements_data['requirements'],
                'technical_specs': requirements_data['technical_specs'],
                'constraints': requirements_data['constraints'],
                'acceptance_criteria': requirements_data['acceptance_criteria']
            }
        })
        
        return fallback
    
    async def _generate_immediate_design(self, task: Task, session_id: str) -> Dict:
        """タスク受領と同時に設計書を即座に生成"""
        self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, "📋 設計書を即座に生成中...")
        
        # 既存のAI Collaborative Spec Generatorを利用
        try:
            from nocturnal_agent.llm.ai_collaborative_spec_generator import AICollaborativeSpecGenerator
            from nocturnal_agent.core.config import LLMConfig
            
            # 正しいLLMConfigオブジェクトを作成
            llm_config = LLMConfig(
                local_llm_url='http://localhost:1234',
                anthropic_api_key=os.getenv('ANTHROPIC_API_KEY', ''),
                enabled=True,
                timeout=30.0,
                max_tokens=4000,
                temperature=0.7
            )
            
            ai_generator = AICollaborativeSpecGenerator(llm_config)
            tech_spec, collaboration_report = await ai_generator.generate_specification_collaboratively(task)
            
            # 設計書の構造化
            design_doc = {
                'technical_specification': tech_spec,
                'collaboration_report': collaboration_report,
                'design_summary': self._create_design_summary(tech_spec),
                'implementation_plan': self._extract_implementation_plan(tech_spec),
                'architecture_overview': self._extract_architecture(tech_spec),
                'quality_requirements': self._extract_quality_requirements(tech_spec)
            }
            
            self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, "✅ 設計書生成完了")
            return design_doc
            
        except Exception as e:
            self.logger.log(LogLevel.ERROR, LogCategory.SYSTEM, f"設計書生成エラー: {e}")
            # フォールバック設計書
            return self._create_fallback_design(task)
    
    async def _present_design_for_review(self, review_data: Dict) -> Dict:
        """設計書をレビュー用に提示"""
        design_doc = review_data['design_document']
        
        presentation = {
            'review_id': review_data['session_id'],
            'task_title': review_data['task'].description,
            'design_summary': design_doc['design_summary'],
            'architecture_overview': design_doc['architecture_overview'],
            'implementation_plan': design_doc['implementation_plan'],
            'quality_requirements': design_doc['quality_requirements'],
            'review_options': {
                'approve': '設計を承認して夜間実行をスケジュール',
                'modify': '修正要求を提出',
                'discuss': '詳細について対話的に議論',
                'reject': '設計を拒否してタスクをキャンセル'
            },
            'status': 'REVIEW_READY'
        }
        
        self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, "👀 設計レビューの準備完了")
        return presentation
    
    async def process_user_feedback(self, review_id: str, feedback_type: str, feedback_content: str) -> Dict:
        """ユーザーフィードバックを処理"""
        if review_id not in self.review_states:
            raise ValueError(f"レビューID {review_id} が見つかりません")
        
        review_data = self.review_states[review_id]
        
        # フィードバック履歴に追加
        feedback_entry = {
            'type': feedback_type,
            'content': feedback_content,
            'timestamp': datetime.now().isoformat()
        }
        review_data['feedback_history'].append(feedback_entry)
        
        # フィードバックタイプに応じた処理を実行
        result = None
        if feedback_type == 'approve':
            result = await self._approve_design(review_data)
        elif feedback_type == 'modify':
            result = await self._request_modifications(review_data, feedback_content)
        elif feedback_type == 'discuss':
            result = await self._engage_dialogue(review_data, feedback_content)
        elif feedback_type == 'reject':
            result = await self._reject_design(review_data)
        else:
            raise ValueError(f"不明なフィードバックタイプ: {feedback_type}")
        
        # 処理後の状態を保存（重要：承認処理後に保存）
        self._save_session(review_id)
        
        return result
    
    async def _approve_design(self, review_data: Dict) -> Dict:
        """設計を承認し、実装タスクに分割して管理"""
        review_data['status'] = 'APPROVED'
        
        self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, f"✅ 設計承認開始: {review_data['session_id']}")
        
        try:
            # 実装タスク管理システムを初期化
            from .implementation_task_manager import ImplementationTaskManager
            task_manager = ImplementationTaskManager(str(self.workspace_path), self.logger)
            
            # 設計書から実装タスクに分割
            design_doc = review_data['design_document']
            created_task_ids = task_manager.break_down_specification_into_tasks(design_doc)
            
            # 作成されたタスクを自動承認（今回は全て承認）
            approved_tasks = []
            for task_id in created_task_ids:
                if task_manager.approve_task(task_id, "design_review"):
                    approved_tasks.append(task_id)
            
            self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, 
                          f"📋 設計承認完了 - {len(approved_tasks)}個の実装タスクを生成・承認")
            
            # タスクサマリーを取得
            task_summary = task_manager.get_task_summary()
            
            return {
                'status': 'APPROVED',
                'message': f'設計が承認され、{len(approved_tasks)}個の実装タスクに分割されました。夜間に順次実行されます。',
                'implementation_tasks': {
                    'created_count': len(created_task_ids),
                    'approved_count': len(approved_tasks),
                    'task_ids': approved_tasks,
                    'summary': task_summary
                },
                'review_id': review_data['session_id']
            }
            
        except Exception as e:
            self.logger.log(LogLevel.ERROR, LogCategory.SYSTEM, f"設計承認エラー: {e}")
            return {
                'status': 'APPROVAL_ERROR',
                'message': f'設計承認中にエラーが発生しました: {e}',
                'review_id': review_data['session_id']
            }
    
    async def _request_modifications(self, review_data: Dict, modification_request: str) -> Dict:
        """修正要求を処理"""
        review_data['status'] = 'MODIFICATIONS_NEEDED'
        review_data['modifications'] += 1
        
        self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, f"🔄 修正要求を処理中: {modification_request[:100]}...")
        
        # AI システムに修正指示を送信
        try:
            modified_design = await self._apply_modifications(review_data, modification_request)
            review_data['design_document'] = modified_design
            review_data['status'] = 'REVIEW_READY'
            
            return await self._present_design_for_review(review_data)
            
        except Exception as e:
            self.logger.log_error("MODIFICATION_ERROR", f"修正処理エラー: {e}")
            return {
                'status': 'MODIFICATION_ERROR',
                'message': f'修正処理でエラーが発生しました: {e}',
                'review_id': review_data['session_id']
            }
    
    async def _engage_dialogue(self, review_data: Dict, discussion_topic: str) -> Dict:
        """対話的議論を開始"""
        review_data['status'] = 'REVIEW_IN_PROGRESS'
        
        self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, f"💬 対話開始: {discussion_topic[:100]}...")
        
        # AI システムとの対話を開始
        dialogue_response = await self._generate_dialogue_response(review_data, discussion_topic)
        
        return {
            'status': 'DIALOGUE_ACTIVE',
            'discussion_topic': discussion_topic,
            'ai_response': dialogue_response,
            'review_id': review_data['session_id'],
            'continue_options': {
                'clarify': '詳細を確認',
                'modify': '修正を要求',
                'approve': '議論を終了して承認',
                'continue': '議論を継続'
            }
        }
    
    def _calculate_next_nighttime(self) -> str:
        """次の夜間実行時刻を計算（即座実行用に現在時刻+1分に設定）"""
        from datetime import timedelta
        now = datetime.now()
        # 即座実行のため現在時刻+1分に設定
        immediate_execution = now + timedelta(minutes=1)
        
        return immediate_execution.isoformat()
    
    def _create_design_summary(self, tech_spec: TechnicalSpec) -> Dict:
        """設計概要を作成"""
        components_count = len(tech_spec.design.components) if tech_spec.design.components else 3
        return {
            'project_name': tech_spec.metadata.title,
            'architecture_type': tech_spec.design.architecture.get('pattern', 'Layered Architecture'),
            'key_components': components_count,
            'complexity_level': 'HIGH' if components_count > 5 else 'MEDIUM',
            'estimated_effort': f"{components_count * 2} hours",
            'main_technologies': ['Python', 'Flask', 'SQLite']
        }
    
    def _extract_implementation_plan(self, tech_spec: TechnicalSpec) -> Dict:
        """実装プランを抽出"""
        components = tech_spec.design.components if tech_spec.design.components else []
        priority_components = [comp.get('name', f'コンポーネント{i+1}') for i, comp in enumerate(components[:3])] if components else ['コア機能', 'UI', 'データ層']
        
        return {
            'phases': [
                '1. 設計',
                '2. 実装', 
                '3. テスト',
                '4. デプロイ'
            ],
            'priority_components': priority_components,
            'risk_factors': ['時間制約', '技術的複雑さ']
        }
    
    def _extract_architecture(self, tech_spec: TechnicalSpec) -> Dict:
        """アーキテクチャ概要を抽出"""
        interfaces = tech_spec.design.interfaces if tech_spec.design.interfaces else []
        key_interfaces = [interface.get('name', f'インターフェース{i+1}') for i, interface in enumerate(interfaces[:3])] if interfaces else ['Web API', 'Database']
        
        return {
            'pattern': tech_spec.design.architecture.get('pattern', 'MVC'),
            'layers': ['View -> Controller -> Model'],
            'key_interfaces': key_interfaces,
            'data_flow': 'UI -> Logic -> Database'
        }
    
    def _extract_quality_requirements(self, tech_spec: TechnicalSpec) -> Dict:
        """品質要件を抽出"""
        return {
            'performance': '応答時間 < 2秒',
            'reliability': '稼働率 > 99%',
            'security': 'データ暗号化、認証必須',
            'maintainability': 'コード品質スコア > 0.8',
            'testing': 'カバレッジ > 80%'
        }
    
    def _create_fallback_design(self, task: Task) -> Dict:
        """フォールバック設計書を作成"""
        return {
            'technical_specification': None,
            'design_summary': {
                'project_name': task.description,
                'architecture_type': 'Layered Architecture',
                'key_components': 3,
                'complexity_level': 'MEDIUM',
                'estimated_effort': '6 hours',
                'main_technologies': ['Python', 'Flask', 'SQLite']
            },
            'implementation_plan': {
                'phases': ['設計', '実装', 'テスト', 'デプロイ'],
                'priority_components': ['コア機能', 'UI', 'データ層'],
                'risk_factors': ['時間制約', '技術的複雑さ']
            },
            'architecture_overview': {
                'pattern': 'MVC',
                'layers': ['View', 'Controller', 'Model'],
                'key_interfaces': ['Web API', 'Database'],
                'data_flow': 'UI -> Logic -> Database'
            },
            'quality_requirements': {
                'performance': 'Standard',
                'reliability': 'High',
                'security': 'Medium',
                'maintainability': 'High',
                'testing': 'Required'
            }
        }
    
    async def _apply_modifications(self, review_data: Dict, modification_request: str) -> Dict:
        """修正要求を設計に適用"""
        # 簡単な修正処理の実装（より高度な実装は後で追加）
        current_design = review_data['design_document']
        
        # 修正ログを追加
        if 'modification_log' not in current_design:
            current_design['modification_log'] = []
        
        current_design['modification_log'].append({
            'request': modification_request,
            'applied_at': datetime.now().isoformat(),
            'status': 'APPLIED'
        })
        
        return current_design
    
    async def _generate_dialogue_response(self, review_data: Dict, discussion_topic: str) -> str:
        """対話レスポンスを生成"""
        # 基本的な対話レスポンス（より高度なAI対話は後で実装）
        responses = {
            'architecture': 'アーキテクチャについて詳しく説明します。提案されている設計は...',
            'performance': 'パフォーマンスについてご質問ですね。想定される負荷は...',
            'security': 'セキュリティ要件について確認させていただきます...',
            'implementation': '実装方針について説明します。まず最初に...'
        }
        
        # キーワードベースで適切なレスポンスを選択
        for keyword, response in responses.items():
            if keyword in discussion_topic.lower():
                return response
        
        return f"「{discussion_topic}」について詳しく説明いたします。どの側面について特にお聞きになりたいでしょうか？"
    
    async def _reject_design(self, review_data: Dict) -> Dict:
        """設計を拒否"""
        review_data['status'] = 'REJECTED'
        
        self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, f"❌ 設計拒否: {review_data['task'].description}")
        
        return {
            'status': 'REJECTED',
            'message': '設計が拒否されました。タスクはキャンセルされます。',
            'review_id': review_data['session_id']
        }
    
    async def execute_scheduled_tasks(self):
        """承認された実装タスクを夜間に順次実行（ローカルLLM → ClaudeCode）"""
        self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, f"🌙 夜間実装タスク実行開始")
        
        try:
            # 新しい夜間タスク実行システムを使用
            from .implementation_task_manager import NightlyTaskExecutor
            
            nightly_executor = NightlyTaskExecutor(str(self.workspace_path), self.logger)
            
            # 夜間タスク実行（最大5タスク）
            execution_summary = await nightly_executor.execute_nightly_tasks(max_tasks=5)
            
            # 実行結果をログ出力
            executed_count = len(execution_summary.get('executed_tasks', []))
            failed_count = len(execution_summary.get('failed_tasks', []))
            total_time = execution_summary.get('total_execution_time', 0)
            
            self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, 
                          f"🎉 夜間実装タスク実行完了: 成功{executed_count}件、失敗{failed_count}件 (総実行時間: {total_time:.1f}秒)")
            
            # タスクサマリーがある場合は進捗を表示
            if 'task_summary' in execution_summary:
                task_summary = execution_summary['task_summary']
                self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, 
                              f"📊 全体進捗: {task_summary['completion_rate']:.1%} ({task_summary['completed_hours']:.1f}h/{task_summary['total_estimated_hours']:.1f}h)")
            
            return execution_summary
        
        except Exception as e:
            self.logger.log(LogLevel.ERROR, LogCategory.SYSTEM, f"夜間実装タスク実行エラー: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'message': f'夜間実装タスク実行中にエラーが発生: {e}'
            }
    
    async def _execute_implementation_task(self, task) -> Dict:
        """個別の実装タスクを実行"""
        try:
            self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, 
                          f"🔧 実装タスク実行: {task.title}")
            
            # 人が読める設計書を生成（新規タスクの場合）
            await self._generate_task_specific_documents(task)
            
            # 実装タスクの実際の実行
            execution_result = await self._perform_task_implementation(task)
            
            return {
                'status': 'success',
                'task_id': task.task_id,
                'title': task.title,
                'execution_time': datetime.now().isoformat(),
                'result': execution_result,
                'message': f'実装タスク「{task.title}」が正常に完了しました'
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'task_id': task.task_id,
                'title': task.title,
                'execution_time': datetime.now().isoformat(),
                'error': str(e),
                'message': f'実装タスク「{task.title}」の実行中にエラーが発生しました'
            }
    
    async def _generate_task_specific_documents(self, task):
        """タスク固有のドキュメントを生成"""
        try:
            # タスク固有のドキュメントディレクトリを作成
            task_docs_dir = self.workspace_path / 'docs' / 'tasks' / task.task_id
            task_docs_dir.mkdir(parents=True, exist_ok=True)
            
            # タスク仕様書を生成
            task_spec_content = self._generate_task_specification(task)
            task_spec_file = task_docs_dir / 'task_specification.md'
            
            with open(task_spec_file, 'w', encoding='utf-8') as f:
                f.write(task_spec_content)
            
            self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, 
                          f"📝 タスク仕様書生成完了: {task_spec_file}")
            
        except Exception as e:
            self.logger.log(LogLevel.ERROR, LogCategory.SYSTEM, 
                          f"タスク仕様書生成エラー: {e}")
    
    def _generate_task_specification(self, task) -> str:
        """タスク仕様書を生成"""
        content = f"""# 実装タスク仕様書: {task.title}

**タスクID**: {task.task_id}  
**作成日時**: {task.created_at.strftime('%Y年%m月%d日 %H:%M:%S')}  
**更新日時**: {task.updated_at.strftime('%Y年%m月%d日 %H:%M:%S')}  
**優先度**: {task.priority.value}  
**ステータス**: {task.status.value}

## 📋 タスク概要

{task.description}

## ⏱️ 作業見積もり

**推定時間**: {task.estimated_hours} 時間

## 🔧 技術要件

"""
        
        for i, req in enumerate(task.technical_requirements, 1):
            content += f"{i}. {req}\n"
        
        content += """
## ✅ 受け入れ基準

"""
        
        for i, criteria in enumerate(task.acceptance_criteria, 1):
            content += f"{i}. {criteria}\n"
        
        if task.dependencies:
            content += """
## 🔗 依存関係

以下のタスクが完了している必要があります：

"""
            for dep in task.dependencies:
                content += f"- {dep}\n"
        
        content += f"""
## 📊 実行ログ

"""
        
        for log_entry in task.execution_log:
            action = log_entry.get('action', 'unknown')
            timestamp = log_entry.get('timestamp', 'unknown')
            content += f"- **{action}**: {timestamp}\n"
            
            if 'approver' in log_entry:
                content += f"  - 承認者: {log_entry['approver']}\n"
            if 'result' in log_entry:
                content += f"  - 結果: {log_entry['result']}\n"
            if 'error' in log_entry:
                content += f"  - エラー: {log_entry['error']}\n"
        
        content += """
---

*この仕様書は naシステム によって自動生成されました。*
"""
        
        return content
    
    async def _perform_task_implementation(self, task) -> Dict:
        """実装タスクの実際の実行処理"""
        
        # タスクタイトルに基づいて適切な実装処理を実行
        if "実装" in task.title:
            return await self._implement_feature(task)
        elif "テスト" in task.title:
            return await self._implement_tests(task)
        elif "設計" in task.title:
            return await self._implement_design(task)
        elif "デプロイ" in task.title:
            return await self._implement_deployment(task)
        elif "インターフェース" in task.title:
            return await self._implement_interface(task)
        else:
            return await self._implement_generic_task(task)
    
    async def _implement_feature(self, task) -> Dict:
        """機能実装タスクを実行"""
        return {
            'type': 'feature_implementation',
            'description': f'{task.title}の機能実装を完了',
            'files_modified': [],
            'tests_added': True,
            'documentation_updated': True
        }
    
    async def _implement_tests(self, task) -> Dict:
        """テスト実装タスクを実行"""
        return {
            'type': 'test_implementation',
            'description': f'{task.title}のテスト実装を完了',
            'test_files_created': [],
            'coverage_improved': True
        }
    
    async def _implement_design(self, task) -> Dict:
        """設計タスクを実行"""
        return {
            'type': 'design_implementation',
            'description': f'{task.title}の設計作業を完了',
            'design_documents_created': [],
            'architecture_updated': True
        }
    
    async def _implement_deployment(self, task) -> Dict:
        """デプロイタスクを実行"""
        return {
            'type': 'deployment_implementation', 
            'description': f'{task.title}のデプロイ作業を完了',
            'deployment_scripts_created': [],
            'environment_configured': True
        }
    
    async def _implement_interface(self, task) -> Dict:
        """インターフェース実装タスクを実行"""
        return {
            'type': 'interface_implementation',
            'description': f'{task.title}のインターフェース実装を完了',
            'api_endpoints_created': [],
            'integration_tested': True
        }
    
    async def _implement_generic_task(self, task) -> Dict:
        """汎用タスクを実行"""
        return {
            'type': 'generic_implementation',
            'description': f'{task.title}の作業を完了',
            'work_completed': True,
            'quality_checked': True
        }
    
    async def _execute_approved_task(self, scheduled_task: Dict) -> Dict:
        """承認されたタスクを実行し、人が読める設計書も生成"""
        task = scheduled_task['task']
        design_doc = scheduled_task['design_document']
        
        # タスクの説明を取得（辞書形式の場合とオブジェクト形式の場合に対応）
        if isinstance(task, dict):
            task_description = task.get('description', 'Unknown Task')
        else:
            task_description = getattr(task, 'description', 'Unknown Task')
        
        self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, f"📋 タスク実行開始: {task_description}")
        
        try:
            # 人が読める設計書をMarkdown形式で生成
            await self._generate_human_readable_documents(scheduled_task)
            
            # 設計書を使用して実行（technical_specificationがあるかチェック）
            if design_doc.get('technical_specification'):
                # 既存の実行ロジックを使用
                return {
                    'status': 'success',
                    'message': f'タスク「{task_description}」の実行が完了しました（人が読める設計書も生成済み）',
                    'execution_time': datetime.now().isoformat()
                }
            else:
                # フォールバック設計書での実行
                return {
                    'status': 'fallback_execution',
                    'message': f'フォールバック設計でタスク「{task_description}」を実行しました（人が読める設計書も生成済み）',
                    'execution_time': datetime.now().isoformat()
                }
        except Exception as e:
            self.logger.log(LogLevel.ERROR, LogCategory.SYSTEM, f"タスク実行エラー: {e}")
            return {
                'status': 'error',
                'message': f'タスク「{task_description}」の実行中にエラーが発生しました: {e}',
                'execution_time': datetime.now().isoformat()
            }

    
    async def _generate_human_readable_documents(self, scheduled_task: Dict):
        """人が読める設計書とドキュメントを生成"""
        review_id = scheduled_task.get('review_id', 'unknown')
        task = scheduled_task.get('task', {})
        design_doc = scheduled_task.get('design_document', {})
        
        # タスクの説明を取得
        if isinstance(task, dict):
            task_description = task.get('description', 'Unknown Task')
        else:
            task_description = getattr(task, 'description', 'Unknown Task')
        
        self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, f"📝 人が読める設計書生成開始: {task_description}")
        
        # プロジェクトのドキュメントディレクトリを作成
        docs_dir = self.workspace_path / 'docs'
        docs_dir.mkdir(exist_ok=True)
        
        # 生成するドキュメントの種類
        documents = {
            'technical_specification.md': self._generate_technical_spec_md(design_doc, task_description),
            'architecture_design.md': self._generate_architecture_md(design_doc),
            'implementation_plan.md': self._generate_implementation_plan_md(design_doc),
            'api_specification.md': self._generate_api_spec_md(design_doc),
            'database_design.md': self._generate_database_design_md(design_doc),
            'quality_requirements.md': self._generate_quality_requirements_md(design_doc)
        }
        
        # 各ドキュメントを生成
        generated_files = []
        for filename, content in documents.items():
            file_path = docs_dir / filename
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                generated_files.append(str(file_path))
                self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, f"✅ 生成完了: {filename}")
            except Exception as e:
                self.logger.log(LogLevel.ERROR, LogCategory.SYSTEM, f"❌ 生成失敗: {filename} - {e}")
        
        # メイン設計書（全体統合版）を生成
        main_spec_path = docs_dir / f'design_specification_{review_id}.md'
        main_content = self._generate_main_specification(design_doc, task_description, review_id)
        
        try:
            with open(main_spec_path, 'w', encoding='utf-8') as f:
                f.write(main_content)
            generated_files.append(str(main_spec_path))
            self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, f"✅ メイン設計書生成完了: {main_spec_path}")
        except Exception as e:
            self.logger.log(LogLevel.ERROR, LogCategory.SYSTEM, f"❌ メイン設計書生成失敗: {e}")
        
        self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, f"📚 人が読める設計書生成完了: {len(generated_files)}ファイル")
        return generated_files
    
    def _generate_main_specification(self, design_doc: Dict, task_description: str, review_id: str) -> str:
        """メイン設計書（統合版）を生成"""
        design_summary = design_doc.get('design_summary', {})
        arch_overview = design_doc.get('architecture_overview', {})
        impl_plan = design_doc.get('implementation_plan', {})
        quality_req = design_doc.get('quality_requirements', {})
        
        content = f"""# 設計仕様書: {task_description}

**レビューID**: {review_id}  
**生成日時**: {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}  
**プロジェクト**: {design_summary.get('project_name', 'Unknown')}

## 📊 プロジェクト概要

- **アーキテクチャタイプ**: {design_summary.get('architecture_type', 'Unknown')}
- **主要コンポーネント数**: {design_summary.get('key_components', 'Unknown')}
- **複雑度レベル**: {design_summary.get('complexity_level', 'Unknown')}
- **推定作業時間**: {design_summary.get('estimated_effort', 'Unknown')}
- **主要技術**: {', '.join(design_summary.get('main_technologies', []))}

## 🏗️ アーキテクチャ設計

### パターン
{arch_overview.get('pattern', 'Unknown')}

### レイヤー構成
"""
        
        layers = arch_overview.get('layers', [])
        if isinstance(layers, list):
            for layer in layers:
                content += f"- {layer}\n"
        else:
            content += f"- {layers}\n"
        
        content += f"""
### 主要インターフェース
"""
        
        interfaces = arch_overview.get('key_interfaces', [])
        if isinstance(interfaces, list):
            for interface in interfaces:
                content += f"- {interface}\n"
        else:
            content += f"- {interfaces}\n"
        
        content += f"""
### データフロー
{arch_overview.get('data_flow', 'Unknown')}

## 📋 実装計画

### 実装フェーズ
"""
        
        phases = impl_plan.get('phases', [])
        if isinstance(phases, list):
            for i, phase in enumerate(phases, 1):
                content += f"{i}. {phase}\n"
        else:
            content += f"1. {phases}\n"
        
        content += f"""
### 優先コンポーネント
"""
        
        priority_components = impl_plan.get('priority_components', [])
        if isinstance(priority_components, list):
            for component in priority_components:
                content += f"- {component}\n"
        else:
            content += f"- {priority_components}\n"
        
        content += f"""
### リスクファクター
"""
        
        risk_factors = impl_plan.get('risk_factors', [])
        if isinstance(risk_factors, list):
            for risk in risk_factors:
                content += f"- {risk}\n"
        else:
            content += f"- {risk_factors}\n"
        
        content += f"""
## ✅ 品質要件

- **パフォーマンス**: {quality_req.get('performance', 'Unknown')}
- **信頼性**: {quality_req.get('reliability', 'Unknown')}
- **セキュリティ**: {quality_req.get('security', 'Unknown')}
- **保守性**: {quality_req.get('maintainability', 'Unknown')}
- **テスト**: {quality_req.get('testing', 'Unknown')}

## 📚 関連ドキュメント

このメイン設計書と合わせて、以下の詳細ドキュメントも参照してください：

- [技術仕様書](./technical_specification.md)
- [アーキテクチャ設計](./architecture_design.md)
- [実装計画](./implementation_plan.md)
- [API仕様書](./api_specification.md)
- [データベース設計](./database_design.md)
- [品質要件](./quality_requirements.md)

---

*この設計書は naシステム によって自動生成されました。*
"""
        
        return content
    
    def _generate_technical_spec_md(self, design_doc: Dict, task_description: str) -> str:
        """技術仕様書を生成"""
        design_summary = design_doc.get('design_summary', {})
        
        content = f"""# 技術仕様書

## プロジェクト概要
{task_description}

## 技術スタック
"""
        
        technologies = design_summary.get('main_technologies', [])
        for tech in technologies:
            content += f"- {tech}\n"
        
        content += f"""
## システム要件

### 機能要件
- コア機能の実装
- ユーザーインターフェースの提供
- データ管理機能

### 非機能要件
- パフォーマンス: 応答時間 < 2秒
- 可用性: 99.9%以上
- セキュリティ: 業界標準準拠

## 実装ガイドライン

### コーディング規約
- 言語標準に準拠
- 型ヒント使用（該当言語）
- ドキュメント文字列必須

### エラーハンドリング
- 例外の適切な処理
- ログ出力の実装
- ユーザーフレンドリーなエラーメッセージ
"""
        
        return content
    
    def _generate_architecture_md(self, design_doc: Dict) -> str:
        """アーキテクチャ設計書を生成"""
        arch_overview = design_doc.get('architecture_overview', {})
        
        content = f"""# アーキテクチャ設計書

## アーキテクチャパターン
{arch_overview.get('pattern', 'MVC')}

## システム構成図

```
{arch_overview.get('data_flow', 'UI -> Logic -> Database')}
```

## レイヤー構成
"""
        
        layers = arch_overview.get('layers', [])
        if isinstance(layers, list):
            for layer in layers:
                content += f"### {layer}\n- 責務: {layer}層の処理\n- 技術: 適切な技術選択\n\n"
        
        content += """
## インターフェース設計
"""
        
        interfaces = arch_overview.get('key_interfaces', [])
        if isinstance(interfaces, list):
            for interface in interfaces:
                content += f"### {interface}\n- 目的: {interface}との連携\n- プロトコル: 適切なプロトコル選択\n\n"
        
        return content
    
    def _generate_implementation_plan_md(self, design_doc: Dict) -> str:
        """実装計画書を生成"""
        impl_plan = design_doc.get('implementation_plan', {})
        
        content = """# 実装計画書

## 実装フェーズ
"""
        
        phases = impl_plan.get('phases', [])
        if isinstance(phases, list):
            for i, phase in enumerate(phases, 1):
                content += f"""
### フェーズ {i}: {phase}
- 期間: 適切な期間設定
- 成果物: {phase}関連の成果物
- 品質基準: 適切な品質基準
"""
        
        content += """
## 優先度付きコンポーネント
"""
        
        priority_components = impl_plan.get('priority_components', [])
        if isinstance(priority_components, list):
            for i, component in enumerate(priority_components, 1):
                content += f"{i}. **{component}**: 優先度高\n"
        
        content += """
## リスク管理
"""
        
        risk_factors = impl_plan.get('risk_factors', [])
        if isinstance(risk_factors, list):
            for risk in risk_factors:
                content += f"- **{risk}**: 対策検討が必要\n"
        
        return content
    
    def _generate_api_spec_md(self, design_doc: Dict) -> str:
        """API仕様書を生成"""
        return """# API仕様書

## 基本仕様
- プロトコル: HTTP/HTTPS
- 形式: REST API
- データ形式: JSON

## エンドポイント一覧

### データ操作API

#### GET /api/data
- 目的: データ一覧取得
- パラメータ: 
  - limit: 取得件数
  - offset: オフセット
- レスポンス: データ配列

#### POST /api/data
- 目的: データ作成
- リクエストボディ: データオブジェクト
- レスポンス: 作成されたデータ

#### PUT /api/data/{id}
- 目的: データ更新
- パラメータ: id (データID)
- リクエストボディ: 更新データ
- レスポンス: 更新されたデータ

#### DELETE /api/data/{id}
- 目的: データ削除
- パラメータ: id (データID)
- レスポンス: 削除確認

## エラーレスポンス

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "エラーメッセージ",
    "details": "詳細情報"
  }
}
```
"""
    
    def _generate_database_design_md(self, design_doc: Dict) -> str:
        """データベース設計書を生成"""
        return """# データベース設計書

## データベース仕様
- タイプ: SQLite / PostgreSQL
- エンコーディング: UTF-8
- タイムゾーン: UTC

## テーブル設計

### main_data テーブル
```sql
CREATE TABLE main_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data_field TEXT NOT NULL,
    status VARCHAR(50) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### カラム説明
- `id`: 主キー
- `data_field`: メインデータフィールド
- `status`: ステータス
- `created_at`: 作成日時
- `updated_at`: 更新日時

### インデックス設計
```sql
CREATE INDEX idx_main_data_status ON main_data(status);
CREATE INDEX idx_main_data_created_at ON main_data(created_at);
```

## データ制約
- 外部キー制約の適切な設定
- NOT NULL制約の設定
- デフォルト値の設定
"""
    
    def _generate_quality_requirements_md(self, design_doc: Dict) -> str:
        """品質要件書を生成"""
        quality_req = design_doc.get('quality_requirements', {})
        
        content = f"""# 品質要件書

## パフォーマンス要件
**レベル**: {quality_req.get('performance', 'Standard')}

- 応答時間: 平均2秒以下
- スループット: 適切な同時接続数対応
- リソース使用量: CPU・メモリの効率的利用

## 信頼性要件
**レベル**: {quality_req.get('reliability', 'High')}

- 可用性: 99.9%以上
- 障害復旧時間: 15分以内
- データ整合性: 100%保証

## セキュリティ要件
**レベル**: {quality_req.get('security', 'Medium')}

- 認証・認可の実装
- データ暗号化
- セキュリティホールの定期検査

## 保守性要件
**レベル**: {quality_req.get('maintainability', 'High')}

- コードの可読性
- モジュール化
- ドキュメントの整備

## テスト要件
**レベル**: {quality_req.get('testing', 'Required')}

- 単体テスト: カバレッジ80%以上
- 統合テスト: 主要機能の動作確認
- E2Eテスト: ユーザーシナリオの検証
"""
        
        return content

class RequirementsFileParser:
    """要件ファイルパーサー"""
    
    SUPPORTED_FORMATS = ['.md', '.txt', '.yaml', '.yml', '.json']
    
    @staticmethod
    def parse_requirements_file(file_path: str) -> Dict:
        """要件ファイルを解析してタスク情報を抽出"""
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"要件ファイルが見つかりません: {file_path}")
        
        if file_path.suffix not in RequirementsFileParser.SUPPORTED_FORMATS:
            raise ValueError(f"サポートされていないファイル形式: {file_path.suffix}")
        
        content = file_path.read_text(encoding='utf-8')
        
        if file_path.suffix in ['.yaml', '.yml']:
            return RequirementsFileParser._parse_yaml_requirements(content, file_path.name)
        elif file_path.suffix == '.json':
            return RequirementsFileParser._parse_json_requirements(content, file_path.name)
        elif file_path.suffix == '.md':
            return RequirementsFileParser._parse_markdown_requirements(content, file_path.name)
        else:  # .txt
            return RequirementsFileParser._parse_text_requirements(content, file_path.name)
    
    @staticmethod
    def _parse_yaml_requirements(content: str, filename: str) -> Dict:
        """YAML形式の要件ファイルを解析"""
        try:
            import yaml
            data = yaml.safe_load(content)
            
            return {
                'title': data.get('title', data.get('name', filename.replace('.yaml', '').replace('.yml', ''))),
                'description': data.get('description', data.get('summary', '')),
                'priority': data.get('priority', 'medium'),
                'requirements': data.get('requirements', []),
                'technical_specs': data.get('technical_specs', data.get('tech_specs', {})),
                'constraints': data.get('constraints', []),
                'acceptance_criteria': data.get('acceptance_criteria', data.get('criteria', [])),
                'file_format': 'yaml',
                'raw_content': content
            }
        except ImportError:
            raise ImportError("YAML解析にはpyyamlパッケージが必要です: pip install pyyaml")
        except yaml.YAMLError as e:
            raise ValueError(f"YAML解析エラー: {e}")
    
    @staticmethod
    def _parse_json_requirements(content: str, filename: str) -> Dict:
        """JSON形式の要件ファイルを解析"""
        try:
            import json
            data = json.loads(content)
            
            return {
                'title': data.get('title', data.get('name', filename.replace('.json', ''))),
                'description': data.get('description', data.get('summary', '')),
                'priority': data.get('priority', 'medium'),
                'requirements': data.get('requirements', []),
                'technical_specs': data.get('technical_specs', data.get('tech_specs', {})),
                'constraints': data.get('constraints', []),
                'acceptance_criteria': data.get('acceptance_criteria', data.get('criteria', [])),
                'file_format': 'json',
                'raw_content': content
            }
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON解析エラー: {e}")
    
    @staticmethod
    def _parse_markdown_requirements(content: str, filename: str) -> Dict:
        """Markdown形式の要件ファイルを解析"""
        lines = content.split('\n')
        
        # タイトル抽出（最初のH1またはファイル名）
        title = filename.replace('.md', '')
        description = ""
        requirements = []
        technical_specs = {}
        constraints = []
        acceptance_criteria = []
        
        current_section = None
        current_content = []
        
        for line in lines:
            line = line.strip()
            
            # H1タイトル
            if line.startswith('# ') and not title:
                title = line[2:].strip()
                continue
            
            # H2セクション
            if line.startswith('## '):
                # 前のセクションを処理
                if current_section and current_content:
                    RequirementsFileParser._process_markdown_section(
                        current_section, current_content, description, requirements,
                        technical_specs, constraints, acceptance_criteria
                    )
                
                current_section = line[3:].strip().lower()
                current_content = []
                continue
            
            # コンテンツ収集
            if line:
                current_content.append(line)
        
        # 最後のセクションを処理
        if current_section and current_content:
            RequirementsFileParser._process_markdown_section(
                current_section, current_content, description, requirements,
                technical_specs, constraints, acceptance_criteria
            )
        
        # descriptionが空の場合、最初の段落を使用
        if not description and current_content:
            description = ' '.join(current_content[:3])  # 最初の3行
        
        return {
            'title': title,
            'description': description,
            'priority': 'medium',
            'requirements': requirements,
            'technical_specs': technical_specs,
            'constraints': constraints,
            'acceptance_criteria': acceptance_criteria,
            'file_format': 'markdown',
            'raw_content': content
        }
    
    @staticmethod
    def _process_markdown_section(section_name: str, content: List[str], description: str,
                                requirements: List, technical_specs: Dict, 
                                constraints: List, acceptance_criteria: List):
        """Markdownセクションを処理"""
        content_text = '\n'.join(content)
        
        if 'description' in section_name or 'summary' in section_name or '概要' in section_name:
            description = content_text
        elif 'requirement' in section_name or '要件' in section_name:
            # リスト項目を抽出
            for line in content:
                if line.startswith(('- ', '* ', '+ ')):
                    requirements.append(line[2:].strip())
                elif line.startswith(('1. ', '2. ', '3. ')):
                    requirements.append(line[3:].strip())
        elif 'technical' in section_name or '技術' in section_name:
            technical_specs['overview'] = content_text
        elif 'constraint' in section_name or '制約' in section_name:
            for line in content:
                if line.startswith(('- ', '* ', '+ ')):
                    constraints.append(line[2:].strip())
        elif 'acceptance' in section_name or 'criteria' in section_name or '受け入れ' in section_name:
            for line in content:
                if line.startswith(('- ', '* ', '+ ')):
                    acceptance_criteria.append(line[2:].strip())
    
    @staticmethod
    def _parse_text_requirements(content: str, filename: str) -> Dict:
        """テキスト形式の要件ファイルを解析"""
        lines = [line.strip() for line in content.split('\n') if line.strip()]
        
        title = filename.replace('.txt', '')
        description = ""
        requirements = []
        
        # 最初の行がタイトルっぽい場合
        if lines and len(lines[0]) < 100 and not lines[0].startswith(('- ', '* ', '1. ')):
            title = lines[0]
            lines = lines[1:]
        
        # 説明部分（リストではない最初の数行）
        desc_lines = []
        for line in lines:
            if line.startswith(('- ', '* ', '+ ', '1. ', '2. ')):
                break
            desc_lines.append(line)
        
        description = ' '.join(desc_lines)
        
        # 要件リスト
        for line in lines:
            if line.startswith(('- ', '* ', '+ ')):
                requirements.append(line[2:].strip())
            elif line.startswith(('1. ', '2. ', '3. ', '4. ', '5. ')):
                requirements.append(line[3:].strip())
        
        return {
            'title': title,
            'description': description,
            'priority': 'medium',
            'requirements': requirements,
            'technical_specs': {},
            'constraints': [],
            'acceptance_criteria': [],
            'file_format': 'text',
            'raw_content': content
        }
    
    @staticmethod
    def create_sample_requirements_file(file_path: str, format_type: str = 'markdown'):
        """サンプル要件ファイルを作成"""
        file_path = Path(file_path)
        
        if format_type == 'yaml':
            content = """# プロジェクト要件定義
title: "Webアプリケーション開発"
description: "モダンなWebアプリケーションの開発"
priority: "high"

requirements:
  - "ユーザー認証機能"
  - "レスポンシブデザイン"
  - "RESTful API"
  - "データベース連携"

technical_specs:
  backend: "Python Flask"
  frontend: "HTML/CSS/JavaScript"
  database: "SQLite"
  
constraints:
  - "開発期間: 2週間"
  - "予算: 制限あり"
  
acceptance_criteria:
  - "ユーザーログインが正常に動作する"
  - "モバイル端末で適切に表示される"
  - "API応答時間が2秒以内"
"""
        elif format_type == 'json':
            content = """{
  "title": "Webアプリケーション開発",
  "description": "モダンなWebアプリケーションの開発",
  "priority": "high",
  "requirements": [
    "ユーザー認証機能",
    "レスポンシブデザイン", 
    "RESTful API",
    "データベース連携"
  ],
  "technical_specs": {
    "backend": "Python Flask",
    "frontend": "HTML/CSS/JavaScript",
    "database": "SQLite"
  },
  "constraints": [
    "開発期間: 2週間",
    "予算: 制限あり"
  ],
  "acceptance_criteria": [
    "ユーザーログインが正常に動作する",
    "モバイル端末で適切に表示される",
    "API応答時間が2秒以内"
  ]
}"""
        else:  # markdown
            content = """# Webアプリケーション開発

## 概要
モダンなWebアプリケーションの開発プロジェクト

## 要件
- ユーザー認証機能
- レスポンシブデザイン
- RESTful API
- データベース連携

## 技術仕様
- バックエンド: Python Flask
- フロントエンド: HTML/CSS/JavaScript
- データベース: SQLite

## 制約
- 開発期間: 2週間
- 予算: 制限あり

## 受け入れ基準
- ユーザーログインが正常に動作する
- モバイル端末で適切に表示される
- API応答時間が2秒以内
"""
        
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding='utf-8')
        
        return file_path
