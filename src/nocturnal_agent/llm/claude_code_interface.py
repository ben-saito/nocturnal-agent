#!/usr/bin/env python3
"""
ClaudeCode Interface - ClaudeCodeとの通信インターフェース
ローカルLLMからの指示をClaudeCodeに送信し、高品質な仕様書を生成
"""

import asyncio
import json
import logging
import os
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
import aiohttp

from ..core.models import Task


@dataclass
class ClaudeCodeConfig:
    """ClaudeCode設定"""
    api_key: str
    api_url: str = "https://api.anthropic.com/v1/messages"
    model: str = "claude-3-5-sonnet-20241022"
    max_tokens: int = 8192
    timeout: int = 300
    enabled: bool = True


@dataclass 
class SpecificationDocument:
    """生成された仕様書"""
    title: str
    content: str
    sections: Dict[str, str]
    metadata: Dict[str, Any]
    quality_indicators: Dict[str, float]
    generation_time: float
    word_count: int


class ClaudeCodeInterface:
    """ClaudeCode指示・通信システム"""
    
    def __init__(self, config: ClaudeCodeConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.session: Optional[aiohttp.ClientSession] = None
        
        # API キーの検証
        if not self.config.api_key or self.config.api_key.startswith("sk-"):
            self.logger.warning("ClaudeCode API キーが設定されていません。フォールバックモードで動作します。")
            self.config.enabled = False
    
    async def __aenter__(self):
        """Async context manager entry"""
        if self.config.enabled:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.config.timeout),
                headers={
                    "x-api-key": self.config.api_key,
                    "content-type": "application/json",
                    "anthropic-version": "2023-06-01"
                }
            )
            
            try:
                await self._test_api_connection()
                self.logger.info("ClaudeCode APIに正常に接続しました")
            except Exception as e:
                self.logger.error(f"ClaudeCode API接続失敗: {e}")
                self.config.enabled = False
        
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
    
    async def _test_api_connection(self) -> bool:
        """ClaudeCode API接続テスト"""
        test_payload = {
            "model": self.config.model,
            "max_tokens": 10,
            "messages": [
                {
                    "role": "user",
                    "content": "テスト接続"
                }
            ]
        }
        
        try:
            async with self.session.post(self.config.api_url, json=test_payload) as response:
                if response.status == 200:
                    return True
                else:
                    raise Exception(f"API テストエラー: {response.status}")
        except Exception as e:
            raise ConnectionError(f"ClaudeCode API接続失敗: {e}")
    
    async def _call_claude_api(self, messages: List[Dict], system_prompt: str = None) -> str:
        """ClaudeCode APIを呼び出し"""
        if not self.config.enabled:
            return self._generate_fallback_spec()
        
        if not self.session:
            raise RuntimeError("ClaudeCodeセッションが初期化されていません")
        
        payload = {
            "model": self.config.model,
            "max_tokens": self.config.max_tokens,
            "messages": messages
        }
        
        if system_prompt:
            payload["system"] = system_prompt
        
        try:
            async with self.session.post(self.config.api_url, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    return data["content"][0]["text"]
                else:
                    error_text = await response.text()
                    raise Exception(f"API エラー {response.status}: {error_text}")
                    
        except Exception as e:
            self.logger.error(f"ClaudeCode API呼び出しエラー: {e}")
            return self._generate_fallback_spec()
    
    def _generate_fallback_spec(self) -> str:
        """フォールバック仕様書生成"""
        self.logger.info("フォールバックモードで仕様書を生成します")
        
        fallback_spec = f"""
        # 技術仕様書 (フォールバック生成)
        
        Generated at: {datetime.now().isoformat()}
        Mode: Fallback Generation
        
        ## 1. プロジェクト概要
        
        本プロジェクトは、指定された要件に基づいて開発されるシステムです。
        
        ### 1.1 目的
        - 高品質なソフトウェアシステムの提供
        - 技術要件の完全な実装
        - 保守性と拡張性の確保
        
        ## 2. システム要件
        
        ### 2.1 機能要件
        - コア機能の実装
        - ユーザーインターフェースの提供
        - データ管理機能
        
        ### 2.2 非機能要件
        - パフォーマンス: 応答時間 < 2秒
        - 可用性: 99.9%以上
        - セキュリティ: 業界標準準拠
        
        ## 3. アーキテクチャ設計
        
        ### 3.1 システム構成
        ```
        [フロントエンド] -> [API層] -> [ビジネスロジック] -> [データ層]
        ```
        
        ### 3.2 技術スタック
        - Backend: Python 3.9+
        - Database: SQLite/PostgreSQL
        - API: REST API
        - Frontend: HTML/CSS/JavaScript
        
        ## 4. データベース設計
        
        ### 4.1 メインテーブル
        ```sql
        CREATE TABLE main_data (
            id INTEGER PRIMARY KEY,
            data_field TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        ```
        
        ## 5. API仕様
        
        ### 5.1 エンドポイント
        - GET /api/data - データ取得
        - POST /api/data - データ作成
        - PUT /api/data/{id} - データ更新
        - DELETE /api/data/{id} - データ削除
        
        ## 6. 実装ガイドライン
        
        ### 6.1 コーディング規約
        - PEP 8準拠
        - 型ヒント使用
        - ドキュメント文字列必須
        
        ### 6.2 エラーハンドリング
        - 例外の適切な処理
        - ログ出力の実装
        - ユーザーフレンドリーなエラーメッセージ
        
        ## 7. テスト戦略
        
        ### 7.1 テスト種別
        - 単体テスト: pytest使用
        - 統合テスト: API テスト
        - E2Eテスト: Seleniumベース
        
        ## 8. デプロイメント
        
        ### 8.1 環境構成
        - 開発環境: ローカル開発
        - ステージング環境: テスト用
        - 本番環境: 本格運用
        
        ### 8.2 CI/CD
        - GitHub Actions使用
        - 自動テスト実行
        - 自動デプロイメント
        
        ---
        
        **注意**: これはフォールバック生成された仕様書です。
        実際のプロジェクト要件に応じて詳細化が必要です。
        """
        
        return fallback_spec.strip()
    
    async def generate_specification_document(
        self, 
        instruction: str, 
        task: Task,
        additional_context: Dict = None
    ) -> SpecificationDocument:
        """ClaudeCodeに指示を送信して詳細な仕様書を生成"""
        start_time = datetime.now()
        self.logger.info("ClaudeCodeによる仕様書生成開始...")
        
        # システムプロンプト
        system_prompt = """
        あなたは経験豊富なソフトウェアアーキテクトです。
        与えられた指示に基づいて、実装可能で詳細な技術仕様書を作成してください。
        
        仕様書には以下のセクションを含めてください：
        1. プロジェクト概要
        2. システム要件（機能要件・非機能要件）
        3. アーキテクチャ設計
        4. データベース設計
        5. API仕様
        6. 実装ガイドライン
        7. テスト戦略
        8. デプロイメント手順
        9. 保守・運用方針
        
        回答は明確で実装可能な内容とし、GitHub Spec Kit標準に準拠してください。
        """
        
        # ユーザーメッセージ
        context_info = ""
        if additional_context:
            context_info = f"\n\n**追加コンテキスト:**\n{json.dumps(additional_context, ensure_ascii=False, indent=2)}"
        
        user_message = f"""
        {instruction}
        
        **タスク詳細:**
        - 説明: {task.description}
        - 優先度: {task.priority.value}
        - 要件: {json.dumps(task.requirements, ensure_ascii=False)}
        {context_info}
        
        上記の情報に基づいて、詳細で実装可能な技術仕様書を作成してください。
        """
        
        messages = [
            {
                "role": "user",
                "content": user_message
            }
        ]
        
        # ClaudeCode API呼び出し
        spec_content = await self._call_claude_api(messages, system_prompt)
        
        # 仕様書の解析と構造化
        sections = self._parse_specification_sections(spec_content)
        quality_indicators = self._analyze_specification_quality(spec_content)
        
        generation_time = (datetime.now() - start_time).total_seconds()
        word_count = len(spec_content.split())
        
        spec_document = SpecificationDocument(
            title=f"{task.description}の技術仕様書",
            content=spec_content,
            sections=sections,
            metadata={
                "task_id": task.id,
                "generation_method": "ClaudeCode API" if self.config.enabled else "Fallback",
                "generated_at": start_time.isoformat(),
                "task_priority": task.priority.value,
                "requirements_count": len(task.requirements)
            },
            quality_indicators=quality_indicators,
            generation_time=generation_time,
            word_count=word_count
        )
        
        self.logger.info(f"仕様書生成完了: {word_count}語, {generation_time:.2f}秒")
        return spec_document
    
    def _parse_specification_sections(self, content: str) -> Dict[str, str]:
        """仕様書をセクションごとに解析"""
        sections = {}
        
        # Markdownヘッダーベースの解析
        lines = content.split('\n')
        current_section = None
        current_content = []
        
        for line in lines:
            if line.startswith('## '):
                # 前のセクションを保存
                if current_section:
                    sections[current_section] = '\n'.join(current_content).strip()
                
                # 新しいセクション開始
                current_section = line.replace('## ', '').strip()
                current_content = []
            elif current_section:
                current_content.append(line)
        
        # 最後のセクションを保存
        if current_section:
            sections[current_section] = '\n'.join(current_content).strip()
        
        return sections
    
    def _analyze_specification_quality(self, content: str) -> Dict[str, float]:
        """仕様書の品質指標を分析"""
        word_count = len(content.split())
        line_count = len(content.split('\n'))
        
        # 基本的な品質指標
        quality_indicators = {
            "length_score": min(word_count / 1000, 1.0),  # 1000語を満点とする
            "structure_score": len([line for line in content.split('\n') if line.startswith('##')]) / 10,  # 10セクションを満点
            "detail_score": content.count('```') / 10,  # コードブロック数
            "completeness_score": 0.8  # 基本スコア
        }
        
        # キーワード分析
        important_keywords = [
            'API', 'データベース', 'テスト', 'デプロイ', 'セキュリティ',
            'パフォーマンス', 'エラーハンドリング', '実装', '要件'
        ]
        
        keyword_count = sum(1 for keyword in important_keywords if keyword in content)
        quality_indicators["keyword_coverage"] = keyword_count / len(important_keywords)
        
        return quality_indicators
    
    async def enhance_specification_iteratively(
        self, 
        initial_spec: SpecificationDocument,
        enhancement_requests: List[str]
    ) -> SpecificationDocument:
        """仕様書の反復的改善"""
        self.logger.info("仕様書の反復的改善を開始...")
        
        enhancement_prompt = f"""
        以下の仕様書を改善してください：
        
        **改善要求:**
        {chr(10).join(f"- {req}" for req in enhancement_requests)}
        
        **現在の仕様書:**
        {initial_spec.content}
        
        改善要求に基づいて、より詳細で高品質な仕様書に更新してください。
        """
        
        messages = [
            {
                "role": "user", 
                "content": enhancement_prompt
            }
        ]
        
        enhanced_content = await self._call_claude_api(messages)
        
        # 改善された仕様書として再構築
        enhanced_spec = SpecificationDocument(
            title=initial_spec.title + " (改善版)",
            content=enhanced_content,
            sections=self._parse_specification_sections(enhanced_content),
            metadata={
                **initial_spec.metadata,
                "enhanced_at": datetime.now().isoformat(),
                "enhancement_requests": enhancement_requests
            },
            quality_indicators=self._analyze_specification_quality(enhanced_content),
            generation_time=initial_spec.generation_time,
            word_count=len(enhanced_content.split())
        )
        
        return enhanced_spec


# ユーティリティ関数
def load_claude_config() -> ClaudeCodeConfig:
    """設定ファイルからClaudeCode設定を読み込み"""
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    
    # フォールバック設定
    if not api_key:
        api_key = "fallback-mode"
    
    return ClaudeCodeConfig(
        api_key=api_key,
        enabled=bool(api_key and not api_key.startswith("fallback"))
    )


# 使用例
if __name__ == "__main__":
    async def test_claude_interface():
        config = load_claude_config()
        
        from ..core.models import Task, TaskPriority
        
        test_task = Task(
            description="AIニュース収集システム",
            priority=TaskPriority.HIGH,
            requirements=["Webスクレイピング", "データベース保存", "Web画面表示"]
        )
        
        async with ClaudeCodeInterface(config) as claude:
            spec = await claude.generate_specification_document(
                "詳細な技術仕様書を作成してください",
                test_task
            )
            
            print(f"仕様書タイトル: {spec.title}")
            print(f"文字数: {spec.word_count}")
            print(f"品質指標: {spec.quality_indicators}")
    
    # asyncio.run(test_claude_interface())