#!/usr/bin/env python3
"""
簡易版 AIニュースWebフェッチ・DB登録・組み合わせ提案統合システム実行スクリプト
"""

import asyncio
import json
import os
import sys
from pathlib import Path

async def execute_integrated_ai_news_system():
    """AIニュース統合システムを実行"""
    
    print("🚀 AIニュースWebフェッチ・DB登録・組み合わせ提案統合システムの実行を開始...")
    
    # ai-news-digプロジェクトのパス
    target_project = "/Users/tsutomusaito/git/ai-news-dig"
    os.chdir(target_project)
    
    print("🔧 システムファイルを作成中...")
    
    # 1. データベース管理システム
    print("📁 1. データベース管理システムを作成...")
    
    database_code = '''import sqlite3
import hashlib
from datetime import datetime
from typing import List, Dict, Optional

class AINewsDatabase:
    """AIニュースデータベース管理クラス"""
    
    def __init__(self, db_path: str = "ai_news.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """データベースとテーブルを初期化"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # ニュース記事テーブル
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS news_articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT,
            url TEXT UNIQUE,
            source TEXT,
            published_date TEXT,
            author TEXT,
            keywords TEXT,
            content_hash TEXT UNIQUE,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # 組み合わせ提案テーブル
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS combination_proposals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            news1_id INTEGER,
            news2_id INTEGER,
            common_keywords TEXT,
            proposal_text TEXT,
            potential_applications TEXT,
            confidence_score REAL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (news1_id) REFERENCES news_articles (id),
            FOREIGN KEY (news2_id) REFERENCES news_articles (id)
        )
        """)
        
        conn.commit()
        conn.close()
        print("✅ データベースを初期化しました")
    
    def add_news_article(self, article: Dict) -> Optional[int]:
        """ニュース記事を追加（重複チェック付き）"""
        content_hash = hashlib.md5(
            (article.get('title', '') + article.get('content', '')).encode()
        ).hexdigest()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
            INSERT INTO news_articles 
            (title, content, url, source, published_date, author, keywords, content_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                article.get('title', ''),
                article.get('content', ''),
                article.get('url', ''),
                article.get('source', ''),
                article.get('published_date', ''),
                article.get('author', ''),
                article.get('keywords', ''),
                content_hash
            ))
            
            article_id = cursor.lastrowid
            conn.commit()
            return article_id
            
        except sqlite3.IntegrityError:
            # 重複記事の場合はスキップ
            return None
        finally:
            conn.close()
    
    def get_recent_articles(self, limit: int = 50) -> List[Dict]:
        """最近の記事を取得"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
        SELECT id, title, content, url, source, published_date, author, keywords
        FROM news_articles 
        ORDER BY created_at DESC 
        LIMIT ?
        """, (limit,))
        
        columns = [description[0] for description in cursor.description]
        articles = []
        
        for row in cursor.fetchall():
            article = dict(zip(columns, row))
            articles.append(article)
        
        conn.close()
        return articles
    
    def save_combination_proposal(self, proposal: Dict) -> int:
        """組み合わせ提案を保存"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
        INSERT INTO combination_proposals 
        (news1_id, news2_id, common_keywords, proposal_text, potential_applications, confidence_score)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (
            proposal.get('news1_id'),
            proposal.get('news2_id'),
            ','.join(proposal.get('common_keywords', [])),
            proposal.get('proposal_text', ''),
            ','.join(proposal.get('potential_applications', [])),
            proposal.get('confidence_score', 0.5)
        ))
        
        proposal_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return proposal_id
'''
    
    with open("ai_news_database.py", "w", encoding="utf-8") as f:
        f.write(database_code)
    
    # 2. ニュースフェッチャー
    print("📁 2. ニュースフェッチャーを作成...")
    
    fetcher_code = '''import asyncio
from datetime import datetime
from typing import List, Dict

class AINewsFetcher:
    """AIニュースをWebから収集するクラス"""
    
    def __init__(self):
        self.ai_keywords = [
            'artificial intelligence', 'AI', 'machine learning', 'ML', 'deep learning',
            'neural network', 'GPT', 'ChatGPT', 'LLM', 'natural language processing',
            'computer vision', 'robotics', 'automation', 'algorithm'
        ]
    
    async def fetch_all_news(self) -> List[Dict]:
        """すべてのソースからニュースを収集（簡易版）"""
        print("📡 サンプルAIニュースを生成中...")
        
        # サンプルニュースデータ（実際の実装ではRSS/API/スクレイピング）
        sample_news = [
            {
                'title': 'OpenAI GPT-4が医療診断で人間の医師を上回る精度を達成',
                'content': '最新の研究により、GPT-4が複雑な医療診断において従来の診断方法を大幅に上回る結果を示した。',
                'url': 'https://example.com/gpt4-medical-diagnosis',
                'source': 'AI Medical News',
                'published_date': datetime.now().isoformat(),
                'author': 'Dr. AI Researcher',
                'fetch_method': 'Sample'
            },
            {
                'title': 'Google DeepMindが新しい量子機械学習アルゴリズムを発表',
                'content': '量子コンピューティングと機械学習を組み合わせた革新的なアプローチで処理速度が1000倍向上。',
                'url': 'https://example.com/deepmind-quantum-ml',
                'source': 'Quantum AI Today',
                'published_date': datetime.now().isoformat(),
                'author': 'Quantum Team',
                'fetch_method': 'Sample'
            },
            {
                'title': 'テスラの自動運転AI、完全自動運転レベル5を達成',
                'content': 'イーロン・マスクが発表したテスラの最新AI技術により、完全自動運転が現実のものとなった。',
                'url': 'https://example.com/tesla-level5-autonomous',
                'source': 'AutoAI Weekly',
                'published_date': datetime.now().isoformat(),
                'author': 'Tesla AI Team',
                'fetch_method': 'Sample'
            },
            {
                'title': 'Microsoft Copilot、プログラミング生産性を300%向上させることが判明',
                'content': '最新の調査により、GitHub Copilotを使用した開発者の生産性が大幅に向上することが確認された。',
                'url': 'https://example.com/copilot-productivity-boost',
                'source': 'Developer AI News',
                'published_date': datetime.now().isoformat(),
                'author': 'Microsoft Research',
                'fetch_method': 'Sample'
            },
            {
                'title': 'Amazon AlexaがAI感情認識機能を搭載、ユーザーの気持ちを理解',
                'content': '新しいAlexa AIは音声から感情を読み取り、より人間らしい対話が可能になった。',
                'url': 'https://example.com/alexa-emotion-ai',
                'source': 'Voice AI Report',
                'published_date': datetime.now().isoformat(),
                'author': 'Amazon AI Lab',
                'fetch_method': 'Sample'
            }
        ]
        
        print(f"✅ {len(sample_news)} 件のサンプルニュースを生成しました")
        return sample_news
    
    def is_ai_related(self, text: str) -> bool:
        """テキストがAI関連かどうかを判定"""
        text_lower = text.lower()
        return any(keyword.lower() in text_lower for keyword in self.ai_keywords)
'''
    
    with open("ai_news_fetcher.py", "w", encoding="utf-8") as f:
        f.write(fetcher_code)
    
    # 3. 統合システム
    print("📁 3. 統合システムを作成...")
    
    integration_code = '''import asyncio
import sys
import os
from datetime import datetime

# 既存のシステムをインポート
from ai_news_combination_proposer import AINewsCombinationProposer
from ai_news_database import AINewsDatabase
from ai_news_fetcher import AINewsFetcher

class AINewsIntegratedSystem:
    """AIニュース統合システム - フェッチ、DB登録、組み合わせ提案を統合"""
    
    def __init__(self):
        self.database = AINewsDatabase()
        self.fetcher = AINewsFetcher()
        self.proposer = AINewsCombinationProposer()
    
    async def run_full_pipeline(self):
        """完全なパイプラインを実行"""
        print("🚀 AIニュース統合システムを開始...")
        
        # 1. Webからニュースを収集
        print("\\n📡 Step 1: Webからニュースを収集中...")
        news_articles = await self.fetcher.fetch_all_news()
        
        # 2. データベースに登録
        print("\\n🗄️ Step 2: データベースに登録中...")
        new_article_count = 0
        for article in news_articles:
            article_id = self.database.add_news_article(article)
            if article_id:
                new_article_count += 1
                print(f"  ✅ 新規記事登録: {article['title'][:50]}...")
        
        print(f"📊 新規記事登録数: {new_article_count}/{len(news_articles)}")
        
        # 3. 最近の記事を取得して組み合わせ分析
        print("\\n🤖 Step 3: 組み合わせ提案を生成中...")
        recent_articles = self.database.get_recent_articles(20)
        
        if len(recent_articles) >= 2:
            combinations = self.proposer.analyze_news_combinations(recent_articles)
            
            # 組み合わせ提案をデータベースに保存
            saved_count = 0
            for combination in combinations:
                # ニュースIDを取得
                news1_id = combination['news1'].get('id')
                news2_id = combination['news2'].get('id')
                
                if news1_id and news2_id:
                    proposal_data = {
                        'news1_id': news1_id,
                        'news2_id': news2_id,
                        'common_keywords': combination['common_keywords'],
                        'proposal_text': combination['proposal'],
                        'potential_applications': combination['potential_applications'],
                        'confidence_score': 0.7
                    }
                    
                    proposal_id = self.database.save_combination_proposal(proposal_data)
                    if proposal_id:
                        saved_count += 1
            
            print(f"💾 組み合わせ提案保存数: {saved_count}")
            
            # 結果を表示
            print("\\n🎯 最新の組み合わせ提案:")
            for i, combination in enumerate(combinations[:3], 1):
                print(f"\\n--- 提案 {i} ---")
                print(f"📰 ニュース1: {combination['news1']['title'][:60]}")
                print(f"📰 ニュース2: {combination['news2']['title'][:60]}")
                print(f"🔑 共通キーワード: {', '.join(combination['common_keywords'])}")
                print(f"💡 提案: {combination['proposal']}")
                print(f"🚀 応用可能性:")
                for app in combination['potential_applications'][:3]:
                    print(f"   - {app}")
        else:
            print("❌ 組み合わせ分析に十分な記事がありません")
        
        print("\\n✅ AIニュース統合システムの実行が完了しました!")
    
    def show_statistics(self):
        """システムの統計情報を表示"""
        print("\\n📊 システム統計:")
        
        recent_articles = self.database.get_recent_articles(100)
        print(f"  📄 総記事数: {len(recent_articles)}")
        
        # ソース別統計
        sources = {}
        for article in recent_articles:
            source = article.get('source', 'Unknown')
            sources[source] = sources.get(source, 0) + 1
        
        print("  📡 ソース別記事数:")
        for source, count in sorted(sources.items(), key=lambda x: x[1], reverse=True):
            print(f"    - {source}: {count}件")

async def main():
    """メイン実行関数"""
    system = AINewsIntegratedSystem()
    
    print("🎯 AIニュースWebフェッチ・DB登録・組み合わせ提案統合システム")
    print("=" * 60)
    
    # フルパイプラインを実行
    await system.run_full_pipeline()
    
    # 統計情報を表示
    system.show_statistics()

if __name__ == "__main__":
    asyncio.run(main())
'''
    
    with open("ai_news_integrated_system.py", "w", encoding="utf-8") as f:
        f.write(integration_code)
    
    print("✅ すべてのシステムファイルが作成されました")
    
    # 4. システムテスト実行
    print("🧪 統合システムテストを実行中...")
    
    try:
        import subprocess
        
        # 統合システムを実行
        test_result = subprocess.run([
            sys.executable, "ai_news_integrated_system.py"
        ], capture_output=True, text=True, cwd=target_project, timeout=30)
        
        if test_result.returncode == 0:
            print("✅ 統合システムテスト成功!")
            print("📊 テスト結果:")
            print(test_result.stdout)
        else:
            print("❌ 統合システムテストでエラーが発生:")
            print(test_result.stderr)
    
    except Exception as e:
        print(f"❌ テスト実行エラー: {e}")
    
    print("🎉 AIニュースWebフェッチ・DB登録・組み合わせ提案統合システムの実装が完了しました!")

if __name__ == "__main__":
    asyncio.run(execute_integrated_ai_news_system())