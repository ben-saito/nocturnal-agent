"""
要件から設計ファイル生成システム
解析された要件から各エージェント用の設計ファイルを自動生成する
"""
import yaml
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any
from .requirements_parser import RequirementAnalysis

class DesignFileGenerator:
    """設計ファイル生成器"""
    
    def __init__(self):
        self.base_template_path = Path(__file__).parent.parent.parent.parent / "templates" / "design_template.yaml"

    def generate_design_files(self, analysis: RequirementAnalysis, workspace_path: str, 
                            project_name: str) -> Dict[str, str]:
        """解析結果から各エージェント用の設計ファイルを生成"""
        workspace = Path(workspace_path)
        generated_files = {}
        
        # 各専門エージェント用の設計ファイルを生成
        for agent_name, tasks in analysis.agent_assignments.items():
            if tasks:  # タスクがある場合のみ生成
                design_file_path = self._generate_agent_design_file(
                    agent_name, analysis, tasks, workspace, project_name
                )
                generated_files[agent_name] = str(design_file_path)
        
        # メイン統合設計ファイルを生成
        main_design_path = self._generate_main_design_file(
            analysis, workspace, project_name
        )
        generated_files['main'] = str(main_design_path)
        
        return generated_files

    def _generate_agent_design_file(self, agent_name: str, analysis: RequirementAnalysis,
                                  tasks: List[str], workspace: Path, project_name: str) -> Path:
        """個別エージェント用設計ファイル生成"""
        
        # エージェント別の設定を取得
        agent_config = self._get_agent_specific_config(agent_name, analysis)
        
        # 設計ファイル内容を作成
        design_content = {
            "project_info": {
                "name": f"{project_name} - {agent_config['display_name']}",
                "description": f"{agent_config['display_name']}が担当する{project_name}の開発タスク",
                "version": "1.0.0",
                "agent_type": agent_name,
                "created_at": datetime.now().isoformat(),
                "priority": "HIGH"
            },
            "requirements": {
                "overview": f"{agent_config['focus_area']}に特化した実装",
                "functional_requirements": tasks,
                "non_functional_requirements": analysis.quality_requirements,
                "constraints": agent_config['constraints'],
                "acceptance_criteria": agent_config['acceptance_criteria']
            },
            "architecture": {
                "type": analysis.suggested_architecture,
                "components": agent_config['components'],
                "data_flow": agent_config['data_flow'],
                "integration_points": agent_config['integration_points']
            },
            "technology_stack": agent_config['tech_stack'],
            "implementation_plan": {
                "phases": agent_config['phases'],
                "milestones": agent_config['milestones'],
                "dependencies": agent_config['dependencies'],
                "risk_mitigation": agent_config['risks']
            },
            "task_breakdown": {
                "epics": self._create_epics_for_agent(agent_name, tasks),
                "stories": self._create_stories_for_agent(agent_name, tasks),
                "tasks": self._create_detailed_tasks(agent_name, tasks),
                "estimated_hours": self._estimate_hours(agent_name, tasks)
            },
            "quality_requirements": {
                "testing_strategy": agent_config['testing_strategy'],
                "code_quality": agent_config['code_quality'],
                "performance_targets": agent_config['performance_targets'],
                "security_requirements": agent_config['security_requirements']
            },
            "execution_config": {
                "mode": "immediate",
                "max_parallel_tasks": 2,
                "timeout_per_task": 3600,
                "retry_on_failure": True,
                "notification_settings": {
                    "on_completion": True,
                    "on_failure": True,
                    "on_milestone": True
                }
            },
            "metadata": {
                "generated_from": "natural_language_requirements",
                "complexity": analysis.estimated_complexity,
                "estimated_completion": self._estimate_completion_time(agent_name, len(tasks)),
                "collaboration_notes": f"このファイルは{agent_config['display_name']}用に自動生成されました",
                "review_required": True
            }
        }
        
        # ファイルパスを決定
        agent_workspace = workspace / "team_designs" / "designs" / f"agent_{agent_name.replace('_specialist', '')}"
        agent_workspace.mkdir(parents=True, exist_ok=True)
        
        design_file_path = agent_workspace / f"{agent_name}_design.yaml"
        
        # YAMLファイルとして保存
        with open(design_file_path, 'w', encoding='utf-8') as f:
            yaml.dump(design_content, f, default_flow_style=False, allow_unicode=True, indent=2)
        
        return design_file_path

    def _generate_main_design_file(self, analysis: RequirementAnalysis, 
                                 workspace: Path, project_name: str) -> Path:
        """メイン統合設計ファイル生成"""
        
        main_design_content = {
            "project_info": {
                "name": project_name,
                "description": "自然言語要件から生成されたプロジェクト設計",
                "version": "1.0.0",
                "type": analysis.project_type,
                "workspace_path": str(workspace.absolute()),
                "created_at": datetime.now().isoformat(),
                "priority": "HIGH"
            },
            "requirements": {
                "overview": "自然言語要件から解析された機能要件",
                "functional_requirements": analysis.primary_features,
                "technical_requirements": analysis.technical_requirements,
                "database_requirements": analysis.database_needs,
                "ui_requirements": analysis.ui_requirements,
                "quality_requirements": analysis.quality_requirements,
                "non_functional_requirements": analysis.quality_requirements,
                "constraints": [],
                "acceptance_criteria": ["自然言語要件の完全実装", "各エージェントタスクの完了", "品質基準の達成"]
            },
            "architecture": {
                "type": analysis.suggested_architecture,
                "complexity": analysis.estimated_complexity,
                "components": ["Frontend Layer", "Backend Layer", "Database Layer", "Integration Layer"],
                "data_flow": ["User Request → Frontend → Backend → Database → Response"],
                "integration_points": ["API Endpoints", "Database Connections", "External Services"],
                "agent_distribution": {
                    agent: len(tasks) for agent, tasks in analysis.agent_assignments.items()
                }
            },
            "technology_stack": {
                "frontend": ["React", "TypeScript", "Tailwind CSS"],
                "backend": ["Node.js", "Express", "TypeScript"],
                "database": ["PostgreSQL", "Redis"],
                "tools": ["Docker", "Jest", "ESLint"],
                "deployment": ["Vercel", "Railway", "Docker"]
            },
            "implementation_plan": {
                "phases": [
                    {
                        "name": "設計・アーキテクチャ",
                        "duration": "1-2日",
                        "description": "システム設計とアーキテクチャの決定",
                        "deliverables": ["システム設計書", "API仕様書", "データベース設計"]
                    },
                    {
                        "name": "基盤実装",
                        "duration": "3-5日", 
                        "description": "データベース、バックエンドAPI、フロントエンド基盤の実装",
                        "deliverables": ["データベーススキーマ", "基本API", "UI基盤"]
                    },
                    {
                        "name": "機能実装",
                        "duration": "5-7日",
                        "description": "主要機能の実装と統合",
                        "deliverables": ["各機能の実装", "統合テスト", "E2Eテスト"]
                    },
                    {
                        "name": "テスト・最適化",
                        "duration": "2-3日",
                        "description": "包括的テストとパフォーマンス最適化",
                        "deliverables": ["テストレポート", "最適化完了", "デプロイ準備"]
                    }
                ],
                "milestones": [
                    "データベース設計完了",
                    "API仕様確定",
                    "フロントエンド基盤完成",
                    "主要機能実装完了",
                    "統合テスト完了",
                    "本番デプロイ完了"
                ],
                "dependencies": [
                    "データベース設計 → バックエンド実装",
                    "API仕様確定 → フロントエンド実装",
                    "基盤実装完了 → 機能実装開始"
                ],
                "risk_mitigation": [
                    "技術選定の早期検証",
                    "段階的実装とテスト",
                    "定期的な進捗確認"
                ]
            },
            "task_breakdown": {
                "epics": [
                    {
                        "id": "epic-001",
                        "title": "システム基盤構築",
                        "description": "データベース、API、フロントエンド基盤の構築",
                        "priority": "HIGH",
                        "estimated_story_points": 20
                    },
                    {
                        "id": "epic-002", 
                        "title": "主要機能実装",
                        "description": "ニュース取得、データ保存、UI表示機能の実装",
                        "priority": "HIGH",
                        "estimated_story_points": 30
                    },
                    {
                        "id": "epic-003",
                        "title": "AI提案機能",
                        "description": "AI組み合わせ提案機能の実装",
                        "priority": "MEDIUM", 
                        "estimated_story_points": 25
                    }
                ],
                "stories": [],
                "tasks": [],
                "estimated_hours": sum(
                    self._estimate_hours(agent, tasks) 
                    for agent, tasks in analysis.agent_assignments.items()
                )
            },
            "quality_requirements": {
                "testing_strategy": ["単体テスト", "統合テスト", "E2Eテスト"],
                "code_quality": ["TypeScript", "ESLint", "Prettier"],
                "performance_targets": ["初期表示 < 3秒", "API応答 < 500ms"],
                "security_requirements": ["認証・認可", "データ暗号化", "HTTPS通信"],
                "documentation": ["API仕様書", "ユーザーガイド", "開発者向けドキュメント"]
            },
            "agent_coordination": {
                "execution_order": self._determine_execution_order(analysis),
                "dependencies": self._determine_agent_dependencies(analysis),
                "communication_plan": self._create_communication_plan(analysis)
            },
            "execution_config": {
                "mode": "immediate",
                "coordination_required": True,
                "parallel_execution": False,
                "milestone_tracking": True,
                "max_parallel_tasks": 2,
                "timeout_per_task": 3600,
                "retry_on_failure": True,
                "notification_settings": {
                    "on_completion": True,
                    "on_failure": True,
                    "on_milestone": True
                }
            },
            "metadata": {
                "generated_from": "natural_language_requirements",
                "agent_files_created": list(analysis.agent_assignments.keys()),
                "total_estimated_hours": sum(
                    self._estimate_hours(agent, tasks) 
                    for agent, tasks in analysis.agent_assignments.items()
                ),
                "complexity": analysis.estimated_complexity,
                "estimated_completion": f"{sum(self._estimate_hours(agent, tasks) for agent, tasks in analysis.agent_assignments.items()) // 8}日間",
                "collaboration_notes": "自動生成された設計ファイル - 各エージェントが並行作業可能",
                "review_required": False
            }
        }
        
        main_design_path = workspace / "team_designs" / "main_design.yaml"
        main_design_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(main_design_path, 'w', encoding='utf-8') as f:
            yaml.dump(main_design_content, f, default_flow_style=False, allow_unicode=True, indent=2)
        
        return main_design_path

    def _get_agent_specific_config(self, agent_name: str, analysis: RequirementAnalysis) -> Dict[str, Any]:
        """エージェント別の詳細設定を取得"""
        
        configs = {
            "frontend_specialist": {
                "display_name": "フロントエンド専門家",
                "focus_area": "ユーザーインターフェース開発",
                "constraints": ["ブラウザ互換性", "レスポンシブ対応", "アクセシビリティ"],
                "acceptance_criteria": ["UI/UXガイドライン準拠", "クロスブラウザテスト完了"],
                "components": ["UI Components", "State Management", "Routing"],
                "data_flow": ["User Input → State → UI Update"],
                "integration_points": ["Backend API", "Authentication Service"],
                "tech_stack": {
                    "frontend": ["React", "TypeScript", "Tailwind CSS"],
                    "tools": ["Vite", "ESLint", "Prettier"],
                    "testing": ["Jest", "React Testing Library", "Cypress"]
                },
                "phases": [
                    {"name": "設計・プロトタイプ", "duration": "1-2日"},
                    {"name": "コンポーネント実装", "duration": "3-5日"},
                    {"name": "統合・テスト", "duration": "1-2日"}
                ],
                "milestones": ["UIコンポーネント完成", "画面遷移実装完了", "テスト完了"],
                "dependencies": ["API仕様確定", "デザインガイドライン"],
                "risks": ["デザイン変更", "ブラウザ互換性問題"],
                "testing_strategy": ["単体テスト", "UIテスト", "E2Eテスト"],
                "code_quality": ["TypeScript strict mode", "ESLint rules"],
                "performance_targets": ["First Paint < 1s", "TTI < 3s"],
                "security_requirements": ["XSS対策", "CSRF対策"]
            },
            "backend_specialist": {
                "display_name": "バックエンド専門家",
                "focus_area": "サーバーサイド開発・API設計",
                "constraints": ["スケーラビリティ", "セキュリティ", "パフォーマンス"],
                "acceptance_criteria": ["API仕様書作成", "セキュリティテスト完了"],
                "components": ["API Endpoints", "Business Logic", "Data Access Layer"],
                "data_flow": ["Request → Validation → Business Logic → Database → Response"],
                "integration_points": ["Database", "External APIs", "Authentication"],
                "tech_stack": {
                    "backend": ["Node.js", "Express", "TypeScript"],
                    "database": ["PostgreSQL", "Redis"],
                    "tools": ["Docker", "Jest", "Swagger"]
                },
                "phases": [
                    {"name": "API設計", "duration": "1-2日"},
                    {"name": "実装", "duration": "4-6日"},
                    {"name": "テスト・最適化", "duration": "2-3日"}
                ],
                "milestones": ["API設計完了", "主要機能実装完了", "パフォーマンステスト完了"],
                "dependencies": ["データベース設計", "認証システム"],
                "risks": ["パフォーマンス問題", "セキュリティ脆弱性"],
                "testing_strategy": ["単体テスト", "統合テスト", "APIテスト"],
                "code_quality": ["TypeScript", "ESLint", "SonarQube"],
                "performance_targets": ["Response Time < 200ms", "Throughput > 1000 req/s"],
                "security_requirements": ["認証・認可", "入力検証", "SQLインジェクション対策"]
            },
            "database_specialist": {
                "display_name": "データベース専門家",
                "focus_area": "データ設計・最適化",
                "constraints": ["データ整合性", "パフォーマンス", "バックアップ戦略"],
                "acceptance_criteria": ["ER図作成", "パフォーマンスチューニング完了"],
                "components": ["Database Schema", "Indexes", "Stored Procedures"],
                "data_flow": ["Application → ORM → Database"],
                "integration_points": ["Backend API", "Analytics Tools"],
                "tech_stack": {
                    "database": ["PostgreSQL", "Redis"],
                    "tools": ["pgAdmin", "Redis CLI", "Database Migration Tools"],
                    "monitoring": ["pg_stat_statements", "Redis Monitor"]
                },
                "phases": [
                    {"name": "データ設計", "duration": "1-2日"},
                    {"name": "スキーマ実装", "duration": "2-3日"},
                    {"name": "最適化・テスト", "duration": "1-2日"}
                ],
                "milestones": ["ER図完成", "マイグレーション完了", "パフォーマンステスト完了"],
                "dependencies": ["要件定義", "データ仕様"],
                "risks": ["データ損失", "パフォーマンス劣化"],
                "testing_strategy": ["データ整合性テスト", "パフォーマンステスト"],
                "code_quality": ["正規化", "インデックス最適化"],
                "performance_targets": ["Query Time < 100ms", "Concurrent Users > 100"],
                "security_requirements": ["アクセス制御", "データ暗号化"]
            },
            "qa_specialist": {
                "display_name": "品質保証専門家",
                "focus_area": "テスト設計・品質保証",
                "constraints": ["カバレッジ率", "テスト実行時間", "品質基準"],
                "acceptance_criteria": ["テストカバレッジ85%以上", "全テストケース実行完了"],
                "components": ["Test Suites", "Test Data", "Test Automation"],
                "data_flow": ["Requirements → Test Cases → Execution → Reports"],
                "integration_points": ["CI/CD Pipeline", "Monitoring Tools"],
                "tech_stack": {
                    "testing": ["Jest", "Cypress", "Playwright"],
                    "tools": ["GitHub Actions", "SonarQube", "Allure"],
                    "monitoring": ["Sentry", "DataDog"]
                },
                "phases": [
                    {"name": "テスト計画", "duration": "1日"},
                    {"name": "テストケース作成", "duration": "2-3日"},
                    {"name": "実行・レポート", "duration": "1-2日"}
                ],
                "milestones": ["テスト計画完成", "自動テスト実装完了", "品質レポート完成"],
                "dependencies": ["実装完了", "テスト環境"],
                "risks": ["テスト漏れ", "環境問題"],
                "testing_strategy": ["単体テスト", "統合テスト", "E2Eテスト", "負荷テスト"],
                "code_quality": ["テストカバレッジ", "テストコード品質"],
                "performance_targets": ["Test Suite Runtime < 10min"],
                "security_requirements": ["セキュリティテスト", "脆弱性スキャン"]
            }
        }
        
        return configs.get(agent_name, configs["frontend_specialist"])

    def _create_epics_for_agent(self, agent_name: str, tasks: List[str]) -> List[Dict[str, Any]]:
        """エージェント用エピック作成"""
        agent_focus = {
            "frontend_specialist": "ユーザーインターフェース開発",
            "backend_specialist": "サーバーサイド機能開発",
            "database_specialist": "データ基盤構築",
            "qa_specialist": "品質保証・テスト"
        }
        
        return [{
            "id": f"epic-{agent_name}-001",
            "title": agent_focus.get(agent_name, "機能開発"),
            "description": f"{agent_name}が担当する主要機能の実装",
            "tasks": tasks,
            "priority": "HIGH",
            "estimated_story_points": len(tasks) * 2
        }]

    def _create_stories_for_agent(self, agent_name: str, tasks: List[str]) -> List[Dict[str, Any]]:
        """エージェント用ストーリー作成"""
        stories = []
        for i, task in enumerate(tasks, 1):
            stories.append({
                "id": f"story-{agent_name}-{i:03d}",
                "title": task,
                "description": f"{task}の実装を行う",
                "acceptance_criteria": [f"{task}が正常に動作する", "テストが通る", "コードレビュー完了"],
                "priority": "HIGH" if i <= 3 else "MEDIUM",
                "estimated_hours": 4 if "実装" in task else 2
            })
        return stories

    def _create_detailed_tasks(self, agent_name: str, tasks: List[str]) -> List[Dict[str, Any]]:
        """詳細タスク作成"""
        detailed_tasks = []
        for i, task in enumerate(tasks, 1):
            detailed_tasks.extend([
                {
                    "id": f"task-{agent_name}-{i:03d}-design",
                    "title": f"{task} - 設計",
                    "description": f"{task}の詳細設計を行う",
                    "type": "design",
                    "estimated_hours": 1,
                    "priority": "HIGH"
                },
                {
                    "id": f"task-{agent_name}-{i:03d}-implement",
                    "title": f"{task} - 実装",
                    "description": f"{task}の実装を行う",
                    "type": "implementation",
                    "estimated_hours": 3,
                    "priority": "HIGH",
                    "dependencies": [f"task-{agent_name}-{i:03d}-design"]
                },
                {
                    "id": f"task-{agent_name}-{i:03d}-test",
                    "title": f"{task} - テスト",
                    "description": f"{task}のテストを作成・実行する",
                    "type": "testing",
                    "estimated_hours": 1,
                    "priority": "MEDIUM",
                    "dependencies": [f"task-{agent_name}-{i:03d}-implement"]
                }
            ])
        return detailed_tasks

    def _estimate_hours(self, agent_name: str, tasks: List[str]) -> int:
        """作業時間見積もり"""
        base_hours_per_task = {
            "frontend_specialist": 6,
            "backend_specialist": 8,
            "database_specialist": 4,
            "qa_specialist": 3
        }
        return len(tasks) * base_hours_per_task.get(agent_name, 5)

    def _estimate_completion_time(self, agent_name: str, task_count: int) -> str:
        """完了時間見積もり"""
        hours = self._estimate_hours(agent_name, ['dummy'] * task_count)
        days = max(1, hours // 8)
        return f"{days}日間"

    def _determine_execution_order(self, analysis: RequirementAnalysis) -> List[str]:
        """実行順序決定"""
        if analysis.project_type == 'fullstack':
            return ['database_specialist', 'backend_specialist', 'frontend_specialist', 'qa_specialist']
        elif analysis.project_type == 'frontend':
            return ['frontend_specialist', 'qa_specialist']
        elif analysis.project_type == 'backend':
            return ['database_specialist', 'backend_specialist', 'qa_specialist']
        else:
            return ['database_specialist', 'backend_specialist', 'frontend_specialist', 'qa_specialist']

    def _determine_agent_dependencies(self, analysis: RequirementAnalysis) -> Dict[str, List[str]]:
        """エージェント間依存関係決定"""
        return {
            'frontend_specialist': ['backend_specialist'],
            'backend_specialist': ['database_specialist'],
            'qa_specialist': ['frontend_specialist', 'backend_specialist'],
            'database_specialist': []
        }

    def _create_communication_plan(self, analysis: RequirementAnalysis) -> Dict[str, Any]:
        """コミュニケーション計画作成"""
        return {
            "milestone_meetings": ["設計完了時", "実装完了時", "テスト完了時"],
            "daily_standup": True,
            "progress_sharing": "リアルタイム",
            "issue_escalation": "1時間以内",
            "documentation_updates": "各フェーズ完了時"
        }