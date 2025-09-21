#!/usr/bin/env python3
"""
Stability Manager - 一晩中動作するエージェントシステムの安定性管理
Nocturnal Agent AI協調システム用
"""

import asyncio
import signal
import logging
import threading
import time
import psutil
import gc
from typing import Optional, Dict, List, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass
from contextlib import asynccontextmanager


@dataclass
class SystemHealth:
    """システムヘルス状態"""
    memory_usage_percent: float
    cpu_usage_percent: float
    disk_usage_percent: float
    ollama_running: bool
    last_check: datetime
    errors_count: int
    warnings_count: int


@dataclass
class StabilityMetrics:
    """安定性メトリクス"""
    uptime_hours: float
    total_requests: int
    successful_requests: int
    failed_requests: int
    average_response_time: float
    memory_leaks_detected: int
    restarts_count: int


class StabilityManager:
    """一晩中動作するシステムの安定性管理"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.start_time = datetime.now()
        self.health_check_interval = 60  # 1分間隔
        self.cleanup_interval = 300      # 5分間隔
        self.max_memory_usage = 80.0     # 80%でアラート
        self.max_cpu_usage = 90.0        # 90%でアラート
        
        # 監視フラグ
        self._running = False
        self._health_monitor_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        
        # メトリクス
        self.metrics = StabilityMetrics(
            uptime_hours=0.0,
            total_requests=0,
            successful_requests=0,
            failed_requests=0,
            average_response_time=0.0,
            memory_leaks_detected=0,
            restarts_count=0
        )
        
        # ヘルスチェック履歴
        self.health_history: List[SystemHealth] = []
        self.max_history_size = 144  # 24時間分（10分間隔）
        
        # エラーハンドラー
        self.error_handlers: Dict[str, Callable] = {}
        
        # シグナルハンドラー設定
        self._setup_signal_handlers()
    
    def _setup_signal_handlers(self):
        """シグナルハンドラーの設定（優雅な終了）"""
        def signal_handler(signum, frame):
            self.logger.info(f"🛑 シグナル {signum} を受信。優雅な終了を開始...")
            asyncio.create_task(self.shutdown())
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    async def start_monitoring(self):
        """安定性監視を開始"""
        if self._running:
            self.logger.warning("⚠️ 監視は既に実行中です")
            return
        
        self._running = True
        self.logger.info("🎯 安定性監視を開始しました")
        
        # 監視タスクを開始
        self._health_monitor_task = asyncio.create_task(self._health_monitor_loop())
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        # タスクの例外処理
        asyncio.create_task(self._monitor_tasks())
    
    async def _health_monitor_loop(self):
        """ヘルスチェック監視ループ"""
        while self._running:
            try:
                health = await self._check_system_health()
                self.health_history.append(health)
                
                # 履歴サイズ制限
                if len(self.health_history) > self.max_history_size:
                    self.health_history.pop(0)
                
                # アラートチェック
                await self._check_alerts(health)
                
                # メトリクス更新
                self._update_metrics()
                
            except Exception as e:
                self.logger.error(f"❌ ヘルスチェックエラー: {e}")
                await asyncio.sleep(10)  # エラー時は短い間隔で再試行
                continue
            
            await asyncio.sleep(self.health_check_interval)
    
    async def _cleanup_loop(self):
        """定期クリーンアップループ"""
        while self._running:
            try:
                await self._perform_cleanup()
            except Exception as e:
                self.logger.error(f"❌ クリーンアップエラー: {e}")
            
            await asyncio.sleep(self.cleanup_interval)
    
    async def _monitor_tasks(self):
        """監視タスクの異常終了を監視"""
        while self._running:
            await asyncio.sleep(30)
            
            if self._health_monitor_task and self._health_monitor_task.done():
                if self._health_monitor_task.exception():
                    self.logger.error(f"❌ ヘルス監視タスクが異常終了: {self._health_monitor_task.exception()}")
                    self._health_monitor_task = asyncio.create_task(self._health_monitor_loop())
            
            if self._cleanup_task and self._cleanup_task.done():
                if self._cleanup_task.exception():
                    self.logger.error(f"❌ クリーンアップタスクが異常終了: {self._cleanup_task.exception()}")
                    self._cleanup_task = asyncio.create_task(self._cleanup_loop())
    
    async def _check_system_health(self) -> SystemHealth:
        """システムヘルス状態を確認"""
        # CPU使用率
        cpu_percent = psutil.cpu_percent(interval=1)
        
        # メモリ使用率
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        
        # ディスク使用率
        disk = psutil.disk_usage('/')
        disk_percent = (disk.used / disk.total) * 100
        
        # Ollamaプロセス確認
        ollama_running = self._check_ollama_process()
        
        return SystemHealth(
            memory_usage_percent=memory_percent,
            cpu_usage_percent=cpu_percent,
            disk_usage_percent=disk_percent,
            ollama_running=ollama_running,
            last_check=datetime.now(),
            errors_count=0,  # 実装必要
            warnings_count=0  # 実装必要
        )
    
    def _check_ollama_process(self) -> bool:
        """Ollamaプロセスの動作確認"""
        try:
            for proc in psutil.process_iter(['pid', 'name']):
                if 'ollama' in proc.info['name'].lower():
                    return True
            return False
        except:
            return False
    
    async def _check_alerts(self, health: SystemHealth):
        """アラート条件をチェック"""
        alerts = []
        
        if health.memory_usage_percent > self.max_memory_usage:
            alerts.append(f"🚨 メモリ使用率が高すぎます: {health.memory_usage_percent:.1f}%")
        
        if health.cpu_usage_percent > self.max_cpu_usage:
            alerts.append(f"🚨 CPU使用率が高すぎます: {health.cpu_usage_percent:.1f}%")
        
        if not health.ollama_running:
            alerts.append("🚨 Ollamaプロセスが停止しています")
            await self._handle_ollama_restart()
        
        for alert in alerts:
            self.logger.warning(alert)
    
    async def _handle_ollama_restart(self):
        """Ollama自動再起動"""
        try:
            self.logger.info("🔄 Ollamaプロセスを再起動中...")
            from ..llm.ollama_manager import OllamaManager
            
            manager = OllamaManager()
            if manager.start_server_with_timeout():
                self.logger.info("✅ Ollama再起動成功")
                self.metrics.restarts_count += 1
            else:
                self.logger.error("❌ Ollama再起動失敗")
        except Exception as e:
            self.logger.error(f"❌ Ollama再起動エラー: {e}")
    
    async def _perform_cleanup(self):
        """定期的なクリーンアップ処理"""
        self.logger.debug("🧹 定期クリーンアップを実行中...")
        
        # ガベージコレクション
        collected = gc.collect()
        if collected > 0:
            self.logger.debug(f"🗑️ ガベージコレクション: {collected} オブジェクト回収")
        
        # メモリリーク検出
        current_memory = psutil.virtual_memory().percent
        if len(self.health_history) > 10:
            avg_memory = sum(h.memory_usage_percent for h in self.health_history[-10:]) / 10
            if current_memory > avg_memory + 10:  # 10%以上の増加
                self.metrics.memory_leaks_detected += 1
                self.logger.warning(f"🧯 メモリリーク検出の可能性: {current_memory:.1f}% (平均: {avg_memory:.1f}%)")
    
    def _update_metrics(self):
        """メトリクスを更新"""
        now = datetime.now()
        self.metrics.uptime_hours = (now - self.start_time).total_seconds() / 3600
    
    def record_request(self, success: bool, response_time: float):
        """リクエストメトリクスを記録"""
        self.metrics.total_requests += 1
        if success:
            self.metrics.successful_requests += 1
        else:
            self.metrics.failed_requests += 1
        
        # 平均応答時間を更新
        total_time = self.metrics.average_response_time * (self.metrics.total_requests - 1) + response_time
        self.metrics.average_response_time = total_time / self.metrics.total_requests
    
    def get_health_summary(self) -> Dict:
        """ヘルス状況のサマリーを取得"""
        if not self.health_history:
            return {"status": "no_data"}
        
        latest = self.health_history[-1]
        return {
            "status": "healthy" if latest.ollama_running else "unhealthy",
            "uptime_hours": self.metrics.uptime_hours,
            "memory_usage": latest.memory_usage_percent,
            "cpu_usage": latest.cpu_usage_percent,
            "ollama_running": latest.ollama_running,
            "total_requests": self.metrics.total_requests,
            "success_rate": (self.metrics.successful_requests / max(self.metrics.total_requests, 1)) * 100,
            "average_response_time": self.metrics.average_response_time,
            "restarts_count": self.metrics.restarts_count
        }
    
    async def shutdown(self):
        """優雅な終了処理"""
        self.logger.info("🛑 安定性監視を終了しています...")
        self._running = False
        
        # 監視タスクを停止
        if self._health_monitor_task:
            self._health_monitor_task.cancel()
        if self._cleanup_task:
            self._cleanup_task.cancel()
        
        # タスクの完了を待機
        await asyncio.sleep(1)
        
        self.logger.info("✅ 安定性監視が正常に終了しました")


@asynccontextmanager
async def stable_runtime():
    """安定性管理されたランタイム"""
    manager = StabilityManager()
    try:
        await manager.start_monitoring()
        yield manager
    finally:
        await manager.shutdown()


# グローバル安定性マネージャー
_global_stability_manager: Optional[StabilityManager] = None

def get_stability_manager() -> Optional[StabilityManager]:
    """グローバル安定性マネージャーを取得"""
    return _global_stability_manager

def set_stability_manager(manager: StabilityManager):
    """グローバル安定性マネージャーを設定"""
    global _global_stability_manager
    _global_stability_manager = manager