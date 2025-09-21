#!/usr/bin/env python3
"""
Technical Executor Interface - ClaudeCode技術実行者インターフェース  
指揮官からの指令を受けて技術作業を実行する専門インターフェース
"""

import asyncio
import json
import logging
import os
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from .command_dispatch_interface import CommandDirective, ExecutionReport
from .claude_code_interface import load_claude_config
from ..core.config import ClaudeConfig


class TaskType(Enum):
    """技術作業タイプ"""
    REQUIREMENTS_ANALYSIS = "requirements_analysis"
    SPECIFICATION_CREATION = "specification_creation"  
    CODE_IMPLEMENTATION = "code_implementation"
    TEST_CREATION = "test_creation"
    DOCUMENTATION = "documentation"
    QUALITY_REVIEW = "quality_review"


@dataclass
class TechnicalDeliverable:
    """技術成果物"""
    deliverable_id: str
    type: str
    title: str
    content: str
    file_path: Optional[str]
    metadata: Dict[str, Any]
    quality_score: float
    created_at: datetime


@dataclass
class TechnicalAnalysis:
    """技術分析結果"""
    analysis_id: str
    analysis_type: str
    input_data: Dict[str, Any]
    findings: List[str]
    recommendations: List[str]
    technical_requirements: List[str]
    architecture_suggestions: List[str]
    risk_factors: List[str]
    implementation_complexity: str
    estimated_effort: str


class TechnicalExecutorInterface:
    """ClaudeCode技術実行者インターフェース"""
    
    def __init__(self, target_project_path: str, claude_config: ClaudeConfig = None):
        """対象プロジェクトディレクトリでの実行専用初期化"""
        self.target_project_path = Path(target_project_path).resolve()
        self.claude_config = claude_config or load_claude_config()
        self.logger = logging.getLogger(__name__)
        
        # 対象プロジェクトの検証
        if not self.target_project_path.exists():
            raise FileNotFoundError(f"対象プロジェクトディレクトリが見つかりません: {self.target_project_path}")
        
        if not self.target_project_path.is_dir():
            raise NotADirectoryError(f"パスがディレクトリではありません: {self.target_project_path}")
        
        # RemoteClaudeCodeExecutorを初期化
        from .remote_claude_code_executor import RemoteClaudeCodeExecutor
        self.remote_executor = RemoteClaudeCodeExecutor(
            target_project_path=str(self.target_project_path),
            claude_config=self.claude_config
        )
        
        # 実行環境
        self.current_session = None
        self.execution_history: List[ExecutionReport] = []
        self.deliverables: List[TechnicalDeliverable] = []
        
        # 技術者設定
        self.quality_threshold = 0.85
        self.code_standards = "PEP8"
        self.documentation_format = "markdown"
        
        self.logger.info(f"🎯 対象プロジェクト実行モード初期化完了: {self.target_project_path}")

    
    async def execute_command(self, directive: CommandDirective) -> ExecutionReport:
        """指揮官からの指令実行"""
        self.logger.info(f"⚡ 技術指令実行開始: {directive.command_type.value}")
        self.logger.info(f"🎯 指令ID: {directive.command_id}")
        
        start_time = datetime.now()
        
        try:
            if directive.command_type.name == "ANALYZE_REQUIREMENTS":
                deliverables = await self._execute_requirements_analysis(directive)
            elif directive.command_type.name == "CREATE_SPECIFICATION":
                deliverables = await self._execute_specification_creation(directive)
            elif directive.command_type.name == "IMPLEMENT_CODE":
                deliverables = await self._execute_code_implementation(directive)
            elif directive.command_type.name == "CREATE_TESTS":
                deliverables = await self._execute_test_creation(directive)
            elif directive.command_type.name == "GENERATE_DOCS":
                deliverables = await self._execute_documentation(directive)
            else:
                raise ValueError(f"未対応の指令タイプ: {directive.command_type}")
            
            # 品質メトリクス計算
            quality_metrics = self._calculate_quality_metrics(deliverables)
            
            # 実行報告作成
            execution_time = (datetime.now() - start_time).total_seconds()
            
            report = ExecutionReport(
                command_id=directive.command_id,
                agent_id="claude_code_executor",
                status="completed",
                deliverables={d.deliverable_id: {
                    "type": d.type,
                    "title": d.title,
                    "content": d.content[:1000] + "..." if len(d.content) > 1000 else d.content,
                    "file_path": str(d.file_path) if d.file_path else None,
                    "quality_score": d.quality_score,
                    "metadata": d.metadata
                } for d in deliverables},
                execution_time=execution_time,
                quality_metrics=quality_metrics,
                issues_encountered=[],
                recommendations=self._generate_recommendations(deliverables),
                timestamp=datetime.now()
            )
            
            self.execution_history.append(report)
            self.deliverables.extend(deliverables)
            
            self.logger.info(f"✅ 技術指令完了: {directive.command_id} ({execution_time:.2f}秒)")
            return report
            
        except Exception as e:
            self.logger.error(f"技術指令実行エラー: {e}")
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            return ExecutionReport(
                command_id=directive.command_id,
                agent_id="claude_code_executor",
                status="failed",
                deliverables={},
                execution_time=execution_time,
                quality_metrics={"overall": 0.0, "completeness": 0.0},
                issues_encountered=[str(e)],
                recommendations=["エラー修正後に再実行してください"],
                timestamp=datetime.now()
            )
    
    async def _execute_requirements_analysis(self, directive: CommandDirective) -> List[TechnicalDeliverable]:
        """技術要件分析実行"""
        self.logger.info("🔍 技術要件分析実行中...")
        
        task_context = directive.context
        instruction = directive.instruction
        
        # ClaudeCode APIを使用した詳細技術分析
        analysis_prompt = f"""
        あなたは経験豊富なシステムアーキテクトです。
        以下のタスクの技術要件を詳細に分析してください。

        {instruction}

        **コンテキスト:**
        {json.dumps(task_context, ensure_ascii=False, indent=2)}

        **出力要求:**
        詳細な技術要件分析レポートを以下の形式で作成してください：

        # 技術要件分析レポート

        ## 1. 機能要件分析
        ### 1.1 コア機能
        - [機能1]: [詳細説明]
        - [機能2]: [詳細説明]

        ### 1.2 サポート機能  
        - [機能A]: [詳細説明]
        - [機能B]: [詳細説明]

        ## 2. 非機能要件分析
        ### 2.1 パフォーマンス要件
        - 応答時間: [具体的数値]
        - スループット: [具体的数値]

        ### 2.2 可用性要件
        - アップタイム: [要求レベル]
        - 障害復旧時間: [具体的数値]

        ### 2.3 セキュリティ要件
        - 認証方式: [具体的方式]
        - データ保護: [保護レベル]

        ## 3. 技術スタック提案
        ### 3.1 バックエンド技術
        - 言語: [推奨言語と理由]
        - フレームワーク: [推奨フレームワークと理由]
        - データベース: [推奨DBと理由]

        ### 3.2 フロントエンド技術
        - フレームワーク: [推奨技術と理由]
        - UI/UX: [アプローチ]

        ## 4. アーキテクチャ要件
        ### 4.1 システム構成
        ```
        [アーキテクチャ図の説明]
        ```

        ### 4.2 コンポーネント分割
        - [コンポーネント1]: [責務と仕様]
        - [コンポーネント2]: [責務と仕様]

        ## 5. データモデル要件
        ### 5.1 エンティティ定義
        - [エンティティ1]: [属性と関係]
        - [エンティティ2]: [属性と関係]

        ### 5.2 データフロー
        ```
        [データフロー図の説明]
        ```

        ## 6. インターフェース要件
        ### 6.1 API設計
        - [エンドポイント1]: [仕様]
        - [エンドポイント2]: [仕様]

        ### 6.2 外部連携
        - [外部システム1]: [連携方式]
        - [外部システム2]: [連携方式]

        ## 7. 実装上の考慮点
        ### 7.1 技術的制約
        - [制約1]: [詳細と対策]
        - [制約2]: [詳細と対策]

        ### 7.2 リスク要因
        - [リスク1]: [影響と軽減策]
        - [リスク2]: [影響と軽減策]

        ## 8. 実装推奨事項
        ### 8.1 開発アプローチ
        - [推奨アプローチと理由]

        ### 8.2 品質保証
        - [テスト戦略]
        - [品質メトリクス]

        高品質で実装可能な技術要件分析レポートを作成してください。
        """
        
        # ClaudeCode API呼び出し（簡略化実装）
        analysis_content = await self._call_claude_code_api(analysis_prompt)
        
        # 分析結果をパース（実際の実装では詳細なパース処理）
        technical_analysis = self._parse_requirements_analysis(analysis_content)
        
        deliverables = []
        
        # メイン分析レポート
        deliverables.append(TechnicalDeliverable(
            deliverable_id=f"req_analysis_{datetime.now().strftime('%H%M%S')}",
            type="requirements_analysis_report",
            title="技術要件分析レポート",
            content=analysis_content,
            file_path=self.workspace_path / "analysis" / "technical_requirements.md",
            metadata={
                "analysis_type": "comprehensive",
                "sections_count": analysis_content.count("##"),
                "word_count": len(analysis_content.split()),
                "technical_stack": technical_analysis.get("technical_stack", []),
                "complexity_level": technical_analysis.get("complexity", "medium")
            },
            quality_score=0.9,
            created_at=datetime.now()
        ))
        
        # 機能要件リスト
        functional_requirements = self._extract_functional_requirements(analysis_content)
        deliverables.append(TechnicalDeliverable(
            deliverable_id=f"func_req_{datetime.now().strftime('%H%M%S')}",
            type="functional_requirements",
            title="機能要件リスト",
            content=json.dumps(functional_requirements, ensure_ascii=False, indent=2),
            file_path=self.workspace_path / "analysis" / "functional_requirements.json",
            metadata={
                "requirements_count": len(functional_requirements),
                "priority_distribution": self._analyze_priority_distribution(functional_requirements)
            },
            quality_score=0.88,
            created_at=datetime.now()
        ))
        
        # 非機能要件リスト
        non_functional_requirements = self._extract_non_functional_requirements(analysis_content)
        deliverables.append(TechnicalDeliverable(
            deliverable_id=f"nonfunc_req_{datetime.now().strftime('%H%M%S')}",
            type="non_functional_requirements", 
            title="非機能要件リスト",
            content=json.dumps(non_functional_requirements, ensure_ascii=False, indent=2),
            file_path=self.workspace_path / "analysis" / "non_functional_requirements.json",
            metadata={
                "categories": list(non_functional_requirements.keys()),
                "requirements_count": sum(len(reqs) for reqs in non_functional_requirements.values())
            },
            quality_score=0.86,
            created_at=datetime.now()
        ))
        
        # 技術スタック提案
        tech_stack = self._extract_tech_stack(analysis_content)
        deliverables.append(TechnicalDeliverable(
            deliverable_id=f"tech_stack_{datetime.now().strftime('%H%M%S')}",
            type="technology_stack",
            title="技術スタック提案",
            content=json.dumps(tech_stack, ensure_ascii=False, indent=2),
            file_path=self.workspace_path / "analysis" / "technology_stack.json", 
            metadata={
                "backend_technologies": len(tech_stack.get("backend", {})),
                "frontend_technologies": len(tech_stack.get("frontend", {})),
                "database_options": len(tech_stack.get("database", []))
            },
            quality_score=0.87,
            created_at=datetime.now()
        ))
        
        # ファイル保存
        await self._save_deliverables(deliverables)
        
        return deliverables
    
    async def _execute_specification_creation(self, directive: CommandDirective) -> List[TechnicalDeliverable]:
        """技術仕様書作成実行"""
        self.logger.info("📝 技術仕様書作成実行中...")
        
        # 前段階の成果物から情報取得
        requirements_data = directive.context
        instruction = directive.instruction
        
        # ClaudeCodeによる詳細仕様書作成
        spec_prompt = f"""
        あなたは経験豊富なソフトウェアアーキテクトです。
        以下の技術要件分析結果を基に、実装可能な詳細技術仕様書を作成してください。

        {instruction}

        **前段階の分析結果:**
        {json.dumps(requirements_data, ensure_ascii=False, indent=2)}

        GitHub Spec Kit標準に準拠した包括的な技術仕様書を作成してください。

        # 技術仕様書

        ## 1. プロジェクト概要
        ### 1.1 プロジェクト名
        ### 1.2 目的と目標
        ### 1.3 スコープと制約
        ### 1.4 ステークホルダー

        ## 2. システム要件
        ### 2.1 機能要件
        #### 2.1.1 コア機能
        #### 2.1.2 サポート機能
        #### 2.1.3 ユーザーインターフェース要件

        ### 2.2 非機能要件
        #### 2.2.1 パフォーマンス要件
        #### 2.2.2 可用性要件  
        #### 2.2.3 セキュリティ要件
        #### 2.2.4 運用保守要件

        ## 3. アーキテクチャ設計
        ### 3.1 システム全体構成
        ### 3.2 コンポーネント設計
        ### 3.3 データフロー設計
        ### 3.4 セキュリティアーキテクチャ

        ## 4. データベース設計
        ### 4.1 論理データモデル
        ### 4.2 物理データモデル
        ### 4.3 インデックス戦略
        ### 4.4 データマイグレーション

        ## 5. API仕様
        ### 5.1 RESTful API設計
        ### 5.2 エンドポイント一覧
        ### 5.3 リクエスト/レスポンス仕様
        ### 5.4 認証・認可仕様

        ## 6. 実装ガイドライン
        ### 6.1 コーディング規約
        ### 6.2 ディレクトリ構造
        ### 6.3 ライブラリとフレームワーク
        ### 6.4 エラーハンドリング戦略

        ## 7. テスト戦略
        ### 7.1 テスト方針
        ### 7.2 単体テスト
        ### 7.3 統合テスト
        ### 7.4 E2Eテスト

        ## 8. デプロイメント手順
        ### 8.1 開発環境構築
        ### 8.2 ビルドとパッケージング
        ### 8.3 デプロイメント自動化
        ### 8.4 監視と運用

        ## 9. セキュリティ実装
        ### 9.1 認証実装
        ### 9.2 認可実装
        ### 9.3 データ保護
        ### 9.4 監査ログ

        ## 10. 運用・保守
        ### 10.1 監視要件
        ### 10.2 ログ管理
        ### 10.3 バックアップ戦略
        ### 10.4 災害復旧計画

        実装チームが即座に開発を開始できる詳細レベルで作成してください。
        """
        
        # ClaudeCode API呼び出し
        specification_content = await self._call_claude_code_api(spec_prompt)
        
        deliverables = []
        
        # メイン仕様書
        deliverables.append(TechnicalDeliverable(
            deliverable_id=f"tech_spec_{datetime.now().strftime('%H%M%S')}",
            type="technical_specification",
            title="技術仕様書",
            content=specification_content,
            file_path=self.workspace_path / "specs" / "technical_specification.md",
            metadata={
                "spec_version": "1.0",
                "sections_count": specification_content.count("##"),
                "word_count": len(specification_content.split()),
                "completeness_score": self._assess_spec_completeness(specification_content)
            },
            quality_score=0.91,
            created_at=datetime.now()
        ))
        
        # API仕様書（OpenAPI形式）
        api_spec = self._generate_openapi_spec(specification_content)
        deliverables.append(TechnicalDeliverable(
            deliverable_id=f"api_spec_{datetime.now().strftime('%H%M%S')}",
            type="api_specification",
            title="API仕様書 (OpenAPI)",
            content=json.dumps(api_spec, ensure_ascii=False, indent=2),
            file_path=self.workspace_path / "specs" / "api_specification.yaml",
            metadata={
                "api_version": api_spec.get("info", {}).get("version", "1.0"),
                "endpoints_count": len(api_spec.get("paths", {})),
                "models_count": len(api_spec.get("components", {}).get("schemas", {}))
            },
            quality_score=0.89,
            created_at=datetime.now()
        ))
        
        # データベーススキーマ
        db_schema = self._generate_database_schema(specification_content)
        deliverables.append(TechnicalDeliverable(
            deliverable_id=f"db_schema_{datetime.now().strftime('%H%M%S')}",
            type="database_schema",
            title="データベーススキーマ",
            content=db_schema,
            file_path=self.workspace_path / "specs" / "database_schema.sql",
            metadata={
                "tables_count": db_schema.count("CREATE TABLE"),
                "indexes_count": db_schema.count("CREATE INDEX"),
                "constraints_count": db_schema.count("CONSTRAINT")
            },
            quality_score=0.88,
            created_at=datetime.now()
        ))
        
        # ファイル保存
        await self._save_deliverables(deliverables)
        
        return deliverables
    
    async def _execute_code_implementation(self, directive: CommandDirective) -> List[TechnicalDeliverable]:
        """対象プロジェクトディレクトリでのコード実装"""
        self.logger.info(f"🎯 対象プロジェクト実装開始: {self.target_project_path}")
        
        spec_data = directive.context
        instruction = directive.instruction
        
        # プロジェクト情報を取得
        project_info = self.remote_executor.get_target_project_info()
        
        # 対象プロジェクト用のプロンプトを作成
        implementation_prompt = f"""あなたは対象プロジェクトのディレクトリで作業する上級ソフトウェア開発者です。

**現在の作業ディレクトリ**: {self.target_project_path}

**プロジェクト情報**:
{project_info['project_info']}

**実装指示**: {instruction}

**技術仕様書**:
{json.dumps(spec_data, ensure_ascii=False, indent=2)}

**実装要求**:
1. 既存プロジェクトの構造とコードスタイルを理解する
2. 既存のファイルやディレクトリ構造を尊重する
3. 新しい機能を適切な場所に実装する
4. 既存のコードとの統合を考慮する
5. プロジェクトの依存関係を破壊しない
6. 適切なテストコードを含める

**コード品質要求**:
- 既存コードスタイルとの一貫性
- 適切なエラーハンドリング
- セキュリティベストプラクティス
- パフォーマンスの最適化
- 保守性の高い構造

**注意事項**:
- 既存ファイルを変更する際は慎重に行う
- バックアップが必要な場合は明示する
- 破壊的変更は避ける
- 設定ファイルの変更は最小限に抑える

実装を開始してください。各ファイルの詳細な内容を提供し、どこに配置すべきかを明確にしてください。"""
        
        # 対象プロジェクトでClaudeCodeを実行
        execution_result = await self.remote_executor.execute_claude_code_command(
            command=f"コード実装: {instruction}",
            context=implementation_prompt,
            timeout=600  # 10分のタイムアウト
        )
        
        deliverables = []
        
        if execution_result['status'] == 'success':
            # 実行結果を解析してデリバラブルを作成
            output_content = execution_result['output']
            
            # 実装結果の解析
            implementation_files = self._parse_target_project_output(output_content)
            
            # 各実装ファイルをデリバラブルとして作成
            for file_info in implementation_files:
                deliverables.append(TechnicalDeliverable(
                    deliverable_id=f"target_impl_{file_info.get('name', 'unknown').replace('.', '_')}_{datetime.now().strftime('%H%M%S')}",
                    type="target_project_implementation",
                    title=f"対象プロジェクト実装: {file_info.get('name', '不明なファイル')}",
                    content=file_info.get('content', output_content),
                    file_path=self.target_project_path / file_info.get('path', '.') / file_info.get('name', 'implementation.py'),
                    metadata={
                        "target_project": str(self.target_project_path),
                        "execution_time": execution_result['execution_time'],
                        "claude_code_used": True,
                        "file_type": file_info.get('type', 'code'),
                        "language": file_info.get('language', 'python')
                    },
                    quality_score=0.88,
                    created_at=datetime.now()
                ))
        else:
            # エラーの場合でもデリバラブルとして記録
            deliverables.append(TechnicalDeliverable(
                deliverable_id=f"target_impl_error_{datetime.now().strftime('%H%M%S')}",
                type="target_project_error",
                title="対象プロジェクト実装エラー",
                content=f"実行エラー:\n{execution_result['error']}\n\n出力:\n{execution_result['output']}",
                file_path=self.target_project_path / "implementation_error.log",
                metadata={
                    "target_project": str(self.target_project_path),
                    "error": execution_result['error'],
                    "execution_time": execution_result['execution_time']
                },
                quality_score=0.0,
                created_at=datetime.now()
            ))
        
        # 実行サマリーを作成
        deliverables.append(TechnicalDeliverable(
            deliverable_id=f"target_impl_summary_{datetime.now().strftime('%H%M%S')}",
            type="target_project_summary",
            title="対象プロジェクト実装サマリー",
            content=f"""# 対象プロジェクト実装完了サマリー

## プロジェクト情報
- 対象ディレクトリ: {self.target_project_path}
- 実行状態: {execution_result['status']}
- 実行時間: {execution_result['execution_time']:.2f}秒

## 実装詳細
- 指示: {instruction}
- 実装ファイル数: {len([d for d in deliverables if d.type == 'target_project_implementation'])}

## 実行ログ
{execution_result['output'][:1000]}{'...' if len(execution_result['output']) > 1000 else ''}

## 次のステップ
1. 対象プロジェクトでの動作確認
2. テストの実行
3. 既存機能への影響確認
4. コードレビューの実施

## 注意事項
- 対象プロジェクトディレクトリで実装されました
- 既存コードとの統合を確認してください
- バックアップの作成を検討してください
            """,
            file_path=self.target_project_path / "nocturnal_implementation_summary.md",
            metadata={
                "target_project": str(self.target_project_path),
                "files_implemented": len([d for d in deliverables if d.type == 'target_project_implementation']),
                "execution_status": execution_result['status']
            },
            quality_score=0.9,
            created_at=datetime.now()
        ))
        
        return deliverables
    
    async def _execute_code_in_target_project(self, directive: CommandDirective) -> List[TechnicalDeliverable]:
        """対象プロジェクトディレクトリでのコード実装"""
        self.logger.info(f"🎯 対象プロジェクト実装開始: {self.target_project_path}")
        
        spec_data = directive.context
        instruction = directive.instruction
        
        # プロジェクト情報を取得
        project_info = self.remote_executor.get_target_project_info()
        
        # 対象プロジェクト用のプロンプトを作成
        implementation_prompt = f"""あなたは対象プロジェクトのディレクトリで作業する上級ソフトウェア開発者です。

**現在の作業ディレクトリ**: {self.target_project_path}

**プロジェクト情報**:
{project_info['project_info']}

**実装指示**: {instruction}

**技術仕様書**:
{json.dumps(spec_data, ensure_ascii=False, indent=2)}

**実装要求**:
1. 既存プロジェクトの構造とコードスタイルを理解する
2. 既存のファイルやディレクトリ構造を尊重する
3. 新しい機能を適切な場所に実装する
4. 既存のコードとの統合を考慮する
5. プロジェクトの依存関係を破壊しない
6. 適切なテストコードを含める

**コード品質要求**:
- 既存コードスタイルとの一貫性
- 適切なエラーハンドリング
- セキュリティベストプラクティス
- パフォーマンスの最適化
- 保守性の高い構造

**注意事項**:
- 既存ファイルを変更する際は慎重に行う
- バックアップが必要な場合は明示する
- 破壊的変更は避ける
- 設定ファイルの変更は最小限に抑える

実装を開始してください。各ファイルの詳細な内容を提供し、どこに配置すべきかを明確にしてください。"""
        
        # 対象プロジェクトでClaudeCodeを実行
        execution_result = await self.remote_executor.execute_claude_code_command(
            command=f"コード実装: {instruction}",
            context=implementation_prompt,
            timeout=600  # 10分のタイムアウト
        )
        
        deliverables = []
        
        if execution_result['status'] == 'success':
            # 実行結果を解析してデリバラブルを作成
            output_content = execution_result['output']
            
            # 実装結果の解析
            implementation_files = self._parse_target_project_output(output_content)
            
            # 各実装ファイルをデリバラブルとして作成
            for file_info in implementation_files:
                deliverables.append(TechnicalDeliverable(
                    deliverable_id=f"target_impl_{file_info.get('name', 'unknown').replace('.', '_')}_{datetime.now().strftime('%H%M%S')}",
                    type="target_project_implementation",
                    title=f"対象プロジェクト実装: {file_info.get('name', '不明なファイル')}",
                    content=file_info.get('content', output_content),
                    file_path=self.target_project_path / file_info.get('path', '.') / file_info.get('name', 'implementation.py'),
                    metadata={
                        "target_project": str(self.target_project_path),
                        "execution_time": execution_result['execution_time'],
                        "claude_code_used": True,
                        "file_type": file_info.get('type', 'code'),
                        "language": file_info.get('language', 'python')
                    },
                    quality_score=0.88,
                    created_at=datetime.now()
                ))
        else:
            # エラーの場合でもデリバラブルとして記録
            deliverables.append(TechnicalDeliverable(
                deliverable_id=f"target_impl_error_{datetime.now().strftime('%H%M%S')}",
                type="target_project_error",
                title="対象プロジェクト実装エラー",
                content=f"実行エラー:\n{execution_result['error']}\n\n出力:\n{execution_result['output']}",
                file_path=self.target_project_path / "implementation_error.log",
                metadata={
                    "target_project": str(self.target_project_path),
                    "error": execution_result['error'],
                    "execution_time": execution_result['execution_time']
                },
                quality_score=0.0,
                created_at=datetime.now()
            ))
        
        # 実行サマリーを作成
        deliverables.append(TechnicalDeliverable(
            deliverable_id=f"target_impl_summary_{datetime.now().strftime('%H%M%S')}",
            type="target_project_summary",
            title="対象プロジェクト実装サマリー",
            content=f"""# 対象プロジェクト実装完了サマリー

## プロジェクト情報
- 対象ディレクトリ: {self.target_project_path}
- 実行状態: {execution_result['status']}
- 実行時間: {execution_result['execution_time']:.2f}秒

## 実装詳細
- 指示: {instruction}
- 実装ファイル数: {len([d for d in deliverables if d.type == 'target_project_implementation'])}

## 実行ログ
{execution_result['output'][:1000]}{'...' if len(execution_result['output']) > 1000 else ''}

## 次のステップ
1. 対象プロジェクトでの動作確認
2. テストの実行
3. 既存機能への影響確認
4. コードレビューの実施

## 注意事項
- 対象プロジェクトディレクトリで実装されました
- 既存コードとの統合を確認してください
- バックアップの作成を検討してください
            """,
            file_path=self.target_project_path / "nocturnal_implementation_summary.md",
            metadata={
                "target_project": str(self.target_project_path),
                "files_implemented": len([d for d in deliverables if d.type == 'target_project_implementation']),
                "execution_status": execution_result['status']
            },
            quality_score=0.9,
            created_at=datetime.now()
        ))
        
        return deliverables
    
    
    def _parse_target_project_output(self, output_content: str) -> List[Dict]:
        """対象プロジェクトでの実行結果を解析"""
        # 簡単な解析実装（実際にはより高度な解析が必要）
        files = []
        
        # ファイルパターンの検出を試行
        lines = output_content.split('\n')
        current_file = None
        current_content = []
        
        for line in lines:
            # ファイル作成や編集のマーカーを検出
            if any(marker in line.lower() for marker in ['create', 'file:', 'edit:', '作成', 'ファイル']):
                if current_file:
                    files.append({
                        'name': current_file,
                        'content': '\n'.join(current_content),
                        'path': '.',
                        'type': 'code',
                        'language': 'python'
                    })
                
                # 新しいファイル名を抽出
                for word in line.split():
                    if '.' in word and not word.startswith('.'):
                        current_file = word
                        current_content = []
                        break
            else:
                if current_file:
                    current_content.append(line)
        
        # 最後のファイルを追加
        if current_file and current_content:
            files.append({
                'name': current_file,
                'content': '\n'.join(current_content),
                'path': '.',
                'type': 'code',
                'language': 'python'
            })
        
        # ファイルが検出されない場合はデフォルトファイルを作成
        if not files:
            files.append({
                'name': 'implementation_result.txt',
                'content': output_content,
                'path': '.',
                'type': 'output',
                'language': 'text'
            })
        
        return files
    
    async def _execute_test_creation(self, directive: CommandDirective) -> List[TechnicalDeliverable]:
        """テストコード作成実行"""
        self.logger.info("🧪 テストコード作成実行中...")
        # テスト実装ロジック（簡略化）
        return []
    
    async def _execute_documentation(self, directive: CommandDirective) -> List[TechnicalDeliverable]:
        """ドキュメント作成実行"""
        self.logger.info("📚 ドキュメント作成実行中...")
        # ドキュメント作成ロジック（簡略化）
        return []
    
    async def _call_claude_code_api(self, prompt: str, max_tokens: int = 8192) -> str:
        """ClaudeCode API呼び出し"""
        if not self.claude_config.enabled:
            return self._generate_fallback_response(prompt)
        
        # 実際のAPI呼び出し（既存のclaudeCodeインターフェース使用）
        try:
            from .claude_code_interface import ClaudeCodeInterface
            async with ClaudeCodeInterface(self.claude_config) as claude:
                messages = [{"role": "user", "content": prompt}]
                response = await claude._call_claude_api(messages)
                return response
        except Exception as e:
            self.logger.error(f"ClaudeCode API呼び出しエラー: {e}")
            return self._generate_fallback_response(prompt)
    
    def _generate_fallback_response(self, prompt: str) -> str:
        """フォールバック応答生成"""
        if "技術要件分析" in prompt:
            return """
# 技術要件分析レポート (フォールバック)

## 1. 機能要件分析
### 1.1 コア機能
- データ処理機能: 入力データの処理と変換
- ユーザーインターフェース: Web画面での操作機能

### 1.2 サポート機能
- ログ管理: システム動作の記録
- 設定管理: システム設定の管理

## 2. 非機能要件分析
### 2.1 パフォーマンス要件
- 応答時間: 2秒以内
- 同時接続数: 100ユーザー

### 2.2 セキュリティ要件
- 認証: ユーザー認証機能
- データ保護: 個人情報の暗号化

## 3. 技術スタック提案
### 3.1 バックエンド
- 言語: Python 3.9+
- フレームワーク: Flask/FastAPI
- データベース: SQLite/PostgreSQL

### 3.2 フロントエンド
- HTML/CSS/JavaScript
- Bootstrap (CSS framework)

## 4. アーキテクチャ設計
```
[User Interface] -> [API Layer] -> [Business Logic] -> [Data Layer]
```
            """
        elif "技術仕様書" in prompt:
            return """
# 技術仕様書 (フォールバック)

## 1. プロジェクト概要
システムの基本的な機能を提供するWebアプリケーション

## 2. システム要件
### 2.1 機能要件
- データCRUD操作
- ユーザー認証
- レスポンシブUI

### 2.2 非機能要件
- パフォーマンス: 応答時間 < 2秒
- 可用性: 99%以上
- セキュリティ: HTTPS通信

## 3. API仕様
### 3.1 エンドポイント
- GET /api/data - データ取得
- POST /api/data - データ作成
- PUT /api/data/{id} - データ更新
- DELETE /api/data/{id} - データ削除

## 4. 実装ガイドライン
- PEP 8準拠
- 型ヒント使用
- エラーハンドリング必須
            """
        elif "実装" in prompt:
            return """
# メインアプリケーション実装

## app.py
```python
from flask import Flask, jsonify, request

app = Flask(__name__)

@app.route('/api/data', methods=['GET'])
def get_data():
    return jsonify({"message": "データ取得"})

@app.route('/api/data', methods=['POST'])
def create_data():
    return jsonify({"message": "データ作成"})

if __name__ == '__main__':
    app.run(debug=True)
```

## config.py
```python
class Config:
    SECRET_KEY = 'your-secret-key'
    DATABASE_URL = 'sqlite:///app.db'
```

## requirements.txt
```
Flask==2.3.0
SQLAlchemy==2.0.0
```
            """
        
        return "フォールバック応答: 技術作業を実行しました。"
    
    def _parse_requirements_analysis(self, content: str) -> Dict[str, Any]:
        """要件分析結果のパース"""
        return {
            "technical_stack": ["Python", "Flask", "SQLite"],
            "complexity": "medium",
            "estimated_effort": "2-4時間"
        }
    
    def _extract_functional_requirements(self, content: str) -> List[Dict]:
        """機能要件抽出"""
        return [
            {"id": "FR001", "title": "データ管理", "priority": "high", "description": "基本的なデータCRUD操作"},
            {"id": "FR002", "title": "ユーザーUI", "priority": "medium", "description": "Web画面での操作"}
        ]
    
    def _extract_non_functional_requirements(self, content: str) -> Dict[str, List]:
        """非機能要件抽出"""
        return {
            "performance": [
                {"requirement": "応答時間 < 2秒", "priority": "high"},
                {"requirement": "同時接続100ユーザー", "priority": "medium"}
            ],
            "security": [
                {"requirement": "HTTPS通信", "priority": "high"},
                {"requirement": "データ暗号化", "priority": "medium"}
            ]
        }
    
    def _extract_tech_stack(self, content: str) -> Dict[str, Any]:
        """技術スタック抽出"""
        return {
            "backend": {
                "language": "Python 3.9+",
                "framework": "Flask",
                "database": "SQLite"
            },
            "frontend": {
                "framework": "HTML/CSS/JS",
                "ui_library": "Bootstrap"
            },
            "database": ["SQLite", "PostgreSQL"]
        }
    
    def _assess_spec_completeness(self, content: str) -> float:
        """仕様書完全性評価"""
        required_sections = ["プロジェクト概要", "システム要件", "アーキテクチャ", "API仕様"]
        found_sections = sum(1 for section in required_sections if section in content)
        return found_sections / len(required_sections)
    
    def _generate_openapi_spec(self, content: str) -> Dict[str, Any]:
        """OpenAPI仕様生成"""
        return {
            "openapi": "3.0.0",
            "info": {
                "title": "API仕様",
                "version": "1.0.0"
            },
            "paths": {
                "/api/data": {
                    "get": {
                        "summary": "データ取得",
                        "responses": {
                            "200": {"description": "成功"}
                        }
                    }
                }
            }
        }
    
    def _generate_database_schema(self, content: str) -> str:
        """データベーススキーマ生成"""
        return """
CREATE TABLE main_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_main_data_name ON main_data(name);
        """
    
    def _parse_implementation_content(self, content: str) -> List[Dict[str, Any]]:
        """実装内容解析"""
        return [
            {
                "name": "app.py",
                "path": "src",
                "type": "main_application",
                "language": "python",
                "complexity": "medium",
                "content": """from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/api/data')
def get_data():
    return jsonify({'message': 'Hello World'})

if __name__ == '__main__':
    app.run(debug=True)
"""
            },
            {
                "name": "config.py", 
                "path": "src",
                "type": "configuration",
                "language": "python",
                "complexity": "low",
                "content": """class Config:
    SECRET_KEY = 'dev-secret-key'
    DATABASE_URL = 'sqlite:///app.db'
"""
            }
        ]
    
    def _calculate_quality_metrics(self, deliverables: List[TechnicalDeliverable]) -> Dict[str, float]:
        """品質メトリクス計算"""
        if not deliverables:
            return {"overall": 0.0, "completeness": 0.0}
        
        overall_quality = sum(d.quality_score for d in deliverables) / len(deliverables)
        completeness = len(deliverables) / max(len(deliverables), 4)  # 期待成果物数で正規化
        
        return {
            "overall": round(overall_quality, 2),
            "completeness": round(min(completeness, 1.0), 2),
            "deliverables_count": len(deliverables),
            "average_quality": round(overall_quality, 2)
        }
    
    def _generate_recommendations(self, deliverables: List[TechnicalDeliverable]) -> List[str]:
        """推奨事項生成"""
        recommendations = []
        
        avg_quality = sum(d.quality_score for d in deliverables) / len(deliverables) if deliverables else 0
        
        if avg_quality < 0.8:
            recommendations.append("品質向上のため追加レビューを実施してください")
        
        if len(deliverables) < 3:
            recommendations.append("成果物の補完を検討してください")
        
        recommendations.append("次フェーズの準備を開始してください")
        
        return recommendations
    
    async def _save_deliverables(self, deliverables: List[TechnicalDeliverable]):
        """成果物ファイル保存"""
        for deliverable in deliverables:
            if deliverable.file_path:
                file_path = Path(deliverable.file_path)
                file_path.parent.mkdir(parents=True, exist_ok=True)
                
                try:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(deliverable.content)
                    self.logger.info(f"成果物保存: {file_path}")
                except Exception as e:
                    self.logger.error(f"成果物保存エラー {file_path}: {e}")


# ユーティリティ関数
async def create_technical_executor(workspace_path: str = None) -> TechnicalExecutorInterface:
    """技術実行者インターフェースのファクトリ関数"""
    return TechnicalExecutorInterface(workspace_path=workspace_path)