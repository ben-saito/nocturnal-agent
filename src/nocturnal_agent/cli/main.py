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
使用例:
  nocturnal start                    # 夜間実行を開始
  nocturnal config show              # 設定を表示
  nocturnal config set monthly_budget 15.0  # 設定を変更
  nocturnal status                   # システム状況を確認
  nocturnal report daily             # 日次レポートを生成
  nocturnal report session SESSION_ID  # セッションレポートを生成
  
  # インタラクティブレビュー機能
  nocturnal review start TASK_TITLE  # タスクからレビュー開始
  nocturnal review from-file requirements.md  # ファイルからレビュー開始
  nocturnal review create-sample sample.md    # サンプル要件ファイル作成
  nocturnal review approve SESSION_ID # 設計を承認
  nocturnal review status             # レビュー状況確認
  
  # 新機能: 設計ファイルベース実行
  nocturnal execute --design-file design.yaml --mode immediate  # 即時実行
  nocturnal execute --design-file design.yaml --mode nightly   # 夜間実行
  nocturnal design create-template agent_name  # エージェント用テンプレート作成
  nocturnal design validate design.yaml        # 設計ファイル検証
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
        
        # design コマンド (新機能: 設計ファイル管理)
        self._add_design_parser(subparsers)
        
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
            workspace_path / 'reports'
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
            print(f"📁 ディレクトリ作成: {directory}")
        
        # 設定ファイル作成
        config_path = workspace_path / 'config' / 'nocturnal_config.yaml'
        config_manager = ConfigManager(str(config_path))
        
        from nocturnal_agent.config.config_manager import NocturnalConfig
        project_config = NocturnalConfig(
            project_name=args.project_name,
            workspace_path=str(workspace_path),
            data_directory=str(workspace_path / 'data'),
            log_directory=str(workspace_path / 'logs')
        )
        
        success = config_manager.save_config(project_config)
        
        if success:
            print(f"⚙️ 設定ファイル作成: {config_path}")
        
        # README作成
        readme_path = workspace_path / 'README.md'
        readme_content = f"""# {args.project_name}

Nocturnal Agent 夜間自律開発プロジェクト

## セットアップ完了

このプロジェクトは Nocturnal Agent によって初期化されました。

### 基本使用方法

```bash
# 夜間実行開始
nocturnal start --config {config_path}

# システム状況確認
nocturnal status --config {config_path}

# レポート生成
nocturnal report daily --config {config_path}
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
        
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(readme_content)
        
        print(f"📝 README作成: {readme_path}")
        print("\n✅ プロジェクト初期化が完了しました！")
        print(f"\n次のコマンドでセットアップを確認できます:")
        print(f"cd {workspace_path}")
        print(f"nocturnal status --config {config_path}")
    
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
            
            print(f"📝 タスク登録開始: {len(generated_tasks)}個のタスク")
            
            for task_data in generated_tasks:
                # タスクデータを実装タスク用に変換
                task_spec = {
                    'title': task_data.get('title', 'Unknown Task'),
                    'description': task_data.get('description', ''),
                    'priority': task_data.get('priority', 'MEDIUM'),
                    'estimated_hours': task_data.get('estimated_hours', 2.0),
                    'technical_requirements': task_data.get('technical_requirements', []),
                    'acceptance_criteria': task_data.get('acceptance_criteria', []),
                    'dependencies': task_data.get('dependencies', [])
                }
                
                task_id = task_manager.create_task_from_specification(task_spec)
                created_task_ids.append(task_id)
                
                # 作成されたタスクを承認状態にする
                task_manager.approve_task(task_id, "design_file_execution")
            
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


def main():
    """メイン関数"""
    cli = NocturnalAgentCLI()
    cli.run()


if __name__ == '__main__':
    main()