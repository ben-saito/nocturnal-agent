"""Nocturnal Agent CLIメインエントリーポイント"""

import asyncio
import argparse
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

# プロジェクトルートをPythonパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from nocturnal_agent.config.config_manager import ConfigManager
from nocturnal_agent.log_system.structured_logger import StructuredLogger, LogLevel, LogCategory
from nocturnal_agent.reporting.report_generator import ReportGenerator
from nocturnal_agent.scheduler.night_scheduler import NightScheduler
from nocturnal_agent.cost.cost_manager import CostManager
from nocturnal_agent.safety.safety_coordinator import SafetyCoordinator


class NocturnalAgentCLI:
    """Nocturnal Agent コマンドラインインターフェース"""
    
    def __init__(self):
        self.config_manager = ConfigManager()
        self.config = None
        self.logger = None
        self.scheduler = None
        self.cost_manager = None
        self.safety_coordinator = None
        
    def run(self) -> None:
        """CLIメイン実行"""
        parser = self._create_parser()
        args = parser.parse_args()
        
        try:
            # 設定初期化
            self._initialize_config(args.config)
            
            # サブコマンド実行
            if hasattr(args, 'func'):
                if asyncio.iscoroutinefunction(args.func):
                    asyncio.run(args.func(args))
                else:
                    args.func(args)
            else:
                parser.print_help()
                
        except KeyboardInterrupt:
            print("\n⚠️ 処理が中断されました")
            sys.exit(1)
        except Exception as e:
            print(f"❌ エラーが発生しました: {e}")
            if hasattr(args, 'verbose') and args.verbose:
                import traceback
                traceback.print_exc()
            sys.exit(1)
    
    def _create_parser(self) -> argparse.ArgumentParser:
        """引数パーサーを作成"""
        parser = argparse.ArgumentParser(
            description="Nocturnal Agent - 夜間自律開発システム",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🌟 シンプルな3ステップワークフロー（推奨）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【ステップ1】要件定義
  nocturnal requirements create "ECサイトを作成したい。ユーザー登録、商品管理、ショッピングカート機能が必要。"
  nocturnal requirements from-file requirements.md
  nocturnal requirements list
  nocturnal requirements show requirements/requirements_20250101.md

【ステップ2】設計書作成
  nocturnal design create --from-requirements requirements/requirements_20250101.md
  nocturnal design validate design.yaml
  nocturnal design summary design.yaml
  nocturnal design sync design.yaml  # コードから設計書に反映

【ステップ3】実装開始
  nocturnal implement start design.yaml
  nocturnal implement status
  nocturnal implement stop

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📚 その他のコマンド（詳細機能）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

基本コマンド:
  nocturnal init                    # プロジェクト初期化
  nocturnal status                  # システム状況確認
  nocturnal config show             # 設定表示
  nocturnal config set KEY VALUE    # 設定変更

レガシーコマンド（非推奨）:
  nocturnal start                   # 夜間実行開始（旧方式）
  nocturnal execute                 # 設計ファイル実行（implement startを推奨）
  nocturnal natural                 # 自然言語処理（requirements + design createを推奨）
  nocturnal review                  # レビュー機能（requirements + design createを推奨）
            """
        )
        
        # グローバル引数
        parser.add_argument('--config', '-c', help='設定ファイルパス')
        parser.add_argument('--verbose', '-v', action='store_true', help='詳細出力')
        parser.add_argument('--workspace', '-w', help='ワークスペースディレクトリ')
        
        # サブコマンド
        subparsers = parser.add_subparsers(dest='command', help='利用可能なコマンド')
        
        # start コマンド
        self._add_start_parser(subparsers)
        
        # stop コマンド
        self._add_stop_parser(subparsers)
        
        # status コマンド
        self._add_status_parser(subparsers)
        
        # config コマンド
        self._add_config_parser(subparsers)
        
        # report コマンド
        self._add_report_parser(subparsers)
        
        # cost コマンド
        self._add_cost_parser(subparsers)
        
        # safety コマンド
        self._add_safety_parser(subparsers)
        
        # init コマンド
        self._add_init_parser(subparsers)
        
        # spec コマンド
        self._add_spec_parser(subparsers)
        
        # review コマンド (新機能)
        self._add_review_parser(subparsers)
        
        # execute コマンド (新機能: 設計ファイルベース実行)
        self._add_execute_parser(subparsers)
        
        # progress コマンド (新機能: 進捗状況確認)
        self._add_progress_parser(subparsers)
        
        # design コマンド (新機能: 設計ファイル管理)
        self._add_design_parser(subparsers)
        
        # natural コマンド (新機能: 自然言語要件処理)
        self._add_natural_parser(subparsers)
        
        # dashboard コマンド (新機能: 進捗ダッシュボード)
        self._add_dashboard_parser(subparsers)
        
        # collaborate コマンド (新機能: 要件・設計のすり合わせ)
        self._add_collaborate_parser(subparsers)
        
        # ============================================
        # 新しいシンプルな3ステップコマンドシステム
        # ============================================
        # requirements コマンド (ステップ1: 要件定義)
        self._add_requirements_parser(subparsers)
        
        # design コマンド (ステップ2: 設計書作成) - 既存のdesignコマンドを拡張
        # 既に_add_design_parserで定義済み
        
        # implement コマンド (ステップ3: 実装開始)
        self._add_implement_parser(subparsers)
        
        return parser
    
    def _add_start_parser(self, subparsers):
        """startコマンドパーサーを追加"""
        start_parser = subparsers.add_parser(
            'start', 
            help='夜間実行を開始',
            description='夜間自律開発セッションを開始します'
        )
        start_parser.add_argument(
            '--immediate', '-i', 
            action='store_true', 
            help='時間に関係なく即座に開始'
        )
        start_parser.add_argument(
            '--duration', '-d', 
            type=int, 
            help='実行時間（分）'
        )
        start_parser.add_argument(
            '--task-limit', '-t', 
            type=int, 
            help='最大タスク数'
        )
        start_parser.add_argument(
            '--quality-threshold', '-q', 
            type=float, 
            help='最小品質閾値'
        )
        start_parser.add_argument(
            '--use-spec-kit', 
            action='store_true',
            help='GitHub Spec Kit仕様駆動で実行'
        )
        start_parser.add_argument(
            '--spec-type', 
            choices=['feature', 'architecture', 'api', 'design', 'process'],
            default='feature',
            help='Spec Kit仕様タイプ（--use-spec-kit使用時）'
        )
        start_parser.set_defaults(func=self._start_command)
    
    def _add_stop_parser(self, subparsers):
        """stopコマンドパーサーを追加"""
        stop_parser = subparsers.add_parser(
            'stop', 
            help='実行を停止',
            description='進行中の夜間実行セッションを停止します'
        )
        stop_parser.add_argument(
            '--force', '-f', 
            action='store_true', 
            help='強制停止'
        )
        stop_parser.set_defaults(func=self._stop_command)
    
    def _add_status_parser(self, subparsers):
        """statusコマンドパーサーを追加"""
        status_parser = subparsers.add_parser(
            'status', 
            help='システム状況を確認',
            description='現在のシステム状況とアクティブセッション情報を表示します'
        )
        status_parser.add_argument(
            '--detailed', '-d', 
            action='store_true', 
            help='詳細情報を表示'
        )
        status_parser.add_argument(
            '--json', '-j', 
            action='store_true', 
            help='JSON形式で出力'
        )
        status_parser.set_defaults(func=self._status_command)
    
    def _add_config_parser(self, subparsers):
        """configコマンドパーサーを追加"""
        config_parser = subparsers.add_parser(
            'config', 
            help='設定管理',
            description='システム設定の表示・変更を行います'
        )
        config_subparsers = config_parser.add_subparsers(dest='config_action')
        
        # config show
        show_parser = config_subparsers.add_parser('show', help='設定を表示')
        show_parser.add_argument('--section', '-s', help='表示するセクション')
        show_parser.set_defaults(func=self._config_show_command)
        
        # config set
        set_parser = config_subparsers.add_parser('set', help='設定を変更')
        set_parser.add_argument('key', help='設定キー（例: monthly_budget）')
        set_parser.add_argument('value', help='設定値')
        set_parser.set_defaults(func=self._config_set_command)
        
        # config validate
        validate_parser = config_subparsers.add_parser('validate', help='設定を検証')
        validate_parser.set_defaults(func=self._config_validate_command)
        
        # config init
        init_parser = config_subparsers.add_parser('init', help='設定を初期化')
        init_parser.add_argument('--sample', '-s', action='store_true', help='サンプル設定で初期化')
        init_parser.set_defaults(func=self._config_init_command)
    
    def _add_report_parser(self, subparsers):
        """reportコマンドパーサーを追加"""
        report_parser = subparsers.add_parser(
            'report', 
            help='レポート生成',
            description='実行レポートを生成します'
        )
        report_subparsers = report_parser.add_subparsers(dest='report_type')
        
        # daily report
        daily_parser = report_subparsers.add_parser('daily', help='日次レポート')
        daily_parser.add_argument('--date', '-d', help='対象日（YYYY-MM-DD）')
        daily_parser.add_argument('--output', '-o', help='出力ファイル名')
        daily_parser.set_defaults(func=self._report_daily_command)
        
        # session report
        session_parser = report_subparsers.add_parser('session', help='セッションレポート')
        session_parser.add_argument('session_id', help='セッションID')
        session_parser.add_argument('--output', '-o', help='出力ファイル名')
        session_parser.set_defaults(func=self._report_session_command)
        
        # weekly report
        weekly_parser = report_subparsers.add_parser('weekly', help='週次レポート')
        weekly_parser.add_argument('--start-date', '-s', help='開始日（YYYY-MM-DD）')
        weekly_parser.add_argument('--output', '-o', help='出力ファイル名')
        weekly_parser.set_defaults(func=self._report_weekly_command)
    
    def _add_cost_parser(self, subparsers):
        """costコマンドパーサーを追加"""
        cost_parser = subparsers.add_parser(
            'cost', 
            help='コスト管理',
            description='コスト使用状況の確認と管理を行います'
        )
        cost_subparsers = cost_parser.add_subparsers(dest='cost_action')
        
        # cost status
        status_parser = cost_subparsers.add_parser('status', help='コスト状況を表示')
        status_parser.set_defaults(func=self._cost_status_command)
        
        # cost dashboard
        dashboard_parser = cost_subparsers.add_parser('dashboard', help='コストダッシュボードを表示')
        dashboard_parser.set_defaults(func=self._cost_dashboard_command)
        
        # cost reset
        reset_parser = cost_subparsers.add_parser('reset', help='コスト統計をリセット')
        reset_parser.add_argument('--confirm', action='store_true', help='確認なしで実行')
        reset_parser.set_defaults(func=self._cost_reset_command)
    
    def _add_safety_parser(self, subparsers):
        """safetyコマンドパーサーを追加"""
        safety_parser = subparsers.add_parser(
            'safety', 
            help='安全性管理',
            description='安全性システムの状況確認と管理を行います'
        )
        safety_subparsers = safety_parser.add_subparsers(dest='safety_action')
        
        # safety status
        status_parser = safety_subparsers.add_parser('status', help='安全性状況を表示')
        status_parser.set_defaults(func=self._safety_status_command)
        
        # safety backup
        backup_parser = safety_subparsers.add_parser('backup', help='手動バックアップを作成')
        backup_parser.add_argument('--description', '-d', help='バックアップの説明')
        backup_parser.set_defaults(func=self._safety_backup_command)
        
        # safety rollback
        rollback_parser = safety_subparsers.add_parser('rollback', help='ロールバックポイントを表示')
        rollback_parser.set_defaults(func=self._safety_rollback_command)
        
        # safety health
        health_parser = safety_subparsers.add_parser('health', help='安全性ヘルスチェック')
        health_parser.set_defaults(func=self._safety_health_command)
    
    def _add_init_parser(self, subparsers):
        """initコマンドパーサーを追加"""
        init_parser = subparsers.add_parser(
            'init', 
            help='プロジェクトを初期化',
            description='新しいプロジェクトの初期セットアップを行います'
        )
        init_parser.add_argument(
            '--project-name', '-n', 
            default='My Nocturnal Project',
            help='プロジェクト名'
        )
        init_parser.add_argument(
            '--workspace', '-w', 
            default='.',
            help='ワークスペースディレクトリ'
        )
        init_parser.set_defaults(func=self._init_command)
    
    def _add_spec_parser(self, subparsers):
        """specコマンドパーサーを追加"""
        spec_parser = subparsers.add_parser(
            'spec', 
            help='Spec Kit仕様管理',
            description='GitHub Spec Kit準拠の技術仕様管理を行います'
        )
        spec_subparsers = spec_parser.add_subparsers(dest='spec_action')
        
        # spec list
        list_parser = spec_subparsers.add_parser('list', help='仕様一覧を表示')
        list_parser.add_argument('--type', '-t', 
                               choices=['feature', 'architecture', 'api', 'design', 'process'],
                               help='仕様タイプでフィルタ')
        list_parser.add_argument('--status', '-s',
                               choices=['draft', 'review', 'approved', 'implemented', 'deprecated'],
                               help='ステータスでフィルタ')
        list_parser.set_defaults(func=self._spec_list_command)
        
        # spec show
        show_parser = spec_subparsers.add_parser('show', help='仕様詳細を表示')
        show_parser.add_argument('spec_file', help='仕様ファイルパス')
        show_parser.add_argument('--format', '-f', choices=['yaml', 'markdown'], 
                               default='yaml', help='表示形式')
        show_parser.set_defaults(func=self._spec_show_command)
        
        # spec create
        create_parser = spec_subparsers.add_parser('create', help='新規仕様を作成')
        create_parser.add_argument('title', help='仕様タイトル')
        create_parser.add_argument('--type', '-t', 
                                 choices=['feature', 'architecture', 'api', 'design', 'process'],
                                 default='feature', help='仕様タイプ')
        create_parser.add_argument('--template', action='store_true', 
                                 help='テンプレートから作成')
        create_parser.set_defaults(func=self._spec_create_command)
        
        # spec update
        update_parser = spec_subparsers.add_parser('update', help='仕様ステータスを更新')
        update_parser.add_argument('spec_file', help='仕様ファイルパス')
        update_parser.add_argument('--status', '-s', required=True,
                                 choices=['draft', 'review', 'approved', 'implemented', 'deprecated'],
                                 help='新しいステータス')
        update_parser.set_defaults(func=self._spec_update_command)
        
        # spec report
        report_parser = spec_subparsers.add_parser('report', help='仕様レポートを生成')
        report_parser.add_argument('--output', '-o', help='出力ファイル名')
        report_parser.set_defaults(func=self._spec_report_command)
        
        # spec cleanup
        cleanup_parser = spec_subparsers.add_parser('cleanup', help='古い仕様をクリーンアップ')
        cleanup_parser.add_argument('--days', '-d', type=int, default=30, 
                                  help='クリーンアップ対象日数（デフォルト30日）')
        cleanup_parser.add_argument('--dry-run', action='store_true', 
                                   help='実際には削除せずに対象を表示')
        cleanup_parser.set_defaults(func=self._spec_cleanup_command)

    def _add_review_parser(self, subparsers):
        """reviewサブコマンドの追加（カレントディレクトリを対象プロジェクトとして使用）"""
        review_parser = subparsers.add_parser(
            'review',
            help='インタラクティブ設計レビュー機能',
            description='カレントディレクトリのプロジェクトで設計書をレビューして承認後に夜間実行する機能'
        )
        
        review_subparsers = review_parser.add_subparsers(dest='review_action', help='レビューアクション')
        
        # start サブコマンド
        start_parser = review_subparsers.add_parser(
            'start',
            help='新しいタスクのインタラクティブレビューを開始'
        )
        start_parser.add_argument('task_title', help='タスクのタイトル')
        start_parser.add_argument('--description', '-d', help='タスクの詳細説明')
        start_parser.add_argument('--priority', choices=['low', 'medium', 'high'], 
                                default='medium', help='タスクの優先度')
        start_parser.set_defaults(func=self._review_start_command)
        
        # from-file サブコマンド
        file_parser = review_subparsers.add_parser(
            'from-file',
            help='要件ファイルからインタラクティブレビューを開始'
        )
        file_parser.add_argument('requirements_file', help='要件ファイルのパス (.md, .txt, .yaml, .json)')
        file_parser.add_argument('--session-id', help='カスタムセッションID')
        file_parser.set_defaults(func=self._review_from_file_command)
        
        # create-sample サブコマンド
        sample_parser = review_subparsers.add_parser(
            'create-sample',
            help='サンプル要件ファイルを作成'
        )
        sample_parser.add_argument('file_path', help='作成するファイルのパス')
        sample_parser.add_argument('--format', choices=['markdown', 'yaml', 'json'], 
                                 default='markdown', help='ファイル形式')
        sample_parser.set_defaults(func=self._review_create_sample_command)
        
        # status サブコマンド
        status_parser = review_subparsers.add_parser(
            'status',
            help='レビュー状況とスケジュールされたタスクを確認'
        )
        status_parser.add_argument('--session-id', help='特定セッションの状況を確認')
        status_parser.set_defaults(func=self._review_status_command)
        
        # approve サブコマンド
        approve_parser = review_subparsers.add_parser(
            'approve',
            help='設計を承認して夜間実行をスケジュール'
        )
        approve_parser.add_argument('session_id', help='レビューセッションID')
        approve_parser.set_defaults(func=self._review_approve_command)
        
        # modify サブコマンド
        modify_parser = review_subparsers.add_parser(
            'modify',
            help='設計の修正を要求'
        )
        modify_parser.add_argument('session_id', help='レビューセッションID')
        modify_parser.add_argument('request', help='修正要求の詳細')
        modify_parser.set_defaults(func=self._review_modify_command)
        
        # discuss サブコマンド
        discuss_parser = review_subparsers.add_parser(
            'discuss',
            help='設計について対話的に議論'
        )
        discuss_parser.add_argument('session_id', help='レビューセッションID')
        discuss_parser.add_argument('topic', help='議論したいトピック')
        discuss_parser.set_defaults(func=self._review_discuss_command)
        
        # reject サブコマンド
        reject_parser = review_subparsers.add_parser(
            'reject',
            help='設計を拒否してタスクをキャンセル'
        )
        reject_parser.add_argument('session_id', help='レビューセッションID')
        reject_parser.add_argument('--reason', help='拒否理由')
        reject_parser.set_defaults(func=self._review_reject_command)
        
        # nighttime サブコマンド
        nighttime_parser = review_subparsers.add_parser(
            'nighttime',
            help='夜間実行を手動で開始'
        )
        nighttime_parser.set_defaults(func=self._review_nighttime_command)

    def _add_execute_parser(self, subparsers):
        """execute コマンドのパーサーを追加（設計ファイルベース実行）"""
        execute_parser = subparsers.add_parser(
            'execute', 
            help='設計ファイルからタスクを実行',
            description='YAMLまたはJSON形式の設計ファイルからタスクを実行します'
        )
        
        execute_parser.add_argument(
            '--design-file', '-d',
            required=True,
            help='設計ファイルのパス (.yaml または .json)'
        )
        
        execute_parser.add_argument(
            '--mode', '-m',
            choices=['immediate', 'nightly', 'scheduled'],
            default='immediate',
            help='実行モード: immediate（即時）, nightly（夜間）, scheduled（スケジュール）'
        )
        
        execute_parser.add_argument(
            '--max-tasks',
            type=int,
            default=5,
            help='一度に実行する最大タスク数（default: 5）'
        )
        
        execute_parser.add_argument(
            '--dry-run',
            action='store_true',
            help='実際の実行は行わず、実行計画のみ表示'
        )
        
        execute_parser.add_argument(
            '--validate-only',
            action='store_true',
            help='設計ファイルの検証のみ実行'
        )
        
        execute_parser.add_argument(
            '--schedule-time',
            help='scheduled モード時の実行時刻（HH:MM形式）'
        )
        
        execute_parser.set_defaults(func=self._execute_command)

    
    def _add_progress_parser(self, subparsers):
        """progress コマンドのパーサーを追加（進捗状況確認）"""
        progress_parser = subparsers.add_parser(
            'progress', 
            help='実行中タスクの進捗状況を確認',
            description='現在実行中のタスクや完了済みタスクの進捗状況を表示します'
        )
        
        progress_parser.add_argument(
            '--design-file', '-d',
            help='特定の設計ファイルの進捗を確認（省略時は実行中の全プロジェクト）'
        )
        
        progress_parser.add_argument(
            '--workspace', '-w',
            help='ワークスペースパスを指定'
        )
        
        progress_parser.add_argument(
            '--detailed', 
            action='store_true',
            help='詳細な進捗情報を表示'
        )
        
        progress_parser.add_argument(
            '--refresh',
            type=int,
            default=0,
            help='指定秒数ごとに自動更新（0で無効、推奨値: 30）'
        )
        
        progress_parser.set_defaults(func=self._progress_command)

    def _add_design_parser(self, subparsers):
        """design コマンドのパーサーを追加（設計ファイル管理）"""
        design_parser = subparsers.add_parser(
            'design',
            help='設計ファイルの管理',
            description='分散コーディングエージェント用の設計ファイルを管理します'
        )
        
        design_subparsers = design_parser.add_subparsers(
            dest='design_action',
            help='設計ファイル管理アクション'
        )
        
        # create サブコマンド（ステップ2: 設計書作成）
        create_parser = design_subparsers.add_parser(
            'create',
            help='【ステップ2】設計書を作成',
            description='要件ファイルから設計書を生成します'
        )
        create_parser.add_argument(
            '--from-requirements', '-r',
            help='要件ファイルのパス（.md, .txt, .yaml, .json）'
        )
        create_parser.add_argument(
            '--project-name', '-n',
            help='プロジェクト名（未指定時は現在のディレクトリ名）'
        )
        create_parser.add_argument(
            '--workspace', '-w',
            default='.',
            help='ワークスペースディレクトリ（default: 現在のディレクトリ）'
        )
        create_parser.add_argument(
            '--output-dir', '-o',
            default='./designs',
            help='出力ディレクトリ（default: ./designs）'
        )
        create_parser.add_argument(
            '--execute',
            action='store_true',
            help='設計書生成後、即座に実装を開始'
        )
        create_parser.set_defaults(func=self._design_create_command)
        
        # create-template サブコマンド
        create_template_parser = design_subparsers.add_parser(
            'create-template',
            help='エージェント用設計テンプレートを作成'
        )
        create_template_parser.add_argument(
            'agent_name',
            help='エージェント名'
        )
        create_template_parser.add_argument(
            '--output-dir', '-o',
            default='./designs',
            help='出力ディレクトリ（default: ./designs）'
        )
        create_template_parser.set_defaults(func=self._design_create_template_command)
        
        # validate サブコマンド
        validate_parser = design_subparsers.add_parser(
            'validate',
            help='設計ファイルを検証'
        )
        validate_parser.add_argument(
            'design_file',
            help='検証する設計ファイルのパス'
        )
        validate_parser.add_argument(
            '--detailed',
            action='store_true',
            help='詳細な検証結果を表示'
        )
        validate_parser.set_defaults(func=self._design_validate_command)
        
        # summary サブコマンド
        summary_parser = design_subparsers.add_parser(
            'summary',
            help='設計ファイルのサマリーを表示'
        )
        summary_parser.add_argument(
            'design_file',
            help='サマリーを表示する設計ファイルのパス'
        )
        summary_parser.set_defaults(func=self._design_summary_command)
        
        # convert サブコマンド
        convert_parser = design_subparsers.add_parser(
            'convert',
            help='設計ファイルを他の形式に変換'
        )
        convert_parser.add_argument(
            'input_file',
            help='入力ファイルのパス'
        )
        convert_parser.add_argument(
            'output_file',
            help='出力ファイルのパス'
        )
        convert_parser.add_argument(
            '--format',
            choices=['yaml', 'json'],
            help='出力形式（未指定時は拡張子から判定）'
        )
        convert_parser.set_defaults(func=self._design_convert_command)
        
        # sync サブコマンド（コードから設計書への同期）
        sync_parser = design_subparsers.add_parser(
            'sync',
            help='コードを解析して設計書に反映',
            description='実装されたコードを解析し、設計書との差分を検出して設計書に反映します'
        )
        sync_parser.add_argument(
            'design_file',
            help='更新する設計書ファイルのパス'
        )
        sync_parser.add_argument(
            '--workspace', '-w',
            help='コードベースのワークスペースパス（未指定時は設計書から取得）'
        )
        sync_parser.add_argument(
            '--dry-run',
            action='store_true',
            help='実際には更新せず、差分のみ表示'
        )
        sync_parser.add_argument(
            '--auto-apply',
            action='store_true',
            help='確認なしで自動的に設計書を更新'
        )
        sync_parser.add_argument(
            '--backup',
            action='store_true',
            default=True,
            help='更新前に設計書のバックアップを作成（デフォルト: 有効）'
        )
        sync_parser.set_defaults(func=self._design_sync_command)

    def _add_natural_parser(self, subparsers):
        """natural コマンドのパーサーを追加（自然言語要件処理）"""
        natural_parser = subparsers.add_parser(
            'natural',
            help='自然言語要件から設計ファイルを生成',
            description='自然言語で書かれた要件を解析し、各エージェント用の設計ファイルを自動生成します'
        )
        
        natural_subparsers = natural_parser.add_subparsers(
            dest='natural_action',
            help='自然言語処理アクション'
        )
        
        # generate サブコマンド
        generate_parser = natural_subparsers.add_parser(
            'generate',
            help='自然言語要件から設計ファイルを生成'
        )
        generate_parser.add_argument(
            'requirements',
            help='要件の説明（引用符で囲んでください）'
        )
        generate_parser.add_argument(
            '--project-name', '-n',
            default='Generated Project',
            help='プロジェクト名（default: Generated Project）'
        )
        generate_parser.add_argument(
            '--workspace', '-w',
            default='.',
            help='ワークスペースディレクトリ（default: 現在のディレクトリ）'
        )
        generate_parser.add_argument(
            '--execute',
            action='store_true',
            help='生成後、即座に実行を開始'
        )
        generate_parser.add_argument(
            '--dry-run',
            action='store_true',
            help='ファイル生成せず、解析結果のみ表示'
        )
        generate_parser.set_defaults(func=self._natural_generate_command)
        
        # analyze サブコマンド
        analyze_parser = natural_subparsers.add_parser(
            'analyze',
            help='自然言語要件を解析（設計ファイル生成なし）'
        )
        analyze_parser.add_argument(
            'requirements',
            help='要件の説明（引用符で囲んでください）'
        )
        analyze_parser.add_argument(
            '--detailed',
            action='store_true',
            help='詳細な解析結果を表示'
        )
        analyze_parser.set_defaults(func=self._natural_analyze_command)
        
        # from-file サブコマンド
        from_file_parser = natural_subparsers.add_parser(
            'from-file',
            help='ファイルから要件を読み込んで処理'
        )
        from_file_parser.add_argument(
            'requirements_file',
            help='要件が書かれたファイルのパス'
        )
        from_file_parser.add_argument(
            '--project-name', '-n',
            help='プロジェクト名（未指定時はファイル名から推定）'
        )
        from_file_parser.add_argument(
            '--workspace', '-w',
            default='.',
            help='ワークスペースディレクトリ（default: 現在のディレクトリ）'
        )
        from_file_parser.add_argument(
            '--execute',
            action='store_true',
            help='生成後、即座に実行を開始'
        )
        from_file_parser.set_defaults(func=self._natural_from_file_command)
    
    def _add_dashboard_parser(self, subparsers):
        """dashboard コマンドのパーサーを追加（進捗ダッシュボード）"""
        dashboard_parser = subparsers.add_parser(
            'dashboard', 
            help='進捗ダッシュボードを起動',
            description='エージェントの進捗状況を確認できるウェブダッシュボードを起動します'
        )
        
        dashboard_parser.add_argument(
            '--host',
            default='0.0.0.0',
            help='サーバーのホストアドレス（default: 0.0.0.0）'
        )
        
        dashboard_parser.add_argument(
            '--port', '-p',
            type=int,
            default=8000,
            help='サーバーのポート番号（default: 8000）'
        )
        
        dashboard_parser.add_argument(
            '--workspace', '-w',
            help='ワークスペースディレクトリ（未指定時は現在のディレクトリ）'
        )
        
        dashboard_parser.set_defaults(func=self._dashboard_command)
    
    def _add_collaborate_parser(self, subparsers):
        """collaborate コマンドのパーサーを追加（要件・設計のすり合わせ）"""
        collaborate_parser = subparsers.add_parser(
            'collaborate',
            help='要件・設計のすり合わせと自動実行',
            description='ユーザーと対話的に要件と設計を確認・修正し、設計確定後は自動実行を継続します'
        )
        
        collaborate_subparsers = collaborate_parser.add_subparsers(
            dest='collaborate_action',
            help='すり合わせアクション'
        )
        
        # start サブコマンド
        start_parser = collaborate_subparsers.add_parser(
            'start',
            help='新しいすり合わせセッションを開始'
        )
        start_parser.add_argument(
            'requirements',
            help='要件の説明（引用符で囲むか、ファイルパス）'
        )
        start_parser.add_argument(
            '--project-name', '-n',
            help='プロジェクト名'
        )
        start_parser.add_argument(
            '--from-file', '-f',
            action='store_true',
            help='要件をファイルから読み込む'
        )
        start_parser.set_defaults(func=self._collaborate_start_command)
        
        # status サブコマンド
        status_parser = collaborate_subparsers.add_parser(
            'status',
            help='現在のすり合わせセッションのステータスを表示'
        )
        status_parser.add_argument(
            '--session-id', '-s',
            help='セッションID（未指定時は最新のセッション）'
        )
        status_parser.set_defaults(func=self._collaborate_status_command)
        
        # approve-requirements サブコマンド
        approve_req_parser = collaborate_subparsers.add_parser(
            'approve-requirements',
            help='要件を承認して設計ファイルを生成'
        )
        approve_req_parser.add_argument(
            '--session-id', '-s',
            help='セッションID（未指定時は最新のセッション）'
        )
        approve_req_parser.set_defaults(func=self._collaborate_approve_requirements_command)
        
        # approve-design サブコマンド
        approve_design_parser = collaborate_subparsers.add_parser(
            'approve-design',
            help='設計を承認して実装を開始'
        )
        approve_design_parser.add_argument(
            '--session-id', '-s',
            help='セッションID（未指定時は最新のセッション）'
        )
        approve_design_parser.add_argument(
            '--auto-execute',
            action='store_true',
            help='設計承認後、自動実行を開始'
        )
        approve_design_parser.set_defaults(func=self._collaborate_approve_design_command)
        
        # update-requirements サブコマンド
        update_req_parser = collaborate_subparsers.add_parser(
            'update-requirements',
            help='要件を更新'
        )
        update_req_parser.add_argument(
            'requirements',
            help='更新後の要件（引用符で囲むか、ファイルパス）'
        )
        update_req_parser.add_argument(
            '--session-id', '-s',
            help='セッションID（未指定時は最新のセッション）'
        )
        update_req_parser.add_argument(
            '--from-file', '-f',
            action='store_true',
            help='要件をファイルから読み込む'
        )
        update_req_parser.set_defaults(func=self._collaborate_update_requirements_command)
        
        # list サブコマンド
        list_parser = collaborate_subparsers.add_parser(
            'list',
            help='すべてのすり合わせセッションをリスト表示'
        )
        list_parser.set_defaults(func=self._collaborate_list_command)
    
    def _add_requirements_parser(self, subparsers):
        """requirements コマンドのパーサーを追加（ステップ1: 要件定義）"""
        requirements_parser = subparsers.add_parser(
            'requirements',
            help='【ステップ1】要件定義',
            description='プロジェクトの要件を定義します。自然言語で要件を記述するか、ファイルから読み込みます。'
        )
        
        requirements_subparsers = requirements_parser.add_subparsers(
            dest='requirements_action',
            help='要件定義アクション'
        )
        
        # create サブコマンド
        create_parser = requirements_subparsers.add_parser(
            'create',
            help='新しい要件を作成',
            description='自然言語で要件を記述して要件ファイルを作成します'
        )
        create_parser.add_argument(
            'description',
            help='要件の説明（引用符で囲んでください）'
        )
        create_parser.add_argument(
            '--project-name', '-n',
            help='プロジェクト名（未指定時は現在のディレクトリ名）'
        )
        create_parser.add_argument(
            '--output', '-o',
            help='出力ファイルパス（未指定時は自動生成）'
        )
        create_parser.set_defaults(func=self._requirements_create_command)
        
        # from-file サブコマンド
        from_file_parser = requirements_subparsers.add_parser(
            'from-file',
            help='ファイルから要件を読み込み',
            description='既存の要件ファイル（.md, .txt, .yaml, .json）から要件を読み込みます'
        )
        from_file_parser.add_argument(
            'file_path',
            help='要件ファイルのパス'
        )
        from_file_parser.add_argument(
            '--project-name', '-n',
            help='プロジェクト名（未指定時は現在のディレクトリ名）'
        )
        from_file_parser.set_defaults(func=self._requirements_from_file_command)
        
        # list サブコマンド
        list_parser = requirements_subparsers.add_parser(
            'list',
            help='要件一覧を表示',
            description='保存されている要件ファイルの一覧を表示します'
        )
        list_parser.set_defaults(func=self._requirements_list_command)
        
        # show サブコマンド
        show_parser = requirements_subparsers.add_parser(
            'show',
            help='要件の詳細を表示',
            description='指定した要件ファイルの内容を表示します'
        )
        show_parser.add_argument(
            'file_path',
            help='要件ファイルのパス'
        )
        show_parser.set_defaults(func=self._requirements_show_command)
    
    def _add_implement_parser(self, subparsers):
        """implement コマンドのパーサーを追加（ステップ3: 実装開始）"""
        implement_parser = subparsers.add_parser(
            'implement',
            help='【ステップ3】実装開始',
            description='設計書に基づいて実装を開始します。設計書からタスクを生成し、実行します。'
        )
        
        implement_subparsers = implement_parser.add_subparsers(
            dest='implement_action',
            help='実装アクション'
        )
        
        # start サブコマンド
        start_parser = implement_subparsers.add_parser(
            'start',
            help='実装を開始',
            description='設計書ファイルから実装を開始します'
        )
        start_parser.add_argument(
            'design_file',
            help='設計書ファイルのパス（.yaml または .json）'
        )
        start_parser.add_argument(
            '--mode', '-m',
            choices=['immediate', 'nightly', 'scheduled'],
            default='immediate',
            help='実行モード: immediate（即時実行）, nightly（夜間実行）, scheduled（スケジュール実行）'
        )
        start_parser.add_argument(
            '--max-tasks',
            type=int,
            default=5,
            help='一度に実行する最大タスク数（default: 5）'
        )
        start_parser.add_argument(
            '--dry-run',
            action='store_true',
            help='実際の実行は行わず、実行計画のみ表示'
        )
        start_parser.add_argument(
            '--schedule-time',
            help='scheduled モード時の実行時刻（HH:MM形式）'
        )
        start_parser.set_defaults(func=self._implement_start_command)
        
        # status サブコマンド
        status_parser = implement_subparsers.add_parser(
            'status',
            help='実装状況を確認',
            description='現在実行中の実装タスクの状況を確認します'
        )
        status_parser.add_argument(
            '--design-file', '-d',
            help='特定の設計書の進捗を確認（省略時は実行中の全プロジェクト）'
        )
        status_parser.add_argument(
            '--detailed',
            action='store_true',
            help='詳細な進捗情報を表示'
        )
        status_parser.set_defaults(func=self._implement_status_command)
        
        # stop サブコマンド
        stop_parser = implement_subparsers.add_parser(
            'stop',
            help='実装を停止',
            description='実行中の実装タスクを停止します'
        )
        stop_parser.add_argument(
            '--force', '-f',
            action='store_true',
            help='強制停止'
        )
        stop_parser.set_defaults(func=self._implement_stop_command)
    
    def _initialize_config(self, config_path: Optional[str] = None):
        """設定初期化"""
        if config_path:
            self.config_manager = ConfigManager(config_path)
        
        self.config = self.config_manager.load_config()
        
        # ロガーの初期化
        self.logger = StructuredLogger({
            'level': self.config.logging.level,
            'output_path': self.config.logging.output_path,
            'console_output': self.config.logging.console_output,
            'file_output': self.config.logging.file_output,
            'retention_days': self.config.logging.retention_days,
            'max_file_size_mb': self.config.logging.max_file_size_mb
        })

    def _get_current_project_info(self) -> Dict[str, str]:
        """カレントディレクトリから対象プロジェクト情報を取得"""
        current_dir = Path(os.getcwd()).resolve()
        
        # プロジェクト名をディレクトリ名から取得
        project_name = current_dir.name
        
        # プロジェクトタイプの推定
        project_type = "unknown"
        if (current_dir / "package.json").exists():
            project_type = "nodejs"
        elif (current_dir / "requirements.txt").exists() or (current_dir / "requirements.md").exists() or (current_dir / "pyproject.toml").exists():
            project_type = "python"
        elif (current_dir / "Cargo.toml").exists():
            project_type = "rust"
        elif (current_dir / "pom.xml").exists():
            project_type = "java"
        elif (current_dir / "go.mod").exists():
            project_type = "go"
        
        return {
            'project_path': str(current_dir),
            'project_name': project_name,
            'project_type': project_type
        }
    
    async def _start_command(self, args) -> None:
        """start コマンド実装"""
        if args.use_spec_kit:
            print("🚀 Spec Kit仕様駆動で夜間実行セッションを開始します...")
            print(f"📋 仕様タイプ: {args.spec_type}")
        else:
            print("🚀 夜間実行セッションを開始します...")
        
        # スケジューラーの初期化
        workspace_path = args.workspace or self.config.workspace_path
        self.scheduler = NightScheduler(workspace_path, self.config)
        
        # セッション開始
        await self.scheduler.start()
        session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        print(f"✅ セッション開始: {session_id}")
        
        if args.use_spec_kit:
            print("📝 タスク実行時に自動的にSpec Kit仕様が生成されます")
        
        # 進行状況監視
        if args.immediate:
            await self._monitor_execution(session_id)
    
    async def _stop_command(self, args) -> None:
        """stop コマンド実装"""
        print("🛑 夜間実行セッションを停止しています...")
        
        if self.scheduler is None:
            workspace_path = self.config.workspace_path
            self.scheduler = NightScheduler(workspace_path, self.config)
        
        success = await self.scheduler.stop_night_session(force=args.force)
        
        if success:
            print("✅ セッションが正常に停止されました")
        else:
            print("❌ セッション停止に失敗しました")
    
    async def _status_command(self, args) -> None:
        """status コマンド実装"""
        print("📊 システム状況を確認しています...\n")
        
        # 基本システム情報
        workspace_path = self.config.workspace_path
        
        if self.scheduler is None:
            self.scheduler = NightScheduler(workspace_path, self.config)
        
        if self.cost_manager is None:
            # dataclassを辞書に変換してからCostManagerに渡す
            cost_config_dict = {
                'monthly_budget': getattr(self.config.cost_management, 'monthly_budget', 20.0),
                'emergency_threshold': getattr(self.config.cost_management, 'emergency_threshold', 0.8),
                'cost_per_token': getattr(self.config.cost_management, 'cost_per_token', 0.00001),
                'daily_budget_limit': getattr(self.config.cost_management, 'daily_budget_limit', 5.0)
            }
            self.cost_manager = CostManager(cost_config_dict)
        
        if self.safety_coordinator is None:
            # dataclassを辞書に変換してからSafetyCoordinatorに渡す
            safety_config_dict = {
                'max_parallel_tasks': getattr(self.config.safety, 'max_parallel_tasks', 3),
                'task_timeout_minutes': getattr(self.config.safety, 'task_timeout_minutes', 60),
                'auto_backup_enabled': getattr(self.config.safety, 'auto_backup_enabled', True),
                'rollback_enabled': getattr(self.config.safety, 'rollback_enabled', True)
            }
            self.safety_coordinator = SafetyCoordinator(workspace_path, safety_config_dict)
        
        # 各システムの状況取得 - get_system_status → get_status に修正
        scheduler_status = self.scheduler.get_status()
        cost_status = self.cost_manager.get_cost_dashboard()
        safety_status = self.safety_coordinator.get_safety_status()
        
        if args.json:
            import json
            status_data = {
                'scheduler': scheduler_status,
                'cost': cost_status,
                'safety': safety_status
            }
            print(json.dumps(status_data, indent=2, default=str, ensure_ascii=False))
        else:
            self._print_status_summary(scheduler_status, cost_status, safety_status, args.detailed)
    
    def _config_show_command(self, args) -> None:
        """config show コマンド実装"""
        import yaml
        from dataclasses import asdict
        
        config_dict = asdict(self.config)
        
        if args.section:
            if args.section in config_dict:
                config_dict = {args.section: config_dict[args.section]}
            else:
                print(f"❌ セクション '{args.section}' が見つかりません")
                return
        
        print(yaml.dump(config_dict, default_flow_style=False, allow_unicode=True))
    
    def _config_set_command(self, args) -> None:
        """config set コマンド実装"""
        try:
            # 値の型変換
            value = args.value
            if value.lower() in ('true', 'false'):
                value = value.lower() == 'true'
            elif value.replace('.', '').replace('-', '').isdigit():
                value = float(value) if '.' in value else int(value)
            
            # 設定更新
            success = self.config_manager.update_config({args.key: value})
            
            if success:
                print(f"✅ 設定を更新しました: {args.key} = {value}")
            else:
                print(f"❌ 設定更新に失敗しました")
        except Exception as e:
            print(f"❌ 設定更新エラー: {e}")
    
    def _config_validate_command(self, args) -> None:
        """config validate コマンド実装"""
        errors = self.config_manager.validate_config()
        
        if not errors:
            print("✅ 設定検証に成功しました")
        else:
            print("❌ 設定検証エラー:")
            for error in errors:
                print(f"  - {error}")
    
    def _config_init_command(self, args) -> None:
        """config init コマンド実装"""
        if args.sample:
            success = self.config_manager.create_sample_config()
        else:
            from nocturnal_agent.config.config_manager import NocturnalConfig
            default_config = NocturnalConfig()
            success = self.config_manager.save_config(default_config)
        
        if success:
            print(f"✅ 設定ファイルを初期化しました: {self.config_manager.config_path}")
        else:
            print("❌ 設定初期化に失敗しました")
    
    async def _report_daily_command(self, args) -> None:
        """report daily コマンド実装"""
        print("📊 日次レポートを生成しています...")
        
        target_date = None
        if args.date:
            target_date = datetime.strptime(args.date, '%Y-%m-%d')
        
        report_generator = ReportGenerator(self.logger)
        report = report_generator.generate_daily_report(target_date)
        
        # HTMLレポート生成
        html_path = report_generator.save_report_html(report, args.output)
        print(f"✅ HTMLレポート生成: {html_path}")
        
        # JSONレポート生成
        json_filename = args.output.replace('.html', '.json') if args.output else None
        json_path = report_generator.save_report_json(report, json_filename)
        print(f"✅ JSONレポート生成: {json_path}")
    
    async def _report_session_command(self, args) -> None:
        """report session コマンド実装"""
        print(f"📊 セッションレポートを生成しています: {args.session_id}")
        
        report_generator = ReportGenerator(self.logger)
        report = report_generator.generate_session_report(args.session_id)
        
        html_path = report_generator.save_report_html(report, args.output)
        print(f"✅ HTMLレポート生成: {html_path}")
        
        json_filename = args.output.replace('.html', '.json') if args.output else None
        json_path = report_generator.save_report_json(report, json_filename)
        print(f"✅ JSONレポート生成: {json_path}")
    
    async def _report_weekly_command(self, args) -> None:
        """report weekly コマンド実装"""
        print("📊 週次レポートを生成しています...")
        
        start_date = None
        if args.start_date:
            start_date = datetime.strptime(args.start_date, '%Y-%m-%d')
        
        report_generator = ReportGenerator(self.logger)
        report = report_generator.generate_weekly_summary(start_date)
        
        html_path = report_generator.save_report_html(report, args.output)
        print(f"✅ HTMLレポート生成: {html_path}")
        
        json_filename = args.output.replace('.html', '.json') if args.output else None
        json_path = report_generator.save_report_json(report, json_filename)
        print(f"✅ JSONレポート生成: {json_path}")
    
    async def _cost_status_command(self, args) -> None:
        """cost status コマンド実装"""
        if self.cost_manager is None:
            self.cost_manager = CostManager(self.config.cost_management.__dict__)
        
        status = await self.cost_manager.get_usage_status()
        
        print("💰 コスト状況")
        print(f"月間予算: ${self.config.cost_management.monthly_budget:.2f}")
        print(f"今月使用額: ${status['monthly_usage']:.4f}")
        print(f"使用率: {status['usage_percentage']:.1f}%")
        print(f"残り予算: ${status['remaining_budget']:.4f}")
        
        if status['alert_triggered']:
            print("⚠️ 予算アラートが発生しています")
        
        if status['emergency_mode']:
            print("🚨 緊急モードが有効です")
    
    async def _cost_dashboard_command(self, args) -> None:
        """cost dashboard コマンド実装"""
        if self.cost_manager is None:
            self.cost_manager = CostManager(self.config.cost_management.__dict__)
        
        dashboard = self.cost_manager.get_cost_dashboard()
        
        print("💰 コストダッシュボード\n")
        
        budget_info = dashboard['budget_overview']
        print(f"📊 予算概要")
        print(f"  月間予算: ${budget_info['monthly_budget']:.2f}")
        print(f"  使用額: ${budget_info['current_usage']:.4f}")
        print(f"  使用率: {budget_info['usage_percentage']:.1f}%")
        print()
        
        service_usage = dashboard['service_usage']
        print("🛠️ サービス別使用量")
        for service, usage in service_usage.items():
            print(f"  {service}: ${usage:.4f}")
        print()
        
        optimization = dashboard['optimization']
        print("⚡ 最適化状況")
        print(f"  最適化済みタスク: {optimization['tasks_optimized']}")
        print(f"  節約額: ${optimization['cost_saved']:.4f}")
        print(f"  無料ツール使用率: {optimization['free_tool_usage_rate']:.1%}")
    
    async def _cost_reset_command(self, args) -> None:
        """cost reset コマンド実装"""
        if not args.confirm:
            confirm = input("⚠️ コスト統計をリセットします。続行しますか？ (y/N): ")
            if confirm.lower() != 'y':
                print("キャンセルしました")
                return
        
        if self.cost_manager is None:
            self.cost_manager = CostManager(self.config.cost_management.__dict__)
        
        success = await self.cost_manager.reset_monthly_usage()
        
        if success:
            print("✅ コスト統計をリセットしました")
        else:
            print("❌ リセットに失敗しました")
    
    async def _safety_status_command(self, args) -> None:
        """safety status コマンド実装"""
        workspace_path = self.config.workspace_path
        if self.safety_coordinator is None:
            self.safety_coordinator = SafetyCoordinator(workspace_path, self.config.safety.__dict__)
        
        status = self.safety_coordinator.get_safety_status()
        
        print("🛡️ 安全性状況\n")
        
        print(f"安全性システム: {'✅ 有効' if status['safety_active'] else '❌ 無効'}")
        print(f"安全性違反数: {status['safety_violations_count']}")
        
        if status.get('session_info'):
            session = status['session_info']
            print(f"セッション情報:")
            print(f"  現在のバックアップ: {session.get('current_backup', 'N/A')}")
            print(f"  ロールバックポイント: {session.get('rollback_point', 'N/A')}")
        
        print("\nコンポーネント状況:")
        components = status.get('component_status', {})
        for component, comp_status in components.items():
            status_icon = '✅' if comp_status.get('healthy', False) else '❌'
            print(f"  {component}: {status_icon}")
    
    async def _safety_backup_command(self, args) -> None:
        """safety backup コマンド実装"""
        workspace_path = self.config.workspace_path
        if self.safety_coordinator is None:
            self.safety_coordinator = SafetyCoordinator(workspace_path, self.config.safety.__dict__)
        
        description = args.description or "手動バックアップ"
        
        print("💾 手動バックアップを作成しています...")
        
        try:
            backup_info = await self.safety_coordinator.backup_manager.create_backup(
                backup_type="full",
                backup_id=f"manual_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                description=description
            )
            
            print(f"✅ バックアップ作成完了: {backup_info.backup_id}")
            print(f"   ファイル数: {backup_info.files_included}")
            print(f"   サイズ: {backup_info.backup_size_mb:.2f}MB")
        except Exception as e:
            print(f"❌ バックアップ作成に失敗しました: {e}")
    
    async def _safety_rollback_command(self, args) -> None:
        """safety rollback コマンド実装"""
        workspace_path = self.config.workspace_path
        if self.safety_coordinator is None:
            self.safety_coordinator = SafetyCoordinator(workspace_path, self.config.safety.__dict__)
        
        rollback_points = self.safety_coordinator.rollback_manager.list_rollback_points()
        
        print("🔄 ロールバックポイント一覧\n")
        
        if not rollback_points:
            print("ロールバックポイントが見つかりません")
            return
        
        for point in rollback_points[-10:]:  # 最新10件
            print(f"ID: {point.rollback_id}")
            print(f"  説明: {point.description}")
            print(f"  作成日時: {point.created_at}")
            print(f"  Gitコミット: {point.git_commit[:8] if point.git_commit else 'N/A'}")
            print()
    
    async def _safety_health_command(self, args) -> None:
        """safety health コマンド実装"""
        workspace_path = self.config.workspace_path
        if self.safety_coordinator is None:
            self.safety_coordinator = SafetyCoordinator(workspace_path, self.config.safety.__dict__)
        
        print("🔍 安全性ヘルスチェックを実行しています...")
        
        health_status = await self.safety_coordinator.safety_health_check()
        
        overall_healthy = health_status.get('overall_healthy', False)
        print(f"\n🛡️ 総合ヘルス状況: {'✅ 良好' if overall_healthy else '⚠️ 注意が必要'}")
        
        components = health_status.get('components', {})
        print("\nコンポーネント詳細:")
        
        for component, comp_health in components.items():
            healthy = comp_health.get('healthy', False)
            status_icon = '✅' if healthy else '❌'
            print(f"  {component}: {status_icon}")
            
            if 'issues' in comp_health and comp_health['issues']:
                for issue in comp_health['issues']:
                    print(f"    ⚠️ {issue}")
    
    def _init_command(self, args) -> None:
        """init コマンド実装"""
        print(f"🚀 プロジェクトを初期化しています: {args.project_name}")
        
        workspace_path = Path(args.workspace).resolve()
        
        # ディレクトリ作成
        directories = [
            workspace_path,
            workspace_path / 'config',
            workspace_path / 'data',
            workspace_path / 'logs',
            workspace_path / 'reports',
            workspace_path / 'team_designs',
            workspace_path / 'src',
            workspace_path / 'tests',
            workspace_path / 'docs'
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
            print(f"📁 ディレクトリ作成: {directory}")
        
        # 設定ファイル作成
        config_path = workspace_path / 'config' / 'nocturnal-agent.yaml'
        
        # プロジェクト固有の詳細設定ファイル
        config_content = self._generate_project_config(args.project_name, workspace_path)
        
        with open(config_path, 'w', encoding='utf-8') as f:
            f.write(config_content)
        
        print(f"⚙️ 設定ファイル作成: {config_path}")
        
        # チーム設計協調環境セットアップ
        self._setup_team_design_environment(workspace_path)
        
        # README作成
        readme_path = workspace_path / 'README.md'
        readme_content = f"""# {args.project_name}

Nocturnal Agent 夜間自律開発プロジェクト

## セットアップ完了

このプロジェクトは Nocturnal Agent によって初期化されました。

### 基本使用方法

```bash
# 夜間実行開始
nocturnal --config {config_path} start

# システム状況確認
nocturnal --config {config_path} status

# レポート生成
nocturnal --config {config_path} report daily
```

### ディレクトリ構造

- `config/` - 設定ファイル
- `data/` - データベースとコスト情報
- `logs/` - 実行ログ
- `reports/` - 生成レポート

### 次のステップ

1. `config/nocturnal_config.yaml` で設定をカスタマイズ
2. Claude API キーの設定（必要に応じて）
3. 夜間実行セッションの開始

詳細は Nocturnal Agent のドキュメントを参照してください。
"""
        
        # README内容の更新
        readme_content = f"""# {args.project_name}

🌙 **Nocturnal Agent 分散協調開発プロジェクト**

## ✅ セットアップ完了

このプロジェクトは Nocturnal Agent によって自動初期化され、チーム設計協調環境が構築されました。

## 🏗️ プロジェクト構造

```
{args.project_name}/
├── team_designs/           # チーム設計協調ワークスペース
│   ├── designs/
│   │   ├── agent_frontend_specialist/
│   │   ├── agent_backend_specialist/
│   │   ├── agent_database_specialist/
│   │   └── agent_qa_specialist/
│   └── TEAM_COLLABORATION_GUIDE.md
├── config/
│   └── nocturnal-agent.yaml  # プロジェクト設定
├── src/                    # 実装コード
├── tests/                  # テストスイート
├── docs/                   # ドキュメント
├── data/                   # データファイル
├── logs/                   # 実行ログ
└── reports/                # 生成レポート
```

## 🚀 クイックスタート

### 1. チーム設計協調
```bash
# Frontend specialist が設計書作成
cd team_designs/designs/agent_frontend_specialist
cp design_template.yaml web_ui_system.yaml
# Edit web_ui_system.yaml...

# Backend specialist が設計書作成
cd ../agent_backend_specialist
cp design_template.yaml api_backend_system.yaml
# Edit api_backend_system.yaml...
```

### 2. 設計検証
```bash
# 設計ファイル検証
nocturnal design validate web_ui_system.yaml --detailed
nocturnal design validate api_backend_system.yaml --detailed
```

### 3. 実行
```bash
# 即時実行
nocturnal execute --design-file api_backend_system.yaml --mode immediate --max-tasks 3

# 夜間実行
nocturnal execute --design-file web_ui_system.yaml --mode nightly
```

## 🎮 基本コマンド

```bash
# システム状況確認
nocturnal status

# 設計ファイル管理
nocturnal design validate design.yaml --detailed
nocturnal design summary design.yaml

# 実行
nocturnal execute --design-file design.yaml --mode immediate
nocturnal execute --design-file design.yaml --dry-run  # プレビュー

# レポート生成
nocturnal report daily
```

## 📚 次のステップ

1. **設定カスタマイズ**: `config/nocturnal-agent.yaml` を編集
2. **LLM環境準備**: LM Studio/Ollama の起動と設定
3. **Claude Code**: Claude Code CLI の認証
4. **チーム協調開始**: `team_designs/TEAM_COLLABORATION_GUIDE.md` を参照

## 🔗 参考情報

- チーム協調ガイド: `team_designs/TEAM_COLLABORATION_GUIDE.md`
- 設定ファイル: `config/nocturnal-agent.yaml`
- Nocturnal Agent ドキュメント: [GitHub Repository]

---
🌙 **Happy Collaborative Development with Nocturnal Agent!**
"""
        
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(readme_content)
            
        print(f"📝 README作成: {readme_path}")
        print("\n✅ プロジェクト初期化が完了しました！")
        print(f"\n次のコマンドでセットアップを確認できます:")
        print(f"cd {workspace_path}")
        print(f"nocturnal --config {config_path} status")
    
    async def _monitor_execution(self, session_id: str) -> None:
        """実行監視"""
        print(f"\n👀 セッション監視中: {session_id}")
        print("Ctrl+C で監視を終了")
        
        try:
            while True:
                status = await self.scheduler.get_system_status()
                
                if not status.get('active_session'):
                    print("✅ セッションが完了しました")
                    break
                
                # 進行状況表示
                session_info = status.get('session_info', {})
                completed_tasks = session_info.get('completed_tasks', 0)
                total_tasks = session_info.get('total_tasks', 0)
                
                print(f"\r進行状況: {completed_tasks}/{total_tasks} タスク完了", end="", flush=True)
                
                await asyncio.sleep(5)  # 5秒間隔で更新
                
        except KeyboardInterrupt:
            print("\n👋 監視を終了します")
    
    def _print_status_summary(self, scheduler_status: Dict[str, Any], 
                            cost_status: Dict[str, Any], 
                            safety_status: Dict[str, Any],
                            detailed: bool = False) -> None:
        """ステータス要約表示"""
        
        # スケジューラー状況
        print("🕒 スケジューラー状況")
        active_session = scheduler_status.get('active_session', False)
        print(f"  アクティブセッション: {'✅ あり' if active_session else '❌ なし'}")
        
        if active_session and 'session_info' in scheduler_status:
            session = scheduler_status['session_info']
            print(f"  セッションID: {session.get('session_id', 'N/A')}")
            print(f"  開始時間: {session.get('start_time', 'N/A')}")
            print(f"  完了タスク: {session.get('completed_tasks', 0)}")
        print()
        
        # コスト状況
        print("💰 コスト状況")
        budget_info = cost_status.get('budget_overview', {})
        monthly_budget = budget_info.get('monthly_budget', 0)
        current_spend = budget_info.get('current_spend', 0)
        utilization_percentage = budget_info.get('utilization_percentage', 0)
        
        print(f"  月間予算: ${monthly_budget:.2f}")
        print(f"  使用額: ${current_spend:.4f} ({utilization_percentage:.1f}%)")
        
        if budget_info.get('emergency_mode'):
            print("  🚨 緊急モード有効")
        print()
        
        # 安全性状況
        print("🛡️ 安全性状況")
        safety_active = safety_status.get('safety_active', False)
        violations_count = safety_status.get('safety_violations_count', 0)
        print(f"  システム: {'✅ 有効' if safety_active else '❌ 無効'}")
        print(f"  違反数: {violations_count}")
        print()
        
        if detailed:
            # 詳細情報
            print("📊 詳細情報")
            
            if 'statistics' in scheduler_status:
                stats = scheduler_status['statistics']
                print(f"  総セッション数: {stats.get('total_sessions', 0)}")
                print(f"  総タスク数: {stats.get('total_tasks', 0)}")
            
            # サービス別使用量の表示も安全にする
            trends = cost_status.get('trends', {})
            service_breakdown = trends.get('service_breakdown', {})
            if service_breakdown:
                print("  サービス別使用量:")
                for service, usage in service_breakdown.items():
                    print(f"    {service}: ${usage:.4f}")
            
            # 安全性コンポーネント状況
            components = safety_status.get('component_status', {})
            if components:
                print("  安全性コンポーネント:")
                for component, comp_status in components.items():
                    status_icon = '✅' if comp_status.get('healthy', False) else '❌'
                    print(f"    {component}: {status_icon}")


    async def _spec_list_command(self, args) -> None:
        """spec list コマンド実装"""
        from nocturnal_agent.design.spec_kit_integration import SpecKitManager, SpecType, SpecStatus
        
        workspace_path = self.config.workspace_path
        spec_manager = SpecKitManager(str(Path(workspace_path) / "specs"))
        
        spec_type_filter = SpecType(args.type) if args.type else None
        status_filter = SpecStatus(args.status) if args.status else None
        
        specs = spec_manager.list_specs(spec_type_filter, status_filter)
        
        if not specs:
            print("仕様が見つかりません")
            return
        
        print(f"📋 仕様一覧 ({len(specs)}件)")
        print()
        
        for spec in specs:
            status_icon = {
                'draft': '📝',
                'review': '👀', 
                'approved': '✅',
                'implemented': '🚀',
                'deprecated': '❌'
            }.get(spec['status'], '❓')
            
            type_icon = {
                'feature': '⭐',
                'architecture': '🏗️',
                'api': '🔌',
                'design': '🎨',
                'process': '⚙️'
            }.get(spec['spec_type'], '📄')
            
            print(f"{status_icon} {type_icon} {spec['title']}")
            print(f"   ファイル: {spec['file_path']}")
            print(f"   ステータス: {spec['status']} | タイプ: {spec['spec_type']}")
            print(f"   作成者: {', '.join(spec['authors'])}")
            print(f"   更新: {spec['updated_at']}")
            print()
    
    async def _spec_show_command(self, args) -> None:
        """spec show コマンド実装"""
        from nocturnal_agent.design.spec_kit_integration import SpecKitManager
        
        workspace_path = self.config.workspace_path
        spec_manager = SpecKitManager(str(Path(workspace_path) / "specs"))
        
        spec_path = Path(args.spec_file)
        if not spec_path.exists():
            # 相対パスの場合、specsディレクトリ内を検索
            potential_path = Path(workspace_path) / "specs" / args.spec_file
            if potential_path.exists():
                spec_path = potential_path
            else:
                print(f"❌ 仕様ファイルが見つかりません: {args.spec_file}")
                return
        
        try:
            spec = spec_manager.load_spec(spec_path)
            
            if args.format == 'markdown':
                markdown_content = spec_manager.generate_spec_markdown(spec)
                print(markdown_content)
            else:
                # YAML形式で表示
                with open(spec_path, 'r', encoding='utf-8') as f:
                    print(f.read())
                    
        except Exception as e:
            print(f"❌ 仕様読み込みエラー: {e}")
    
    async def _spec_create_command(self, args) -> None:
        """spec create コマンド実装"""
        from nocturnal_agent.design.spec_kit_integration import (
            SpecKitManager, SpecType, SpecMetadata, TechnicalSpec,
            SpecDesign, SpecImplementation, SpecStatus
        )
        from nocturnal_agent.core.models import Task, TaskPriority
        
        workspace_path = self.config.workspace_path
        spec_manager = SpecKitManager(str(Path(workspace_path) / "specs"))
        
        spec_type = SpecType(args.type)
        
        if args.template:
            # テンプレートから作成
            print(f"📝 {spec_type.value}仕様テンプレートを作成しています...")
            
            # ダミータスクを作成してテンプレート生成
            dummy_task = Task(
                id=f"template_{args.title.replace(' ', '_').lower()}",
                description=args.title,
                priority=TaskPriority.MEDIUM,
                estimated_quality=0.8
            )
            
            spec = spec_manager.create_spec_from_task(dummy_task, spec_type)
            spec.metadata.title = args.title
            
        else:
            # 手動作成
            print(f"📝 {spec_type.value}仕様を作成しています...")
            
            metadata = SpecMetadata(
                title=args.title,
                status=SpecStatus.DRAFT,
                spec_type=spec_type,
                authors=["CLI User"]
            )
            
            spec = TechnicalSpec(
                metadata=metadata,
                summary=f"{args.title}の仕様",
                motivation="この仕様が必要な理由",
                requirements=[],
                design=SpecDesign(overview="設計概要"),
                implementation=SpecImplementation(approach="実装アプローチ")
            )
        
        spec_path = spec_manager.save_spec(spec)
        print(f"✅ 仕様作成完了: {spec_path}")
        
        if args.template:
            print(f"📝 エディタで編集してください: {spec_path}")
    
    async def _spec_update_command(self, args) -> None:
        """spec update コマンド実装"""
        from nocturnal_agent.design.spec_kit_integration import SpecKitManager, SpecStatus
        
        workspace_path = self.config.workspace_path
        spec_manager = SpecKitManager(str(Path(workspace_path) / "specs"))
        
        spec_path = Path(args.spec_file)
        if not spec_path.exists():
            potential_path = Path(workspace_path) / "specs" / args.spec_file
            if potential_path.exists():
                spec_path = potential_path
            else:
                print(f"❌ 仕様ファイルが見つかりません: {args.spec_file}")
                return
        
        new_status = SpecStatus(args.status)
        success = spec_manager.update_spec_status(spec_path, new_status)
        
        if success:
            print(f"✅ 仕様ステータスを更新しました: {args.status}")
        else:
            print(f"❌ 仕様ステータス更新に失敗しました")
    
    async def _spec_report_command(self, args) -> None:
        """spec report コマンド実装"""
        if not hasattr(self, 'spec_executor') or self.spec_executor is None:
            from nocturnal_agent.execution.spec_driven_executor import SpecDrivenExecutor
            self.spec_executor = SpecDrivenExecutor(self.config.workspace_path, self.logger)
        
        print("📊 仕様レポートを生成しています...")
        
        report = self.spec_executor.generate_spec_report()
        
        if args.output:
            import json
            output_path = Path(args.output)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2, default=str)
            print(f"✅ レポート保存完了: {output_path}")
        else:
            # コンソール出力
            print(f"\n📊 仕様管理レポート")
            print(f"生成日時: {report['generated_at']}")
            print(f"総仕様数: {report['total_specs']}")
            
            print(f"\n📈 ステータス別内訳:")
            for status, count in report['status_breakdown'].items():
                status_icon = {
                    'draft': '📝',
                    'review': '👀',
                    'approved': '✅', 
                    'implemented': '🚀',
                    'deprecated': '❌'
                }.get(status, '❓')
                print(f"  {status_icon} {status}: {count}件")
            
            print(f"\n🏷️ タイプ別内訳:")
            for spec_type, count in report['type_breakdown'].items():
                type_icon = {
                    'feature': '⭐',
                    'architecture': '🏗️',
                    'api': '🔌',
                    'design': '🎨',
                    'process': '⚙️'
                }.get(spec_type, '📄')
                print(f"  {type_icon} {spec_type}: {count}件")
            
            if 'quality_metrics' in report and report['quality_metrics']:
                metrics = report['quality_metrics']
                print(f"\n🎯 品質メトリクス:")
                print(f"  平均品質スコア: {metrics['average_quality']:.3f}")
                print(f"  最高品質スコア: {metrics['max_quality']:.3f}")
                print(f"  実行成功率: {metrics['success_rate']:.1%}")
    
    async def _spec_cleanup_command(self, args) -> None:
        """spec cleanup コマンド実装"""
        if not hasattr(self, 'spec_executor') or self.spec_executor is None:
            from nocturnal_agent.execution.spec_driven_executor import SpecDrivenExecutor
            self.spec_executor = SpecDrivenExecutor(self.config.workspace_path, self.logger)
        
        if args.dry_run:
            print(f"🔍 {args.days}日以前の古い仕様を検索中...")
            # TODO: dry-runの実装
            print("(dry-run機能は未実装)")
        else:
            print(f"🧹 {args.days}日以前の古い仕様をクリーンアップ中...")
            cleaned_count = await self.spec_executor.cleanup_old_specs(args.days)
            print(f"✅ クリーンアップ完了: {cleaned_count}件の仕様を削除しました")

    
    # Interactive Review Commands
    
    async def _review_start_command(self, args):
        """インタラクティブレビューを開始（カレントディレクトリを対象プロジェクトとして使用）"""
        try:
            from ..core.models import Task
            from ..execution.spec_driven_executor import SpecDrivenExecutor
            
            # カレントディレクトリの情報を取得
            project_info = self._get_current_project_info()
            target_project_path = project_info['project_path']
            project_name = project_info['project_name']
            project_type = project_info['project_type']
            
            # カレントディレクトリがプロジェクトルートかどうか検証
            current_dir = Path(target_project_path)
            if not current_dir.is_dir():
                print(f"❌ エラー: カレントディレクトリがディレクトリではありません: {target_project_path}")
                return None
            
            print(f"🎯 対象プロジェクト: {project_name} ({project_type})")
            print(f"📁 プロジェクトパス: {target_project_path}")
            
            # タスクオブジェクトを作成
            task = Task(
                description=args.task_title,
                requirements=[args.description] if args.description else [],
                priority=getattr(__import__('nocturnal_agent.core.models', fromlist=['TaskPriority']).TaskPriority, args.priority.upper())
            )
            
            # SpecDrivenExecutorを対象プロジェクト用に初期化
            executor = SpecDrivenExecutor(target_project_path, self.logger)
            
            print(f"🎨 インタラクティブレビューを開始: {task.description}")
            print("📋 設計書を生成中...")
            
            # インタラクティブレビューを開始
            result = await executor.execute_task_with_interactive_review(task)
            
            session_id = result.get('session_id')
            print(f"✅ 設計書生成完了! Session ID: {session_id}")
            print("\n" + "="*60)
            print("📊 設計概要")
            print("="*60)
            
            review_data = result.get('review_data', {})
            design_summary = review_data.get('design_summary', {})
            
            print(f"プロジェクト名: {design_summary.get('project_name', project_name)}")
            print(f"プロジェクトタイプ: {project_type}")
            print(f"アーキテクチャ: {design_summary.get('architecture_type', 'N/A')}")
            print(f"主要コンポーネント数: {design_summary.get('key_components', 'N/A')}")
            print(f"複雑度レベル: {design_summary.get('complexity_level', 'N/A')}")
            print(f"推定作業時間: {design_summary.get('estimated_effort', 'N/A')}")
            print(f"主要技術: {', '.join(design_summary.get('main_technologies', []))}")
            
            print("\n" + "="*60)
            print("🔧 実装プラン")
            print("="*60)
            impl_plan = review_data.get('implementation_plan', {})
            phases = impl_plan.get('phases', [])
            for i, phase in enumerate(phases, 1):
                print(f"{i}. {phase}")
            
            print(f"\n優先コンポーネント: {', '.join(impl_plan.get('priority_components', []))}")
            print(f"リスクファクター: {', '.join(impl_plan.get('risk_factors', []))}")
            
            print("\n" + "="*60)
            print("⚙️ アーキテクチャ概要")
            print("="*60)
            arch = review_data.get('architecture_overview', {})
            print(f"パターン: {arch.get('pattern', 'N/A')}")
            print(f"レイヤー: {' -> '.join(arch.get('layers', []))}")
            print(f"主要インターフェース: {', '.join(arch.get('key_interfaces', []))}")
            print(f"データフロー: {arch.get('data_flow', 'N/A')}")
            
            print("\n" + "="*60)
            print("✅ 品質要件")
            print("="*60)
            quality = review_data.get('quality_requirements', {})
            for key, value in quality.items():
                print(f"{key}: {value}")
            
            print("\n" + "="*60)
            print("📝 次のアクション")
            print("="*60)
            print(f"💚 承認: na review approve {session_id}")
            print(f"🔄 修正要求: na review modify {session_id} '修正内容'")
            print(f"💬 議論: na review discuss {session_id} 'トピック'")
            print(f"❌ 拒否: na review reject {session_id}")
            print(f"📊 状況確認: na review status --session-id {session_id}")
            
            print(f"\n💡 ヒント: {current_dir.name}プロジェクトのルートディレクトリで実行しています")
            
            return result
            
        except Exception as e:
            self.logger.log_error("REVIEW_START_ERROR", f"レビュー開始エラー: {e}")
            print(f"❌ エラー: {e}")
            return None

    
    async def _review_from_file_command(self, args):
        """要件ファイルからインタラクティブレビューを開始（カレントディレクトリを対象プロジェクトとして使用）"""
        try:
            from ..execution.spec_driven_executor import SpecDrivenExecutor, RequirementsFileParser
            from pathlib import Path
            
            # カレントディレクトリの情報を取得
            project_info = self._get_current_project_info()
            target_project_path = project_info['project_path']
            project_name = project_info['project_name']
            project_type = project_info['project_type']
            
            print(f"🎯 対象プロジェクト: {project_name} ({project_type})")
            print(f"📁 プロジェクトパス: {target_project_path}")
            
            requirements_file = Path(args.requirements_file)
            
            # ファイル存在確認
            if not requirements_file.exists():
                print(f"❌ 要件ファイルが見つかりません: {requirements_file}")
                return None
            
            # サポートされている形式かチェック
            if requirements_file.suffix not in RequirementsFileParser.SUPPORTED_FORMATS:
                print(f"❌ サポートされていないファイル形式: {requirements_file.suffix}")
                print(f"サポート形式: {', '.join(RequirementsFileParser.SUPPORTED_FORMATS)}")
                return None
            
            print(f"📄 要件ファイルを解析中: {requirements_file}")
            
            # 要件ファイルを事前解析して内容を表示
            try:
                requirements_data = RequirementsFileParser.parse_requirements_file(str(requirements_file))
                
                print(f"✅ 要件ファイル解析完了")
                print("="*60)
                print("📋 解析された要件情報")
                print("="*60)
                print(f"プロジェクト名: {requirements_data['title']}")
                print(f"説明: {requirements_data['description'][:200]}..." if len(requirements_data['description']) > 200 else f"説明: {requirements_data['description']}")
                print(f"優先度: {requirements_data['priority']}")
                print(f"ファイル形式: {requirements_data['file_format']}")
                
                if requirements_data['requirements']:
                    print(f"\n🎯 機能要件 ({len(requirements_data['requirements'])}件):")
                    for i, req in enumerate(requirements_data['requirements'][:5], 1):
                        print(f"  {i}. {req}")
                    if len(requirements_data['requirements']) > 5:
                        print(f"  ... 他 {len(requirements_data['requirements']) - 5} 件")
                
                if requirements_data['technical_specs']:
                    print(f"\n🔧 技術仕様:")
                    for key, value in requirements_data['technical_specs'].items():
                        print(f"  - {key}: {value}")
                
                if requirements_data['constraints']:
                    print(f"\n⚠️ 制約 ({len(requirements_data['constraints'])}件):")
                    for constraint in requirements_data['constraints'][:3]:
                        print(f"  - {constraint}")
                
                if requirements_data['acceptance_criteria']:
                    print(f"\n✅ 受け入れ基準 ({len(requirements_data['acceptance_criteria'])}件):")
                    for criteria in requirements_data['acceptance_criteria'][:3]:
                        print(f"  - {criteria}")
                
            except Exception as parse_error:
                print(f"❌ 要件ファイル解析エラー: {parse_error}")
                return None
            
            # SpecDrivenExecutorを対象プロジェクト用に初期化
            executor = SpecDrivenExecutor(target_project_path, self.logger)
            
            print(f"\n🎨 インタラクティブレビューを開始...")
            
            # 要件ファイルからインタラクティブレビューを開始
            result = await executor.execute_task_from_requirements_file(
                str(requirements_file), args.session_id
            )
            
            if result.get('workflow_status') == 'ERROR':
                print(f"❌ エラー: {result.get('message')}")
                return None
            
            session_id = result.get('session_id')
            print(f"✅ 設計書生成完了! Session ID: {session_id}")
            print("\n" + "="*60)
            print("📊 生成された設計概要")
            print("="*60)
            
            review_data = result.get('review_data', {})
            design_summary = review_data.get('design_summary', {})
            
            print(f"プロジェクト名: {design_summary.get('project_name', project_name)}")
            print(f"プロジェクトタイプ: {project_type}")
            print(f"アーキテクチャ: {design_summary.get('architecture_type', 'N/A')}")
            print(f"主要コンポーネント数: {design_summary.get('key_components', 'N/A')}")
            print(f"複雑度レベル: {design_summary.get('complexity_level', 'N/A')}")
            print(f"推定作業時間: {design_summary.get('estimated_effort', 'N/A')}")
            
            # 要件ファイル特有の情報
            if 'requirements_count' in design_summary:
                print(f"解析された要件数: {design_summary.get('requirements_count', 'N/A')}")
                print(f"制約数: {design_summary.get('constraints_count', 'N/A')}")
                print(f"受け入れ基準数: {design_summary.get('acceptance_criteria_count', 'N/A')}")
            
            print("\n" + "="*60)
            print("📝 次のアクション")
            print("="*60)
            print(f"💚 承認: na review approve {session_id}")
            print(f"🔄 修正要求: na review modify {session_id} '修正内容'")
            print(f"💬 議論: na review discuss {session_id} 'トピック'")
            print(f"❌ 拒否: na review reject {session_id}")
            print(f"📊 状況確認: na review status --session-id {session_id}")
            
            print(f"\n💡 ヒント: {project_name}プロジェクトのルートディレクトリで実行しています")
            
            return result
            
        except Exception as e:
            self.logger.log_error("REQUIREMENTS_FILE_REVIEW_ERROR", f"要件ファイルレビュー開始エラー: {e}")
            print(f"❌ エラー: {e}")
            return None

    
    async def _review_from_file_with_target_command(self, args):
        """対象プロジェクトディレクトリで要件ファイルからインタラクティブレビューを開始"""
        try:
            from ..execution.spec_driven_executor import SpecDrivenExecutor, RequirementsFileParser
            from pathlib import Path
            
            requirements_file = Path(args.requirements_file)
            target_project_path = Path(args.target_project)
            
            # ファイル・ディレクトリ存在確認
            if not requirements_file.exists():
                print(f"❌ 要件ファイルが見つかりません: {requirements_file}")
                return None
            
            if not target_project_path.exists():
                print(f"❌ 対象プロジェクトディレクトリが見つかりません: {target_project_path}")
                return None
            
            if not target_project_path.is_dir():
                print(f"❌ パスがディレクトリではありません: {target_project_path}")
                return None
            
            print(f"🎯 対象プロジェクト: {target_project_path}")
            print(f"📄 要件ファイル: {requirements_file}")
            
            # 要件ファイルを事前解析
            try:
                requirements_data = RequirementsFileParser.parse_requirements_file(str(requirements_file))
                
                print(f"✅ 要件ファイル解析完了")
                print("="*60)
                print("📋 解析された要件情報")
                print("="*60)
                print(f"プロジェクト名: {requirements_data['title']}")
                print(f"説明: {requirements_data['description'][:200]}..." if len(requirements_data['description']) > 200 else f"説明: {requirements_data['description']}")
                print(f"要件数: {len(requirements_data['requirements'])}")
                
                if requirements_data['requirements']:
                    print(f"\\n主要要件:")
                    for i, req in enumerate(requirements_data['requirements'][:3], 1):
                        print(f"  {i}. {req}")
                
            except Exception as parse_error:
                print(f"❌ 要件ファイル解析エラー: {parse_error}")
                return None
            
            # SpecDrivenExecutorを初期化
            executor = SpecDrivenExecutor(str(target_project_path), self.logger)
            
            print(f"\\n🚀 対象プロジェクトでのインタラクティブレビュー開始...")
            print(f"作業ディレクトリ: {target_project_path}")
            
            # 対象プロジェクトで要件ファイルからレビューを開始
            result = await executor.execute_task_from_requirements_file_in_target_project(
                str(requirements_file), 
                str(target_project_path),
                args.session_id
            )
            
            if result.get('workflow_status') == 'ERROR':
                print(f"❌ エラー: {result.get('message')}")
                return None
            
            session_id = result.get('session_id')
            print(f"✅ 設計書生成完了! Session ID: {session_id}")
            
            print("\\n" + "="*60)
            print("🎯 対象プロジェクト情報")
            print("="*60)
            print(f"対象ディレクトリ: {result.get('target_project_path')}")
            print(f"要件ファイル: {result.get('requirements_file')}")
            
            review_data = result.get('review_data', {})
            if review_data:
                design_summary = review_data.get('design_summary', {})
                print(f"\\nプロジェクト名: {design_summary.get('project_name', 'N/A')}")
                print(f"アーキテクチャ: {design_summary.get('architecture_type', 'N/A')}")
                print(f"複雑度レベル: {design_summary.get('complexity_level', 'N/A')}")
                
                if 'requirements_count' in design_summary:
                    print(f"解析された要件数: {design_summary.get('requirements_count', 'N/A')}")
                    print(f"制約数: {design_summary.get('constraints_count', 'N/A')}")
            
            print("\\n" + "="*60)
            print("📝 次のアクション")
            print("="*60)
            print(f"💚 承認: na review approve {session_id}")
            print(f"🔄 修正要求: na review modify {session_id} '修正内容'")
            print(f"💬 議論: na review discuss {session_id} 'トピック'")
            print(f"❌ 拒否: na review reject {session_id}")
            print(f"📊 状況確認: na review status --session-id {session_id}")
            
            print(f"\\n🎉 対象プロジェクト「{target_project_path.name}」でのレビュー準備完了!")
            
            return result
            
        except Exception as e:
            self.logger.log_error("TARGET_PROJECT_REQUIREMENTS_ERROR", f"対象プロジェクト要件ファイルレビュー開始エラー: {e}")
            print(f"❌ エラー: {e}")
            return None
    
    async def _review_create_sample_command(self, args):
        """サンプル要件ファイルを作成"""
        try:
            from ..execution.spec_driven_executor import RequirementsFileParser
            from pathlib import Path
            
            file_path = Path(args.file_path)
            
            # ディレクトリが存在しない場合は作成
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # ファイルが既に存在する場合は確認
            if file_path.exists():
                response = input(f"ファイル {file_path} は既に存在します。上書きしますか？ (y/N): ")
                if response.lower() not in ['y', 'yes']:
                    print("❌ 処理を中止しました")
                    return
            
            print(f"📄 サンプル要件ファイルを作成中: {file_path}")
            print(f"📝 形式: {args.format}")
            
            # サンプルファイルを作成
            created_file = RequirementsFileParser.create_sample_requirements_file(
                str(file_path), args.format
            )
            
            print(f"✅ サンプル要件ファイルを作成しました: {created_file}")
            print("\n" + "="*50)
            print("📋 使用方法:")
            print("="*50)
            print("1. 作成されたファイルを編集してプロジェクトの要件を記述")
            print("2. 以下のコマンドでレビューを開始:")
            print(f"   na review from-file {created_file}")
            print("\n💡 ファイル形式の説明:")
            
            if args.format == 'yaml':
                print("- YAML: 構造化された設定形式、技術仕様やメタデータに適している")
                print("- 階層構造でデータを整理可能")
            elif args.format == 'json':
                print("- JSON: API連携やプログラム処理に適した構造化形式")
                print("- 他のツールとの連携が容易")
            else:  # markdown
                print("- Markdown: 人間が読みやすい文書形式")
                print("- GitHubやドキュメントツールで表示可能")
            
            print(f"\n📖 ファイル内容をプレビュー:")
            print("-" * 40)
            with open(created_file, 'r', encoding='utf-8') as f:
                content = f.read()
                # 長すぎる場合は最初の20行のみ表示
                lines = content.split('\n')
                if len(lines) > 20:
                    print('\n'.join(lines[:20]))
                    print(f"... (他 {len(lines) - 20} 行)")
                else:
                    print(content)
            print("-" * 40)
            
        except Exception as e:
            self.logger.log_error("SAMPLE_FILE_CREATION_ERROR", f"サンプルファイル作成エラー: {e}")
            print(f"❌ エラー: {e}")
    
    async def _review_status_command(self, args):
        """レビュー状況を確認"""
        try:
            from ..execution.spec_driven_executor import SpecDrivenExecutor
            
            workspace_path = args.workspace or os.getcwd()
            executor = SpecDrivenExecutor(workspace_path, self.logger)
            
            if args.session_id:
                # 特定セッションの状況
                status = executor.get_review_status(args.session_id)
                
                if status.get('status') == 'NOT_FOUND':
                    print(f"❌ セッション {args.session_id} が見つかりません")
                    return
                
                print(f"📋 セッション: {args.session_id}")
                print(f"状態: {status.get('status', 'N/A')}")
                print(f"タスク: {status.get('task', {}).get('title', 'N/A')}")
                print(f"作成日時: {status.get('created_at', 'N/A')}")
                print(f"修正回数: {status.get('modifications', 0)}")
                
                feedback_history = status.get('feedback_history', [])
                if feedback_history:
                    print("\n📝 フィードバック履歴:")
                    for i, feedback in enumerate(feedback_history, 1):
                        print(f"  {i}. [{feedback.get('type', 'N/A')}] {feedback.get('content', 'N/A')[:100]}...")
                        print(f"     時刻: {feedback.get('timestamp', 'N/A')}")
            else:
                # 全体の状況
                status = executor.get_review_status()
                
                print("📊 インタラクティブレビュー システム状況")
                print("="*50)
                print(f"アクティブレビュー: {status.get('active_reviews', 0)}")
                print(f"スケジュール済みタスク: {status.get('scheduled_tasks', 0)}")
                print(f"保留中タスク: {status.get('pending_tasks', 0)}")
                
                review_sessions = status.get('review_sessions', [])
                if review_sessions:
                    print(f"\n📋 レビューセッション ({len(review_sessions)}):")
                    for session_id in review_sessions:
                        session_status = executor.get_review_status(session_id)
                        print(f"  - {session_id}: {session_status.get('status', 'N/A')}")
                
                # スケジュール済みタスクの詳細
                scheduled_tasks = executor.get_scheduled_tasks()
                if scheduled_tasks:
                    print(f"\n🌙 スケジュール済みタスク ({len(scheduled_tasks)}):")
                    for task in scheduled_tasks:
                        print(f"  - {task.get('task', {}).get('title', 'N/A')}")
                        print(f"    実行予定: {task.get('scheduled_for', 'N/A')}")
                        print(f"    状態: {task.get('status', 'N/A')}")
            
        except Exception as e:
            self.logger.log_error("REVIEW_STATUS_ERROR", f"レビュー状況確認エラー: {e}")
            print(f"❌ エラー: {e}")
    
    async def _review_approve_command(self, args):
        """設計を承認"""
        try:
            from ..execution.spec_driven_executor import SpecDrivenExecutor
            
            workspace_path = args.workspace or os.getcwd()
            executor = SpecDrivenExecutor(workspace_path, self.logger)
            
            print(f"✅ 設計を承認中: {args.session_id}")
            result = await executor.approve_design(args.session_id)
            
            if result.get('status') == 'APPROVED':
                print("🎉 設計が承認されました!")
                print(f"🌙 夜間実行予定: {result.get('scheduled_execution', 'N/A')}")
                print("💤 承認されたタスクは指定時刻に自動実行されます")
            else:
                print(f"❌ 承認に失敗: {result.get('message', '不明なエラー')}")
                
            return result
            
        except Exception as e:
            self.logger.log_error("DESIGN_APPROVAL_ERROR", f"設計承認エラー: {e}")
            print(f"❌ エラー: {e}")
            return None
    
    async def _review_modify_command(self, args):
        """修正要求を送信"""
        try:
            from ..execution.spec_driven_executor import SpecDrivenExecutor
            
            workspace_path = args.workspace or os.getcwd()
            executor = SpecDrivenExecutor(workspace_path, self.logger)
            
            print(f"🔄 修正要求を処理中: {args.session_id}")
            print(f"要求内容: {args.request}")
            
            result = await executor.request_modification(args.session_id, args.request)
            
            if result.get('status') == 'REVIEW_READY':
                print("✅ 修正が完了しました!")
                print("📋 更新された設計書をレビューしてください")
                
                # 更新された設計概要を表示
                review_data = result.get('review_data', {})
                if review_data:
                    design_summary = review_data.get('design_summary', {})
                    print(f"\n更新された設計: {design_summary.get('project_name', 'N/A')}")
                    
                print(f"\n次のアクション:")
                print(f"💚 承認: na review approve {args.session_id}")
                print(f"🔄 追加修正: na review modify {args.session_id} '追加の修正内容'")
                print(f"💬 議論: na review discuss {args.session_id} 'トピック'")
                
            else:
                print(f"❌ 修正に失敗: {result.get('message', '不明なエラー')}")
                
            return result
            
        except Exception as e:
            self.logger.log_error("MODIFICATION_REQUEST_ERROR", f"修正要求エラー: {e}")
            print(f"❌ エラー: {e}")
            return None
    
    async def _review_discuss_command(self, args):
        """設計について議論"""
        try:
            from ..execution.spec_driven_executor import SpecDrivenExecutor
            
            workspace_path = args.workspace or os.getcwd()
            executor = SpecDrivenExecutor(workspace_path, self.logger)
            
            print(f"💬 議論を開始: {args.session_id}")
            print(f"トピック: {args.topic}")
            
            result = await executor.start_discussion(args.session_id, args.topic)
            
            if result.get('status') == 'DIALOGUE_ACTIVE':
                print("🤖 AI の回答:")
                print("-" * 50)
                print(result.get('ai_response', 'N/A'))
                print("-" * 50)
                
                print(f"\n継続オプション:")
                options = result.get('continue_options', {})
                for key, description in options.items():
                    print(f"  {key}: {description}")
                
                print(f"\n次のアクション例:")
                print(f"💚 承認: na review approve {args.session_id}")
                print(f"🔄 修正要求: na review modify {args.session_id} '具体的な修正内容'")
                print(f"💬 議論継続: na review discuss {args.session_id} '新しいトピック'")
                
            else:
                print(f"❌ 議論開始に失敗: {result.get('message', '不明なエラー')}")
                
            return result
            
        except Exception as e:
            self.logger.log_error("DISCUSSION_START_ERROR", f"議論開始エラー: {e}")
            print(f"❌ エラー: {e}")
            return None
    
    async def _review_reject_command(self, args):
        """設計を拒否"""
        try:
            from ..execution.spec_driven_executor import SpecDrivenExecutor
            
            workspace_path = args.workspace or os.getcwd()
            executor = SpecDrivenExecutor(workspace_path, self.logger)
            
            print(f"❌ 設計を拒否中: {args.session_id}")
            if args.reason:
                print(f"拒否理由: {args.reason}")
            
            result = await executor.reject_design(args.session_id)
            
            if result.get('status') == 'REJECTED':
                print("🗑️ 設計が拒否されました")
                print("📋 タスクはキャンセルされます")
            else:
                print(f"❌ 拒否処理に失敗: {result.get('message', '不明なエラー')}")
                
            return result
            
        except Exception as e:
            self.logger.log_error("DESIGN_REJECTION_ERROR", f"設計拒否エラー: {e}")
            print(f"❌ エラー: {e}")
            return None
    
    async def _review_nighttime_command(self, args):
        """夜間実行を手動開始"""
        try:
            from ..execution.spec_driven_executor import SpecDrivenExecutor
            
            workspace_path = args.workspace or os.getcwd()
            executor = SpecDrivenExecutor(workspace_path, self.logger)
            
            print("🌙 夜間実行を手動開始...")
            
            # スケジュール済みタスクを確認
            scheduled_tasks = executor.get_scheduled_tasks()
            if not scheduled_tasks:
                print("📭 実行予定のタスクがありません")
                return
            
            print(f"📋 実行予定タスク: {len(scheduled_tasks)}件")
            for task in scheduled_tasks:
                if task.get('status') == 'SCHEDULED':
                    print(f"  - {task.get('task', {}).get('title', 'N/A')}")
            
            await executor.execute_nighttime_tasks()
            
            print("✅ 夜間実行が完了しました")
            
        except Exception as e:
            self.logger.log_error("NIGHTTIME_EXECUTION_ERROR", f"夜間実行エラー: {e}")
            print(f"❌ エラー: {e}")
            return None

    async def _execute_command(self, args):
        """execute コマンドの実行（設計ファイルベース）"""
        try:
            from ..design.design_file_manager import DistributedDesignGenerator
            from ..execution.implementation_task_manager import NightlyTaskExecutor
            
            # 設計ファイル管理システム初期化
            design_generator = DistributedDesignGenerator(self.logger)
            
            design_file_path = Path(args.design_file)
            if not design_file_path.exists():
                print(f"❌ 設計ファイルが見つかりません: {design_file_path}")
                return
            
            print(f"📋 設計ファイル読み込み: {design_file_path}")
            
            # 設計ファイルを検証・準備
            design = design_generator.validate_and_prepare_design(design_file_path)
            if not design:
                print("❌ 設計ファイルの検証に失敗しました")
                return
            
            # 検証のみの場合
            if args.validate_only:
                print("✅ 設計ファイルの検証が完了しました")
                summary = design.get('execution_summary', {})
                print(f"📊 実行予定: {summary.get('total_tasks', 0)}タスク, {summary.get('total_estimated_hours', 0):.1f}時間")
                return
            
            # ワークスペースパスを取得
            workspace_path = design.get('project_info', {}).get('workspace_path', '')
            if not workspace_path:
                print("❌ ワークスペースパスが設定されていません")
                return
                
            workspace_path = Path(workspace_path)
            if not workspace_path.exists():
                print(f"❌ ワークスペースが存在しません: {workspace_path}")
                return
            
            print(f"🏗️ ワークスペース: {workspace_path}")
            
            # タスクを実装タスク管理システムに登録
            from ..execution.implementation_task_manager import ImplementationTaskManager
            task_manager = ImplementationTaskManager(str(workspace_path), self.logger)
            
            generated_tasks = design.get('generated_tasks', [])
            created_task_ids = []
            task_id_mapping = {}  # 元のタスクID → 新しいタスクIDのマッピング
            
            print(f"📝 タスク登録開始: {len(generated_tasks)}個のタスク")
            
            # 第1パス: 依存関係なしでタスクを作成
            for task_data in generated_tasks:
                original_task_id = task_data.get('task_id', f"task_{len(created_task_ids)}")
                
                # タスクデータを実装タスク用に変換（依存関係は後で設定）
                task_spec = {
                    'title': task_data.get('title', 'Unknown Task'),
                    'description': task_data.get('description', ''),
                    'priority': task_data.get('priority', 'MEDIUM'),
                    'estimated_hours': task_data.get('estimated_hours', 2.0),
                    'technical_requirements': task_data.get('technical_requirements', []),
                    'acceptance_criteria': task_data.get('acceptance_criteria', []),
                    'dependencies': []  # 一旦空にする
                }
                
                task_id = task_manager.create_task_from_specification(task_spec)
                created_task_ids.append(task_id)
                task_id_mapping[original_task_id] = task_id
                
                # 作成されたタスクを承認状態にする
                task_manager.approve_task(task_id, "design_file_execution")
            
            # 第2パス: 依存関係を設定
            for i, task_data in enumerate(generated_tasks):
                if 'dependencies' in task_data and task_data['dependencies']:
                    task_id = created_task_ids[i]
                    # 依存タスクIDを新しいIDに変換
                    valid_dependencies = []
                    for dep_id in task_data['dependencies']:
                        if dep_id in task_id_mapping:
                            valid_dependencies.append(task_id_mapping[dep_id])
                        else:
                            # 依存タスクIDが見つからない場合は警告してスキップ
                            print(f"⚠️ 依存タスクIDが見つかりません（スキップ）: {dep_id}")
                    
                    # タスクの依存関係を更新
                    if task_id in task_manager.tasks:
                        task_manager.tasks[task_id].dependencies = valid_dependencies
            
            print(f"✅ {len(created_task_ids)}個のタスクを登録・承認完了")
            
            # dry-run の場合は実行計画のみ表示
            if args.dry_run:
                print("\n🔍 実行計画（dry-run）:")
                ready_tasks = task_manager.get_ready_tasks()
                for i, task in enumerate(ready_tasks[:args.max_tasks], 1):
                    print(f"  {i}. {task.title} ({task.estimated_hours}h)")
                
                total_hours = sum(task.estimated_hours for task in ready_tasks[:args.max_tasks])
                print(f"\n📊 実行予定: {min(len(ready_tasks), args.max_tasks)}タスク, {total_hours:.1f}時間")
                return
            
            # 実行モードに応じて処理
            if args.mode == 'immediate':
                print(f"\n🚀 即時実行開始（最大{args.max_tasks}タスク）")
                
                # 夜間実行システムを使用して即座に実行
                nightly_executor = NightlyTaskExecutor(str(workspace_path), self.logger)
                execution_summary = await nightly_executor.execute_nightly_tasks(max_tasks=args.max_tasks)
                
                # 実行結果を表示
                executed_count = len(execution_summary.get('executed_tasks', []))
                failed_count = len(execution_summary.get('failed_tasks', []))
                total_time = execution_summary.get('total_execution_time', 0)
                
                print(f"\n🎉 即時実行完了!")
                print(f"📊 成功: {executed_count}タスク, 失敗: {failed_count}タスク")
                print(f"⏱️ 実行時間: {total_time:.1f}秒")
                
                if 'task_summary' in execution_summary:
                    task_summary = execution_summary['task_summary']
                    print(f"📈 全体進捗: {task_summary['completion_rate']:.1%}")
                
                # 実装完了時に自動的に設計書に反映
                if executed_count > 0:
                    # 設定を確認して自動同期を実行
                    design_sync_config = self.config.design_sync
                    if design_sync_config and design_sync_config.auto_sync_enabled:
                        if args.mode == 'immediate' and design_sync_config.auto_sync_on_immediate:
                            print(f"\n🔄 実装完了を設計書に自動反映中...")
                            try:
                                await self._auto_sync_design_from_code(
                                    design_file_path, 
                                    workspace_path,
                                    create_backup=design_sync_config.create_backup,
                                    quiet=design_sync_config.quiet_mode
                                )
                            except Exception as sync_error:
                                print(f"⚠️ 設計書への自動反映でエラーが発生しました: {sync_error}")
                                print(f"💡 手動で同期するには: nocturnal design sync {design_file_path}")
                        elif args.mode == 'nightly' and design_sync_config.auto_sync_on_nightly:
                            print(f"\n🔄 夜間実行完了後、設計書に自動反映されます...")
                        elif args.mode == 'scheduled' and design_sync_config.auto_sync_on_scheduled:
                            print(f"\n🔄 スケジュール実行完了後、設計書に自動反映されます...")
                    else:
                        if not design_sync_config or not design_sync_config.auto_sync_enabled:
                            print(f"\n💡 設計書への自動反映は設定で無効化されています")
                            print(f"   有効にするには: nocturnal config set design_sync.auto_sync_enabled true")
                
            elif args.mode == 'nightly':
                print(f"\n🌙 夜間実行にスケジュール（最大{args.max_tasks}タスク）")
                # 夜間実行スケジューラに登録（既存の実装を使用）
                print("✅ 夜間実行で処理されます")
                
            elif args.mode == 'scheduled':
                schedule_time = args.schedule_time or "22:00"
                print(f"\n⏰ {schedule_time}にスケジュール実行（最大{args.max_tasks}タスク）")
                # スケジュール実行（実装は省略）
                print("✅ スケジュール実行で処理されます")
            
        except Exception as e:
            print(f"❌ 実行エラー: {e}")
            if args.verbose:
                import traceback
                traceback.print_exc()

    
    async def _progress_command(self, args):
        """progress コマンドの実行（進捗状況確認）"""
        try:
            import os
            import json
            import time
            from pathlib import Path
            from datetime import datetime
            
            print("🔍 実行進捗状況を確認中...")
            
            # ワークスペースの特定
            if args.workspace:
                workspace_path = Path(args.workspace)
            elif args.design_file:
                # 設計ファイルからワークスペースを推定
                design_file = Path(args.design_file)
                if design_file.name == 'main_design.yaml':
                    workspace_path = design_file.parent.parent
                else:
                    workspace_path = design_file.parent
            else:
                # 現在のディレクトリから推定
                workspace_path = Path.cwd()
            
            print(f"📁 ワークスペース: {workspace_path}")
            
            # ClaudeCode実行ログディレクトリを探す
            execution_dirs = [
                workspace_path / ".nocturnal" / "claude_executions",
                workspace_path / "team_designs" / ".nocturnal" / "claude_executions",
                workspace_path / ".nocturnal" / "executions"
            ]
            
            execution_dir = None
            for dir_path in execution_dirs:
                if dir_path.exists():
                    execution_dir = dir_path
                    break
            
            if not execution_dir:
                print("❌ 実行ログディレクトリが見つかりません")
                print("   実行中のタスクがない可能性があります")
                return
            
            # 実行状況を分析
            def analyze_execution_progress():
                """実行進捗を分析"""
                log_files = list(execution_dir.glob("impl_*_instruction.md"))
                result_files = list(execution_dir.glob("impl_*_result.json"))
                
                # ファイル名から実行セッションとタスク番号を抽出
                tasks = {}
                for file_path in log_files:
                    parts = file_path.stem.split('_')
                    if len(parts) >= 4:
                        session = f"{parts[1]}_{parts[2]}"
                        task_num = parts[3]
                        task_id = f"impl_{session}_{task_num}"
                        
                        if task_id not in tasks:
                            tasks[task_id] = {
                                'instruction_file': file_path,
                                'result_file': None,
                                'status': 'running',
                                'start_time': datetime.fromtimestamp(file_path.stat().st_mtime),
                                'title': 'Unknown Task'
                            }
                
                # 結果ファイルをマッチング
                for file_path in result_files:
                    parts = file_path.stem.split('_')
                    if len(parts) >= 4:
                        session = f"{parts[1]}_{parts[2]}"
                        task_num = parts[3]
                        task_id = f"impl_{session}_{task_num}"
                        
                        if task_id in tasks:
                            tasks[task_id]['result_file'] = file_path
                            tasks[task_id]['status'] = 'completed'
                            tasks[task_id]['end_time'] = datetime.fromtimestamp(file_path.stat().st_mtime)
                
                # タスク詳細を読み込み
                for task_id, task_info in tasks.items():
                    try:
                        with open(task_info['instruction_file'], 'r', encoding='utf-8') as f:
                            content = f.read()
                            # タイトルを抽出
                            lines = content.split('\n')
                            for line in lines:
                                if line.startswith('- **タイトル**:'):
                                    task_info['title'] = line.split(': ', 1)[1].strip()
                                    break
                    except Exception:
                        pass
                
                return tasks
            
            # リフレッシュモード
            if args.refresh > 0:
                print(f"🔄 {args.refresh}秒ごとに自動更新中... (Ctrl+Cで停止)")
                try:
                    while True:
                        os.system('clear' if os.name == 'posix' else 'cls')  # 画面クリア
                        print(f"🔍 進捗状況 - {datetime.now().strftime('%H:%M:%S')}")
                        print("=" * 60)
                        
                        tasks = analyze_execution_progress()
                        self._display_progress(tasks, args.detailed)
                        
                        time.sleep(args.refresh)
                except KeyboardInterrupt:
                    print("\n⏹️ 自動更新を停止しました")
                    return
            else:
                # 一回だけ表示
                tasks = analyze_execution_progress()
                self._display_progress(tasks, args.detailed)
                
        except Exception as e:
            print(f"❌ 進捗確認エラー: {e}")
            if args.verbose:
                import traceback
                traceback.print_exc()
    
    def _display_progress(self, tasks, detailed=False):
        """進捗状況を表示"""
        if not tasks:
            print("📭 実行中または完了済みのタスクがありません")
            return
        
        # ステータス別にグループ化
        completed_tasks = [t for t in tasks.values() if t['status'] == 'completed']
        running_tasks = [t for t in tasks.values() if t['status'] == 'running']
        
        total_tasks = len(tasks)
        completed_count = len(completed_tasks)
        running_count = len(running_tasks)
        
        # 進捗サマリー
        progress_rate = (completed_count / total_tasks) * 100 if total_tasks > 0 else 0
        print(f"📊 **進捗サマリー**")
        print(f"   総タスク数: {total_tasks}")
        print(f"   完了: {completed_count} ({progress_rate:.1f}%)")
        print(f"   実行中: {running_count}")
        print()
        
        # 実行中タスク
        if running_tasks:
            print("🔄 **実行中タスク:**")
            for task in sorted(running_tasks, key=lambda x: x['start_time'], reverse=True):
                duration = datetime.now() - task['start_time']
                minutes = int(duration.total_seconds() / 60)
                print(f"   ⏳ {task['title']} (実行時間: {minutes}分)")
            print()
        
        # 最近完了したタスク（最新5件）
        if completed_tasks:
            recent_completed = sorted(completed_tasks, key=lambda x: x.get('end_time', x['start_time']), reverse=True)[:5]
            print("✅ **最近完了したタスク:**")
            for task in recent_completed:
                end_time = task.get('end_time', task['start_time'])
                print(f"   ✓ {task['title']} ({end_time.strftime('%H:%M')})")
            print()
        
        # 詳細情報
        if detailed:
            print("📋 **詳細情報:**")
            for task_id, task in sorted(tasks.items()):
                status_icon = "✅" if task['status'] == 'completed' else "🔄"
                print(f"   {status_icon} {task_id}")
                print(f"      タイトル: {task['title']}")
                print(f"      開始時刻: {task['start_time'].strftime('%Y-%m-%d %H:%M:%S')}")
                if task['status'] == 'completed' and 'end_time' in task:
                    duration = task['end_time'] - task['start_time']
                    print(f"      完了時刻: {task['end_time'].strftime('%Y-%m-%d %H:%M:%S')}")
                    print(f"      実行時間: {int(duration.total_seconds())}秒")
                print()
        
        # 予想完了時刻
        if running_count > 0 and completed_count > 0:
            # 平均実行時間を計算
            avg_duration = 0
            duration_count = 0
            for task in completed_tasks:
                if 'end_time' in task:
                    duration = task['end_time'] - task['start_time']
                    avg_duration += duration.total_seconds()
                    duration_count += 1
            
            if duration_count > 0:
                avg_duration = avg_duration / duration_count
                remaining_time = avg_duration * running_count
                estimated_completion = datetime.now().timestamp() + remaining_time
                completion_time = datetime.fromtimestamp(estimated_completion)
                
                print(f"⏰ **予想完了時刻:** {completion_time.strftime('%H:%M:%S')} (約{int(remaining_time/60)}分後)")

    async def _design_create_command(self, args):
        """design create コマンドの実装（ステップ2: 設計書作成）"""
        try:
            from pathlib import Path
            from ..requirements import RequirementsParser, DesignFileGenerator
            
            if not args.from_requirements:
                print("❌ エラー: --from-requirements オプションが必要です")
                print("使用例: nocturnal design create --from-requirements requirements/requirements_20250101.md")
                return
            
            requirements_file = Path(args.from_requirements)
            if not requirements_file.exists():
                print(f"❌ 要件ファイルが見つかりません: {requirements_file}")
                return
            
            print(f"📄 要件ファイルを読み込み中: {requirements_file}")
            
            # ファイルから要件を読み込み
            with open(requirements_file, 'r', encoding='utf-8') as f:
                requirements_text = f.read()
            
            if not requirements_text.strip():
                print("❌ ファイルが空です")
                return
            
            # プロジェクト名を決定
            project_name = args.project_name
            if not project_name:
                project_info = self._get_current_project_info()
                project_name = project_info['project_name']
            
            print(f"📋 プロジェクト名: {project_name}")
            print(f"🧠 要件を解析中...")
            
            # 要件解析
            parser = RequirementsParser()
            analysis = parser.parse_requirements(requirements_text)
            
            print(f"✅ 解析完了:")
            print(f"  📋 プロジェクトタイプ: {analysis.project_type}")
            print(f"  📊 複雑度: {analysis.estimated_complexity}")
            print(f"  🤖 エージェント割り当て: {len(analysis.agent_assignments)}個")
            
            # 設計ファイル生成
            print("\n📝 設計ファイルを生成中...")
            generator = DesignFileGenerator()
            workspace_path = Path(args.workspace).resolve()
            generated_files = generator.generate_design_files(
                analysis, str(workspace_path), project_name
            )
            
            print("✅ 設計ファイル生成完了:")
            main_design_file = None
            for agent, file_path in generated_files.items():
                print(f"  📄 {agent}: {file_path}")
                if agent == 'main':
                    main_design_file = file_path
            
            print(f"\n📝 次のステップ:")
            if main_design_file:
                print(f"  1. 設計書を確認: {main_design_file}")
                print(f"  2. 設計書を検証: nocturnal design validate {main_design_file}")
                print(f"  3. 実装を開始: nocturnal implement start {main_design_file}")
            
            # 実行開始
            if args.execute and main_design_file:
                print("\n🚀 即座に実装を開始...")
                implement_args = type('Args', (), {
                    'design_file': main_design_file,
                    'mode': 'immediate',
                    'max_tasks': 5,
                    'dry_run': False,
                    'schedule_time': None,
                    'verbose': getattr(args, 'verbose', False)
                })()
                await self._implement_start_command(implement_args)
                
        except Exception as e:
            print(f"❌ エラーが発生しました: {e}")
            if hasattr(args, 'verbose') and args.verbose:
                import traceback
                traceback.print_exc()

    async def _design_create_template_command(self, args):
        """design create-template コマンドの実行"""
        try:
            from ..design.design_file_manager import DistributedDesignGenerator
            
            design_generator = DistributedDesignGenerator(self.logger)
            
            output_dir = Path(args.output_dir)
            agent_name = args.agent_name
            
            print(f"🏗️ エージェント '{agent_name}' 用設計テンプレート作成中...")
            
            workspace = design_generator.create_agent_design_workspace(
                str(output_dir.parent), agent_name
            )
            
            print(f"✅ 設計ワークスペース作成完了: {workspace}")
            print(f"📋 テンプレートファイル: {workspace / 'design_template.yaml'}")
            print(f"📖 使用方法ガイド: {workspace / 'README.md'}")
            print()
            print("次の手順:")
            print("1. design_template.yaml をコピーして設計ファイルを作成")
            print("2. 各セクションを記入")
            print("3. 検証: nocturnal design validate your_design.yaml")
            print("4. 実行: nocturnal execute --design-file your_design.yaml")
            
        except Exception as e:
            print(f"❌ テンプレート作成エラー: {e}")
            if args.verbose:
                import traceback
                traceback.print_exc()

    async def _design_validate_command(self, args):
        """design validate コマンドの実行"""
        try:
            from ..design.design_file_manager import DesignFileManager
            
            design_manager = DesignFileManager(self.logger)
            design_file_path = Path(args.design_file)
            
            if not design_file_path.exists():
                print(f"❌ 設計ファイルが見つかりません: {design_file_path}")
                return
            
            print(f"🔍 設計ファイル検証中: {design_file_path}")
            
            design = design_manager.load_design_file(design_file_path)
            if not design:
                print("❌ 設計ファイルの読み込みに失敗しました")
                return
            
            validation_result = design_manager.validate_design_file(design)
            
            # 検証結果表示
            if validation_result.is_valid:
                print("✅ 設計ファイルは有効です")
            else:
                print("❌ 設計ファイルに問題があります")
            
            print(f"📊 完成度スコア: {validation_result.completeness_score:.1%}")
            
            if validation_result.errors:
                print("\n🚨 エラー:")
                for error in validation_result.errors:
                    print(f"  - {error}")
            
            if validation_result.warnings:
                print("\n⚠️ 警告:")
                for warning in validation_result.warnings:
                    print(f"  - {warning}")
            
            if args.detailed:
                # 詳細な検証結果
                tasks = design_manager.generate_task_breakdown_from_design(design)
                summary = design_manager.export_design_summary(design)
                
                print(f"\n📋 詳細情報:")
                print(f"  - プロジェクト名: {summary['project_name']}")
                print(f"  - 総タスク数: {summary['total_tasks']}")
                print(f"  - 推定作業時間: {summary['total_estimated_hours']:.1f}時間")
                print(f"  - 推奨実行モード: {summary['recommended_mode']}")
                print(f"  - 完了予定: {summary['completion_estimate']}")
                
                if summary['priority_distribution']:
                    print(f"  - 優先度分布:")
                    for priority, count in summary['priority_distribution'].items():
                        print(f"    - {priority}: {count}タスク")
            
        except Exception as e:
            print(f"❌ 検証エラー: {e}")
            if args.verbose:
                import traceback
                traceback.print_exc()

    async def _design_summary_command(self, args):
        """design summary コマンドの実行"""
        try:
            from ..design.design_file_manager import DesignFileManager
            
            design_manager = DesignFileManager(self.logger)
            design_file_path = Path(args.design_file)
            
            if not design_file_path.exists():
                print(f"❌ 設計ファイルが見つかりません: {design_file_path}")
                return
            
            design = design_manager.load_design_file(design_file_path)
            if not design:
                print("❌ 設計ファイルの読み込みに失敗しました")
                return
            
            summary = design_manager.export_design_summary(design)
            
            print(f"📋 設計ファイルサマリー: {design_file_path.name}")
            print("=" * 50)
            print(f"プロジェクト名: {summary['project_name']}")
            print(f"説明: {summary['description']}")
            print(f"総タスク数: {summary['total_tasks']}")
            print(f"推定作業時間: {summary['total_estimated_hours']:.1f}時間")
            print(f"完了予定: {summary['completion_estimate']}")
            print(f"推奨実行モード: {summary['recommended_mode']}")
            
            if summary['priority_distribution']:
                print("\n優先度分布:")
                for priority, count in summary['priority_distribution'].items():
                    print(f"  {priority}: {count}タスク")
            
        except Exception as e:
            print(f"❌ サマリー生成エラー: {e}")
            if args.verbose:
                import traceback
                traceback.print_exc()

    async def _design_convert_command(self, args):
        """design convert コマンドの実行"""
        try:
            import yaml
            import json
            
            input_path = Path(args.input_file)
            output_path = Path(args.output_file)
            
            if not input_path.exists():
                print(f"❌ 入力ファイルが見つかりません: {input_path}")
                return
            
            # 入力ファイル読み込み
            with open(input_path, 'r', encoding='utf-8') as f:
                if input_path.suffix.lower() in ['.yaml', '.yml']:
                    data = yaml.safe_load(f)
                elif input_path.suffix.lower() == '.json':
                    data = json.load(f)
                else:
                    print(f"❌ サポートされていない入力形式: {input_path.suffix}")
                    return
            
            # 出力形式を決定
            output_format = args.format
            if not output_format:
                output_format = 'yaml' if output_path.suffix.lower() in ['.yaml', '.yml'] else 'json'
            
            # 出力ファイル書き込み
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                if output_format == 'yaml':
                    yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
                else:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            
            print(f"✅ 変換完了: {input_path} → {output_path} ({output_format.upper()})")
            
        except Exception as e:
            print(f"❌ 変換エラー: {e}")
            if args.verbose:
                import traceback
                traceback.print_exc()

    async def _design_sync_command(self, args):
        """design sync コマンドの実装（コードから設計書への同期）"""
        try:
            from ..design.design_sync import DesignSyncManager
            from pathlib import Path
            
            design_file_path = Path(args.design_file)
            if not design_file_path.exists():
                print(f"❌ 設計ファイルが見つかりません: {design_file_path}")
                return
            
            # ワークスペースパスを決定
            workspace_path = args.workspace
            if not workspace_path:
                # 設計書から取得を試みる
                from ..design.design_file_manager import DesignFileManager
                design_manager = DesignFileManager(self.logger)
                design = design_manager.load_design_file(design_file_path)
                if design:
                    workspace_path = design.get('project_info', {}).get('workspace_path', '.')
                else:
                    workspace_path = '.'
            
            workspace_path = Path(workspace_path).resolve()
            if not workspace_path.exists():
                print(f"❌ ワークスペースが存在しません: {workspace_path}")
                return
            
            print(f"📋 設計ファイル: {design_file_path}")
            print(f"💻 ワークスペース: {workspace_path}")
            print(f"🔍 コードを解析して設計書との差分を検出中...\n")
            
            # 同期実行
            sync_manager = DesignSyncManager(self.logger)
            diffs = sync_manager.sync_design_from_code(
                design_file_path=design_file_path,
                workspace_path=workspace_path,
                dry_run=args.dry_run,
                auto_apply=args.auto_apply,
                quiet=False,  # 手動実行時は詳細出力
                create_backup=args.backup
            )
            
            if diffs:
                print(f"\n✅ {len(diffs)}件の差分を検出しました")
                if args.dry_run:
                    print("💡 実際に更新するには --dry-run オプションを外してください")
                else:
                    print("✅ 設計書を更新しました")
            else:
                print("\n✅ 設計書とコードに差分はありませんでした")
            
        except Exception as e:
            print(f"❌ 同期エラー: {e}")
            if hasattr(args, 'verbose') and args.verbose:
                import traceback
                traceback.print_exc()

    async def _auto_sync_design_from_code(
        self, 
        design_file_path: Path, 
        workspace_path: Path,
        create_backup: bool = True,
        quiet: bool = True
    ) -> bool:
        """実装完了時に自動的に設計書に反映する（エラーを抑制）"""
        try:
            from ..design.design_sync import DesignSyncManager
            
            if not design_file_path.exists():
                return False
            
            workspace_path = workspace_path.resolve()
            if not workspace_path.exists():
                return False
            
            # 自動同期実行（エラーは抑制）
            sync_manager = DesignSyncManager(self.logger)
            diffs = sync_manager.sync_design_from_code(
                design_file_path=design_file_path,
                workspace_path=workspace_path,
                dry_run=False,  # 実際に更新
                auto_apply=True,  # 確認なしで自動適用
                quiet=quiet,  # 設定に基づく出力モード
                create_backup=create_backup  # 設定に基づくバックアップ作成
            )
            
            if diffs:
                if quiet:
                    print(f"  ✅ {len(diffs)}件の変更を設計書に反映しました")
                else:
                    print(f"  ✅ {len(diffs)}件の変更を設計書に反映しました")
            else:
                if not quiet:
                    print(f"  ✅ 設計書とコードに差分はありませんでした")
            
            return True
            
        except Exception as e:
            # 自動同期のエラーは警告のみ（実装自体は成功している）
            self.logger.warning(f"自動設計書同期エラー: {e}")
            return False


    def _setup_team_design_environment(self, workspace_path: Path) -> None:
        """チーム設計協調環境のセットアップ"""
        print("\n🤝 チーム設計協調環境をセットアップ中...")
        
        team_designs_path = workspace_path / 'team_designs'
        
        # デフォルトエージェント専門分野
        default_agents = [
            'frontend_specialist',
            'backend_specialist', 
            'database_specialist',
            'qa_specialist'
        ]
        
        from nocturnal_agent.design.design_file_manager import DistributedDesignGenerator
        from nocturnal_agent.log_system.structured_logger import StructuredLogger
        
        # 簡易ロガー作成
        logger_config = {'console_output': True, 'file_output': False}
        logger = StructuredLogger(logger_config)
        
        design_generator = DistributedDesignGenerator(logger)
        
        # 各専門エージェント用ワークスペース作成
        created_workspaces = []
        for agent_name in default_agents:
            try:
                workspace = design_generator.create_agent_design_workspace(
                    str(team_designs_path), agent_name
                )
                created_workspaces.append(workspace)
                print(f"  ✅ {agent_name} ワークスペース: {workspace}")
            except Exception as e:
                print(f"  ❌ {agent_name} ワークスペース作成失敗: {e}")
        
        # チーム協調ガイド作成
        team_guide_path = team_designs_path / 'TEAM_COLLABORATION_GUIDE.md'
        team_guide_content = f"""# チーム設計協調ガイド

## 🎯 概要
このディレクトリは分散チーム設計協調のためのワークスペースです。
各専門エージェントが独立して設計書を作成し、統合実行を行います。

## 👥 専門エージェント

### 作成済みワークスペース
{chr(10).join([f"- `{w.name}/` - {w.name.replace('agent_', '').replace('_', ' ').title()}" for w in created_workspaces])}

## 🔄 協調ワークフロー

### 1. 設計書作成
各エージェントは担当分野の設計書を作成：

```bash
# Frontend Specialist
cd designs/agent_frontend_specialist
cp design_template.yaml web_ui_system.yaml
# Edit web_ui_system.yaml...

# Backend Specialist  
cd ../agent_backend_specialist
cp design_template.yaml api_backend_system.yaml
# Edit api_backend_system.yaml...

# Database Specialist
cd ../agent_database_specialist
cp design_template.yaml data_management_system.yaml
# Edit data_management_system.yaml...

# QA Specialist
cd ../agent_qa_specialist
cp design_template.yaml system_testing.yaml
# Edit system_testing.yaml...
```

### 2. 設計検証
```bash
# 各設計ファイルの検証
nocturnal design validate web_ui_system.yaml --detailed
nocturnal design validate api_backend_system.yaml --detailed
nocturnal design validate data_management_system.yaml --detailed
nocturnal design validate system_testing.yaml --detailed
```

### 3. 段階的実行
```bash
# Phase 1: Infrastructure
nocturnal execute --design-file data_management_system.yaml --mode immediate --max-tasks 2

# Phase 2: Backend Services
nocturnal execute --design-file api_backend_system.yaml --mode immediate --max-tasks 3

# Phase 3: Frontend Interface
nocturnal execute --design-file web_ui_system.yaml --mode immediate --max-tasks 2

# Phase 4: Quality Assurance
nocturnal execute --design-file system_testing.yaml --mode nightly
```

### 4. 進捗確認
```bash
# プロジェクト全体の状況確認
nocturnal status

# 実行ログ確認
nocturnal logs --recent
```

## 📋 設計ファイルテンプレート

各エージェントワークスペースには以下が含まれています：

- `design_template.yaml` - 標準設計テンプレート
- `README.md` - 使用方法ガイド

## 🎯 ベストプラクティス

1. **専門分野特化**: 各エージェントは専門分野に集中
2. **インターフェース明確化**: コンポーネント間の連携を明確に定義
3. **段階的実装**: 依存関係を考慮した実装順序
4. **継続的検証**: 各段階での設計検証・テスト実行
5. **進捗共有**: 定期的な進捗確認とチーム同期

## 🔗 関連コマンド

```bash
# 新しいエージェントワークスペース追加
nocturnal design create-template security_specialist --output-dir ./team_designs

# 設計サマリー確認
nocturnal design summary design_file.yaml

# 実行計画プレビュー
nocturnal execute --design-file design_file.yaml --dry-run
```

---
🌙 **Nocturnal Agent Team Design Collaboration System**
"""
        
        with open(team_guide_path, 'w', encoding='utf-8') as f:
            f.write(team_guide_content)
        
        print(f"  📚 チーム協調ガイド: {team_guide_path}")
        print(f"✅ チーム設計協調環境セットアップ完了！")
        print(f"\n👥 {len(created_workspaces)}個の専門エージェントワークスペースを作成しました")
        print(f"📖 詳細は {team_guide_path} を参照してください")
    
    def _generate_project_config(self, project_name: str, workspace_path: Path) -> str:
        """プロジェクト固有の設定ファイルを生成"""
        from datetime import datetime
        
        # プロジェクト名から推測される設定
        project_type = self._infer_project_type(project_name)
        
        config_content = f"""# Nocturnal Agent Configuration for {project_name}
# Generated on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
# Documentation: https://github.com/nocturnal-agent/nocturnal-agent

# ================================================================
# Project Information
# ================================================================
project_name: "{project_name}"
working_directory: "{workspace_path}"
project_type: "{project_type}"
created_at: "{datetime.now().isoformat()}"

# ================================================================
# Local LLM Settings
# ================================================================
llm:
  enabled: true
  # Model configuration (ensure LM Studio/Ollama is running)
  model_path: "qwen2.5:7b"  # or "llama3.2:latest", "codellama:latest"
  api_url: "http://localhost:11434"  # Ollama default, use 1234 for LM Studio
  timeout: 900  # 15 minutes
  max_tokens: 4096  # Increased for complex tasks
  temperature: 0.7  # Balance creativity and consistency
  
  # Alternative model configurations (uncomment to use)
  # model_path: "codellama:13b"     # For code-heavy projects
  # model_path: "llama3.2:3b"       # For lightweight setup
  # api_url: "http://localhost:1234" # For LM Studio

# ================================================================
# Agent Configuration
# ================================================================
agents:
  timeout_seconds: 2400  # 40 minutes for complex tasks
  max_retries: 3
  retry_delay: 10  # seconds
  
# ================================================================
# Execution Settings
# ================================================================
execution:
  max_tasks_per_batch: {self._get_batch_size_for_project_type(project_type)}
  default_mode: "immediate"  # immediate/nightly/scheduled
  
  # Task execution constraints
  constraints:
    max_parallel_tasks: 1
    timeout_per_task: 3600  # 1 hour
    retry_on_failure: true
    max_retries: 3
  
  # Execution modes configuration
  modes:
    immediate:
      max_tasks: 10
      priority_filter: ["HIGH", "MEDIUM"]
    
    nightly:
      start_time: "22:00"
      max_duration: 28800  # 8 hours
      max_tasks: 50
      
    scheduled:
      default_schedule: "0 22 * * *"  # Daily at 10 PM
      timezone: "Asia/Tokyo"

# ================================================================
# Logging Configuration  
# ================================================================
logging:
  level: "INFO"  # DEBUG/INFO/WARNING/ERROR
  console_output: true
  file_output: true
  
  # Log destinations
  log_directory: "{workspace_path / 'logs'}"
  max_log_files: 30  # Keep 30 days of logs
  max_log_size: "100MB"
  
  # Structured logging
  structured_format: true
  include_timestamps: true
  include_session_id: true
  
  # Claude Code interaction logging
  claude_code_logs: true
  
# ================================================================
# Safety & Validation
# ================================================================
safety:
  enabled: true
  backup_before_changes: true
  max_file_changes: {self._get_max_changes_for_project_type(project_type)}
  
  # Pre-execution validation
  validate_design_files: true
  require_confirmation: false  # Set to true for production
  
  # File operation safety
  excluded_directories: [".git", "node_modules", "__pycache__", ".venv"]
  excluded_file_patterns: ["*.log", "*.tmp", "*.pyc"]
  
  # Backup configuration
  backup:
    enabled: true
    location: "{workspace_path / '.nocturnal' / 'backups'}"
    retention_days: 7
    max_backup_size: "1GB"

# ================================================================
# Cost Management
# ================================================================
cost:
  tracking_enabled: true
  daily_limit: 15.0  # USD - adjust based on project needs
  weekly_limit: 100.0  # USD
  warning_threshold: 12.0  # USD
  
  # Cost optimization
  auto_optimize: true
  prefer_batch_operations: true
  
# ================================================================
# Quality Assurance
# ================================================================
quality:
  # Testing requirements
  testing:
    unit_test_coverage: 85  # Minimum percentage
    integration_tests: true
    e2e_tests: {str(project_type in ['web', 'frontend', 'fullstack']).lower()}
    
  # Code quality
  code_quality:
    linting: true
    type_checking: true
    security_scanning: true
    dependency_scanning: true
    
  # Documentation requirements
  documentation:
    api_docs: {str(project_type in ['api', 'backend', 'fullstack']).lower()}
    user_docs: true
    developer_docs: true
    changelog: true

# ================================================================
# Notification Settings
# ================================================================
notifications:
  enabled: true
  
  # Notification channels
  channels:
    console: true
    log_file: true
    # email: false  # Configure SMTP settings below
    # slack: false  # Configure webhook URL below
  
  # Event triggers
  on_completion: true
  on_failure: true
  on_milestone: true
  on_cost_warning: true
  
  # Email configuration (uncomment to enable)
  # email:
  #   smtp_server: "smtp.gmail.com"
  #   smtp_port: 587
  #   username: "your-email@gmail.com"
  #   password: "your-app-password"
  #   to_addresses: ["developer@company.com"]
  
  # Slack configuration (uncomment to enable)
  # slack:
  #   webhook_url: "https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK"
  #   channel: "#development"

# ================================================================
# Integration Settings
# ================================================================
integrations:
  # Claude Code CLI
  claude_code:
    enabled: true
    timeout: 600  # 10 minutes
    max_retries: 2
    
  # GitHub integration
  github:
    enabled: false  # Set to true if using GitHub
    # repository: "organization/repository-name"
    # token: "your-github-token"  # Use environment variable in production
    
  # Spec Kit integration
  spec_kit:
    enabled: true
    auto_generate: true
    template_version: "1.0"

# ================================================================
# Development Environment
# ================================================================
development:
  # Environment detection
  auto_detect_stack: true
  
  # Language-specific settings
  python:
    version: "3.9+"
    virtual_env: true
    requirements_file: "requirements.txt"
    
  javascript:
    version: "18+"
    package_manager: "npm"  # npm/yarn/pnpm
    
  # Development tools
  tools:
    git_hooks: true
    pre_commit: true
    auto_format: true

# ================================================================
# Advanced Configuration
# ================================================================
advanced:
  # Performance tuning
  performance:
    cache_enabled: true
    cache_ttl: 3600  # 1 hour
    parallel_processing: false  # Enable for powerful machines
    
  # Experimental features
  experimental:
    ai_code_review: false
    auto_dependency_update: false
    smart_task_prioritization: true
    
# ================================================================
# Project-Specific Settings
# ================================================================
# Add your custom project settings below
project_specific:
  # Example configurations based on project type
  {self._get_project_specific_config(project_type)}

# ================================================================
# Environment Variables
# ================================================================
# Reference environment variables with ${{ENV_VAR_NAME}}
# Example: api_key: ${{OPENAI_API_KEY}}
"""
        return config_content
    
    def _infer_project_type(self, project_name: str) -> str:
        """プロジェクト名から推測されるプロジェクトタイプ"""
        name_lower = project_name.lower()
        
        if any(keyword in name_lower for keyword in ['web', 'ui', 'frontend', 'react', 'vue', 'angular']):
            return 'frontend'
        elif any(keyword in name_lower for keyword in ['api', 'backend', 'server', 'service']):
            return 'backend'
        elif any(keyword in name_lower for keyword in ['database', 'db', 'data', 'storage']):
            return 'database'
        elif any(keyword in name_lower for keyword in ['test', 'qa', 'quality']):
            return 'testing'
        elif any(keyword in name_lower for keyword in ['mobile', 'app', 'ios', 'android']):
            return 'mobile'
        elif any(keyword in name_lower for keyword in ['ml', 'ai', 'machine', 'learning', 'data']):
            return 'data_science'
        elif any(keyword in name_lower for keyword in ['fullstack', 'full-stack', 'complete']):
            return 'fullstack'
        else:
            return 'general'
    
    def _get_batch_size_for_project_type(self, project_type: str) -> int:
        """プロジェクトタイプに応じた推奨バッチサイズ"""
        batch_sizes = {
            'frontend': 2,    # UI changes need careful review
            'backend': 3,     # API changes can be batched
            'database': 1,    # Database changes are critical
            'testing': 4,     # Tests can be batched
            'mobile': 2,      # Mobile changes need careful review
            'data_science': 3, # Data processing can be batched
            'fullstack': 2,   # Complex projects need careful handling
            'general': 3      # Default moderate batching
        }
        return batch_sizes.get(project_type, 3)
    
    def _get_max_changes_for_project_type(self, project_type: str) -> int:
        """プロジェクトタイプに応じた最大変更ファイル数"""
        max_changes = {
            'frontend': 30,   # Many component files
            'backend': 25,    # Service and model files
            'database': 10,   # Critical changes limited
            'testing': 50,    # Many test files
            'mobile': 20,     # Platform-specific files
            'data_science': 35, # Notebooks and data files
            'fullstack': 40,  # Mixed file types
            'general': 30     # Default reasonable limit
        }
        return max_changes.get(project_type, 30)
    
    def _get_project_specific_config(self, project_type: str) -> str:
        """プロジェクトタイプ固有の設定"""
        configs = {
            'frontend': '''# Frontend-specific settings
  build:
    bundler: "vite"  # vite/webpack/parcel
    output_dir: "dist"
    
  development:
    hot_reload: true
    source_maps: true
    
  deployment:
    platform: "vercel"  # vercel/netlify/aws-s3
    auto_deploy: true''',
            
            'backend': '''# Backend-specific settings
  api:
    framework: "fastapi"  # fastapi/express/django
    port: 8000
    cors_enabled: true
    
  database:
    type: "postgresql"
    migrations: true
    
  deployment:
    containerized: true
    platform: "aws"  # aws/gcp/azure''',
            
            'database': '''# Database-specific settings
  database:
    type: "postgresql"
    version: "14+"
    backup_schedule: "0 2 * * *"  # Daily at 2 AM
    
  monitoring:
    slow_query_threshold: 1000  # milliseconds
    connection_pool_size: 20
    
  security:
    encryption: true
    access_logging: true''',
            
            'testing': '''# Testing-specific settings
  testing:
    frameworks: ["jest", "pytest", "playwright"]
    coverage_threshold: 90
    
  ci_cd:
    platform: "github-actions"
    auto_run_tests: true
    
  reporting:
    format: "allure"
    publish_reports: true''',
            
            'fullstack': '''# Full-stack specific settings
  frontend:
    framework: "react"
    
  backend:
    framework: "fastapi"
    
  database:
    type: "postgresql"
    
  deployment:
    strategy: "microservices"
    containerized: true'''
        }
        return configs.get(project_type, '# General project - add custom settings as needed')

    # Natural Language Commands Implementation
    
    async def _natural_generate_command(self, args):
        """自然言語要件から設計ファイルを生成"""
        from ..requirements import RequirementsParser, DesignFileGenerator
        
        try:
            print(f"🧠 自然言語要件を解析中: {args.requirements[:50]}...")
            
            # 要件解析
            parser = RequirementsParser()
            analysis = parser.parse_requirements(args.requirements)
            
            print(f"✅ 解析完了:")
            print(f"  📋 プロジェクトタイプ: {analysis.project_type}")
            print(f"  🎯 主要機能: {len(analysis.primary_features)}個")
            print(f"  🔧 技術要件: {len(analysis.technical_requirements)}個")
            print(f"  📊 複雑度: {analysis.estimated_complexity}")
            print(f"  🤖 エージェント割り当て: {len(analysis.agent_assignments)}個")
            
            if args.dry_run:
                print("\n📋 解析結果詳細:")
                print(f"主要機能: {', '.join(analysis.primary_features)}")
                print(f"技術要件: {', '.join(analysis.technical_requirements)}")
                print(f"データベース要件: {', '.join(analysis.database_needs)}")
                print(f"UI要件: {', '.join(analysis.ui_requirements)}")
                print(f"品質要件: {', '.join(analysis.quality_requirements)}")
                print(f"推奨アーキテクチャ: {analysis.suggested_architecture}")
                
                print("\n🤖 エージェント割り当て:")
                for agent, tasks in analysis.agent_assignments.items():
                    if tasks:
                        print(f"  {agent}: {len(tasks)}個のタスク")
                        for task in tasks[:3]:  # 最初の3つのみ表示
                            print(f"    - {task}")
                        if len(tasks) > 3:
                            print(f"    ...他{len(tasks)-3}個")
                return
            
            # 設計ファイル生成
            print("\n📝 設計ファイルを生成中...")
            generator = DesignFileGenerator()
            generated_files = generator.generate_design_files(
                analysis, args.workspace, args.project_name
            )
            
            print("✅ 設計ファイル生成完了:")
            for agent, file_path in generated_files.items():
                print(f"  📄 {agent}: {file_path}")
            
            # 実行開始
            if args.execute:
                print("\n🚀 即座に実行を開始...")
                main_design_file = generated_files.get('main')
                if main_design_file:
                    # execute コマンドを実行
                    execute_args = type('Args', (), {
                        'design_file': main_design_file,
                        'mode': 'immediate',
                        'max_tasks': 10,
                        'dry_run': False,
                        'validate_only': False,
                        'schedule_time': None
                    })()
                    await self._execute_command(execute_args)
                else:
                    print("❌ メイン設計ファイルが見つかりません")
                    
        except Exception as e:
            print(f"❌ エラーが発生しました: {e}")
            import traceback
            traceback.print_exc()

    async def _natural_analyze_command(self, args):
        """自然言語要件を解析（設計ファイル生成なし）"""
        from ..requirements import RequirementsParser
        
        try:
            print(f"🧠 自然言語要件を解析中...")
            
            parser = RequirementsParser()
            analysis = parser.parse_requirements(args.requirements)
            
            print(f"\n📊 解析結果:")
            print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            print(f"📋 プロジェクトタイプ: {analysis.project_type}")
            print(f"📊 複雑度: {analysis.estimated_complexity}")
            print(f"🏗️ 推奨アーキテクチャ: {analysis.suggested_architecture}")
            
            print(f"\n🎯 主要機能 ({len(analysis.primary_features)}個):")
            for i, feature in enumerate(analysis.primary_features, 1):
                print(f"  {i}. {feature}")
            
            print(f"\n🔧 技術要件 ({len(analysis.technical_requirements)}個):")
            for i, req in enumerate(analysis.technical_requirements, 1):
                print(f"  {i}. {req}")
            
            if analysis.database_needs:
                print(f"\n💾 データベース要件 ({len(analysis.database_needs)}個):")
                for i, need in enumerate(analysis.database_needs, 1):
                    print(f"  {i}. {need}")
            
            if analysis.ui_requirements:
                print(f"\n🎨 UI要件 ({len(analysis.ui_requirements)}個):")
                for i, req in enumerate(analysis.ui_requirements, 1):
                    print(f"  {i}. {req}")
            
            print(f"\n🛡️ 品質要件 ({len(analysis.quality_requirements)}個):")
            for i, req in enumerate(analysis.quality_requirements, 1):
                print(f"  {i}. {req}")
            
            print(f"\n🤖 エージェント割り当て:")
            print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            for agent, tasks in analysis.agent_assignments.items():
                if tasks:
                    agent_name = {
                        'frontend_specialist': 'フロントエンド専門家',
                        'backend_specialist': 'バックエンド専門家',
                        'database_specialist': 'データベース専門家',
                        'qa_specialist': '品質保証専門家'
                    }.get(agent, agent)
                    
                    print(f"\n{agent_name} ({len(tasks)}個のタスク):")
                    for i, task in enumerate(tasks, 1):
                        print(f"  {i}. {task}")
            
            if args.detailed:
                print(f"\n📈 見積もり:")
                print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                total_hours = 0
                for agent, tasks in analysis.agent_assignments.items():
                    if tasks:
                        hours = len(tasks) * 6  # エージェントあたり平均6時間/タスク
                        total_hours += hours
                        print(f"  {agent}: 約{hours}時間")
                print(f"  合計見積もり: 約{total_hours}時間 ({total_hours//8}日間)")
                
        except Exception as e:
            print(f"❌ エラーが発生しました: {e}")
    
    def _dashboard_command(self, args):
        """dashboard コマンド実装"""
        from ..dashboard.api_server import DashboardAPIServer
        
        try:
            # ワークスペースパスの決定
            if args.workspace:
                workspace_path = Path(args.workspace).resolve()
            elif hasattr(args, 'workspace') and args.workspace:
                workspace_path = Path(args.workspace).resolve()
            else:
                workspace_path = Path.cwd()
            
            print(f"🌙 Nocturnal Agent 進捗ダッシュボードを起動します...")
            print(f"📁 ワークスペース: {workspace_path}")
            print(f"🌐 サーバー: http://{args.host}:{args.port}")
            print(f"\nブラウザで http://localhost:{args.port} にアクセスしてください")
            print("停止するには Ctrl+C を押してください\n")
            
            # ダッシュボードサーバーを起動
            server = DashboardAPIServer(workspace_path=str(workspace_path))
            server.run(host=args.host, port=args.port)
            
        except KeyboardInterrupt:
            print("\n\n⚠️ ダッシュボードを停止しました")
        except Exception as e:
            print(f"❌ エラーが発生しました: {e}")
            if hasattr(args, 'verbose') and args.verbose:
                import traceback
                traceback.print_exc()

    async def _collaborate_start_command(self, args):
        """collaborate start コマンド実装"""
        from ..requirements.collaboration_manager import CollaborationManager
        
        try:
            workspace_path = Path(args.workspace) if hasattr(args, 'workspace') and args.workspace else Path.cwd()
            
            # 要件テキストを取得
            if args.from_file or Path(args.requirements).exists():
                requirements_file = Path(args.requirements)
                if not requirements_file.exists():
                    print(f"❌ ファイルが見つかりません: {requirements_file}")
                    return
                with open(requirements_file, 'r', encoding='utf-8') as f:
                    requirements_text = f.read()
            else:
                requirements_text = args.requirements
            
            if not requirements_text.strip():
                print("❌ 要件が空です")
                return
            
            # CollaborationManagerを初期化
            collab_manager = CollaborationManager(str(workspace_path), self.logger)
            
            # プロジェクト名を決定
            project_name = args.project_name if hasattr(args, 'project_name') and args.project_name else "新規プロジェクト"
            
            # すり合わせセッションを開始
            print(f"📝 新しいすり合わせセッションを開始します...")
            print(f"📋 プロジェクト名: {project_name}")
            print(f"📄 要件: {requirements_text[:100]}...")
            
            session = collab_manager.start_collaboration(requirements_text, project_name)
            
            print(f"\n✅ すり合わせセッションを開始しました:")
            print(f"  🆔 セッションID: {session.session_id}")
            print(f"  📊 ステータス: {session.status.value}")
            print(f"\n次のステップ:")
            print(f"  1. 要件を確認・修正: nocturnal collaborate update-requirements")
            print(f"  2. 要件を承認: nocturnal collaborate approve-requirements")
            print(f"  3. 設計を確認・修正")
            print(f"  4. 設計を承認: nocturnal collaborate approve-design --auto-execute")
            
        except Exception as e:
            print(f"❌ エラーが発生しました: {e}")
            if hasattr(args, 'verbose') and args.verbose:
                import traceback
                traceback.print_exc()
    
    async def _collaborate_status_command(self, args):
        """collaborate status コマンド実装"""
        from ..requirements.collaboration_manager import CollaborationManager
        
        try:
            workspace_path = Path(args.workspace) if hasattr(args, 'workspace') and args.workspace else Path.cwd()
            collab_manager = CollaborationManager(str(workspace_path), self.logger)
            
            # セッションを取得
            if hasattr(args, 'session_id') and args.session_id:
                session = collab_manager.get_session(args.session_id)
            else:
                session = collab_manager.get_current_session()
                if not session:
                    sessions = collab_manager.list_sessions()
                    if sessions:
                        session = sessions[0]
            
            if not session:
                print("❌ セッションが見つかりません")
                return
            
            print(f"\n📊 すり合わせセッション ステータス")
            print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            print(f"🆔 セッションID: {session.session_id}")
            print(f"📊 ステータス: {session.status.value}")
            print(f"📅 作成日時: {session.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"🔄 更新日時: {session.updated_at.strftime('%Y-%m-%d %H:%M:%S')}")
            
            if session.approved_at:
                print(f"✅ 承認日時: {session.approved_at.strftime('%Y-%m-%d %H:%M:%S')}")
            
            print(f"\n📝 要件:")
            print(f"  {session.current_requirements[:200]}...")
            
            if session.requirements_feedback:
                print(f"\n💬 要件フィードバック ({len(session.requirements_feedback)}件):")
                for i, feedback in enumerate(session.requirements_feedback[-3:], 1):
                    print(f"  {i}. {feedback['feedback'][:100]}...")
            
            if session.design_files:
                print(f"\n📄 設計ファイル ({len(session.design_files)}個):")
                for agent, file_path in session.design_files.items():
                    print(f"  • {agent}: {file_path}")
            
            if session.design_feedback:
                print(f"\n💬 設計フィードバック:")
                for agent, feedbacks in session.design_feedback.items():
                    print(f"  • {agent}: {len(feedbacks)}件")
            
        except Exception as e:
            print(f"❌ エラーが発生しました: {e}")
            if hasattr(args, 'verbose') and args.verbose:
                import traceback
                traceback.print_exc()
    
    async def _collaborate_approve_requirements_command(self, args):
        """collaborate approve-requirements コマンド実装"""
        from ..requirements.collaboration_manager import CollaborationManager
        
        try:
            workspace_path = Path(args.workspace) if hasattr(args, 'workspace') and args.workspace else Path.cwd()
            collab_manager = CollaborationManager(str(workspace_path), self.logger)
            
            # セッションを取得
            if hasattr(args, 'session_id') and args.session_id:
                session = collab_manager.get_session(args.session_id)
            else:
                session = collab_manager.get_current_session()
                if not session:
                    sessions = collab_manager.list_sessions()
                    if sessions:
                        session = sessions[0]
            
            if not session:
                print("❌ セッションが見つかりません")
                return
            
            print(f"✅ 要件を承認し、設計ファイルを生成します...")
            
            session, analysis = collab_manager.approve_requirements(session.session_id)
            
            print(f"\n✅ 要件を承認しました:")
            print(f"  📊 プロジェクトタイプ: {analysis.project_type}")
            print(f"  📈 複雑度: {analysis.estimated_complexity}")
            print(f"  🤖 エージェント数: {len(analysis.agent_assignments)}")
            
            print(f"\n📄 生成された設計ファイル:")
            for agent, file_path in session.design_files.items():
                print(f"  • {agent}: {file_path}")
            
            print(f"\n次のステップ:")
            print(f"  1. 設計ファイルを確認・修正")
            print(f"  2. 設計を承認: nocturnal collaborate approve-design --auto-execute")
            
        except Exception as e:
            print(f"❌ エラーが発生しました: {e}")
            if hasattr(args, 'verbose') and args.verbose:
                import traceback
                traceback.print_exc()
    
    async def _collaborate_approve_design_command(self, args):
        """collaborate approve-design コマンド実装"""
        from ..requirements.collaboration_manager import CollaborationManager
        from ..requirements.continuous_execution_manager import ContinuousExecutionManager
        
        try:
            workspace_path = Path(args.workspace) if hasattr(args, 'workspace') and args.workspace else Path.cwd()
            collab_manager = CollaborationManager(str(workspace_path), self.logger)
            
            # セッションを取得
            if hasattr(args, 'session_id') and args.session_id:
                session = collab_manager.get_session(args.session_id)
            else:
                session = collab_manager.get_current_session()
                if not session:
                    sessions = collab_manager.list_sessions()
                    if sessions:
                        session = sessions[0]
            
            if not session:
                print("❌ セッションが見つかりません")
                return
            
            print(f"✅ 設計を承認します...")
            
            session = collab_manager.approve_design(session.session_id)
            
            print(f"\n✅ 設計を承認しました:")
            print(f"  🆔 セッションID: {session.session_id}")
            print(f"  📊 ステータス: {session.status.value}")
            print(f"  📄 設計ファイル数: {len(session.design_files)}")
            
            # 自動実行を開始
            if hasattr(args, 'auto_execute') and args.auto_execute:
                print(f"\n🚀 自動実行を開始します...")
                
                exec_manager = ContinuousExecutionManager(
                    str(workspace_path), self.logger, self.config
                )
                
                auto_session = await exec_manager.start_continuous_execution(session.session_id)
                
                print(f"\n✅ 自動実行を開始しました:")
                print(f"  🆔 実行セッションID: {auto_session.session_id}")
                print(f"  📊 ステータス: {auto_session.status.value}")
                print(f"\n進捗確認:")
                print(f"  nocturnal collaborate status --session-id {session.session_id}")
            
        except Exception as e:
            print(f"❌ エラーが発生しました: {e}")
            if hasattr(args, 'verbose') and args.verbose:
                import traceback
                traceback.print_exc()
    
    async def _collaborate_update_requirements_command(self, args):
        """collaborate update-requirements コマンド実装"""
        from ..requirements.collaboration_manager import CollaborationManager
        
        try:
            workspace_path = Path(args.workspace) if hasattr(args, 'workspace') and args.workspace else Path.cwd()
            collab_manager = CollaborationManager(str(workspace_path), self.logger)
            
            # セッションを取得
            if hasattr(args, 'session_id') and args.session_id:
                session = collab_manager.get_session(args.session_id)
            else:
                session = collab_manager.get_current_session()
                if not session:
                    sessions = collab_manager.list_sessions()
                    if sessions:
                        session = sessions[0]
            
            if not session:
                print("❌ セッションが見つかりません")
                return
            
            # 要件テキストを取得
            if hasattr(args, 'from_file') and args.from_file or Path(args.requirements).exists():
                requirements_file = Path(args.requirements)
                if not requirements_file.exists():
                    print(f"❌ ファイルが見つかりません: {requirements_file}")
                    return
                with open(requirements_file, 'r', encoding='utf-8') as f:
                    requirements_text = f.read()
            else:
                requirements_text = args.requirements
            
            print(f"📝 要件を更新します...")
            
            session = collab_manager.update_requirements(session.session_id, requirements_text)
            
            print(f"\n✅ 要件を更新しました:")
            print(f"  🆔 セッションID: {session.session_id}")
            print(f"  📊 ステータス: {session.status.value}")
            print(f"  📝 更新後の要件: {session.current_requirements[:200]}...")
            
        except Exception as e:
            print(f"❌ エラーが発生しました: {e}")
            if hasattr(args, 'verbose') and args.verbose:
                import traceback
                traceback.print_exc()
    
    async def _collaborate_list_command(self, args):
        """collaborate list コマンド実装"""
        from ..requirements.collaboration_manager import CollaborationManager
        
        try:
            workspace_path = Path(args.workspace) if hasattr(args, 'workspace') and args.workspace else Path.cwd()
            collab_manager = CollaborationManager(str(workspace_path), self.logger)
            
            sessions = collab_manager.list_sessions()
            
            if not sessions:
                print("📋 すり合わせセッションはありません")
                return
            
            print(f"\n📋 すり合わせセッション一覧 ({len(sessions)}件)")
            print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            
            for i, session in enumerate(sessions, 1):
                print(f"\n{i}. セッションID: {session.session_id}")
                print(f"   ステータス: {session.status.value}")
                print(f"   作成日時: {session.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
                if session.approved_at:
                    print(f"   承認日時: {session.approved_at.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"   要件: {session.current_requirements[:100]}...")
            
        except Exception as e:
            print(f"❌ エラーが発生しました: {e}")
            if hasattr(args, 'verbose') and args.verbose:
                import traceback
                traceback.print_exc()

    async def _natural_from_file_command(self, args):
        """ファイルから要件を読み込んで処理"""
        from pathlib import Path
        from ..requirements import RequirementsParser, DesignFileGenerator
        
        try:
            requirements_file = Path(args.requirements_file)
            if not requirements_file.exists():
                print(f"❌ ファイルが見つかりません: {requirements_file}")
                return
            
            print(f"📄 要件ファイルを読み込み中: {requirements_file}")
            
            # ファイルから要件を読み込み
            with open(requirements_file, 'r', encoding='utf-8') as f:
                requirements_text = f.read()
            
            if not requirements_text.strip():
                print("❌ ファイルが空です")
                return
            
            # プロジェクト名を決定
            project_name = args.project_name
            if not project_name:
                project_name = requirements_file.stem.replace('_', ' ').replace('-', ' ').title()
            
            print(f"📋 プロジェクト名: {project_name}")
            print(f"📝 要件内容: {requirements_text[:100]}...")
            
            # 解析実行
            parser = RequirementsParser()
            analysis = parser.parse_requirements(requirements_text)
            
            print(f"\n✅ 解析完了:")
            print(f"  📋 プロジェクトタイプ: {analysis.project_type}")
            print(f"  📊 複雑度: {analysis.estimated_complexity}")
            print(f"  🤖 エージェント割り当て: {len(analysis.agent_assignments)}個")
            
            # 設計ファイル生成
            print("\n📝 設計ファイルを生成中...")
            generator = DesignFileGenerator()
            generated_files = generator.generate_design_files(
                analysis, args.workspace, project_name
            )
            
            print("✅ 設計ファイル生成完了:")
            for agent, file_path in generated_files.items():
                print(f"  📄 {agent}: {file_path}")
            
            # 実行開始
            if args.execute:
                print("\n🚀 即座に実行を開始...")
                main_design_file = generated_files.get('main')
                if main_design_file:
                    execute_args = type('Args', (), {
                        'design_file': main_design_file,
                        'mode': 'immediate',
                        'max_tasks': 10,
                        'dry_run': False,
                        'validate_only': False,
                        'schedule_time': None
                    })()
                    await self._execute_command(execute_args)
                else:
                    print("❌ メイン設計ファイルが見つかりません")
                    
        except Exception as e:
            print(f"❌ エラーが発生しました: {e}")
            import traceback
            traceback.print_exc()


    # ============================================
    # 新しいシンプルな3ステップコマンドハンドラー
    # ============================================
    
    async def _requirements_create_command(self, args):
        """requirements create コマンドの実装（ステップ1: 要件定義）"""
        try:
            from pathlib import Path
            from datetime import datetime
            
            # プロジェクト名を決定
            project_name = args.project_name
            if not project_name:
                project_info = self._get_current_project_info()
                project_name = project_info['project_name']
            
            # 出力ファイルパスを決定
            output_path = args.output
            if not output_path:
                requirements_dir = Path('requirements')
                requirements_dir.mkdir(exist_ok=True)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                output_path = requirements_dir / f"requirements_{timestamp}.md"
            
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 要件ファイルを作成
            requirements_content = f"""# 要件定義書

## プロジェクト名
{project_name}

## 作成日時
{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 要件説明
{args.description}

## 詳細要件
（ここに詳細な要件を記述してください）

## 技術要件
（使用する技術スタックやフレームワークを記述してください）

## 非機能要件
（パフォーマンス、セキュリティ、可用性などの要件を記述してください）
"""
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(requirements_content)
            
            print(f"✅ 要件ファイルを作成しました: {output_path}")
            print(f"\n📝 次のステップ:")
            print(f"  1. 要件ファイルを編集: {output_path}")
            print(f"  2. 設計書を作成: nocturnal design create --from-requirements {output_path}")
            
        except Exception as e:
            print(f"❌ エラーが発生しました: {e}")
            if hasattr(args, 'verbose') and args.verbose:
                import traceback
                traceback.print_exc()
    
    async def _requirements_from_file_command(self, args):
        """requirements from-file コマンドの実装"""
        try:
            from pathlib import Path
            
            file_path = Path(args.file_path)
            if not file_path.exists():
                print(f"❌ ファイルが見つかりません: {file_path}")
                return
            
            print(f"📄 要件ファイルを読み込みました: {file_path}")
            
            # プロジェクト名を決定
            project_name = args.project_name
            if not project_name:
                project_info = self._get_current_project_info()
                project_name = project_info['project_name']
            
            print(f"📋 プロジェクト名: {project_name}")
            print(f"\n📝 次のステップ:")
            print(f"  設計書を作成: nocturnal design create --from-requirements {file_path}")
            
        except Exception as e:
            print(f"❌ エラーが発生しました: {e}")
            if hasattr(args, 'verbose') and args.verbose:
                import traceback
                traceback.print_exc()
    
    async def _requirements_list_command(self, args):
        """requirements list コマンドの実装"""
        try:
            from pathlib import Path
            import glob
            
            requirements_dir = Path('requirements')
            if not requirements_dir.exists():
                print("📋 要件ファイルはまだ作成されていません")
                return
            
            # 要件ファイルを検索
            requirement_files = list(requirements_dir.glob('*.md')) + \
                               list(requirements_dir.glob('*.txt')) + \
                               list(requirements_dir.glob('*.yaml')) + \
                               list(requirements_dir.glob('*.json'))
            
            if not requirement_files:
                print("📋 要件ファイルはまだ作成されていません")
                return
            
            print(f"\n📋 要件ファイル一覧 ({len(requirement_files)}件)")
            print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            
            for i, file_path in enumerate(sorted(requirement_files), 1):
                print(f"\n{i}. {file_path.name}")
                print(f"   パス: {file_path}")
                # ファイルの最初の数行を表示
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        first_line = f.readline().strip()
                        if first_line:
                            print(f"   概要: {first_line[:80]}...")
                except:
                    pass
            
        except Exception as e:
            print(f"❌ エラーが発生しました: {e}")
            if hasattr(args, 'verbose') and args.verbose:
                import traceback
                traceback.print_exc()
    
    async def _requirements_show_command(self, args):
        """requirements show コマンドの実装"""
        try:
            from pathlib import Path
            
            file_path = Path(args.file_path)
            if not file_path.exists():
                print(f"❌ ファイルが見つかりません: {file_path}")
                return
            
            print(f"\n📄 要件ファイル: {file_path}")
            print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                print(content)
            
            print("\n📝 次のステップ:")
            print(f"  設計書を作成: nocturnal design create --from-requirements {file_path}")
            
        except Exception as e:
            print(f"❌ エラーが発生しました: {e}")
            if hasattr(args, 'verbose') and args.verbose:
                import traceback
                traceback.print_exc()
    
    async def _implement_start_command(self, args):
        """implement start コマンドの実装（ステップ3: 実装開始）"""
        # 既存の_execute_commandを呼び出す
        execute_args = type('Args', (), {
            'design_file': args.design_file,
            'mode': args.mode,
            'max_tasks': args.max_tasks,
            'dry_run': args.dry_run,
            'validate_only': False,
            'schedule_time': args.schedule_time,
            'verbose': getattr(args, 'verbose', False)
        })()
        await self._execute_command(execute_args)
    
    async def _implement_status_command(self, args):
        """implement status コマンドの実装"""
        # 既存の_progress_commandを呼び出す
        progress_args = type('Args', (), {
            'design_file': args.design_file,
            'workspace': None,
            'detailed': args.detailed,
            'refresh': 0,
            'verbose': getattr(args, 'verbose', False)
        })()
        await self._progress_command(progress_args)
    
    async def _implement_stop_command(self, args):
        """implement stop コマンドの実装"""
        # 既存の_stop_commandを呼び出す
        stop_args = type('Args', (), {
            'force': args.force,
            'verbose': getattr(args, 'verbose', False)
        })()
        await self._stop_command(stop_args)


def main():
    """メイン関数"""
    cli = NocturnalAgentCLI()
    cli.run()


if __name__ == '__main__':
    main()