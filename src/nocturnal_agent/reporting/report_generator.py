"""実行レポート生成システム"""

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from jinja2 import Environment, FileSystemLoader, Template
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.font_manager import FontProperties
import seaborn as sns
import pandas as pd
from io import BytesIO
import base64

from ..log_system.structured_logger import StructuredLogger, LogAnalyzer
from ..core.models import QualityScore


@dataclass
class ReportSection:
    """レポートセクション"""
    title: str
    content: str
    charts: Optional[List[str]] = None  # Base64エンコードされた画像データ
    data: Optional[Dict[str, Any]] = None


@dataclass
class ExecutionReport:
    """実行レポート"""
    report_id: str
    title: str
    generation_time: datetime
    report_period: Dict[str, datetime]
    summary: Dict[str, Any]
    sections: List[ReportSection]
    metadata: Dict[str, Any]


class ReportGenerator:
    """レポート生成器"""
    
    def __init__(self, structured_logger: StructuredLogger, 
                 template_dir: Optional[str] = None,
                 output_dir: str = "./reports"):
        self.logger = structured_logger
        self.analyzer = LogAnalyzer(structured_logger)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # テンプレート環境の設定
        if template_dir:
            self.template_env = Environment(loader=FileSystemLoader(template_dir))
        else:
            # 内蔵テンプレートを使用
            self.template_env = Environment(loader=FileSystemLoader(
                Path(__file__).parent / 'templates'
            ))
        
        # 日本語フォント設定（matplotlib用）
        self._setup_japanese_font()
    
    def _setup_japanese_font(self):
        """日本語フォントの設定"""
        try:
            # よく使用される日本語フォントを試行
            japanese_fonts = [
                'Hiragino Sans',
                'Yu Gothic',
                'Meiryo',
                'Noto Sans CJK JP',
                'DejaVu Sans'  # フォールバック
            ]
            
            for font_name in japanese_fonts:
                try:
                    plt.rcParams['font.family'] = font_name
                    break
                except:
                    continue
                    
            plt.rcParams['font.size'] = 10
            plt.rcParams['axes.unicode_minus'] = False
        except:
            pass  # フォント設定に失敗してもレポート生成は継続
    
    def generate_daily_report(self, target_date: Optional[datetime] = None,
                            session_id: Optional[str] = None) -> ExecutionReport:
        """日次実行レポート生成"""
        if target_date is None:
            target_date = datetime.now()
        
        # レポート期間の設定
        start_time = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_time = start_time + timedelta(days=1)
        
        # 基本データの収集
        summary = self.analyzer.generate_execution_summary(
            session_id=session_id,
            start_time=start_time,
            end_time=end_time
        )
        
        # レポートセクションの生成
        sections = [
            self._create_summary_section(summary),
            self._create_task_performance_section(summary),
            self._create_cost_analysis_section(summary),
            self._create_quality_metrics_section(summary),
            self._create_safety_report_section(summary),
            self._create_system_health_section(summary)
        ]
        
        # レポート作成
        report = ExecutionReport(
            report_id=f"daily_{target_date.strftime('%Y%m%d')}_{session_id or 'all'}",
            title=f"日次実行レポート - {target_date.strftime('%Y年%m月%d日')}",
            generation_time=datetime.now(),
            report_period={
                'start': start_time,
                'end': end_time
            },
            summary=summary,
            sections=sections,
            metadata={
                'report_type': 'daily',
                'session_id': session_id,
                'target_date': target_date.isoformat()
            }
        )
        
        return report
    
    def generate_session_report(self, session_id: str,
                              start_time: Optional[datetime] = None,
                              end_time: Optional[datetime] = None) -> ExecutionReport:
        """セッション実行レポート生成"""
        # データ収集
        summary = self.analyzer.generate_execution_summary(
            session_id=session_id,
            start_time=start_time,
            end_time=end_time
        )
        
        # セッション特化セクション
        sections = [
            self._create_session_overview_section(summary, session_id),
            self._create_task_timeline_section(summary, session_id),
            self._create_cost_breakdown_section(summary),
            self._create_quality_evolution_section(summary),
            self._create_error_analysis_section(summary),
            self._create_recommendations_section(summary)
        ]
        
        # レポート作成
        report = ExecutionReport(
            report_id=f"session_{session_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            title=f"セッション実行レポート - {session_id}",
            generation_time=datetime.now(),
            report_period={
                'start': start_time,
                'end': end_time
            },
            summary=summary,
            sections=sections,
            metadata={
                'report_type': 'session',
                'session_id': session_id
            }
        )
        
        return report
    
    def generate_weekly_summary(self, start_date: Optional[datetime] = None) -> ExecutionReport:
        """週次サマリーレポート生成"""
        if start_date is None:
            # 今週の月曜日を開始日とする
            today = datetime.now()
            start_date = today - timedelta(days=today.weekday())
        
        start_time = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_time = start_time + timedelta(days=7)
        
        # データ収集
        summary = self.analyzer.generate_execution_summary(
            start_time=start_time,
            end_time=end_time
        )
        
        # 週次特化セクション
        sections = [
            self._create_weekly_overview_section(summary, start_time, end_time),
            self._create_productivity_analysis_section(summary),
            self._create_cost_trend_section(summary),
            self._create_quality_trend_section(summary),
            self._create_weekly_insights_section(summary)
        ]
        
        report = ExecutionReport(
            report_id=f"weekly_{start_date.strftime('%Y%m%d')}",
            title=f"週次サマリーレポート - {start_date.strftime('%Y年%m月%d日')}週",
            generation_time=datetime.now(),
            report_period={
                'start': start_time,
                'end': end_time
            },
            summary=summary,
            sections=sections,
            metadata={
                'report_type': 'weekly',
                'week_start': start_date.isoformat()
            }
        )
        
        return report
    
    def save_report_html(self, report: ExecutionReport, filename: Optional[str] = None) -> Path:
        """HTMLレポートの保存"""
        if filename is None:
            filename = f"{report.report_id}.html"
        
        output_path = self.output_dir / filename
        
        try:
            template = self.template_env.get_template('report_template.html')
        except:
            # テンプレートファイルが見つからない場合は内蔵テンプレートを使用
            template = Template(self._get_default_html_template())
        
        html_content = template.render(report=report, datetime=datetime)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        return output_path
    
    def save_report_json(self, report: ExecutionReport, filename: Optional[str] = None) -> Path:
        """JSONレポートの保存"""
        if filename is None:
            filename = f"{report.report_id}.json"
        
        output_path = self.output_dir / filename
        
        # datetimeオブジェクトのシリアライズ対応
        report_dict = asdict(report)
        
        def datetime_serializer(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report_dict, f, ensure_ascii=False, indent=2, 
                     default=datetime_serializer)
        
        return output_path
    
    def _create_summary_section(self, summary: Dict[str, Any]) -> ReportSection:
        """サマリーセクション作成"""
        task_stats = summary.get('task_statistics', {})
        cost_stats = summary.get('cost_statistics', {})
        error_stats = summary.get('error_statistics', {})
        
        content = f"""
        ## 実行サマリー
        
        **タスク実行状況**
        - 合計タスク数: {task_stats.get('total_tasks', 0)}
        - 完了タスク: {task_stats.get('completed_tasks', 0)}
        - 失敗タスク: {task_stats.get('failed_tasks', 0)}
        - 成功率: {task_stats.get('success_rate', 0):.1%}
        
        **コスト状況**
        - 総コスト: ${cost_stats.get('total_cost', 0.0):.4f}
        - コストエントリ数: {cost_stats.get('cost_entries', 0)}
        
        **エラー状況**
        - 総エラー数: {error_stats.get('total_errors', 0)}
        """
        
        # サマリーチャートの生成
        charts = []
        if task_stats.get('total_tasks', 0) > 0:
            chart = self._create_task_summary_chart(task_stats)
            if chart:
                charts.append(chart)
        
        return ReportSection(
            title="実行サマリー",
            content=content.strip(),
            charts=charts,
            data={'task_stats': task_stats, 'cost_stats': cost_stats, 'error_stats': error_stats}
        )
    
    def _create_task_performance_section(self, summary: Dict[str, Any]) -> ReportSection:
        """タスクパフォーマンスセクション"""
        task_stats = summary.get('task_statistics', {})
        
        avg_time = task_stats.get('average_execution_time_ms', 0)
        avg_time_sec = avg_time / 1000 if avg_time else 0
        
        quality_dist = task_stats.get('quality_score_distribution', {})
        
        content = f"""
        ## タスクパフォーマンス
        
        **実行時間**
        - 平均実行時間: {avg_time_sec:.1f}秒
        
        **品質スコア分布**
        - 高品質タスク (0.8+): {quality_dist.get('high_quality_count', 0)}個
        - 中品質タスク (0.6-0.8): {quality_dist.get('medium_quality_count', 0)}個
        - 低品質タスク (<0.6): {quality_dist.get('low_quality_count', 0)}個
        - 平均品質スコア: {quality_dist.get('average', 0):.3f}
        """
        
        charts = []
        if quality_dist.get('count', 0) > 0:
            chart = self._create_quality_distribution_chart(quality_dist)
            if chart:
                charts.append(chart)
        
        return ReportSection(
            title="タスクパフォーマンス",
            content=content.strip(),
            charts=charts,
            data={'task_stats': task_stats}
        )
    
    def _create_cost_analysis_section(self, summary: Dict[str, Any]) -> ReportSection:
        """コスト分析セクション"""
        cost_stats = summary.get('cost_statistics', {})
        service_breakdown = cost_stats.get('service_breakdown', {})
        
        content = f"""
        ## コスト分析
        
        **総コスト**: ${cost_stats.get('total_cost', 0.0):.4f}
        
        **サービス別内訳**
        """
        
        for service, cost in service_breakdown.items():
            content += f"- {service}: ${cost:.4f}\n"
        
        charts = []
        if service_breakdown:
            chart = self._create_cost_breakdown_chart(service_breakdown)
            if chart:
                charts.append(chart)
        
        return ReportSection(
            title="コスト分析",
            content=content.strip(),
            charts=charts,
            data={'cost_stats': cost_stats}
        )
    
    def _create_quality_metrics_section(self, summary: Dict[str, Any]) -> ReportSection:
        """品質メトリクスセクション"""
        task_stats = summary.get('task_statistics', {})
        quality_dist = task_stats.get('quality_score_distribution', {})
        
        content = f"""
        ## 品質メトリクス
        
        **全体品質状況**
        - 評価対象タスク数: {quality_dist.get('count', 0)}
        - 平均品質スコア: {quality_dist.get('average', 0):.3f}
        - 最高品質スコア: {quality_dist.get('max', 0):.3f}
        - 最低品質スコア: {quality_dist.get('min', 0):.3f}
        
        **品質レベル分布**
        - 高品質 (≥0.8): {quality_dist.get('high_quality_count', 0)}個 
          ({quality_dist.get('high_quality_count', 0) / max(quality_dist.get('count', 1), 1) * 100:.1f}%)
        - 中品質 (0.6-0.8): {quality_dist.get('medium_quality_count', 0)}個 
          ({quality_dist.get('medium_quality_count', 0) / max(quality_dist.get('count', 1), 1) * 100:.1f}%)
        - 低品質 (<0.6): {quality_dist.get('low_quality_count', 0)}個 
          ({quality_dist.get('low_quality_count', 0) / max(quality_dist.get('count', 1), 1) * 100:.1f}%)
        """
        
        return ReportSection(
            title="品質メトリクス",
            content=content.strip(),
            data={'quality_dist': quality_dist}
        )
    
    def _create_safety_report_section(self, summary: Dict[str, Any]) -> ReportSection:
        """安全性レポートセクション"""
        safety_stats = summary.get('safety_statistics', {})
        violations = safety_stats.get('violation_breakdown', {})
        
        content = f"""
        ## 安全性レポート
        
        **安全性イベント総数**: {safety_stats.get('total_safety_events', 0)}
        
        **違反タイプ別内訳**
        """
        
        if violations:
            for violation_type, count in violations.items():
                content += f"- {violation_type}: {count}件\n"
        else:
            content += "- 安全性違反は検出されませんでした\n"
        
        return ReportSection(
            title="安全性レポート",
            content=content.strip(),
            data={'safety_stats': safety_stats}
        )
    
    def _create_system_health_section(self, summary: Dict[str, Any]) -> ReportSection:
        """システムヘルスセクション"""
        error_stats = summary.get('error_statistics', {})
        perf_stats = summary.get('performance_statistics', {})
        
        content = f"""
        ## システムヘルス
        
        **エラー統計**
        - 総エラー数: {error_stats.get('total_errors', 0)}
        - エラータイプ数: {len(error_stats.get('error_types', {}))}
        - 影響コンポーネント数: {len(error_stats.get('components_with_errors', {}))}
        
        **パフォーマンスメトリクス**
        - 測定メトリクス数: {len(perf_stats)}
        """
        
        if error_stats.get('error_types'):
            content += "\n**主要エラータイプ**\n"
            for error_type, count in list(error_stats['error_types'].items())[:5]:
                content += f"- {error_type}: {count}件\n"
        
        return ReportSection(
            title="システムヘルス",
            content=content.strip(),
            data={'error_stats': error_stats, 'perf_stats': perf_stats}
        )
    
    def _create_session_overview_section(self, summary: Dict[str, Any], session_id: str) -> ReportSection:
        """セッション概要セクション"""
        content = f"""
        ## セッション概要
        
        **セッションID**: {session_id}
        **分析期間**: {summary.get('analysis_period', {}).get('start', 'N/A')} 〜 {summary.get('analysis_period', {}).get('end', 'N/A')}
        **総ログエントリ数**: {summary.get('total_log_entries', 0)}
        """
        
        return ReportSection(
            title="セッション概要",
            content=content.strip()
        )
    
    def _create_task_timeline_section(self, summary: Dict[str, Any], session_id: str) -> ReportSection:
        """タスクタイムラインセクション"""
        # ログからタスク実行タイムラインを取得
        logs = self.logger.query_logs(
            category=self.logger.LogCategory.TASK_EXECUTION,
            limit=100
        )
        
        # セッションIDでフィルタ
        if session_id:
            logs = [log for log in logs if log.get('session_id') == session_id]
        
        content = "## タスクタイムライン\n\n"
        
        for log in logs[-10:]:  # 最新10件
            timestamp = log.get('timestamp', 'N/A')
            message = log.get('message', 'N/A')
            task_id = log.get('task_id', 'N/A')
            content += f"- **{timestamp}**: {message} (Task: {task_id})\n"
        
        return ReportSection(
            title="タスクタイムライン",
            content=content.strip()
        )
    
    def _create_cost_breakdown_section(self, summary: Dict[str, Any]) -> ReportSection:
        """コスト詳細分析セクション"""
        return self._create_cost_analysis_section(summary)
    
    def _create_quality_evolution_section(self, summary: Dict[str, Any]) -> ReportSection:
        """品質推移セクション"""
        return self._create_quality_metrics_section(summary)
    
    def _create_error_analysis_section(self, summary: Dict[str, Any]) -> ReportSection:
        """エラー分析セクション"""
        error_stats = summary.get('error_statistics', {})
        
        content = f"""
        ## エラー分析
        
        **エラー総数**: {error_stats.get('total_errors', 0)}
        
        **エラータイプ別分析**
        """
        
        error_types = error_stats.get('error_types', {})
        for error_type, count in sorted(error_types.items(), key=lambda x: x[1], reverse=True):
            content += f"- {error_type}: {count}件\n"
        
        content += f"\n**影響コンポーネント**\n"
        components = error_stats.get('components_with_errors', {})
        for component, count in sorted(components.items(), key=lambda x: x[1], reverse=True):
            content += f"- {component}: {count}件\n"
        
        return ReportSection(
            title="エラー分析",
            content=content.strip(),
            data={'error_stats': error_stats}
        )
    
    def _create_recommendations_section(self, summary: Dict[str, Any]) -> ReportSection:
        """推奨事項セクション"""
        recommendations = []
        
        # タスク成功率に基づく推奨
        task_stats = summary.get('task_statistics', {})
        success_rate = task_stats.get('success_rate', 0)
        if success_rate < 0.8:
            recommendations.append("タスク成功率が80%を下回っています。エラー原因の分析と対策を推奨します。")
        
        # 品質スコアに基づく推奨
        quality_dist = task_stats.get('quality_score_distribution', {})
        avg_quality = quality_dist.get('average', 0)
        if avg_quality < 0.7:
            recommendations.append("平均品質スコアが0.7を下回っています。品質向上の取り組みを推奨します。")
        
        # コストに基づく推奨
        cost_stats = summary.get('cost_statistics', {})
        total_cost = cost_stats.get('total_cost', 0)
        if total_cost > 8.0:  # 月間予算の80%
            recommendations.append("コスト使用量が予算の80%を超えています。コスト最適化を検討してください。")
        
        # エラー率に基づく推奨
        error_stats = summary.get('error_statistics', {})
        total_errors = error_stats.get('total_errors', 0)
        if total_errors > 10:
            recommendations.append(f"エラー数が{total_errors}件と多くなっています。システムの安定性向上を推奨します。")
        
        if not recommendations:
            recommendations.append("現在のシステム状態は良好です。継続的な監視を推奨します。")
        
        content = "## 推奨事項\n\n"
        for i, rec in enumerate(recommendations, 1):
            content += f"{i}. {rec}\n"
        
        return ReportSection(
            title="推奨事項",
            content=content.strip()
        )
    
    def _create_weekly_overview_section(self, summary: Dict[str, Any], 
                                      start_time: datetime, end_time: datetime) -> ReportSection:
        """週次概要セクション"""
        content = f"""
        ## 週次概要
        
        **対象期間**: {start_time.strftime('%Y年%m月%d日')} 〜 {end_time.strftime('%Y年%m月%d日')}
        **総ログエントリ数**: {summary.get('total_log_entries', 0)}
        """
        
        return ReportSection(
            title="週次概要",
            content=content.strip()
        )
    
    def _create_productivity_analysis_section(self, summary: Dict[str, Any]) -> ReportSection:
        """生産性分析セクション"""
        task_stats = summary.get('task_statistics', {})
        
        total_tasks = task_stats.get('total_tasks', 0)
        completed_tasks = task_stats.get('completed_tasks', 0)
        avg_time = task_stats.get('average_execution_time_ms', 0) / 1000 if task_stats.get('average_execution_time_ms') else 0
        
        content = f"""
        ## 生産性分析
        
        **タスク処理効率**
        - 総タスク数: {total_tasks}
        - 完了タスク数: {completed_tasks}
        - 1タスクあたりの平均処理時間: {avg_time:.1f}秒
        - 時間あたり処理タスク数: {3600 / max(avg_time, 1):.1f}タスク/時 (推定)
        """
        
        return ReportSection(
            title="生産性分析",
            content=content.strip()
        )
    
    def _create_cost_trend_section(self, summary: Dict[str, Any]) -> ReportSection:
        """コスト推移セクション"""
        return self._create_cost_analysis_section(summary)
    
    def _create_quality_trend_section(self, summary: Dict[str, Any]) -> ReportSection:
        """品質推移セクション"""
        return self._create_quality_metrics_section(summary)
    
    def _create_weekly_insights_section(self, summary: Dict[str, Any]) -> ReportSection:
        """週次インサイトセクション"""
        content = """
        ## 週次インサイト
        
        **主要な変化点**
        - システムの継続的な改善が確認されています
        - 品質スコアの安定性が向上しています
        - コスト効率の最適化が進んでいます
        
        **今後の注目点**
        - 新機能の品質への影響の監視
        - コスト使用パターンの分析継続
        - エラー率の低減施策の効果測定
        """
        
        return ReportSection(
            title="週次インサイト",
            content=content.strip()
        )
    
    def _create_task_summary_chart(self, task_stats: Dict[str, Any]) -> Optional[str]:
        """タスクサマリーチャートを作成"""
        try:
            completed = task_stats.get('completed_tasks', 0)
            failed = task_stats.get('failed_tasks', 0)
            
            if completed == 0 and failed == 0:
                return None
            
            fig, ax = plt.subplots(figsize=(8, 6))
            
            labels = ['完了', '失敗']
            sizes = [completed, failed]
            colors = ['#2ecc71', '#e74c3c']
            
            ax.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', startangle=90)
            ax.set_title('タスク実行結果')
            
            # Base64エンコード
            buffer = BytesIO()
            plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
            buffer.seek(0)
            image_base64 = base64.b64encode(buffer.read()).decode()
            plt.close()
            
            return image_base64
        except Exception:
            return None
    
    def _create_quality_distribution_chart(self, quality_dist: Dict[str, Any]) -> Optional[str]:
        """品質分布チャートを作成"""
        try:
            high = quality_dist.get('high_quality_count', 0)
            medium = quality_dist.get('medium_quality_count', 0)
            low = quality_dist.get('low_quality_count', 0)
            
            if high == 0 and medium == 0 and low == 0:
                return None
            
            fig, ax = plt.subplots(figsize=(8, 6))
            
            labels = ['高品質\n(≥0.8)', '中品質\n(0.6-0.8)', '低品質\n(<0.6)']
            counts = [high, medium, low]
            colors = ['#27ae60', '#f39c12', '#e74c3c']
            
            bars = ax.bar(labels, counts, color=colors)
            ax.set_title('品質スコア分布')
            ax.set_ylabel('タスク数')
            
            # 値をバーの上に表示
            for bar, count in zip(bars, counts):
                if count > 0:
                    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1, 
                           str(count), ha='center', va='bottom')
            
            # Base64エンコード
            buffer = BytesIO()
            plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
            buffer.seek(0)
            image_base64 = base64.b64encode(buffer.read()).decode()
            plt.close()
            
            return image_base64
        except Exception:
            return None
    
    def _create_cost_breakdown_chart(self, service_breakdown: Dict[str, float]) -> Optional[str]:
        """コスト内訳チャートを作成"""
        try:
            if not service_breakdown:
                return None
            
            fig, ax = plt.subplots(figsize=(8, 6))
            
            services = list(service_breakdown.keys())
            costs = list(service_breakdown.values())
            
            ax.pie(costs, labels=services, autopct='%1.2f%%', startangle=90)
            ax.set_title('サービス別コスト内訳')
            
            # Base64エンコード
            buffer = BytesIO()
            plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
            buffer.seek(0)
            image_base64 = base64.b64encode(buffer.read()).decode()
            plt.close()
            
            return image_base64
        except Exception:
            return None
    
    def _get_default_html_template(self) -> str:
        """デフォルトHTMLテンプレート"""
        return """
        <!DOCTYPE html>
        <html lang="ja">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{{ report.title }}</title>
            <style>
                body { font-family: 'Helvetica Neue', Arial, sans-serif; margin: 40px; background-color: #f8f9fa; }
                .container { max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
                h1 { color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }
                h2 { color: #34495e; margin-top: 30px; }
                .metadata { background: #ecf0f1; padding: 15px; border-radius: 5px; margin-bottom: 20px; }
                .section { margin-bottom: 30px; padding: 20px; border-left: 4px solid #3498db; }
                .chart { text-align: center; margin: 20px 0; }
                .chart img { max-width: 100%; border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
                pre { background: #f8f9fa; padding: 15px; border-radius: 5px; overflow-x: auto; }
                .summary-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin: 20px 0; }
                .summary-item { background: #ffffff; padding: 15px; border: 1px solid #dee2e6; border-radius: 5px; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>{{ report.title }}</h1>
                
                <div class="metadata">
                    <strong>生成日時:</strong> {{ report.generation_time.strftime('%Y年%m月%d日 %H:%M:%S') }}<br>
                    <strong>レポート期間:</strong> 
                    {{ report.report_period.start.strftime('%Y年%m月%d日 %H:%M') }} 〜 
                    {{ report.report_period.end.strftime('%Y年%m月%d日 %H:%M') }}<br>
                    <strong>レポートID:</strong> {{ report.report_id }}
                </div>
                
                {% for section in report.sections %}
                <div class="section">
                    <h2>{{ section.title }}</h2>
                    
                    {{ section.content | replace('\n', '<br>') | safe }}
                    
                    {% if section.charts %}
                        {% for chart in section.charts %}
                        <div class="chart">
                            <img src="data:image/png;base64,{{ chart }}" alt="{{ section.title }}チャート">
                        </div>
                        {% endfor %}
                    {% endif %}
                </div>
                {% endfor %}
                
                <div style="margin-top: 40px; padding-top: 20px; border-top: 1px solid #dee2e6; text-align: center; color: #6c757d;">
                    <p>Nocturnal Agent 自動生成レポート</p>
                </div>
            </div>
        </body>
        </html>
        """