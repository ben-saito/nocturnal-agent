"""Spec Kit駆動のタスク実行システム"""

import asyncio
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List
import uuid

from ..core.models import Task, ExecutionResult, AgentType
from ..design.spec_kit_integration import (
    SpecKitManager, TaskSpecTranslator, TechnicalSpec, 
    SpecType, SpecStatus
)
from ..logging.structured_logger import StructuredLogger, LogLevel, LogCategory


class SpecDrivenExecutor:
    """Spec Kit仕様駆動のタスク実行器"""
    
    def __init__(self, workspace_path: str, logger: StructuredLogger):
        self.workspace_path = Path(workspace_path)
        self.logger = logger
        
        # Spec Kit管理システム
        self.spec_manager = SpecKitManager(str(self.workspace_path / "specs"))
        self.translator = TaskSpecTranslator(self.spec_manager)
        
        # 実行履歴
        self.execution_history = []
    
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
    
    async def _generate_spec_from_task(self, task: Task, spec_type: SpecType, 
                                     session_id: str) -> TechnicalSpec:
        """タスクから技術仕様生成"""
        
        self.logger.log(
            LogLevel.INFO,
            LogCategory.SYSTEM,
            f"技術仕様生成: {task.description}",
            task_id=task.id,
            session_id=session_id,
            extra_data={'spec_type': spec_type.value}
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
            f"技術仕様生成完了: {spec_path}",
            task_id=task.id,
            session_id=session_id,
            extra_data={
                'spec_path': str(spec_path),
                'requirements_count': len(spec.requirements)
            }
        )
        
        return spec
    
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
        
        # 実行コンテキストに仕様情報を追加
        enhanced_task.context = enhanced_task.context or {}
        enhanced_task.context.update({
            'spec_driven': True,
            'spec_title': spec.metadata.title,
            'spec_version': spec.metadata.version,
            'components': [comp['name'] for comp in spec.design.components],
            'interfaces': [intf['name'] for intf in spec.design.interfaces],
            'quality_requirements': {
                'target': enhanced_task.estimated_quality,
                'threshold': enhanced_task.minimum_quality_threshold
            }
        })
        
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