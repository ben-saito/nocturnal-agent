"""
設計ファイル管理システム
分散コーディングエージェントが設計書を作成・管理するためのシステム
"""

import yaml
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict
from enum import Enum

from ..log_system.structured_logger import StructuredLogger, LogLevel, LogCategory


class ExecutionMode(Enum):
    """実行モード"""
    IMMEDIATE = "immediate"  # 即時実行
    NIGHTLY = "nightly"     # 夜間実行
    SCHEDULED = "scheduled"  # スケジュール実行


class Priority(Enum):
    """優先度"""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class Complexity(Enum):
    """複雑度"""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class DesignValidationResult:
    """設計ファイル検証結果"""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    completeness_score: float  # 0.0-1.0


class DesignFileManager:
    """設計ファイル管理システム"""
    
    def __init__(self, logger: StructuredLogger):
        self.logger = logger
        # プロジェクトルートからテンプレートパスを取得
        project_root = Path(__file__).parent.parent.parent.parent
        self.template_path = project_root / "templates" / "design_template.yaml"
        
    def load_template(self) -> Dict:
        """設計テンプレートを読み込み"""
        try:
            with open(self.template_path, 'r', encoding='utf-8') as f:
                template = yaml.safe_load(f)
            
            self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, 
                          f"📋 設計テンプレート読み込み完了: {self.template_path}")
            return template
            
        except Exception as e:
            self.logger.log(LogLevel.ERROR, LogCategory.SYSTEM, 
                          f"❌ テンプレート読み込みエラー: {e}")
            raise
    
    def create_design_from_template(self, project_name: str, author: str, 
                                   workspace_path: str) -> Dict:
        """テンプレートから新規設計ファイルを作成"""
        template = self.load_template()
        
        # 基本情報を設定
        template['project_info']['name'] = project_name
        template['project_info']['author'] = author
        template['project_info']['created_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        template['project_info']['workspace_path'] = workspace_path
        
        # メタデータを設定
        template['metadata']['generated_by'] = author
        template['metadata']['generation_timestamp'] = datetime.now().isoformat()
        
        self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, 
                      f"📝 新規設計ファイル作成: {project_name}")
        
        return template
    
    def save_design_file(self, design: Dict, file_path: Union[str, Path]) -> bool:
        """設計ファイルを保存"""
        try:
            file_path = Path(file_path)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                yaml.dump(design, f, default_flow_style=False, 
                         allow_unicode=True, sort_keys=False)
            
            self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, 
                          f"💾 設計ファイル保存完了: {file_path}")
            return True
            
        except Exception as e:
            self.logger.log(LogLevel.ERROR, LogCategory.SYSTEM, 
                          f"❌ 設計ファイル保存エラー: {e}")
            return False
    
    def load_design_file(self, file_path: Union[str, Path]) -> Optional[Dict]:
        """設計ファイルを読み込み"""
        try:
            file_path = Path(file_path)
            
            with open(file_path, 'r', encoding='utf-8') as f:
                design = yaml.safe_load(f)
            
            self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, 
                          f"📋 設計ファイル読み込み完了: {file_path}")
            return design
            
        except Exception as e:
            self.logger.log(LogLevel.ERROR, LogCategory.SYSTEM, 
                          f"❌ 設計ファイル読み込みエラー: {e}")
            return None
    
    def validate_design_file(self, design: Dict) -> DesignValidationResult:
        """設計ファイルの妥当性を検証"""
        errors = []
        warnings = []
        
        # 必須フィールドチェック
        required_fields = [
            'project_info.name',
            'project_info.description', 
            'project_info.workspace_path',
            'requirements',
            'architecture',
            'implementation_plan'
        ]
        
        for field_path in required_fields:
            if not self._check_nested_field(design, field_path):
                errors.append(f"必須フィールドが不足: {field_path}")
        
        # プロジェクト情報の検証
        project_info = design.get('project_info', {})
        if not project_info.get('name', '').strip():
            errors.append("プロジェクト名が空です")
        
        workspace_path = project_info.get('workspace_path', '')
        if workspace_path and not Path(workspace_path).exists():
            warnings.append(f"ワークスペースパスが存在しません: {workspace_path}")
        
        # 要件の検証
        requirements = design.get('requirements', {})
        functional_reqs = requirements.get('functional', [])
        if not functional_reqs:
            warnings.append("機能要件が定義されていません")
        
        # 実装計画の検証
        impl_plan = design.get('implementation_plan', {})
        phases = impl_plan.get('phases', [])
        if not phases:
            warnings.append("実装フェーズが定義されていません")
        
        priority_components = impl_plan.get('priority_components', [])
        if not priority_components:
            warnings.append("優先度付きコンポーネントが定義されていません")
        
        # 完成度スコア算出
        total_checks = 20  # 総チェック項目数
        completed_checks = 0
        
        # 各セクションの完成度をチェック
        if project_info.get('name'): completed_checks += 1
        if project_info.get('description'): completed_checks += 1
        if project_info.get('workspace_path'): completed_checks += 1
        if functional_reqs: completed_checks += 2
        if requirements.get('non_functional'): completed_checks += 2
        if design.get('architecture', {}).get('components'): completed_checks += 2
        if design.get('technology_stack'): completed_checks += 2
        if phases: completed_checks += 2
        if priority_components: completed_checks += 2
        if design.get('task_breakdown'): completed_checks += 2
        if design.get('quality_requirements'): completed_checks += 1
        if design.get('execution_config'): completed_checks += 1
        
        completeness_score = completed_checks / total_checks
        
        is_valid = len(errors) == 0
        
        self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, 
                      f"🔍 設計ファイル検証完了: {'✅ 有効' if is_valid else '❌ 無効'} "
                      f"(完成度: {completeness_score:.1%})")
        
        return DesignValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            completeness_score=completeness_score
        )
    
    def _check_nested_field(self, data: Dict, field_path: str) -> bool:
        """ネストしたフィールドの存在をチェック"""
        keys = field_path.split('.')
        current = data
        
        for key in keys:
            if not isinstance(current, dict) or key not in current:
                return False
            current = current[key]
        
        # 値が空でないかチェック
        if isinstance(current, str):
            return current.strip() != ""
        elif isinstance(current, (list, dict)):
            return len(current) > 0
        else:
            return current is not None
    
    def generate_task_breakdown_from_design(self, design: Dict) -> List[Dict]:
        """設計ファイルからタスク分割を生成"""
        tasks = []
        
        # 明示的なタスクを追加
        explicit_tasks = design.get('task_breakdown', {}).get('explicit_tasks', [])
        for task_data in explicit_tasks:
            if self._is_task_complete(task_data):
                tasks.append(task_data)
        
        # 優先度付きコンポーネントからタスクを自動生成
        priority_components = design.get('implementation_plan', {}).get('priority_components', [])
        phases = design.get('implementation_plan', {}).get('phases', [
            {'name': '設計', 'description': 'システム設計'},
            {'name': '実装', 'description': 'コード実装'},
            {'name': 'テスト', 'description': 'テスト実装'},
            {'name': 'デプロイ', 'description': 'デプロイメント'}
        ])
        
        for component in priority_components:
            component_name = component.get('name', 'Unknown Component')
            priority = component.get('priority', 'MEDIUM')
            base_hours = component.get('estimated_hours', 4.0)
            
            for phase in phases:
                phase_name = phase.get('name', 'Unknown Phase')
                phase_hours = base_hours / len(phases)
                
                task = {
                    'title': f"{component_name} - {phase_name}",
                    'description': f"{component_name}の{phase_name}フェーズを実装する",
                    'priority': priority,
                    'estimated_hours': round(phase_hours, 1),
                    'phase': phase_name,
                    'dependencies': [],
                    'technical_requirements': [
                        f"{component_name}の{phase_name}を完了する",
                        "コーディング規約に準拠する",
                        "適切なテストを実装する"
                    ],
                    'acceptance_criteria': [
                        f"{component_name}の{phase_name}が正常に動作する",
                        "エラーハンドリングが適切に実装されている",
                        "ドキュメントが更新されている"
                    ],
                    'implementation_notes': f"{phase.get('description', '')}の詳細実装"
                }
                
                tasks.append(task)
        
        # インターフェースからタスクを生成
        interfaces = design.get('architecture', {}).get('interfaces', [])
        for interface in interfaces:
            interface_name = interface.get('name', 'Unknown Interface')
            
            task = {
                'title': f"{interface_name}インターフェース実装",
                'description': f"{interface_name}との連携機能を実装する",
                'priority': 'HIGH',
                'estimated_hours': 3.0,
                'phase': '実装',
                'dependencies': [],
                'technical_requirements': [
                    f"{interface_name}との通信を実装する",
                    "エラーハンドリングを実装する",
                    "ログ出力を実装する"
                ],
                'acceptance_criteria': [
                    f"{interface_name}との通信が正常に動作する",
                    "エラー時の適切な処理が実装されている",
                    "パフォーマンス要件を満たしている"
                ],
                'implementation_notes': f"{interface.get('description', '')}の実装詳細"
            }
            
            tasks.append(task)
        
        self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, 
                      f"🔧 タスク分割生成完了: {len(tasks)}個のタスク")
        
        return tasks
    
    def _is_task_complete(self, task_data: Dict) -> bool:
        """タスクデータが完全かチェック"""
        required_fields = ['title', 'description', 'priority', 'estimated_hours']
        return all(task_data.get(field) for field in required_fields)
    
    def export_design_summary(self, design: Dict) -> Dict:
        """設計ファイルのサマリーを出力"""
        project_info = design.get('project_info', {})
        tasks = self.generate_task_breakdown_from_design(design)
        
        total_hours = sum(task.get('estimated_hours', 0) for task in tasks)
        priority_counts = {}
        for task in tasks:
            priority = task.get('priority', 'MEDIUM')
            priority_counts[priority] = priority_counts.get(priority, 0) + 1
        
        return {
            'project_name': project_info.get('name', 'Unknown'),
            'description': project_info.get('description', ''),
            'total_tasks': len(tasks),
            'total_estimated_hours': total_hours,
            'priority_distribution': priority_counts,
            'recommended_mode': design.get('execution_config', {}).get('recommended_mode', 'nightly'),
            'completion_estimate': f"{total_hours / 8:.1f} working days" if total_hours > 0 else "N/A"
        }


class DistributedDesignGenerator:
    """分散コーディングエージェント用の設計生成システム"""
    
    def __init__(self, logger: StructuredLogger):
        self.logger = logger
        self.design_manager = DesignFileManager(logger)
    
    def create_agent_design_workspace(self, base_path: str, agent_name: str) -> Path:
        """エージェント用の設計ワークスペースを作成"""
        workspace = Path(base_path) / 'designs' / f'agent_{agent_name}'
        workspace.mkdir(parents=True, exist_ok=True)
        
        # テンプレートをコピー
        template = self.design_manager.load_template()
        template_file = workspace / 'design_template.yaml'
        self.design_manager.save_design_file(template, template_file)
        
        # 使用方法ガイドを作成
        guide_content = f"""# 設計作成ガイド - Agent {agent_name}

## 手順
1. design_template.yaml をコピーして your_design.yaml として保存
2. 各セクションを記入（空文字列や0の項目を埋める）
3. 検証: python -m nocturnal_agent.design.validate_design your_design.yaml
4. 実行: na --design-file your_design.yaml --mode [immediate|nightly]

## 重要なセクション
- project_info: プロジェクト基本情報
- requirements: 機能要件・非機能要件
- architecture: システム構成
- implementation_plan: 実装計画
- task_breakdown: タスク分割設定

## サンプル実行
```bash
# 設計ファイル検証
python -c "from nocturnal_agent.design.design_file_manager import DesignFileManager; 
from nocturnal_agent.log_system.structured_logger import StructuredLogger;
logger = StructuredLogger({{'console_output': True}});
manager = DesignFileManager(logger);
design = manager.load_design_file('your_design.yaml');
result = manager.validate_design_file(design);
print(f'Valid: {{result.is_valid}}, Score: {{result.completeness_score:.1%}}')"
```
"""
        
        guide_file = workspace / 'README.md'
        with open(guide_file, 'w', encoding='utf-8') as f:
            f.write(guide_content)
        
        self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, 
                      f"🏗️ エージェント設計ワークスペース作成: {workspace}")
        
        return workspace
    
    def validate_and_prepare_design(self, design_file: Path) -> Optional[Dict]:
        """設計ファイルを検証して実行準備"""
        design = self.design_manager.load_design_file(design_file)
        if not design:
            return None
        
        validation_result = self.design_manager.validate_design_file(design)
        
        if not validation_result.is_valid:
            self.logger.log(LogLevel.ERROR, LogCategory.SYSTEM, 
                          "❌ 設計ファイル検証失敗:")
            for error in validation_result.errors:
                self.logger.log(LogLevel.ERROR, LogCategory.SYSTEM, f"  - {error}")
            return None
        
        if validation_result.warnings:
            self.logger.log(LogLevel.WARNING, LogCategory.SYSTEM, 
                          "⚠️ 設計ファイル警告:")
            for warning in validation_result.warnings:
                self.logger.log(LogLevel.WARNING, LogCategory.SYSTEM, f"  - {warning}")
        
        # タスク分割を生成
        tasks = self.design_manager.generate_task_breakdown_from_design(design)
        design['generated_tasks'] = tasks
        
        # サマリーを生成
        summary = self.design_manager.export_design_summary(design)
        design['execution_summary'] = summary
        
        self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, 
                      f"✅ 設計ファイル検証完了: {summary['total_tasks']}タスク, "
                      f"{summary['total_estimated_hours']:.1f}時間")
        
        return design