#!/usr/bin/env python3
"""
naシステムのデバッグ・診断スクリプト
問題の切り分けと原因特定を行う
"""

import asyncio
import json
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path

# プロジェクトのパスを追加
sys.path.append(str(Path(__file__).parent / "src"))

async def debug_na_system():
    """naシステムの包括的診断を実行"""
    
    print("🔍 naシステム診断・デバッグを開始...")
    print("=" * 60)
    
    # 1. 基本環境の確認
    print("\n📋 1. 基本環境の確認")
    print("-" * 30)
    
    print(f"Python バージョン: {sys.version}")
    print(f"作業ディレクトリ: {os.getcwd()}")
    print(f"現在時刻: {datetime.now()}")
    
    # 2. naコマンド自体の動作確認
    print("\n🔧 2. naコマンドの基本動作確認")
    print("-" * 30)
    
    import subprocess
    
    try:
        result = subprocess.run(["na", "--help"], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print("✅ naコマンド実行可能")
            print(f"バージョン確認: {result.stdout[:200]}...")
        else:
            print(f"❌ naコマンドエラー: {result.stderr}")
    except Exception as e:
        print(f"❌ naコマンド実行失敗: {e}")
    
    # 3. Ollamaサーバーの状態確認
    print("\n🤖 3. Ollamaサーバーの状態確認")
    print("-" * 30)
    
    try:
        # Ollamaサーバーのステータス確認
        result = subprocess.run(["curl", "-s", "http://localhost:11434/api/version"], 
                               capture_output=True, text=True, timeout=5)
        if result.returncode == 0 and result.stdout:
            print("✅ Ollamaサーバー稼働中")
            print(f"バージョン: {result.stdout}")
        else:
            print("❌ Ollamaサーバー停止中")
            
            # Ollamaサーバーを起動してみる
            print("🚀 Ollamaサーバーを起動中...")
            start_result = subprocess.run(["ollama", "serve"], 
                                        capture_output=True, text=True, timeout=10)
            print(f"起動結果: {start_result.returncode}")
            
    except Exception as e:
        print(f"❌ Ollamaサーバー確認失敗: {e}")
    
    # 4. モデルの確認
    print("\n📦 4. 利用可能モデルの確認")
    print("-" * 30)
    
    try:
        result = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print("✅ インストール済みモデル:")
            print(result.stdout)
        else:
            print(f"❌ モデル一覧取得失敗: {result.stderr}")
    except Exception as e:
        print(f"❌ モデル確認失敗: {e}")
    
    # 5. 設定ファイルの確認
    print("\n⚙️ 5. naシステム設定の確認")
    print("-" * 30)
    
    config_path = "/Users/tsutomusaito/git/nocturnal-agent/config/nocturnal-agent.yaml"
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config_content = f.read()
        print("✅ 設定ファイル読み込み成功")
        
        # LLM関連設定の抽出
        llm_config_lines = [line for line in config_content.split('\n') 
                           if 'llm:' in line or 'model' in line or 'timeout' in line or 'api_url' in line]
        print("🔧 LLM関連設定:")
        for line in llm_config_lines[:10]:
            print(f"  {line}")
            
    except Exception as e:
        print(f"❌ 設定ファイル読み込み失敗: {e}")
    
    # 6. レビューセッションの状態確認
    print("\n📝 6. レビューセッションの状態確認")
    print("-" * 30)
    
    ai_news_dig_path = "/Users/tsutomusaito/git/ai-news-dig"
    review_sessions_path = f"{ai_news_dig_path}/.nocturnal/review_sessions"
    
    try:
        if os.path.exists(review_sessions_path):
            sessions = os.listdir(review_sessions_path)
            sessions = [s for s in sessions if s.endswith('.json')]
            sessions.sort()
            
            print(f"✅ レビューセッション数: {len(sessions)}")
            
            if sessions:
                latest_session = sessions[-1]
                print(f"📋 最新セッション: {latest_session}")
                
                # 最新セッションの詳細確認
                with open(f"{review_sessions_path}/{latest_session}", 'r', encoding='utf-8') as f:
                    session_data = json.load(f)
                
                print(f"  ステータス: {session_data.get('status', 'Unknown')}")
                print(f"  作成日時: {session_data.get('created_at', 'Unknown')}")
                print(f"  タスク: {session_data.get('task', {}).get('description', 'Unknown')[:60]}...")
                
                # フィードバック履歴
                feedback_history = session_data.get('feedback_history', [])
                print(f"  フィードバック数: {len(feedback_history)}")
                if feedback_history:
                    for fb in feedback_history[-2:]:  # 最新2件
                        print(f"    - {fb.get('type', 'Unknown')}: {fb.get('timestamp', '')}")
        else:
            print("❌ レビューセッションディレクトリが存在しません")
            
    except Exception as e:
        print(f"❌ レビューセッション確認失敗: {e}")
        traceback.print_exc()
    
    # 7. ローカルLLMインターフェースの直接テスト
    print("\n🧪 7. ローカルLLMインターフェースのテスト")
    print("-" * 30)
    
    try:
        from nocturnal_agent.llm.local_llm_interface import LocalLLMInterface
        from nocturnal_agent.config.nocturnal_config import NocturnalConfig
        
        # 設定を読み込み
        config = NocturnalConfig(config_path)
        llm_interface = LocalLLMInterface(config)
        
        print("✅ ローカルLLMインターフェース初期化成功")
        
        # 簡単なテスト実行
        print("🔍 簡単なテスト実行中...")
        
        test_prompt = "Hello, can you respond with 'OK' in JSON format?"
        
        try:
            response = await llm_interface._call_llm(test_prompt, max_tokens=50)
            print(f"✅ LLM応答テスト成功: {response[:100]}...")
        except Exception as llm_error:
            print(f"❌ LLM応答テスト失敗: {llm_error}")
            traceback.print_exc()
            
    except Exception as e:
        print(f"❌ ローカルLLMインターフェーステスト失敗: {e}")
        traceback.print_exc()
    
    # 8. 最新のタイムアウトエラーの詳細確認
    print("\n⏱️ 8. タイムアウト問題の詳細確認")
    print("-" * 30)
    
    # 最新のエラーログを確認
    error_log_path = "/Users/tsutomusaito/git/nocturnal-agent/logs/errors.jsonl"
    if os.path.exists(error_log_path):
        try:
            with open(error_log_path, 'r', encoding='utf-8') as f:
                error_lines = f.readlines()
            
            if error_lines:
                print(f"✅ エラーログ確認: {len(error_lines)}件のエラー")
                
                # 最新のエラーを表示
                for line in error_lines[-3:]:  # 最新3件
                    try:
                        error_data = json.loads(line.strip())
                        print(f"  🚨 {error_data.get('timestamp', '')}: {error_data.get('message', '')[:80]}...")
                    except:
                        print(f"  🚨 {line.strip()[:80]}...")
            else:
                print("✅ エラーログは空です")
        except Exception as e:
            print(f"❌ エラーログ読み込み失敗: {e}")
    else:
        print("ℹ️ エラーログファイルが存在しません")
    
    # 9. 診断結果のまとめ
    print("\n📊 9. 診断結果まとめ")
    print("-" * 30)
    
    print("🔍 問題の可能性:")
    print("  1. Ollamaサーバーの停止またはモデル不足")
    print("  2. ネットワークタイムアウト設定の問題")
    print("  3. レビューセッションの状態管理不具合")
    print("  4. 協調システムの通信エラー")
    print("  5. 設定ファイルの不整合")
    
    print("\n🛠️ 推奨対応:")
    print("  1. Ollamaサーバーの手動起動とモデル確認")
    print("  2. タイムアウト値の調整（現在10分→15分）")
    print("  3. ログレベルをDEBUGに変更して詳細確認")
    print("  4. シンプルなテストケースで段階的確認")
    
    print("\n✅ 診断完了")

async def test_simple_review_session():
    """シンプルなレビューセッションで基本機能をテスト"""
    
    print("\n🧪 シンプルなレビューセッションテスト")
    print("=" * 40)
    
    import subprocess
    
    # 1. 最もシンプルなタスクでテスト
    print("📋 最小限のタスクでレビューセッション作成...")
    
    cmd = [
        "na", "review", "start", 
        "シンプルテスト", 
        "--description", "最小限のテスト用タスクです",
        "--priority", "low"
    ]
    
    try:
        # ai-news-digディレクトリで実行
        result = subprocess.run(
            cmd, 
            cwd="/Users/tsutomusaito/git/ai-news-dig",
            capture_output=True, 
            text=True, 
            timeout=30  # 30秒でタイムアウト
        )
        
        if result.returncode == 0:
            print("✅ シンプルレビューセッション作成成功")
            print(f"出力: {result.stdout[-200:]}")
        else:
            print(f"❌ シンプルレビューセッション作成失敗")
            print(f"エラー: {result.stderr}")
            
    except subprocess.TimeoutExpired:
        print("⏱️ シンプルテストもタイムアウト（30秒）")
        print("→ 根本的なサーバー起動問題の可能性")
    except Exception as e:
        print(f"❌ シンプルテスト実行エラー: {e}")

if __name__ == "__main__":
    print("🚀 naシステム包括診断を開始...")
    
    # 基本診断を実行
    asyncio.run(debug_na_system())
    
    # シンプルテストを実行
    asyncio.run(test_simple_review_session())