"""
自然言語要件解析システム
自然言語で書かれた要件を解析し、構造化された設計ファイルを生成する
"""
import re
import json
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path
import yaml

@dataclass
class RequirementAnalysis:
    """要件解析結果"""
    project_type: str
    primary_features: List[str]
    technical_requirements: List[str]
    database_needs: List[str]
    ui_requirements: List[str]
    quality_requirements: List[str]
    estimated_complexity: str  # simple/medium/complex
    suggested_architecture: str
    agent_assignments: Dict[str, List[str]]

class RequirementsParser:
    """自然言語要件解析器"""
    
    def __init__(self):
        self.project_type_keywords = {
            'frontend': ['ui', 'ux', 'デザイン', 'react', 'vue', 'angular', 'フロントエンド', 'web画面', 'ユーザーインターフェース'],
            'backend': ['api', 'サーバー', 'バックエンド', 'rest', 'graphql', 'エンドポイント', 'サービス'],
            'database': ['データベース', 'db', 'sql', 'nosql', 'データ保存', 'mysql', 'postgresql', 'mongodb'],
            'fullstack': ['フルスタック', 'full-stack', 'ウェブアプリ', 'webアプリ', 'システム構築'],
            'mobile': ['モバイル', 'ios', 'android', 'アプリ', 'スマホ'],
            'testing': ['テスト', 'testing', 'qa', '品質保証', 'テスト自動化'],
            'infrastructure': ['インフラ', 'devops', 'ci/cd', 'docker', 'kubernetes', 'aws', 'cloud']
        }
        
        self.complexity_indicators = {
            'simple': ['簡単', 'シンプル', '基本的', '単純', '小規模'],
            'medium': ['標準的', '一般的', '中規模', 'やや複雑'],
            'complex': ['複雑', '高度', '大規模', '多機能', '包括的', 'エンタープライズ']
        }

    def parse_requirements(self, requirements_text: str) -> RequirementAnalysis:
        """自然言語要件を解析して構造化データに変換"""
        # ClaudeCodeAnalyzerを使用して高精度解析を試行
        try:
            from .claude_code_analyzer import ClaudeCodeAnalyzer
            
            analyzer = ClaudeCodeAnalyzer()
            claude_analysis = analyzer.analyze_requirements(requirements_text)
            
            # ClaudeCodeの解析結果を検証・補完
            validated_analysis = self._validate_and_enhance_analysis(claude_analysis, requirements_text)
            
            return validated_analysis
            
        except Exception as e:
            print(f"⚠️ ClaudeCode解析失敗、フォールバック解析を使用: {e}")
            
            # フォールバック: 従来の解析方式
            return self._fallback_parse_requirements(requirements_text)

    def _validate_and_enhance_analysis(self, claude_analysis: RequirementAnalysis, 
                                     original_text: str) -> RequirementAnalysis:
        """ClaudeCodeの解析結果を検証・補完"""
        
        # 各エージェントに最低限のタスクがあることを確認
        min_tasks_per_agent = 3
        for agent_name, tasks in claude_analysis.agent_assignments.items():
            if len(tasks) < min_tasks_per_agent:
                # 不足分を補完
                additional_tasks = self._generate_additional_tasks(agent_name, min_tasks_per_agent - len(tasks))
                claude_analysis.agent_assignments[agent_name].extend(additional_tasks)
        
        # 主要機能が空の場合は補完
        if not claude_analysis.primary_features:
            claude_analysis.primary_features = self._extract_features(original_text)
        
        # 技術要件が空の場合は補完
        if not claude_analysis.technical_requirements:
            claude_analysis.technical_requirements = self._extract_technical_requirements(original_text)
        
        return claude_analysis

    def _generate_additional_tasks(self, agent_name: str, count: int) -> List[str]:
        """エージェント別の追加タスクを生成"""
        additional_tasks = {
            'frontend_specialist': [
                'UIコンポーネント設計',
                'ユーザビリティテスト実施',
                'フロントエンド最適化',
                'アクセシビリティ対応',
                'ブラウザ互換性確保'
            ],
            'backend_specialist': [
                'API設計・実装',
                'ビジネスロジック実装',
                'セキュリティ実装',
                'パフォーマンス最適化',
                'ログ機能実装'
            ],
            'database_specialist': [
                'データベース設計',
                'インデックス最適化',
                'データ移行戦略',
                'バックアップ戦略',
                'データ整合性確保'
            ],
            'qa_specialist': [
                '単体テスト作成',
                '統合テスト実装',
                'E2Eテスト自動化',
                'パフォーマンステスト',
                'セキュリティテスト',
                '負荷テスト実装'
            ]
        }
        
        return additional_tasks.get(agent_name, ['追加タスク実装'])[:count]

    def _fallback_parse_requirements(self, requirements_text: str) -> RequirementAnalysis:
        """フォールバック: 従来の解析方式"""
        # テキストを前処理
        cleaned_text = self._preprocess_text(requirements_text)
        
        # プロジェクトタイプを推定
        project_type = self._infer_project_type(cleaned_text)
        
        # 機能要件を抽出
        features = self._extract_features(cleaned_text)
        
        # 技術要件を抽出
        tech_requirements = self._extract_technical_requirements(cleaned_text)
        
        # データベース要件を抽出
        db_needs = self._extract_database_needs(cleaned_text)
        
        # UI要件を抽出
        ui_requirements = self._extract_ui_requirements(cleaned_text)
        
        # 品質要件を抽出
        quality_requirements = self._extract_quality_requirements(cleaned_text)
        
        # 複雑度を推定
        complexity = self._estimate_complexity(cleaned_text, features)
        
        # アーキテクチャを提案
        architecture = self._suggest_architecture(project_type, complexity, features)
        
        # エージェント割り当てを決定
        agent_assignments = self._assign_to_agents(features, tech_requirements, db_needs, ui_requirements)
        
        return RequirementAnalysis(
            project_type=project_type,
            primary_features=features,
            technical_requirements=tech_requirements,
            database_needs=db_needs,
            ui_requirements=ui_requirements,
            quality_requirements=quality_requirements,
            estimated_complexity=complexity,
            suggested_architecture=architecture,
            agent_assignments=agent_assignments
        )

    def _preprocess_text(self, text: str) -> str:
        """テキストの前処理"""
        # 改行をスペースに変換
        text = re.sub(r'\n+', ' ', text)
        # 余分なスペースを削除
        text = re.sub(r'\s+', ' ', text)
        return text.strip().lower()

    def _infer_project_type(self, text: str) -> str:
        """プロジェクトタイプを推定"""
        type_scores = {}
        
        for proj_type, keywords in self.project_type_keywords.items():
            score = sum(1 for keyword in keywords if keyword in text)
            type_scores[proj_type] = score
        
        # 最高スコアのタイプを返す（同点の場合はfullstack）
        if not type_scores or max(type_scores.values()) == 0:
            return 'fullstack'
        
        return max(type_scores, key=type_scores.get)

    def _extract_features(self, text: str) -> List[str]:
        """機能要件を抽出"""
        features = []
        
        # より具体的な機能パターンを定義
        specific_patterns = [
            # ニュース・データ関連
            (r'ニュース.*?取得', 'ニュース自動取得機能'),
            (r'データ.*?保存', 'データベース保存機能'),
            (r'データ.*?確認', 'データ表示・確認機能'),
            (r'web.*?ui|ui.*?web|webから.*?確認', 'Web UI管理画面'),
            
            # AI関連
            (r'ai.*?提案|提案.*?ai', 'AI分析・提案機能'),
            (r'ai.*?組み合わせ', 'AI技術組み合わせ提案'),
            (r'分析.*?機能', 'データ分析機能'),
            
            # 一般的な機能
            (r'ユーザー.*?登録|登録.*?ユーザー', 'ユーザー登録機能'),
            (r'ユーザー.*?認証|認証.*?ユーザー', 'ユーザー認証機能'),
            (r'ログイン.*?機能', 'ログイン機能'),
            (r'検索.*?機能', '検索機能'),
            (r'管理.*?画面', '管理画面'),
            (r'一覧.*?表示', '一覧表示機能'),
            (r'詳細.*?表示', '詳細表示機能'),
            (r'編集.*?機能', '編集機能'),
            (r'削除.*?機能', '削除機能'),
            (r'投稿.*?機能', '投稿機能'),
            (r'コメント.*?機能', 'コメント機能'),
            (r'通知.*?機能', '通知機能'),
            (r'レポート.*?生成', 'レポート生成機能'),
            (r'チャート.*?表示', 'チャート表示機能'),
            (r'リアルタイム.*?更新', 'リアルタイム更新機能'),
            (r'ファイル.*?共有', 'ファイル共有機能'),
            (r'決済.*?機能', '決済機能'),
            (r'注文.*?管理', '注文管理機能'),
            (r'在庫.*?管理', '在庫管理機能'),
            (r'商品.*?管理', '商品管理機能'),
            (r'ショッピング.*?カート', 'ショッピングカート機能'),
        ]
        
        # 特定パターンでマッチング
        for pattern, feature_name in specific_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                if feature_name not in features:
                    features.append(feature_name)
        
        # 一般的なパターンも追加（後方互換性のため）
        general_patterns = [
            r'(.{1,30}?)機能',
            r'(.{1,30}?)システム',
            r'(.{1,30}?)画面',
            r'(.{1,30}?)管理',
            r'(.{1,30}?)作成',
            r'(.{1,30}?)表示',
        ]
        
        for pattern in general_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                clean_feature = match.strip()
                # 重複チェックと品質チェック
                if (len(clean_feature) > 3 and 
                    clean_feature not in features and
                    not any(clean_feature in existing for existing in features) and
                    len([f for f in features if clean_feature in f]) == 0):
                    features.append(f"{clean_feature}機能")
        
        # 手動で重要な機能を追加（テキストの内容に基づいて）
        if 'codex' in text.lower() or 'claude' in text.lower():
            if 'AIニュース監視機能' not in features:
                features.append('AIニュース監視機能')
        
        if 'db' in text.lower() or 'データベース' in text:
            if 'データベース管理機能' not in features:
                features.append('データベース管理機能')
        
        return features[:8]  # 最大8個まで  # 上位10個まで

    def _extract_technical_requirements(self, text: str) -> List[str]:
        """技術要件を抽出"""
        tech_keywords = [
            'react', 'vue', 'angular', 'node.js', 'python', 'java', 'go',
            'docker', 'kubernetes', 'aws', 'gcp', 'azure',
            'redis', 'elasticsearch', 'kafka', 'rabbitmq',
            'nginx', 'apache', 'ssl', 'https',
            'jwt', 'oauth', 'api', 'rest', 'graphql'
        ]
        
        return [keyword for keyword in tech_keywords if keyword in text]

    def _extract_database_needs(self, text: str) -> List[str]:
        """データベース要件を抽出"""
        db_indicators = []
        
        if any(word in text for word in ['ユーザー', 'user', '会員', 'アカウント']):
            db_indicators.append('ユーザー管理')
        
        if any(word in text for word in ['商品', 'product', 'アイテム', '在庫']):
            db_indicators.append('商品管理')
        
        if any(word in text for word in ['注文', 'order', '購入', '決済']):
            db_indicators.append('注文管理')
        
        if any(word in text for word in ['コンテンツ', 'content', '記事', 'article']):
            db_indicators.append('コンテンツ管理')
        
        if any(word in text for word in ['ログ', 'log', '履歴', 'history']):
            db_indicators.append('ログ管理')
        
        return db_indicators

    def _extract_ui_requirements(self, text: str) -> List[str]:
        """UI要件を抽出"""
        ui_indicators = []
        
        if any(word in text for word in ['レスポンシブ', 'responsive', 'モバイル対応']):
            ui_indicators.append('レスポンシブデザイン')
        
        if any(word in text for word in ['ダークモード', 'dark mode', 'テーマ']):
            ui_indicators.append('テーマ切り替え')
        
        if any(word in text for word in ['多言語', 'i18n', '国際化']):
            ui_indicators.append('多言語対応')
        
        if any(word in text for word in ['アクセシビリティ', 'accessibility', 'バリアフリー']):
            ui_indicators.append('アクセシビリティ対応')
        
        if any(word in text for word in ['アニメーション', 'animation', 'トランジション']):
            ui_indicators.append('アニメーション')
        
        return ui_indicators

    def _extract_quality_requirements(self, text: str) -> List[str]:
        """品質要件を抽出"""
        quality_indicators = []
        
        if any(word in text for word in ['テスト', 'test', '品質保証', 'qa']):
            quality_indicators.append('自動テスト')
        
        if any(word in text for word in ['セキュリティ', 'security', '安全']):
            quality_indicators.append('セキュリティ対策')
        
        if any(word in text for word in ['パフォーマンス', 'performance', '高速']):
            quality_indicators.append('パフォーマンス最適化')
        
        if any(word in text for word in ['スケーラブル', 'scalable', '拡張']):
            quality_indicators.append('スケーラビリティ')
        
        if any(word in text for word in ['監視', 'monitoring', 'ログ']):
            quality_indicators.append('監視・ログ')
        
        return quality_indicators

    def _estimate_complexity(self, text: str, features: List[str]) -> str:
        """複雑度を推定"""
        complexity_scores = {'simple': 0, 'medium': 0, 'complex': 0}
        
        # キーワードベースのスコア
        for complexity, keywords in self.complexity_indicators.items():
            score = sum(1 for keyword in keywords if keyword in text)
            complexity_scores[complexity] += score
        
        # 機能数ベースのスコア
        feature_count = len(features)
        if feature_count <= 3:
            complexity_scores['simple'] += 2
        elif feature_count <= 7:
            complexity_scores['medium'] += 2
        else:
            complexity_scores['complex'] += 2
        
        return max(complexity_scores, key=complexity_scores.get)

    def _suggest_architecture(self, project_type: str, complexity: str, features: List[str]) -> str:
        """アーキテクチャを提案"""
        if complexity == 'simple':
            if project_type == 'frontend':
                return 'SPA (Single Page Application)'
            elif project_type == 'backend':
                return 'RESTful API with SQLite'
            else:
                return 'Monolithic Architecture'
        
        elif complexity == 'medium':
            if project_type in ['fullstack', 'backend']:
                return 'API + Frontend with PostgreSQL'
            else:
                return 'Component-based Architecture'
        
        else:  # complex
            return 'Microservices Architecture'

    def _assign_to_agents(self, features: List[str], tech_reqs: List[str], 
                         db_needs: List[str], ui_reqs: List[str]) -> Dict[str, List[str]]:
        """エージェントにタスクを割り当て"""
        assignments = {
            'frontend_specialist': [],
            'backend_specialist': [],
            'database_specialist': [],
            'qa_specialist': []
        }
        
        # フロントエンド関連の割り当て
        frontend_keywords = ['ui', '画面', 'ページ', '表示', 'デザイン', 'web', 'チャート', 'ダッシュボード']
        for feature in features:
            if any(keyword in feature.lower() for keyword in frontend_keywords):
                assignments['frontend_specialist'].append(f"{feature}の実装")
        
        # UI要件をフロントエンドに割り当て
        for ui_req in ui_reqs:
            assignments['frontend_specialist'].append(f"{ui_req}の実装")
        
        # 基本的なフロントエンドタスクが不足している場合に追加
        if len(assignments['frontend_specialist']) == 0 and features:
            assignments['frontend_specialist'].extend([
                "Webユーザーインターフェースの設計・実装",
                "レスポンシブデザインの実装",
                "データ表示画面の作成"
            ])
        
        # バックエンド関連の割り当て
        backend_keywords = ['api', 'サーバー', '処理', '計算', 'ビジネスロジック', '取得', '保存', '分析', '提案']
        for feature in features:
            if any(keyword in feature.lower() for keyword in backend_keywords):
                assignments['backend_specialist'].append(f"{feature}のAPI実装")
        
        # 技術要件をバックエンドに割り当て
        for tech_req in tech_reqs:
            assignments['backend_specialist'].append(f"{tech_req}を使用したバックエンド実装")
        
        # 基本的なバックエンドタスクを追加
        if features:
            if not any('api' in task.lower() for task in assignments['backend_specialist']):
                assignments['backend_specialist'].extend([
                    "RESTful API設計・実装",
                    "データ処理ロジックの実装",
                    "外部API連携機能の実装"
                ])
        
        # データベース関連の割り当て
        assignments['database_specialist'] = db_needs.copy()
        
        # 基本的なデータベースタスクを追加
        if features and len(assignments['database_specialist']) == 0:
            assignments['database_specialist'].extend([
                "データベーススキーマ設計",
                "マスターデータ管理",
                "データ整合性確保"
            ])
        
        # より具体的なデータベースタスクを追加
        for feature in features:
            if 'データ' in feature or '保存' in feature:
                assignments['database_specialist'].append(f"{feature}のためのデータ設計")
        
        # QA関連の割り当て
        base_qa_tasks = [
            "単体テストの作成",
            "統合テストの作成", 
            "エンドツーエンドテストの作成",
            "パフォーマンステストの実装"
        ]
        
        # 機能数に応じてQAタスクを調整
        if len(features) > 5:
            base_qa_tasks.extend([
                "負荷テストの実装",
                "セキュリティテストの実装"
            ])
        
        assignments['qa_specialist'] = base_qa_tasks
        
        # 各エージェントの最小タスク数を保証
        min_tasks = 2
        for agent in assignments:
            if len(assignments[agent]) < min_tasks:
                if agent == 'frontend_specialist':
                    assignments[agent].extend([
                        "UIコンポーネントライブラリの構築",
                        "ユーザビリティテストの実施"
                    ][:min_tasks - len(assignments[agent])])
                elif agent == 'backend_specialist':
                    assignments[agent].extend([
                        "バックエンドアーキテクチャ設計",
                        "API ドキュメント作成"
                    ][:min_tasks - len(assignments[agent])])
                elif agent == 'database_specialist':
                    assignments[agent].extend([
                        "データベース最適化",
                        "バックアップ戦略策定"
                    ][:min_tasks - len(assignments[agent])])
        
        return assignments