#!/usr/bin/env python3
"""
Stable Runner - 一晩中動作する安定なエージェントランナー
Nocturnal Agent AI協調システム用
"""

import asyncio
import logging
import signal
import sys
from typing import Optional
from contextlib import asynccontextmanager

from .stability_manager import StabilityManager, set_stability_manager
from ..llm.ollama_manager import OllamaManager


class StableNocturnalRunner:
    """安定性管理機能付きNocturnalエージェントランナー"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.stability_manager: Optional[StabilityManager] = None
        self.ollama_manager: Optional[OllamaManager] = None
        self._shutdown_event = asyncio.Event()
        self._running = False
    
    async def start(self):
        """安定性管理付きでエージェントを起動"""
        self.logger.info("🚀 Nocturnal Agent 安定ランナーを開始します")
        
        try:
            # 安定性マネージャーを初期化
            self.stability_manager = StabilityManager()
            set_stability_manager(self.stability_manager)
            
            # Ollamaマネージャーを初期化
            self.ollama_manager = OllamaManager()
            
            # Ollamaサーバーを確実に起動
            if not self.ollama_manager.ensure_server_running():
                raise RuntimeError("Ollamaサーバーの起動に失敗しました")
            
            # 安定性監視を開始
            await self.stability_manager.start_monitoring()
            
            self._running = True
            self.logger.info("✅ 安定性監視システムが起動しました")
            
            # メインループ
            await self._main_loop()
            
        except KeyboardInterrupt:
            self.logger.info("🛑 キーボード割り込みを受信しました")
        except Exception as e:
            self.logger.error(f"❌ 予期しないエラー: {e}")
            raise
        finally:
            await self._shutdown()
    
    async def _main_loop(self):
        """メインの動作ループ"""
        self.logger.info("🔄 メインループを開始します")
        
        # ヘルス状況を定期的にログ出力
        health_report_interval = 600  # 10分間隔
        last_health_report = 0
        
        while self._running and not self._shutdown_event.is_set():
            try:
                # 定期的なヘルス報告
                current_time = asyncio.get_event_loop().time()
                if current_time - last_health_report > health_report_interval:
                    await self._log_health_status()
                    last_health_report = current_time
                
                # ここで実際のエージェント処理を実行
                # 例: await self._process_nocturnal_tasks()
                
                # 短い間隔で確認
                await asyncio.sleep(30)
                
            except Exception as e:
                self.logger.error(f"❌ メインループエラー: {e}")
                await asyncio.sleep(60)  # エラー時は少し待機
    
    async def _log_health_status(self):
        """ヘルス状況をログ出力"""
        if self.stability_manager:
            health = self.stability_manager.get_health_summary()
            self.logger.info(f"📊 ヘルス状況: {health}")
    
    async def _shutdown(self):
        """優雅な終了処理"""
        self.logger.info("🛑 安定ランナーを終了しています...")
        self._running = False
        
        # 安定性マネージャーの終了
        if self.stability_manager:
            await self.stability_manager.shutdown()
        
        # Ollamaプロセスはそのままにしておく（他で使用中の可能性）
        
        self.logger.info("✅ 安定ランナーが正常に終了しました")
    
    def signal_shutdown(self):
        """外部からの終了シグナル"""
        self._shutdown_event.set()


@asynccontextmanager
async def stable_nocturnal_runtime():
    """安定性管理されたNocturnalランタイム"""
    runner = StableNocturnalRunner()
    try:
        await runner.start()
        yield runner
    finally:
        await runner._shutdown()


# 使用例とテスト関数
async def run_stable_agent():
    """安定エージェントの実行例"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    runner = StableNocturnalRunner()
    
    # シグナルハンドラー設定
    def signal_handler():
        runner.signal_shutdown()
    
    # SIGINT, SIGTERMハンドラー
    loop = asyncio.get_running_loop()
    for sig in [signal.SIGINT, signal.SIGTERM]:
        loop.add_signal_handler(sig, signal_handler)
    
    try:
        await runner.start()
    except KeyboardInterrupt:
        print("🛑 プログラムが中断されました")
    finally:
        print("👋 プログラムを終了します")


if __name__ == "__main__":
    try:
        asyncio.run(run_stable_agent())
    except KeyboardInterrupt:
        print("🛑 強制終了されました")
        sys.exit(0)