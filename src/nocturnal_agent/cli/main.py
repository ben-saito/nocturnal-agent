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
from nocturnal_agent.logging.structured_logger import StructuredLogger, LogLevel, LogCategory
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
        
        # 実行設定の準備
        execution_config = {
            'immediate_start': args.immediate,
            'duration_minutes': args.duration,
            'task_limit': args.task_limit,
            'quality_threshold': args.quality_threshold or self.config.minimum_quality_threshold,
            'use_spec_kit': args.use_spec_kit,
            'spec_type': args.spec_type if args.use_spec_kit else None
        }
        
        # セッション開始
        session_id = await self.scheduler.start_night_session(**execution_config)
        
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
            self.cost_manager = CostManager(self.config.cost_management.__dict__)
        
        if self.safety_coordinator is None:
            self.safety_coordinator = SafetyCoordinator(workspace_path, self.config.safety.__dict__)
        
        # 各システムの状況取得
        scheduler_status = await self.scheduler.get_system_status()
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
        budget_info = cost_status['budget_overview']
        print(f"  月間予算: ${budget_info['monthly_budget']:.2f}")
        print(f"  使用額: ${budget_info['current_usage']:.4f} ({budget_info['usage_percentage']:.1f}%)")
        
        if budget_info.get('emergency_mode'):
            print("  🚨 緊急モード有効")
        print()
        
        # 安全性状況
        print("🛡️ 安全性状況")
        print(f"  システム: {'✅ 有効' if safety_status['safety_active'] else '❌ 無効'}")
        print(f"  違反数: {safety_status['safety_violations_count']}")
        print()
        
        if detailed:
            # 詳細情報
            print("📊 詳細情報")
            
            if 'statistics' in scheduler_status:
                stats = scheduler_status['statistics']
                print(f"  総セッション数: {stats.get('total_sessions', 0)}")
                print(f"  総タスク数: {stats.get('total_tasks', 0)}")
            
            service_usage = cost_status.get('service_usage', {})
            if service_usage:
                print("  サービス別使用量:")
                for service, usage in service_usage.items():
                    print(f"    {service}: ${usage:.4f}")
            
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


def main():
    """メイン関数"""
    cli = NocturnalAgentCLI()
    cli.run()


if __name__ == '__main__':
    main()