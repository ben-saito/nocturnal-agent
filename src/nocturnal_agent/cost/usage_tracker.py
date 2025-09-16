"""使用量追跡機能の実装"""

import json
import logging
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from enum import Enum

logger = logging.getLogger(__name__)


class ServiceType(Enum):
    """サービス種類"""
    OPENAI_API = "openai_api"
    CLAUDE_API = "claude_api"
    LOCAL_LLM = "local_llm"
    GITHUB_API = "github_api"
    OBSIDIAN_API = "obsidian_api"
    OTHER = "other"


@dataclass
class UsageRecord:
    """使用量記録"""
    timestamp: datetime
    service_type: ServiceType
    operation_type: str  # e.g., "chat_completion", "embedding", "search"
    cost: float  # USD
    tokens_used: int = 0
    request_count: int = 1
    task_id: Optional[str] = None
    agent_type: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DayUsage:
    """日次使用量サマリー"""
    date: date
    total_cost: float = 0.0
    total_tokens: int = 0
    total_requests: int = 0
    service_breakdown: Dict[str, float] = field(default_factory=dict)
    operation_breakdown: Dict[str, float] = field(default_factory=dict)
    records: List[UsageRecord] = field(default_factory=list)


@dataclass
class MonthUsage:
    """月次使用量サマリー"""
    year: int
    month: int
    total_cost: float = 0.0
    total_tokens: int = 0
    total_requests: int = 0
    daily_usage: Dict[str, DayUsage] = field(default_factory=dict)
    service_breakdown: Dict[str, float] = field(default_factory=dict)
    free_tool_usage_rate: float = 0.0
    budget_utilization: float = 0.0


class UsageTracker:
    """使用量追跡システム"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        使用量追跡システムを初期化
        
        Args:
            config: 設定辞書
                - storage_path: データ保存パス
                - monthly_budget: 月額予算（USD）
                - alert_thresholds: アラート閾値
                - free_tools: 無料ツールリスト
        """
        self.storage_path = Path(config.get('storage_path', './data/usage'))
        self.monthly_budget = config.get('monthly_budget', 10.0)  # デフォルト$10
        self.alert_thresholds = config.get('alert_thresholds', [0.5, 0.8, 0.9, 0.95])
        self.free_tools = set(config.get('free_tools', [
            ServiceType.LOCAL_LLM.value,
            ServiceType.GITHUB_API.value  # GitHub APIの基本使用量は無料
        ]))
        
        # データ保存パスを作成
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # 現在の使用量キャッシュ
        self.current_month_cache: Optional[MonthUsage] = None
        self.current_day_cache: Optional[DayUsage] = None
        
        # アラートコールバック
        self.alert_callbacks: List[callable] = []
        
        # 統計
        self.tracker_stats = {
            'total_records': 0,
            'total_cost_tracked': 0.0,
            'alerts_sent': 0,
            'last_alert_time': None
        }
    
    def record_usage(self, 
                    service_type: ServiceType,
                    operation_type: str,
                    cost: float,
                    tokens_used: int = 0,
                    task_id: Optional[str] = None,
                    agent_type: Optional[str] = None,
                    metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        使用量を記録
        
        Args:
            service_type: サービス種類
            operation_type: 操作種類
            cost: コスト（USD）
            tokens_used: 使用トークン数
            task_id: 関連タスクID
            agent_type: エージェント種類
            metadata: 追加メタデータ
            
        Returns:
            記録成功フラグ
        """
        try:
            now = datetime.now()
            
            # 使用量記録を作成
            record = UsageRecord(
                timestamp=now,
                service_type=service_type,
                operation_type=operation_type,
                cost=cost,
                tokens_used=tokens_used,
                task_id=task_id,
                agent_type=agent_type,
                metadata=metadata or {}
            )
            
            # 日次使用量を更新
            day_usage = self._get_or_create_day_usage(now.date())
            day_usage.total_cost += cost
            day_usage.total_tokens += tokens_used
            day_usage.total_requests += 1
            day_usage.records.append(record)
            
            # サービス別内訳を更新
            service_name = service_type.value
            day_usage.service_breakdown[service_name] = (
                day_usage.service_breakdown.get(service_name, 0.0) + cost
            )
            
            # 操作別内訳を更新
            day_usage.operation_breakdown[operation_type] = (
                day_usage.operation_breakdown.get(operation_type, 0.0) + cost
            )
            
            # 月次使用量を更新
            month_usage = self._get_or_create_month_usage(now.year, now.month)
            month_usage.total_cost += cost
            month_usage.total_tokens += tokens_used
            month_usage.total_requests += 1
            month_usage.daily_usage[str(now.date())] = day_usage
            
            # 月次サービス別内訳を更新
            month_usage.service_breakdown[service_name] = (
                month_usage.service_breakdown.get(service_name, 0.0) + cost
            )
            
            # 無料ツール使用率を更新
            month_usage.free_tool_usage_rate = self._calculate_free_tool_rate(month_usage)
            
            # 予算使用率を更新
            month_usage.budget_utilization = month_usage.total_cost / self.monthly_budget
            
            # データを保存
            self._save_day_usage(day_usage)
            self._save_month_usage(month_usage)
            
            # 統計を更新
            self.tracker_stats['total_records'] += 1
            self.tracker_stats['total_cost_tracked'] += cost
            
            # 予算アラートをチェック
            self._check_budget_alerts(month_usage)
            
            logger.debug(f"使用量記録完了: {service_type.value} - ${cost:.4f}")
            return True
            
        except Exception as e:
            logger.error(f"使用量記録エラー: {e}")
            return False
    
    def get_current_month_usage(self) -> MonthUsage:
        """現在の月の使用量を取得"""
        now = datetime.now()
        return self._get_or_create_month_usage(now.year, now.month)
    
    def get_current_day_usage(self) -> DayUsage:
        """現在の日の使用量を取得"""
        return self._get_or_create_day_usage(date.today())
    
    def get_usage_by_date_range(self, start_date: date, end_date: date) -> Dict[str, DayUsage]:
        """日付範囲の使用量を取得"""
        usage_data = {}
        current_date = start_date
        
        while current_date <= end_date:
            try:
                day_usage = self._load_day_usage(current_date)
                if day_usage:
                    usage_data[str(current_date)] = day_usage
            except Exception as e:
                logger.warning(f"日次データ読込エラー ({current_date}): {e}")
            
            current_date += timedelta(days=1)
        
        return usage_data
    
    def get_monthly_report(self, year: int, month: int) -> Optional[MonthUsage]:
        """月次レポートを取得"""
        try:
            return self._load_month_usage(year, month)
        except Exception as e:
            logger.error(f"月次レポート取得エラー ({year}-{month:02d}): {e}")
            return None
    
    def get_budget_status(self) -> Dict[str, Any]:
        """予算状況を取得"""
        current_month = self.get_current_month_usage()
        
        remaining_budget = self.monthly_budget - current_month.total_cost
        days_in_month = (datetime.now().replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        days_remaining = (days_in_month.date() - date.today()).days + 1
        
        daily_budget_remaining = remaining_budget / days_remaining if days_remaining > 0 else 0
        
        return {
            'monthly_budget': self.monthly_budget,
            'current_spend': current_month.total_cost,
            'remaining_budget': remaining_budget,
            'budget_utilization': current_month.budget_utilization,
            'days_remaining': days_remaining,
            'daily_budget_remaining': daily_budget_remaining,
            'free_tool_usage_rate': current_month.free_tool_usage_rate,
            'on_track': current_month.budget_utilization <= (datetime.now().day / days_in_month.day) if days_in_month.day > 0 else True,
            'alert_status': self._get_alert_status(current_month.budget_utilization)
        }
    
    def add_alert_callback(self, callback: callable):
        """アラートコールバックを追加"""
        self.alert_callbacks.append(callback)
    
    def get_service_breakdown(self, days: int = 30) -> Dict[str, float]:
        """サービス別使用量内訳を取得"""
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        
        usage_data = self.get_usage_by_date_range(start_date, end_date)
        service_totals = {}
        
        for day_usage in usage_data.values():
            for service, cost in day_usage.service_breakdown.items():
                service_totals[service] = service_totals.get(service, 0.0) + cost
        
        return service_totals
    
    def get_usage_trends(self, days: int = 30) -> Dict[str, List[float]]:
        """使用量トレンドを取得"""
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        
        usage_data = self.get_usage_by_date_range(start_date, end_date)
        
        dates = []
        costs = []
        tokens = []
        requests = []
        
        current_date = start_date
        while current_date <= end_date:
            dates.append(str(current_date))
            day_usage = usage_data.get(str(current_date))
            
            if day_usage:
                costs.append(day_usage.total_cost)
                tokens.append(day_usage.total_tokens)
                requests.append(day_usage.total_requests)
            else:
                costs.append(0.0)
                tokens.append(0)
                requests.append(0)
            
            current_date += timedelta(days=1)
        
        return {
            'dates': dates,
            'costs': costs,
            'tokens': tokens,
            'requests': requests
        }
    
    def _get_or_create_day_usage(self, target_date: date) -> DayUsage:
        """日次使用量データを取得または作成"""
        if (self.current_day_cache and 
            self.current_day_cache.date == target_date):
            return self.current_day_cache
        
        # ディスクから読み込み
        day_usage = self._load_day_usage(target_date)
        if day_usage is None:
            day_usage = DayUsage(date=target_date)
        
        self.current_day_cache = day_usage
        return day_usage
    
    def _get_or_create_month_usage(self, year: int, month: int) -> MonthUsage:
        """月次使用量データを取得または作成"""
        if (self.current_month_cache and 
            self.current_month_cache.year == year and
            self.current_month_cache.month == month):
            return self.current_month_cache
        
        # ディスクから読み込み
        month_usage = self._load_month_usage(year, month)
        if month_usage is None:
            month_usage = MonthUsage(year=year, month=month)
        
        self.current_month_cache = month_usage
        return month_usage
    
    def _save_day_usage(self, day_usage: DayUsage):
        """日次使用量を保存"""
        file_path = self.storage_path / f"daily_{day_usage.date}.json"
        try:
            # UsageRecordのserializationのためにdatetimeを文字列に変換
            data = asdict(day_usage)
            data['records'] = []
            for record in day_usage.records:
                record_data = asdict(record)
                record_data['timestamp'] = record.timestamp.isoformat()
                record_data['service_type'] = record.service_type.value
                data['records'].append(record_data)
            data['date'] = str(day_usage.date)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            logger.error(f"日次データ保存エラー: {e}")
    
    def _save_month_usage(self, month_usage: MonthUsage):
        """月次使用量を保存"""
        file_path = self.storage_path / f"monthly_{month_usage.year}_{month_usage.month:02d}.json"
        try:
            data = asdict(month_usage)
            # DayUsageを辞書形式に変換
            data['daily_usage'] = {}
            for date_str, day_usage in month_usage.daily_usage.items():
                day_data = asdict(day_usage)
                day_data['date'] = str(day_usage.date)
                day_data['records'] = []  # レコードは日次ファイルに保存されるので省略
                data['daily_usage'][date_str] = day_data
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            logger.error(f"月次データ保存エラー: {e}")
    
    def _load_day_usage(self, target_date: date) -> Optional[DayUsage]:
        """日次使用量を読み込み"""
        file_path = self.storage_path / f"daily_{target_date}.json"
        
        if not file_path.exists():
            return None
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # UsageRecordを復元
            records = []
            for record_data in data.get('records', []):
                record = UsageRecord(
                    timestamp=datetime.fromisoformat(record_data['timestamp']),
                    service_type=ServiceType(record_data['service_type']),
                    operation_type=record_data['operation_type'],
                    cost=record_data['cost'],
                    tokens_used=record_data.get('tokens_used', 0),
                    request_count=record_data.get('request_count', 1),
                    task_id=record_data.get('task_id'),
                    agent_type=record_data.get('agent_type'),
                    metadata=record_data.get('metadata', {})
                )
                records.append(record)
            
            return DayUsage(
                date=datetime.strptime(data['date'], '%Y-%m-%d').date(),
                total_cost=data['total_cost'],
                total_tokens=data['total_tokens'],
                total_requests=data['total_requests'],
                service_breakdown=data['service_breakdown'],
                operation_breakdown=data['operation_breakdown'],
                records=records
            )
            
        except Exception as e:
            logger.error(f"日次データ読み込みエラー: {e}")
            return None
    
    def _load_month_usage(self, year: int, month: int) -> Optional[MonthUsage]:
        """月次使用量を読み込み"""
        file_path = self.storage_path / f"monthly_{year}_{month:02d}.json"
        
        if not file_path.exists():
            return None
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # DayUsageを復元
            daily_usage = {}
            for date_str, day_data in data.get('daily_usage', {}).items():
                day_usage = DayUsage(
                    date=datetime.strptime(day_data['date'], '%Y-%m-%d').date(),
                    total_cost=day_data['total_cost'],
                    total_tokens=day_data['total_tokens'],
                    total_requests=day_data['total_requests'],
                    service_breakdown=day_data['service_breakdown'],
                    operation_breakdown=day_data['operation_breakdown'],
                    records=[]  # 詳細レコードは日次ファイルから読み込み
                )
                daily_usage[date_str] = day_usage
            
            return MonthUsage(
                year=data['year'],
                month=data['month'],
                total_cost=data['total_cost'],
                total_tokens=data['total_tokens'],
                total_requests=data['total_requests'],
                daily_usage=daily_usage,
                service_breakdown=data['service_breakdown'],
                free_tool_usage_rate=data['free_tool_usage_rate'],
                budget_utilization=data['budget_utilization']
            )
            
        except Exception as e:
            logger.error(f"月次データ読み込みエラー: {e}")
            return None
    
    def _calculate_free_tool_rate(self, month_usage: MonthUsage) -> float:
        """無料ツール使用率を計算"""
        if month_usage.total_requests == 0:
            return 1.0
        
        free_requests = 0
        for day_usage in month_usage.daily_usage.values():
            for record in day_usage.records:
                if record.service_type.value in self.free_tools:
                    free_requests += record.request_count
        
        return free_requests / month_usage.total_requests
    
    def _check_budget_alerts(self, month_usage: MonthUsage):
        """予算アラートをチェック"""
        for threshold in self.alert_thresholds:
            if (month_usage.budget_utilization >= threshold and
                self.tracker_stats.get('last_alert_time') != threshold):
                
                self._send_alert(threshold, month_usage)
                self.tracker_stats['last_alert_time'] = threshold
                self.tracker_stats['alerts_sent'] += 1
    
    def _send_alert(self, threshold: float, month_usage: MonthUsage):
        """アラートを送信"""
        alert_data = {
            'threshold': threshold,
            'budget_utilization': month_usage.budget_utilization,
            'current_spend': month_usage.total_cost,
            'monthly_budget': self.monthly_budget,
            'remaining_budget': self.monthly_budget - month_usage.total_cost,
            'free_tool_usage_rate': month_usage.free_tool_usage_rate
        }
        
        logger.warning(f"予算アラート: {threshold*100:.0f}% 使用済み (${month_usage.total_cost:.2f}/${self.monthly_budget})")
        
        # コールバック実行
        for callback in self.alert_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    # 非同期コールバックの場合は後で処理
                    asyncio.create_task(callback(alert_data))
                else:
                    callback(alert_data)
            except Exception as e:
                logger.error(f"アラートコールバック実行エラー: {e}")
    
    def _get_alert_status(self, budget_utilization: float) -> str:
        """アラート状態を取得"""
        if budget_utilization >= 0.95:
            return "critical"
        elif budget_utilization >= 0.8:
            return "warning"
        elif budget_utilization >= 0.5:
            return "attention"
        else:
            return "normal"
    
    def get_tracker_status(self) -> Dict[str, Any]:
        """トラッカー状態を取得"""
        current_month = self.get_current_month_usage()
        
        return {
            'tracker_active': True,
            'storage_path': str(self.storage_path),
            'monthly_budget': self.monthly_budget,
            'current_month_usage': {
                'year': current_month.year,
                'month': current_month.month,
                'total_cost': current_month.total_cost,
                'budget_utilization': current_month.budget_utilization,
                'free_tool_usage_rate': current_month.free_tool_usage_rate
            },
            'statistics': self.tracker_stats,
            'alert_thresholds': self.alert_thresholds,
            'free_tools': list(self.free_tools)
        }