"""構造化ログシステム - JSON Lines形式"""

import json
import logging
import logging.handlers
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List
from enum import Enum
import traceback
import os
import gzip
import shutil
from dataclasses import dataclass, asdict

from ..core.models import Task, ExecutionResult, QualityScore


class LogLevel(Enum):
    """ログレベル列挙型"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogCategory(Enum):
    """ログカテゴリ列挙型"""
    SYSTEM = "system"
    TASK_EXECUTION = "task_execution"
    COST_MANAGEMENT = "cost_management"
    SAFETY = "safety"
    PARALLEL_EXECUTION = "parallel_execution"
    QUALITY_ASSESSMENT = "quality_assessment"
    SCHEDULER = "scheduler"
    API_CALL = "api_call"
    ERROR = "error"
    PERFORMANCE = "performance"


@dataclass
class StructuredLogEntry:
    """構造化ログエントリ"""
    timestamp: str
    level: str
    category: str
    message: str
    component: str
    session_id: Optional[str] = None
    task_id: Optional[str] = None
    correlation_id: Optional[str] = None
    user_id: Optional[str] = None
    extra_data: Optional[Dict[str, Any]] = None
    execution_time_ms: Optional[float] = None
    memory_usage_mb: Optional[float] = None
    error_details: Optional[Dict[str, Any]] = None


class JSONLinesFormatter(logging.Formatter):
    """JSON Lines形式のログフォーマッター"""
    
    def format(self, record: logging.LogRecord) -> str:
        """ログレコードをJSON Lines形式にフォーマット"""
        # 基本情報
        log_entry = {
            'timestamp': datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            'level': record.levelname,
            'message': record.getMessage(),
            'component': record.name,
            'thread': record.thread,
            'process': record.process
        }
        
        # 追加属性の処理
        for attr in ['category', 'session_id', 'task_id', 'correlation_id', 
                    'user_id', 'extra_data', 'execution_time_ms', 'memory_usage_mb']:
            if hasattr(record, attr):
                log_entry[attr] = getattr(record, attr)
        
        # エラー情報の処理
        if record.exc_info:
            log_entry['error_details'] = {
                'exception_type': record.exc_info[0].__name__ if record.exc_info[0] else None,
                'exception_message': str(record.exc_info[1]) if record.exc_info[1] else None,
                'traceback': traceback.format_exception(*record.exc_info)
            }
        
        return json.dumps(log_entry, ensure_ascii=False, default=str)


class RotatingJSONLinesHandler(logging.handlers.RotatingFileHandler):
    """JSON Lines用ローテーティングハンドラー"""
    
    def __init__(self, filename: str, maxBytes: int = 0, backupCount: int = 0, 
                 compress: bool = True, **kwargs):
        super().__init__(filename, maxBytes=maxBytes, backupCount=backupCount, **kwargs)
        self.compress = compress
    
    def doRollover(self):
        """ログファイルのローテーション"""
        super().doRollover()
        
        # 圧縮処理
        if self.compress and self.backupCount > 0:
            self._compress_rotated_files()
    
    def _compress_rotated_files(self):
        """ローテーションされたファイルを圧縮"""
        base_filename = self.baseFilename
        for i in range(1, self.backupCount + 1):
            rotated_file = f"{base_filename}.{i}"
            compressed_file = f"{rotated_file}.gz"
            
            if os.path.exists(rotated_file) and not os.path.exists(compressed_file):
                try:
                    with open(rotated_file, 'rb') as f_in:
                        with gzip.open(compressed_file, 'wb') as f_out:
                            shutil.copyfileobj(f_in, f_out)
                    os.remove(rotated_file)
                except Exception:
                    pass  # 圧縮失敗時は元ファイルを残す


class StructuredLogger:
    """構造化ログマネージャー"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.log_path = Path(config.get('output_path', './logs'))
        self.retention_days = config.get('retention_days', 30)
        self.max_file_size_mb = config.get('max_file_size_mb', 100)
        self.console_output = config.get('console_output', True)
        self.file_output = config.get('file_output', True)
        self.log_level = getattr(logging, config.get('level', 'INFO'))
        
        # ログディレクトリの作成
        self.log_path.mkdir(parents=True, exist_ok=True)
        
        # ロガーの設定
        self._setup_loggers()
        
        # クリーンアップのスケジューリング
        self._schedule_cleanup()
    
    def _setup_loggers(self):
        """ロガーのセットアップ"""
        # メインロガー
        self.main_logger = logging.getLogger('nocturnal_agent')
        self.main_logger.setLevel(self.log_level)
        self.main_logger.handlers.clear()
        
        # JSON Linesフォーマッター
        json_formatter = JSONLinesFormatter()
        
        # コンソールハンドラー
        if self.console_output:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(self.log_level)
            
            # コンソール用は読みやすい形式
            console_formatter = logging.Formatter(
                '%(asctime)s [%(levelname)8s] %(name)s: %(message)s'
            )
            console_handler.setFormatter(console_formatter)
            self.main_logger.addHandler(console_handler)
        
        # ファイルハンドラー
        if self.file_output:
            # メインログファイル
            main_log_file = self.log_path / 'nocturnal_agent.jsonl'
            main_handler = RotatingJSONLinesHandler(
                str(main_log_file),
                maxBytes=self.max_file_size_mb * 1024 * 1024,
                backupCount=5,
                compress=True
            )
            main_handler.setLevel(self.log_level)
            main_handler.setFormatter(json_formatter)
            self.main_logger.addHandler(main_handler)
            
            # エラー専用ログファイル
            error_log_file = self.log_path / 'errors.jsonl'
            error_handler = RotatingJSONLinesHandler(
                str(error_log_file),
                maxBytes=self.max_file_size_mb * 1024 * 1024,
                backupCount=3,
                compress=True
            )
            error_handler.setLevel(logging.ERROR)
            error_handler.setFormatter(json_formatter)
            self.main_logger.addHandler(error_handler)
    
    def log(self, level: LogLevel, category: LogCategory, message: str,
            component: str = "main", session_id: Optional[str] = None,
            task_id: Optional[str] = None, correlation_id: Optional[str] = None,
            extra_data: Optional[Dict[str, Any]] = None,
            execution_time_ms: Optional[float] = None,
            memory_usage_mb: Optional[float] = None,
            exc_info: bool = False) -> None:
        """構造化ログを出力"""
        
        # ログレコード作成
        logger = logging.getLogger(component)
        
        # 追加属性の設定
        extra_attrs = {
            'category': category.value,
            'session_id': session_id,
            'task_id': task_id,
            'correlation_id': correlation_id,
            'extra_data': extra_data or {},
            'execution_time_ms': execution_time_ms,
            'memory_usage_mb': memory_usage_mb
        }
        
        # ログ出力
        log_func = getattr(logger, level.value.lower())
        log_func(message, extra=extra_attrs, exc_info=exc_info)
    
    def log_task_start(self, task: Task, session_id: Optional[str] = None) -> None:
        """タスク開始ログ"""
        self.log(
            LogLevel.INFO,
            LogCategory.TASK_EXECUTION,
            f"タスク開始: {task.description}",
            session_id=session_id,
            task_id=task.id,
            extra_data={
                'task_priority': task.priority.value,
                'estimated_quality': task.estimated_quality,
                'requirements_count': len(task.requirements) if task.requirements else 0
            }
        )
    
    def log_task_completion(self, task: Task, result: ExecutionResult, 
                           session_id: Optional[str] = None,
                           execution_time_ms: Optional[float] = None) -> None:
        """タスク完了ログ"""
        self.log(
            LogLevel.INFO if result.success else LogLevel.WARNING,
            LogCategory.TASK_EXECUTION,
            f"タスク{'完了' if result.success else '失敗'}: {task.description}",
            session_id=session_id,
            task_id=task.id,
            execution_time_ms=execution_time_ms,
            extra_data={
                'success': result.success,
                'quality_score': result.quality_score.overall if result.quality_score else None,
                'agent_used': result.agent_used.value if result.agent_used else None,
                'files_modified_count': len(result.files_modified) if result.files_modified else 0,
                'files_created_count': len(result.files_created) if result.files_created else 0,
                'cost_incurred': result.cost_incurred,
                'error_count': len(result.errors) if result.errors else 0
            }
        )
    
    def log_cost_usage(self, service_type: str, operation_type: str, 
                      cost: float, tokens_used: int = 0,
                      session_id: Optional[str] = None,
                      task_id: Optional[str] = None) -> None:
        """コスト使用ログ"""
        self.log(
            LogLevel.INFO,
            LogCategory.COST_MANAGEMENT,
            f"コスト使用: {service_type} - {operation_type}",
            session_id=session_id,
            task_id=task_id,
            extra_data={
                'service_type': service_type,
                'operation_type': operation_type,
                'cost': cost,
                'tokens_used': tokens_used
            }
        )
    
    def log_safety_violation(self, violation_type: str, details: str,
                           task_id: Optional[str] = None,
                           session_id: Optional[str] = None) -> None:
        """安全性違反ログ"""
        self.log(
            LogLevel.ERROR,
            LogCategory.SAFETY,
            f"安全性違反検出: {violation_type}",
            session_id=session_id,
            task_id=task_id,
            extra_data={
                'violation_type': violation_type,
                'details': details
            }
        )
    
    def log_api_call(self, api_name: str, endpoint: str, 
                    response_time_ms: float, status_code: int,
                    request_size_bytes: Optional[int] = None,
                    response_size_bytes: Optional[int] = None,
                    session_id: Optional[str] = None,
                    task_id: Optional[str] = None) -> None:
        """API呼び出しログ"""
        level = LogLevel.INFO if 200 <= status_code < 300 else LogLevel.WARNING
        
        self.log(
            level,
            LogCategory.API_CALL,
            f"API呼び出し: {api_name} {endpoint}",
            execution_time_ms=response_time_ms,
            session_id=session_id,
            task_id=task_id,
            extra_data={
                'api_name': api_name,
                'endpoint': endpoint,
                'status_code': status_code,
                'request_size_bytes': request_size_bytes,
                'response_size_bytes': response_size_bytes
            }
        )
    
    def log_error(self, error_type: str, message: str, 
                 component: str = "main",
                 session_id: Optional[str] = None,
                 task_id: Optional[str] = None,
                 exc_info: bool = True) -> None:
        """エラーログ"""
        self.log(
            LogLevel.ERROR,
            LogCategory.ERROR,
            f"{error_type}: {message}",
            component=component,
            session_id=session_id,
            task_id=task_id,
            exc_info=exc_info
        )
    
    def log_performance_metric(self, metric_name: str, value: float,
                              unit: str = "", component: str = "main",
                              session_id: Optional[str] = None,
                              task_id: Optional[str] = None) -> None:
        """パフォーマンスメトリクスログ"""
        self.log(
            LogLevel.INFO,
            LogCategory.PERFORMANCE,
            f"パフォーマンスメトリクス: {metric_name} = {value}{unit}",
            component=component,
            session_id=session_id,
            task_id=task_id,
            extra_data={
                'metric_name': metric_name,
                'value': value,
                'unit': unit
            }
        )
    
    def query_logs(self, start_time: Optional[datetime] = None,
                  end_time: Optional[datetime] = None,
                  level: Optional[LogLevel] = None,
                  category: Optional[LogCategory] = None,
                  component: Optional[str] = None,
                  task_id: Optional[str] = None,
                  limit: int = 1000) -> List[Dict[str, Any]]:
        """ログクエリ"""
        results = []
        
        # ログファイルを読み込んで条件に合致するエントリを抽出
        log_files = [
            self.log_path / 'nocturnal_agent.jsonl',
            self.log_path / 'errors.jsonl'
        ]
        
        # 古いローテーションファイルも含める
        for log_file in self.log_path.glob('*.jsonl*'):
            if log_file not in log_files:
                log_files.append(log_file)
        
        for log_file in log_files:
            if not log_file.exists():
                continue
                
            try:
                if log_file.suffix == '.gz':
                    opener = gzip.open
                else:
                    opener = open
                
                with opener(log_file, 'rt', encoding='utf-8') as f:
                    for line in f:
                        if len(results) >= limit:
                            break
                        
                        try:
                            entry = json.loads(line.strip())
                            
                            # フィルター条件チェック
                            if start_time:
                                entry_time = datetime.fromisoformat(entry['timestamp'].replace('Z', '+00:00'))
                                if entry_time < start_time:
                                    continue
                            
                            if end_time:
                                entry_time = datetime.fromisoformat(entry['timestamp'].replace('Z', '+00:00'))
                                if entry_time > end_time:
                                    continue
                            
                            if level and entry.get('level') != level.value:
                                continue
                            
                            if category and entry.get('category') != category.value:
                                continue
                            
                            if component and entry.get('component') != component:
                                continue
                            
                            if task_id and entry.get('task_id') != task_id:
                                continue
                            
                            results.append(entry)
                            
                        except (json.JSONDecodeError, KeyError, ValueError):
                            continue
            
            except Exception:
                continue
        
        return sorted(results, key=lambda x: x['timestamp'])[:limit]
    
    def cleanup_old_logs(self) -> int:
        """古いログファイルのクリーンアップ"""
        if self.retention_days <= 0:
            return 0
        
        cutoff_time = datetime.now().timestamp() - (self.retention_days * 24 * 3600)
        deleted_count = 0
        
        for log_file in self.log_path.glob('*.jsonl*'):
            try:
                if log_file.stat().st_mtime < cutoff_time:
                    log_file.unlink()
                    deleted_count += 1
            except Exception:
                continue
        
        return deleted_count
    
    def get_log_statistics(self) -> Dict[str, Any]:
        """ログ統計情報"""
        stats = {
            'total_log_files': 0,
            'total_size_mb': 0.0,
            'oldest_log_date': None,
            'newest_log_date': None,
            'level_counts': {},
            'category_counts': {}
        }
        
        for log_file in self.log_path.glob('*.jsonl*'):
            if not log_file.exists():
                continue
            
            stats['total_log_files'] += 1
            stats['total_size_mb'] += log_file.stat().st_size / (1024 * 1024)
            
            file_mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
            if not stats['oldest_log_date'] or file_mtime < stats['oldest_log_date']:
                stats['oldest_log_date'] = file_mtime
            if not stats['newest_log_date'] or file_mtime > stats['newest_log_date']:
                stats['newest_log_date'] = file_mtime
        
        # レベル・カテゴリ別統計（最近のログファイルから）
        recent_entries = self.query_logs(limit=10000)
        for entry in recent_entries:
            level = entry.get('level', 'UNKNOWN')
            category = entry.get('category', 'unknown')
            
            stats['level_counts'][level] = stats['level_counts'].get(level, 0) + 1
            stats['category_counts'][category] = stats['category_counts'].get(category, 0) + 1
        
        return stats
    
    def _schedule_cleanup(self):
        """定期クリーンアップのスケジューリング（簡易版）"""
        # 実際の実装では、スケジューラーやバックグラウンドタスクで実行
        pass


class LogAnalyzer:
    """ログ解析ツール"""
    
    def __init__(self, structured_logger: StructuredLogger):
        self.logger = structured_logger
    
    def generate_execution_summary(self, session_id: Optional[str] = None,
                                 start_time: Optional[datetime] = None,
                                 end_time: Optional[datetime] = None) -> Dict[str, Any]:
        """実行サマリーレポート生成"""
        # セッション関連のログを取得
        logs = self.logger.query_logs(
            start_time=start_time,
            end_time=end_time,
            limit=10000
        )
        
        if session_id:
            logs = [log for log in logs if log.get('session_id') == session_id]
        
        # 統計情報の集計
        summary = {
            'session_id': session_id,
            'analysis_period': {
                'start': start_time.isoformat() if start_time else None,
                'end': end_time.isoformat() if end_time else None
            },
            'total_log_entries': len(logs),
            'task_statistics': self._analyze_tasks(logs),
            'cost_statistics': self._analyze_costs(logs),
            'error_statistics': self._analyze_errors(logs),
            'performance_statistics': self._analyze_performance(logs),
            'safety_statistics': self._analyze_safety(logs)
        }
        
        return summary
    
    def _analyze_tasks(self, logs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """タスク統計分析"""
        task_logs = [log for log in logs if log.get('category') == 'task_execution']
        
        completed_tasks = []
        failed_tasks = []
        
        for log in task_logs:
            extra_data = log.get('extra_data', {})
            if 'success' in extra_data:
                if extra_data['success']:
                    completed_tasks.append(log)
                else:
                    failed_tasks.append(log)
        
        return {
            'total_tasks': len(set(log.get('task_id') for log in task_logs if log.get('task_id'))),
            'completed_tasks': len(completed_tasks),
            'failed_tasks': len(failed_tasks),
            'success_rate': len(completed_tasks) / max(len(completed_tasks) + len(failed_tasks), 1),
            'average_execution_time_ms': self._calculate_average_execution_time(task_logs),
            'quality_score_distribution': self._analyze_quality_scores(completed_tasks)
        }
    
    def _analyze_costs(self, logs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """コスト統計分析"""
        cost_logs = [log for log in logs if log.get('category') == 'cost_management']
        
        total_cost = 0.0
        service_costs = {}
        
        for log in cost_logs:
            extra_data = log.get('extra_data', {})
            cost = extra_data.get('cost', 0.0)
            service = extra_data.get('service_type', 'unknown')
            
            total_cost += cost
            service_costs[service] = service_costs.get(service, 0.0) + cost
        
        return {
            'total_cost': total_cost,
            'service_breakdown': service_costs,
            'cost_entries': len(cost_logs)
        }
    
    def _analyze_errors(self, logs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """エラー統計分析"""
        error_logs = [log for log in logs if log.get('level') in ['ERROR', 'CRITICAL']]
        
        error_types = {}
        components_with_errors = {}
        
        for log in error_logs:
            component = log.get('component', 'unknown')
            error_details = log.get('error_details', {})
            error_type = error_details.get('exception_type', 'unknown')
            
            error_types[error_type] = error_types.get(error_type, 0) + 1
            components_with_errors[component] = components_with_errors.get(component, 0) + 1
        
        return {
            'total_errors': len(error_logs),
            'error_types': error_types,
            'components_with_errors': components_with_errors
        }
    
    def _analyze_performance(self, logs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """パフォーマンス統計分析"""
        perf_logs = [log for log in logs if log.get('category') == 'performance']
        
        metrics = {}
        for log in perf_logs:
            extra_data = log.get('extra_data', {})
            metric_name = extra_data.get('metric_name', 'unknown')
            value = extra_data.get('value', 0)
            
            if metric_name not in metrics:
                metrics[metric_name] = []
            metrics[metric_name].append(value)
        
        # 統計値計算
        metric_stats = {}
        for metric_name, values in metrics.items():
            if values:
                metric_stats[metric_name] = {
                    'count': len(values),
                    'average': sum(values) / len(values),
                    'min': min(values),
                    'max': max(values)
                }
        
        return metric_stats
    
    def _analyze_safety(self, logs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """安全性統計分析"""
        safety_logs = [log for log in logs if log.get('category') == 'safety']
        
        violations = {}
        for log in safety_logs:
            extra_data = log.get('extra_data', {})
            violation_type = extra_data.get('violation_type', 'unknown')
            violations[violation_type] = violations.get(violation_type, 0) + 1
        
        return {
            'total_safety_events': len(safety_logs),
            'violation_breakdown': violations
        }
    
    def _calculate_average_execution_time(self, task_logs: List[Dict[str, Any]]) -> Optional[float]:
        """平均実行時間計算"""
        execution_times = [
            log.get('execution_time_ms', 0) for log in task_logs 
            if log.get('execution_time_ms') is not None and log.get('execution_time_ms') > 0
        ]
        
        if execution_times:
            return sum(execution_times) / len(execution_times)
        return None
    
    def _analyze_quality_scores(self, completed_tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """品質スコア分布分析"""
        quality_scores = []
        
        for log in completed_tasks:
            extra_data = log.get('extra_data', {})
            score = extra_data.get('quality_score')
            if score is not None:
                quality_scores.append(score)
        
        if not quality_scores:
            return {}
        
        return {
            'count': len(quality_scores),
            'average': sum(quality_scores) / len(quality_scores),
            'min': min(quality_scores),
            'max': max(quality_scores),
            'high_quality_count': len([s for s in quality_scores if s >= 0.8]),
            'medium_quality_count': len([s for s in quality_scores if 0.6 <= s < 0.8]),
            'low_quality_count': len([s for s in quality_scores if s < 0.6])
        }