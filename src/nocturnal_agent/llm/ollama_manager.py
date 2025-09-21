#!/usr/bin/env python3
"""
Ollama Server Manager - 10分タイムアウト設定での確実な起動管理
Nocturnal Agent AI協調システム用
"""

import os
import time
import asyncio
import subprocess
import logging
from typing import Optional
import aiohttp


class OllamaManager:
    """Ollamaサーバーの起動・管理クラス"""
    
    def __init__(self, api_url: str = "http://localhost:11434"):
        self.api_url = api_url
        self.logger = logging.getLogger(__name__)
        self._process: Optional[subprocess.Popen] = None
        
    def start_server_with_timeout(self) -> bool:
        """10分タイムアウト設定でOllamaサーバーを起動"""
        self.logger.info("🚀 Ollama サーバーを10分タイムアウト設定で起動中...")
        
        try:
            # 既存プロセスを停止
            self.stop_server()
            
            # 環境変数設定
            env = os.environ.copy()
            env.update({
                'OLLAMA_LOAD_TIMEOUT': '600',        # 10分
                'OLLAMA_KEEP_ALIVE': '10m',          # 10分
                'OLLAMA_NUM_PARALLEL': '1',          # 並列処理制限
                'OLLAMA_CONTEXT_LENGTH': '4096'      # コンテキスト長制限
            })
            
            # サーバー起動
            self._process = subprocess.Popen(
                ['ollama', 'serve'],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # 起動確認（最大30秒待機）
            for i in range(30):
                time.sleep(1)
                if self.check_server_status():
                    self.logger.info("✅ Ollamaサーバーが正常に起動しました")
                    return True
                    
            self.logger.error("❌ Ollamaサーバーの起動に失敗しました（タイムアウト）")
            return False
            
        except Exception as e:
            self.logger.error(f"❌ Ollamaサーバー起動エラー: {e}")
            return False
    
    def stop_server(self) -> None:
        """Ollamaサーバーを停止（優雅な終了）"""
        try:
            # 管理中のプロセスを優雅に終了
            if self._process:
                self.logger.info("🛑 Ollamaプロセスに終了シグナルを送信中...")
                self._process.terminate()
                
                try:
                    # 最大10秒待機
                    self._process.wait(timeout=10)
                    self.logger.info("✅ Ollamaプロセスが正常に終了しました")
                except subprocess.TimeoutExpired:
                    self.logger.warning("⚠️ Ollamaプロセスが応答しません。強制終了します")
                    self._process.kill()
                    self._process.wait()
                
                self._process = None
            
            # 残存プロセスをクリーンアップ
            try:
                result = subprocess.run(['pkill', '-f', 'ollama'], 
                                      capture_output=True, timeout=5)
                if result.returncode == 0:
                    self.logger.info("🧹 残存Ollamaプロセスをクリーンアップしました")
            except subprocess.TimeoutExpired:
                self.logger.warning("⚠️ プロセスクリーンアップがタイムアウトしました")
                
            time.sleep(2)  # 完全停止待機
            self.logger.info("✅ Ollamaサーバー停止処理が完了しました")
            
        except Exception as e:
            self.logger.error(f"❌ サーバー停止時エラー: {e}")
    
    def check_server_status(self) -> bool:
        """サーバーの動作状況確認"""
        try:
            import requests
            response = requests.get(f"{self.api_url}/api/tags", timeout=5)
            return response.status_code == 200
        except:
            return False
    
    async def async_check_server_status(self) -> bool:
        """非同期でサーバーの動作状況確認"""
        try:
            timeout = aiohttp.ClientTimeout(total=5)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(f"{self.api_url}/api/tags") as response:
                    return response.status == 200
        except:
            return False
    
    def ensure_server_running(self) -> bool:
        """サーバーが動作していることを確認し、必要に応じて起動"""
        if self.check_server_status():
            self.logger.info("✅ Ollamaサーバーは既に動作中です")
            return True
        else:
            self.logger.info("🔄 Ollamaサーバーが停止中です。起動します...")
            return self.start_server_with_timeout()
    
    def get_available_models(self) -> list:
        """利用可能なモデル一覧を取得"""
        try:
            import requests
            response = requests.get(f"{self.api_url}/api/tags", timeout=5)
            if response.status_code == 200:
                data = response.json()
                return [model['name'] for model in data.get('models', [])]
            return []
        except:
            return []


# ユーティリティ関数
def ensure_ollama_running(api_url: str = "http://localhost:11434") -> bool:
    """Ollamaサーバーが動作していることを確認"""
    manager = OllamaManager(api_url)
    return manager.ensure_server_running()


# 使用例とテスト
if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    
    manager = OllamaManager()
    
    print("=== Ollama Manager テスト ===")
    
    # サーバー起動
    if manager.start_server_with_timeout():
        print("✅ サーバー起動成功")
        
        # モデル一覧取得
        models = manager.get_available_models()
        print(f"📋 利用可能モデル: {models}")
        
    else:
        print("❌ サーバー起動失敗")