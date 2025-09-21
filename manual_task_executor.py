#!/usr/bin/env python3
"""
手動でAIニュース組み合わせ提案システムを実行するスクリプト
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# プロジェクトのパスを追加
sys.path.append(str(Path(__file__).parent / "src"))

async def execute_ai_news_combination_system():
    """AIニュース組み合わせ提案システムを手動実行"""
    
    print("🚀 AIニュースWebフェッチ・DB登録・組み合わせ提案統合システムの手動実行を開始...")
    
    # ai-news-digプロジェクトのパス
    target_project = "/Users/tsutomusaito/git/ai-news-dig"
    os.chdir(target_project)
    
    # 最新のレビューセッションの詳細を読み込み
    review_session_path = target_project + "/.nocturnal/review_sessions/review_20250920_211203.json"
    
    if not os.path.exists(review_session_path):
        print(f"❌ レビューセッションが見つかりません: {review_session_path}")
        return
    
    with open(review_session_path, 'r', encoding='utf-8') as f:
        review_data = json.load(f)
    
    print(f"📋 タスク: {review_data['task']['description']}")
    print(f"📊 ステータス: {review_data['status']}")
    
    # 承認済みの場合は実行
    if any(feedback['type'] == 'approve' for feedback in review_data['feedback_history']):
        print("✅ 承認済みタスクを実行中...")
        
        # 実際の実装作業を開始
        await implement_ai_news_web_fetch_system(target_project, review_data)
        
        print("🎉 AIニュースWebフェッチ・DB登録・組み合わせ提案統合システムの実装が完了しました！")
    else:
        print("❌ タスクが承認されていません")

async def implement_ai_news_web_fetch_system(project_path: str, review_data: dict):
    """AIニュースWebフェッチ・DB登録・組み合わせ提案統合システムの実装"""
    
    print("🔧 AIニュースWebフェッチ・DB登録・組み合わせ提案統合システム実装を開始...")
    
    # 1. 既存のシステムを確認
    print("📁 既存プロジェクト構造を確認中...")
    
    existing_files = []
    for file in os.listdir(project_path):
        if file.endswith('.py'):
            existing_files.append(file)
            print(f"  ✅ {file}")
    
    # 2. データベーススキーマの作成
    print("🗄️ SQLiteデータベーススキーマを作成中...")
    
    db_schema = '''import sqlite3
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
        cursor.execute('''
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
        ''')
        
        # 組み合わせ提案テーブル
        cursor.execute('''
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
        ''')
        
        # フェッチログテーブル
        cursor.execute('''
CREATE TABLE IF NOT EXISTS fetch_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_type TEXT,
                source_url TEXT,
                fetch_count INTEGER,
                success_count INTEGER,
                error_count INTEGER,
                last_fetch_time TEXT,
                status TEXT
            )
        ''')
        
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
            cursor.execute('''
INSERT INTO news_articles 
                (title, content, url, source, published_date, author, keywords, content_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
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
        
        cursor.execute('''
SELECT id, title, content, url, source, published_date, author, keywords
            FROM news_articles 
            ORDER BY created_at DESC 
            LIMIT ?
        ''', (limit,))
        
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
        
        cursor.execute('''
INSERT INTO combination_proposals 
            (news1_id, news2_id, common_keywords, proposal_text, potential_applications, confidence_score)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
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
    
    db_file = os.path.join(project_path, "ai_news_database.py")
    with open(db_file, 'w', encoding='utf-8') as f:
        f.write(db_schema)
    
    print(f"✅ データベース管理システムを作成: {db_file}")
    
    # 3. Webフェッチャーの作成
    print("🌐 Webニュースフェッチャーを作成中...")
    
    web_fetcher_code = '''import requests
import feedparser
from bs4 import BeautifulSoup
import asyncio
import aiohttp
from datetime import datetime
from typing import List, Dict
import re

class AINewsFetcher:
    """AIニュースをWebから収集するクラス"""
    
    def __init__(self):
        self.rss_feeds = [
            'https://feeds.feedburner.com/venturebeat/ai',
            'https://www.artificialintelligence-news.com/feed/',
            'https://machinelearningmastery.com/feed/',
            'https://hai.stanford.edu/news/rss.xml',
            'https://www.deeplearning.ai/feed/'
        ]
        
        self.ai_keywords = [
            'artificial intelligence', 'AI', 'machine learning', 'ML', 'deep learning',
            'neural network', 'GPT', 'ChatGPT', 'LLM', 'natural language processing',
            'computer vision', 'robotics', 'automation', 'algorithm'
        ]
    
    async def fetch_all_news(self) -> List[Dict]:
        """すべてのソースからニュースを収集"""
        all_news = []
        
        print("📡 RSSフィードからニュースを収集中...")
        rss_news = await self.fetch_rss_news()
        all_news.extend(rss_news)
        
        print("🔍 AI関連サイトをスクレイピング中...")
        scraped_news = await self.scrape_ai_news_sites()
        all_news.extend(scraped_news)
        
        print("🎯 APIからニュースを取得中...")
        api_news = await self.fetch_api_news()
        all_news.extend(api_news)
        
        # 重複除去
        unique_news = self.remove_duplicates(all_news)
        
        print(f"✅ 合計 {len(unique_news)} 件のユニークなニュースを収集しました")
        return unique_news
    
    async def fetch_rss_news(self) -> List[Dict]:
        """RSSフィードからニュースを取得"""
        news_list = []
        
        for feed_url in self.rss_feeds:
            try:
                print(f"  📄 RSS取得中: {feed_url}")
                feed = feedparser.parse(feed_url)
                
                for entry in feed.entries[:10]:  # 最新10件
                    if self.is_ai_related(entry.get('title', '') + ' ' + entry.get('summary', '')):
                        news_item = {
                            'title': entry.get('title', ''),
                            'content': entry.get('summary', ''),
                            'url': entry.get('link', ''),
                            'source': feed.feed.get('title', 'RSS Feed'),
                            'published_date': entry.get('published', ''),
                            'author': entry.get('author', ''),
                            'fetch_method': 'RSS'
                        }
                        news_list.append(news_item)
                        
            except Exception as e:
                print(f"    ❌ RSS取得エラー ({feed_url}): {e}")
        
        return news_list
    
    async def scrape_ai_news_sites(self) -> List[Dict]:
        """AI関連サイトをスクレイピング"""
        news_list = []
        
        # AI関連サイトのURL
        ai_sites = [
            'https://www.artificialintelligence-news.com/',
            'https://venturebeat.com/ai/',
            'https://www.theverge.com/ai-artificial-intelligence'
        ]
        
        async with aiohttp.ClientSession() as session:
            for site_url in ai_sites:
                try:
                    print(f"  🕷️ スクレイピング中: {site_url}")
                    async with session.get(site_url, timeout=10) as response:
                        if response.status == 200:
                            html = await response.text()
                            soup = BeautifulSoup(html, 'html.parser')
                            
                            # 記事のタイトルとリンクを抽出（サイトによって構造が異なる）
                            articles = soup.find_all(['article', 'div'], class_=re.compile(r'article|post|news'))[:5]
                            
                            for article in articles:
                                title_elem = article.find(['h1', 'h2', 'h3', 'a'])
                                if title_elem:
                                    title = title_elem.get_text(strip=True)
                                    if self.is_ai_related(title):
                                        link = title_elem.get('href') if title_elem.name == 'a' else None
                                        if link and not link.startswith('http'):
                                            link = f"{site_url.rstrip('/')}/{link.lstrip('/')}"
                                        
                                        news_item = {
                                            'title': title,
                                            'content': title,  # 詳細は後で取得可能
                                            'url': link or site_url,
                                            'source': site_url,
                                            'published_date': datetime.now().isoformat(),
                                            'author': '',
                                            'fetch_method': 'Scraping'
                                        }
                                        news_list.append(news_item)
                                        
                except Exception as e:
                    print(f"    ❌ スクレイピングエラー ({site_url}): {e}")
        
        return news_list
    
    async def fetch_api_news(self) -> List[Dict]:
        """News APIなどからニュースを取得"""
        news_list = []
        
        # News API (要API Key)
        # api_key = os.getenv('NEWS_API_KEY')
        # if api_key:
        #     # News API実装
        #     pass
        
        # GitHub Trending AI projects (簡易実装)
        try:
            async with aiohttp.ClientSession() as session:
                url = "https://api.github.com/search/repositories?q=artificial+intelligence&sort=stars&order=desc"
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        for repo in data.get('items', [])[:3]:
                            news_item = {
                                'title': f"AI Project: {repo['name']}",
                                'content': repo.get('description', ''),
                                'url': repo['html_url'],
                                'source': 'GitHub Trending',
                                'published_date': repo.get('created_at', ''),
                                'author': repo.get('owner', {}).get('login', ''),
                                'fetch_method': 'API'
                            }
                            news_list.append(news_item)
        except Exception as e:
            print(f"    ❌ GitHub API エラー: {e}")
        
        return news_list
    
    def is_ai_related(self, text: str) -> bool:
        """テキストがAI関連かどうかを判定"""
        text_lower = text.lower()
        return any(keyword.lower() in text_lower for keyword in self.ai_keywords)
    
    def remove_duplicates(self, news_list: List[Dict]) -> List[Dict]:
        """重複記事を除去"""
        seen_titles = set()
        unique_news = []
        
        for news in news_list:
            title_hash = hash(news.get('title', '').lower().strip())
            if title_hash not in seen_titles:
                seen_titles.add(title_hash)
                unique_news.append(news)
        
        return unique_news
'''
    
    fetcher_file = os.path.join(project_path, "ai_news_fetcher.py")
    with open(fetcher_file, 'w', encoding='utf-8') as f:
        f.write(web_fetcher_code)
    
    print(f"✅ Webフェッチャーを作成: {fetcher_file}")
    
    # 4. 統合システムの作成
    print("🔗 統合システムを作成中...")
    
    integration_code = f'''import asyncio
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
                print(f"  ✅ 新規記事登録: {{article['title'][:50]}}...")
        
        print(f"📊 新規記事登録数: {{new_article_count}}/{{len(news_articles)}}")
        
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
                    proposal_data = {{
                        'news1_id': news1_id,
                        'news2_id': news2_id,
                        'common_keywords': combination['common_keywords'],
                        'proposal_text': combination['proposal'],
                        'potential_applications': combination['potential_applications'],
                        'confidence_score': 0.7
                    }}
                    
                    proposal_id = self.database.save_combination_proposal(proposal_data)
                    if proposal_id:
                        saved_count += 1
            
            print(f"💾 組み合わせ提案保存数: {{saved_count}}")
            
            # 結果を表示
            print("\\n🎯 最新の組み合わせ提案:")
            for i, combination in enumerate(combinations[:3], 1):
                print(f"\\n--- 提案 {{i}} ---")
                print(f"📰 ニュース1: {{combination['news1']['title'][:60]}}...")
                print(f"📰 ニュース2: {{combination['news2']['title'][:60]}}...")
                print(f"🔑 共通キーワード: {{', '.join(combination['common_keywords'])}}")
                print(f"💡 提案: {{combination['proposal']}}")
                print(f"🚀 応用可能性:")
                for app in combination['potential_applications'][:3]:
                    print(f"   - {{app}}")
        else:
            print("❌ 組み合わせ分析に十分な記事がありません")
        
        print("\\n✅ AIニュース統合システムの実行が完了しました!")
    
    def show_statistics(self):
        """システムの統計情報を表示"""
        print("\\n📊 システム統計:")
        
        recent_articles = self.database.get_recent_articles(100)
        print(f"  📄 総記事数: {{len(recent_articles)}}")
        
        # ソース別統計
        sources = {{}}
        for article in recent_articles:
            source = article.get('source', 'Unknown')
            sources[source] = sources.get(source, 0) + 1
        
        print("  📡 ソース別記事数:")
        for source, count in sorted(sources.items(), key=lambda x: x[1], reverse=True):
            print(f"    - {{source}}: {{count}}件")

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
    # 必要なライブラリの確認とインストール案内
    try:
        import requests
        import feedparser
        import aiohttp
        from bs4 import BeautifulSoup
    except ImportError as e:
        print(f"❌ 必要なライブラリが不足しています: {{e}}")
        print("以下のコマンドでインストールしてください:")
        print("pip install requests feedparser aiohttp beautifulsoup4")
        sys.exit(1)
    
    asyncio.run(main())
'''
    
    integrated_file = os.path.join(project_path, "ai_news_integrated_system.py")
    with open(integrated_file, 'w', encoding='utf-8') as f:
        f.write(integration_code)
    
    print(f"✅ 統合システムを作成: {integrated_file}")
    
    # 5. requirements.txtの作成
    print("📦 requirements.txtを作成中...")
    
    requirements = '''requests>=2.25.1
feedparser>=6.0.8
aiohttp>=3.8.0
beautifulsoup4>=4.9.3
sqlite3
hashlib
'''
    
    requirements_file = os.path.join(project_path, "requirements.txt")
    with open(requirements_file, 'w', encoding='utf-8') as f:
        f.write(requirements.strip())
    
    print(f"✅ 依存関係ファイルを作成: {requirements_file}")
    
    # 6. システムテストの実行
    print("🧪 統合システムテストを実行中...")
    
    try:
        # 必要なライブラリをインストール
        import subprocess
        install_result = subprocess.run([
            sys.executable, "-m", "pip", "install", "requests", "feedparser", "aiohttp", "beautifulsoup4"
        ], capture_output=True, text=True)
        
        if install_result.returncode == 0:
            print("✅ 依存関係のインストール完了")
            
            # 統合システムを実行
            test_result = subprocess.run([
                sys.executable, integrated_file
            ], capture_output=True, text=True, cwd=project_path, timeout=60)
            
            if test_result.returncode == 0:
                print("✅ 統合システムテスト成功!")
                print("📊 テスト結果:")
                print(test_result.stdout[-1000:])  # 最後の1000文字を表示
            else:
                print("❌ 統合システムテストでエラーが発生:")
                print(test_result.stderr)
        else:
            print("❌ 依存関係のインストールでエラーが発生:")
            print(install_result.stderr)
    
    except Exception as e:
        print(f"❌ テスト実行エラー: {{e}}")
    
    print("🎉 AIニュースWebフェッチ・DB登録・組み合わせ提案統合システムの実装が完了しました!")

async def implement_ai_news_combination_system(project_path: str, review_data: dict):
    """AIニュース組み合わせ提案システムの実装"""
    
    print("🔧 システム実装を開始...")
    
    # 1. 既存のシステムを確認
    print("📁 既存プロジェクト構造を確認中...")
    
    # 主要なファイルをチェック
    main_files = [
        "main.py",
        "app.py", 
        "requirements.txt",
        "README.md"
    ]
    
    existing_files = []
    for file in main_files:
        file_path = os.path.join(project_path, file)
        if os.path.exists(file_path):
            existing_files.append(file)
            print(f"  ✅ {file}")
        else:
            print(f"  ❌ {file}")
    
    # 2. AIニュース組み合わせ提案機能の実装
    print("🤖 AIニュース組み合わせ提案機能を実装中...")
    
    # 組み合わせ提案システムのコード
    combination_system_code = '''
# AIニュース組み合わせ提案システム
class AINewsCombinationProposer:
    """AIニュースの組み合わせを分析し、新しい可能性を提案するシステム"""
    
    def __init__(self):
        self.news_database = []
        self.combination_patterns = []
    
    def analyze_news_combinations(self, news_list):
        """ニュース記事の組み合わせを分析"""
        combinations = []
        
        for i, news1 in enumerate(news_list):
            for j, news2 in enumerate(news_list[i+1:], i+1):
                combination = self.create_combination_proposal(news1, news2)
                if combination:
                    combinations.append(combination)
        
        return combinations
    
    def create_combination_proposal(self, news1, news2):
        """2つのニュースから組み合わせ提案を生成"""
        # キーワード抽出
        keywords1 = self.extract_keywords(news1)
        keywords2 = self.extract_keywords(news2)
        
        # 共通要素の発見
        common_elements = set(keywords1) & set(keywords2)
        
        if common_elements:
            return {
                'news1': news1,
                'news2': news2,
                'common_keywords': list(common_elements),
                'proposal': self.generate_proposal_text(news1, news2, common_elements),
                'potential_applications': self.suggest_applications(news1, news2)
            }
        
        return None
    
    def extract_keywords(self, news_item):
        """ニュース記事からキーワードを抽出"""
        # 簡単な実装（実際はより高度なNLP処理が必要）
        text = news_item.get('title', '') + ' ' + news_item.get('content', '')
        
        # AI関連キーワード
        ai_keywords = ['AI', '人工知能', '機械学習', 'ML', 'LLM', 'GPT', 'ChatGPT', 
                      '深層学習', 'ディープラーニング', '自然言語処理', 'NLP']
        
        # 技術キーワード
        tech_keywords = ['API', 'クラウド', 'IoT', 'ブロックチェーン', 'AR', 'VR', 
                        '5G', 'エッジコンピューティング', 'コンテナ', 'Kubernetes']
        
        # 産業キーワード
        industry_keywords = ['自動車', '医療', '金融', '教育', '製造業', '農業', 
                           '物流', '小売', 'エンターテイメント', 'ゲーム']
        
        all_keywords = ai_keywords + tech_keywords + industry_keywords
        
        found_keywords = []
        for keyword in all_keywords:
            if keyword in text:
                found_keywords.append(keyword)
        
        return found_keywords
    
    def generate_proposal_text(self, news1, news2, common_elements):
        """組み合わせ提案テキストを生成"""
        return f"「{news1.get('title', 'ニュース1')}」と「{news2.get('title', 'ニュース2')}」を組み合わせることで、{', '.join(common_elements)}の分野で新しい可能性が生まれるかもしれません。"
    
    def suggest_applications(self, news1, news2):
        """具体的な応用例を提案"""
        applications = [
            "既存サービスの機能拡張",
            "新しいビジネスモデルの創出", 
            "技術的課題の解決策",
            "ユーザー体験の向上",
            "コスト削減の実現"
        ]
        
        return applications[:3]  # 上位3つを返す
'''
    
    # 組み合わせ提案システムをファイルに保存
    combination_file = os.path.join(project_path, "ai_news_combination_proposer.py")
    with open(combination_file, 'w', encoding='utf-8') as f:
        f.write(combination_system_code)
    
    print(f"✅ 組み合わせ提案システムを作成: {combination_file}")
    
    # 3. 統合コードの作成
    print("🔗 既存システムとの統合コードを作成中...")
    
    integration_code = '''
# AIニュース組み合わせ提案システム統合
from ai_news_combination_proposer import AINewsCombinationProposer

def integrate_combination_system():
    """既存のAIニュースシステムに組み合わせ提案機能を統合"""
    
    print("🤖 AIニュース組み合わせ提案システムを初期化中...")
    proposer = AINewsCombinationProposer()
    
    # サンプルニュースデータ（実際は既存のDBから取得）
    sample_news = [
        {
            'title': 'ChatGPT APIを活用した新しい教育プラットフォーム',
            'content': '人工知能を活用した個別学習支援システムが開発された',
            'source': 'AI Education News'
        },
        {
            'title': 'IoTセンサーを使った農業の自動化',
            'content': 'IoT技術とAIを組み合わせたスマート農業が普及中',
            'source': 'Smart Agriculture Today'
        },
        {
            'title': '医療現場でのAI診断支援システム',
            'content': '機械学習を活用した画像診断の精度が向上',
            'source': 'Medical AI Report'
        }
    ]
    
    print("📊 ニュース組み合わせ分析を実行中...")
    combinations = proposer.analyze_news_combinations(sample_news)
    
    print(f"🎯 {len(combinations)}件の組み合わせ提案を生成しました:")
    
    for i, combination in enumerate(combinations, 1):
        print(f"\\n--- 提案 {i} ---")
        print(f"📰 ニュース1: {combination['news1']['title']}")
        print(f"📰 ニュース2: {combination['news2']['title']}")
        print(f"🔑 共通キーワード: {', '.join(combination['common_keywords'])}")
        print(f"💡 提案: {combination['proposal']}")
        print(f"🚀 応用可能性:")
        for app in combination['potential_applications']:
            print(f"   - {app}")
    
    return combinations

if __name__ == "__main__":
    integrate_combination_system()
'''
    
    integration_file = os.path.join(project_path, "integration_demo.py")
    with open(integration_file, 'w', encoding='utf-8') as f:
        f.write(integration_code)
    
    print(f"✅ 統合デモを作成: {integration_file}")
    
    # 4. 実際に実行してテスト
    print("🧪 システムテストを実行中...")
    
    try:
        # Pythonファイルを実行
        import subprocess
        result = subprocess.run([sys.executable, integration_file], 
                              capture_output=True, text=True, cwd=project_path)
        
        if result.returncode == 0:
            print("✅ システムテスト成功!")
            print("📊 テスト結果:")
            print(result.stdout)
        else:
            print("❌ システムテストでエラーが発生:")
            print(result.stderr)
    
    except Exception as e:
        print(f"❌ テスト実行エラー: {e}")
    
    print("🎉 AIニュース組み合わせ提案システムの実装が完了しました!")

if __name__ == "__main__":
    asyncio.run(execute_ai_news_combination_system())