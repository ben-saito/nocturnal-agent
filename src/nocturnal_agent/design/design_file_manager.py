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
        
        # 1. メイン設計ファイルの明示的なタスクを追加
        explicit_tasks = design.get('task_breakdown', {}).get('tasks', [])
        for task_data in explicit_tasks:
            if self._is_task_complete(task_data):
                tasks.append(task_data)
        
        # 2. 各エージェントの設計ファイルからタスクを収集
        workspace_path = design.get('project_info', {}).get('workspace_path', '')
        if workspace_path:
            workspace_path = Path(workspace_path)
            
            # team_designs配下の各エージェント設計ファイルを探索
            agent_design_dirs = [
                workspace_path / "team_designs" / "designs" / "agent_frontend",
                workspace_path / "team_designs" / "designs" / "agent_backend", 
                workspace_path / "team_designs" / "designs" / "agent_database",
                workspace_path / "team_designs" / "designs" / "agent_qa"
            ]
            
            for agent_dir in agent_design_dirs:
                if agent_dir.exists():
                    # 各エージェントディレクトリ内の設計ファイルを探す
                    for design_file in agent_dir.glob("*_design.yaml"):
                        try:
                            agent_design = self.load_design_file(design_file)
                            if agent_design:
                                agent_tasks = agent_design.get('task_breakdown', {}).get('tasks', [])
                                for task_data in agent_tasks:
                                    if self._is_task_complete(task_data):
                                        # エージェント情報をタスクに追加
                                        task_data['agent_type'] = agent_design.get('project_info', {}).get('agent_type', 'unknown')
                                        task_data['source_file'] = str(design_file)
                                        tasks.append(task_data)
                        except Exception as e:
                            self.logger.log(LogLevel.WARNING, LogCategory.SYSTEM, 
                                          f"エージェント設計ファイル読み込みエラー {design_file}: {e}")
        
        # 3. 優先度付きコンポーネントからタスクを自動生成（フォールバック）
        if not tasks:
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
            
            # 4. インターフェースからタスクを生成（フォールバック）
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
        
        # 汎用テンプレートをコピー
        template = self.design_manager.load_template()
        template_file = workspace / 'design_template.yaml'
        self.design_manager.save_design_file(template, template_file)
        
        # 専門分野特化のデフォルト設計ファイルを作成
        specialist_design = self._create_specialist_design(agent_name, str(workspace.parent.parent))
        specialist_file = workspace / f'{agent_name}_default_design.yaml'
        self.design_manager.save_design_file(specialist_design, specialist_file)
        
        # 使用方法ガイドを作成
        guide_content = f"""# 設計作成ガイド - Agent {agent_name}

## 🚀 すぐに使える設計ファイル

**`{agent_name}_default_design.yaml`** - {agent_name.replace('_', ' ').title()} 向けのデフォルト設計ファイル
- そのまま実行可能な設定済みファイル
- 必要に応じてカスタマイズ可能

## 📋 手順

### Option 1: デフォルト設計を使用（推奨）
```bash
# デフォルト設計をそのまま実行
nocturnal execute --design-file {agent_name}_default_design.yaml --mode immediate

# または実行前に内容確認
nocturnal design validate {agent_name}_default_design.yaml --detailed
nocturnal design summary {agent_name}_default_design.yaml
```

### Option 2: カスタム設計を作成
```bash
# デフォルト設計をベースにカスタマイズ
cp {agent_name}_default_design.yaml my_custom_design.yaml
# Edit my_custom_design.yaml...

# 検証・実行
nocturnal design validate my_custom_design.yaml --detailed
nocturnal execute --design-file my_custom_design.yaml --mode immediate
```

### Option 3: 汎用テンプレートから作成
```bash
# 空のテンプレートから作成
cp design_template.yaml my_design.yaml
# Fill in all sections...
```

## 🎯 専門分野: {agent_name.replace('_', ' ').title()}

デフォルト設計ファイルには以下が含まれています:
- 専門分野に特化した要件定義
- 推奨技術スタック
- 実装計画とタスク分割
- ベストプラクティス

## 🔧 カスタマイズポイント

- `project_info.name`: プロジェクト名
- `project_info.workspace_path`: 作業ディレクトリパス  
- `requirements.functional`: 具体的な機能要件
- `technology_stack`: 使用技術の選択
- `implementation_plan.priority_components`: 優先度調整

## 📊 実行例
```bash
# 設計ファイル検証
nocturnal design validate {agent_name}_default_design.yaml --detailed

# 実行計画プレビュー
nocturnal execute --design-file {agent_name}_default_design.yaml --dry-run

# 即時実行
nocturnal execute --design-file {agent_name}_default_design.yaml --mode immediate --max-tasks 3
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
    
    def _create_specialist_design(self, agent_name: str, workspace_path: str) -> Dict:
        """専門分野特化のデフォルト設計ファイルを作成"""
        base_template = self.design_manager.load_template()
        
        # 専門分野別の設定を取得
        specialist_configs = {
            'frontend_specialist': self._get_frontend_specialist_config(),
            'backend_specialist': self._get_backend_specialist_config(),
            'database_specialist': self._get_database_specialist_config(),
            'qa_specialist': self._get_qa_specialist_config()
        }
        
        config = specialist_configs.get(agent_name, {})
        
        # ベーステンプレートを専門分野向けにカスタマイズ
        specialist_design = base_template.copy()
        
        # プロジェクト基本情報
        specialist_design['project_info'].update({
            'name': config.get('default_project_name', f"{agent_name.replace('_', ' ').title()} System"),
            'description': config.get('description', f"A system designed by {agent_name.replace('_', ' ').title()}"),
            'workspace_path': workspace_path,
            'author': f"Agent {agent_name.replace('_', ' ').title()}",
            'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        
        # 機能要件
        specialist_design['requirements']['functional'] = config.get('functional_requirements', [])
        
        # 非機能要件
        if 'non_functional' in config:
            specialist_design['requirements']['non_functional'].update(config['non_functional'])
        
        # アーキテクチャ
        if 'architecture' in config:
            specialist_design['architecture'].update(config['architecture'])
        
        # 技術スタック
        if 'technology_stack' in config:
            specialist_design['technology_stack'].update(config['technology_stack'])
        
        # 実装計画
        if 'implementation_plan' in config:
            specialist_design['implementation_plan'].update(config['implementation_plan'])
        
        # 実行設定
        specialist_design['execution_config'].update({
            'recommended_mode': config.get('recommended_mode', 'immediate'),
            'batch_size': config.get('batch_size', 3)
        })
        
        # メタデータ更新
        specialist_design['metadata'].update({
            'generated_by': f"Agent {agent_name}",
            'generation_timestamp': datetime.now().isoformat(),
            'specialist_type': agent_name
        })
        
        return specialist_design
    
    def _get_frontend_specialist_config(self) -> Dict:
        """Frontend Specialist 向けの設定"""
        return {
            'default_project_name': "Modern Web UI System",
            'description': "Responsive and interactive web user interface with modern frameworks",
            'functional_requirements': [
                {
                    'description': "User authentication and authorization system",
                    'priority': "HIGH",
                    'acceptance_criteria': [
                        "Users can register with email/password",
                        "Secure login with JWT tokens",
                        "Role-based access control",
                        "Password reset functionality"
                    ]
                },
                {
                    'description': "Responsive dashboard with real-time data visualization",
                    'priority': "HIGH",
                    'acceptance_criteria': [
                        "Mobile-first responsive design",
                        "Real-time charts and graphs",
                        "Dark/light theme support",
                        "Customizable dashboard layout"
                    ]
                },
                {
                    'description': "Component library and design system",
                    'priority': "MEDIUM",
                    'acceptance_criteria': [
                        "Reusable UI component library",
                        "Consistent design tokens",
                        "Accessibility compliance (WCAG 2.1)",
                        "Interactive component documentation"
                    ]
                }
            ],
            'non_functional': {
                'performance': {
                    'response_time': "< 1秒",
                    'first_contentful_paint': "< 1.5秒",
                    'lighthouse_score': "> 90"
                },
                'maintainability': {
                    'component_coverage': "> 85%",
                    'documentation': "Storybook必須"
                }
            },
            'architecture': {
                'pattern': "Component-based SPA",
                'components': [
                    {
                        'name': "Authentication Module",
                        'type': "Frontend",
                        'description': "User login, registration, and profile management",
                        'technologies': ["React", "TypeScript", "React Router", "Formik"]
                    },
                    {
                        'name': "Dashboard Module",
                        'type': "Frontend", 
                        'description': "Main application interface with data visualization",
                        'technologies': ["React", "Chart.js", "Material-UI", "React Query"]
                    },
                    {
                        'name': "Component Library",
                        'type': "Frontend",
                        'description': "Reusable UI components and design system",
                        'technologies': ["React", "Styled Components", "Storybook"]
                    }
                ]
            },
            'technology_stack': {
                'frontend': {
                    'language': "TypeScript",
                    'framework': "React 18",
                    'state_management': "Zustand",
                    'styling': "Styled Components",
                    'ui_library': "Material-UI",
                    'routing': "React Router",
                    'data_fetching': "React Query",
                    'charts': "Chart.js",
                    'forms': "React Hook Form"
                },
                'devops': {
                    'bundler': "Vite",
                    'testing': "Jest + React Testing Library",
                    'e2e_testing': "Playwright",
                    'deployment': "Vercel/Netlify"
                }
            },
            'implementation_plan': {
                'phases': [
                    {
                        'name': "Setup & Foundation",
                        'description': "プロジェクト初期設定とベースコンポーネント",
                        'duration': "1-2 days",
                        'deliverables': ["プロジェクト構成", "基本コンポーネント", "ルーティング設定"]
                    },
                    {
                        'name': "Authentication System",
                        'description': "ユーザー認証システムの実装",
                        'duration': "2-3 days", 
                        'deliverables': ["Login/Register forms", "JWT handling", "Protected routes"]
                    },
                    {
                        'name': "Dashboard & Visualization",
                        'description': "メインダッシュボードとデータ可視化",
                        'duration': "3-4 days",
                        'deliverables': ["Dashboard layout", "Charts integration", "Responsive design"]
                    }
                ],
                'priority_components': [
                    {
                        'name': "Authentication Module",
                        'priority': "HIGH",
                        'estimated_hours': 12,
                        'complexity': "MEDIUM"
                    },
                    {
                        'name': "Dashboard Module",
                        'priority': "HIGH", 
                        'estimated_hours': 16,
                        'complexity': "HIGH"
                    },
                    {
                        'name': "Component Library",
                        'priority': "MEDIUM",
                        'estimated_hours': 8,
                        'complexity': "MEDIUM"
                    }
                ]
            },
            'recommended_mode': 'immediate',
            'batch_size': 2
        }
    
    def _get_backend_specialist_config(self) -> Dict:
        """Backend Specialist 向けの設定"""
        return {
            'default_project_name': "Scalable API Backend System",
            'description': "RESTful API backend with microservices architecture and robust data management",
            'functional_requirements': [
                {
                    'description': "RESTful API with comprehensive endpoints",
                    'priority': "HIGH",
                    'acceptance_criteria': [
                        "CRUD operations for all entities",
                        "API versioning support",
                        "Pagination and filtering",
                        "OpenAPI/Swagger documentation"
                    ]
                },
                {
                    'description': "Authentication and authorization system",
                    'priority': "HIGH", 
                    'acceptance_criteria': [
                        "JWT-based authentication",
                        "Role-based access control (RBAC)",
                        "OAuth2 integration",
                        "API rate limiting"
                    ]
                },
                {
                    'description': "Data processing and business logic",
                    'priority': "HIGH",
                    'acceptance_criteria': [
                        "Efficient data processing pipelines",
                        "Business rule validation",
                        "Background job processing",
                        "Event-driven architecture"
                    ]
                }
            ],
            'architecture': {
                'pattern': "Layered Architecture with Microservices",
                'components': [
                    {
                        'name': "API Gateway",
                        'type': "Backend",
                        'description': "Request routing and API management",
                        'technologies': ["FastAPI", "Nginx", "Redis"]
                    },
                    {
                        'name': "Authentication Service",
                        'type': "Backend",
                        'description': "User authentication and authorization",
                        'technologies': ["FastAPI", "JWT", "OAuth2"]
                    },
                    {
                        'name': "Business Logic Service",
                        'type': "Backend",
                        'description': "Core business operations and data processing",
                        'technologies': ["FastAPI", "SQLAlchemy", "Celery"]
                    }
                ]
            },
            'technology_stack': {
                'backend': {
                    'language': "Python",
                    'framework': "FastAPI",
                    'database': "PostgreSQL", 
                    'orm': "SQLAlchemy",
                    'cache': "Redis",
                    'queue': "Celery",
                    'validation': "Pydantic"
                },
                'devops': {
                    'containerization': "Docker",
                    'orchestration': "Docker Compose",
                    'monitoring': "Prometheus + Grafana",
                    'deployment': "AWS/GCP"
                }
            },
            'implementation_plan': {
                'priority_components': [
                    {
                        'name': "API Gateway",
                        'priority': "HIGH",
                        'estimated_hours': 8,
                        'complexity': "MEDIUM"
                    },
                    {
                        'name': "Authentication Service", 
                        'priority': "HIGH",
                        'estimated_hours': 12,
                        'complexity': "HIGH"
                    },
                    {
                        'name': "Business Logic Service",
                        'priority': "HIGH",
                        'estimated_hours': 20,
                        'complexity': "HIGH"
                    }
                ]
            },
            'recommended_mode': 'immediate',
            'batch_size': 3
        }
    
    def _get_database_specialist_config(self) -> Dict:
        """Database Specialist 向けの設定"""
        return {
            'default_project_name': "Robust Data Management System", 
            'description': "Scalable database architecture with data modeling, optimization, and backup strategies",
            'functional_requirements': [
                {
                    'description': "Database schema design and optimization",
                    'priority': "HIGH",
                    'acceptance_criteria': [
                        "Normalized database schema",
                        "Optimized indexes and queries",
                        "Data integrity constraints",
                        "Migration scripts and versioning"
                    ]
                },
                {
                    'description': "Data backup and recovery system",
                    'priority': "HIGH",
                    'acceptance_criteria': [
                        "Automated daily backups",
                        "Point-in-time recovery",
                        "Disaster recovery procedures",
                        "Backup validation and testing"
                    ]
                },
                {
                    'description': "Performance monitoring and optimization",
                    'priority': "MEDIUM", 
                    'acceptance_criteria': [
                        "Query performance monitoring",
                        "Database metrics dashboard",
                        "Slow query identification",
                        "Resource usage optimization"
                    ]
                }
            ],
            'architecture': {
                'pattern': "Multi-tier Database Architecture",
                'components': [
                    {
                        'name': "Primary Database",
                        'type': "Database",
                        'description': "Main transactional database",
                        'technologies': ["PostgreSQL", "Connection Pooling"]
                    },
                    {
                        'name': "Read Replicas",
                        'type': "Database",
                        'description': "Read-only replicas for scaling",
                        'technologies': ["PostgreSQL Replicas", "Load Balancer"]
                    },
                    {
                        'name': "Data Warehouse",
                        'type': "Database", 
                        'description': "Analytics and reporting database",
                        'technologies': ["PostgreSQL", "ClickHouse"]
                    }
                ]
            },
            'technology_stack': {
                'backend': {
                    'database': "PostgreSQL",
                    'migration_tool': "Alembic",
                    'connection_pool': "PgBouncer",
                    'monitoring': "pg_stat_monitor"
                },
                'devops': {
                    'backup': "pg_dump + AWS S3",
                    'monitoring': "Prometheus + Grafana",
                    'deployment': "Docker + Kubernetes"
                }
            },
            'implementation_plan': {
                'priority_components': [
                    {
                        'name': "Database Schema",
                        'priority': "HIGH",
                        'estimated_hours': 16,
                        'complexity': "HIGH"
                    },
                    {
                        'name': "Backup System",
                        'priority': "HIGH", 
                        'estimated_hours': 8,
                        'complexity': "MEDIUM"
                    },
                    {
                        'name': "Monitoring Setup",
                        'priority': "MEDIUM",
                        'estimated_hours': 6,
                        'complexity': "MEDIUM"
                    }
                ]
            },
            'recommended_mode': 'nightly',
            'batch_size': 2
        }
    
    def _get_qa_specialist_config(self) -> Dict:
        """QA Specialist 向けの設定"""
        return {
            'default_project_name': "Comprehensive Quality Assurance System",
            'description': "Multi-layered testing strategy with automated testing, CI/CD integration, and quality metrics",
            'functional_requirements': [
                {
                    'description': "Automated testing suite",
                    'priority': "HIGH",
                    'acceptance_criteria': [
                        "Unit test coverage > 90%",
                        "Integration test coverage > 80%", 
                        "End-to-end test scenarios",
                        "Performance test benchmarks"
                    ]
                },
                {
                    'description': "CI/CD quality gates",
                    'priority': "HIGH",
                    'acceptance_criteria': [
                        "Automated test execution on commits",
                        "Quality gate enforcement",
                        "Code quality metrics",
                        "Security vulnerability scanning"
                    ]
                },
                {
                    'description': "Test reporting and analytics",
                    'priority': "MEDIUM",
                    'acceptance_criteria': [
                        "Test execution reports",
                        "Coverage trend analysis",
                        "Defect tracking integration",
                        "Quality metrics dashboard"
                    ]
                }
            ],
            'architecture': {
                'pattern': "Test Pyramid Architecture",
                'components': [
                    {
                        'name': "Unit Test Suite",
                        'type': "Testing",
                        'description': "Component and function level testing",
                        'technologies': ["Jest", "pytest", "JUnit"]
                    },
                    {
                        'name': "Integration Test Suite", 
                        'type': "Testing",
                        'description': "API and service integration testing",
                        'technologies': ["Postman", "pytest", "TestContainers"]
                    },
                    {
                        'name': "E2E Test Suite",
                        'type': "Testing",
                        'description': "Full user journey testing",
                        'technologies': ["Playwright", "Cypress", "Selenium"]
                    }
                ]
            },
            'technology_stack': {
                'frontend': {
                    'testing': "Jest + React Testing Library",
                    'e2e': "Playwright"
                },
                'backend': {
                    'testing': "pytest",
                    'api_testing': "FastAPI TestClient"
                },
                'devops': {
                    'ci_cd': "GitHub Actions",
                    'reporting': "Allure Reports",
                    'coverage': "Codecov"
                }
            },
            'implementation_plan': {
                'priority_components': [
                    {
                        'name': "Unit Test Framework",
                        'priority': "HIGH",
                        'estimated_hours': 12,
                        'complexity': "MEDIUM"
                    },
                    {
                        'name': "Integration Test Suite",
                        'priority': "HIGH",
                        'estimated_hours': 16,
                        'complexity': "HIGH"
                    },
                    {
                        'name': "CI/CD Pipeline",
                        'priority': "HIGH",
                        'estimated_hours': 10,
                        'complexity': "MEDIUM"
                    }
                ]
            },
            'recommended_mode': 'nightly',
            'batch_size': 2
        }