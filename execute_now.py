#!/usr/bin/env python3
"""
スケジュールされたタスクを即座に実行するスクリプト
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta

# プロジェクトのパスを追加
sys.path.append(str(Path(__file__).parent / "src"))

async def execute_scheduled_tasks_now():
    """スケジュールされたタスクを即座に実行"""
    print("🚀 スケジュールされたタスクの即座実行を開始...")
    print("=" * 60)
    
    try:
        # 必要なクラスをインポート
        from nocturnal_agent.execution.spec_driven_executor import InteractiveReviewManager
        from nocturnal_agent.log_system.structured_logger import StructuredLogger
        from nocturnal_agent.core.config import load_config
        
        # 設定を読み込み
        config_path = "/Users/tsutomusaito/git/nocturnal-agent/config/nocturnal_config.yaml"
        config = load_config(config_path)
        
        # StructuredLogger用の設定を辞書形式で作成
        logging_config = {
            'output_path': './logs',
            'retention_days': 30,
            'max_file_size_mb': 100,
            'console_output': True,
            'file_output': True,
            'level': 'INFO'
        }
        
        # StructuredLoggerを初期化
        logger = StructuredLogger(logging_config)
        
        # ai-news-digプロジェクトでInteractiveReviewManagerを初期化
        workspace_path = "/Users/tsutomusaito/git/ai-news-dig"
        review_manager = InteractiveReviewManager(workspace_path, logger)
        
        print(f"✅ InteractiveReviewManager初期化完了")
        print(f"📁 作業ディレクトリ: {workspace_path}")
        print(f"📅 スケジュールタスク数: {len(review_manager.scheduled_tasks)}")
        
        # 全てのスケジュールされたタスクの実行時刻を現在時刻に更新
        now = datetime.now()
        updated_count = 0
        
        for task in review_manager.scheduled_tasks:
            if task.get('status') == 'SCHEDULED':
                # 実行時刻を現在時刻に更新
                task['scheduled_for'] = now.isoformat()
                updated_count += 1
                print(f"📝 タスク更新: {task.get('review_id')} -> {now.isoformat()}")
        
        if updated_count > 0:
            # 更新されたスケジュールを保存
            review_manager._save_scheduled_tasks()
            print(f"💾 {updated_count}個のタスクの実行時刻を更新しました")
        
        # スケジュールされたタスクを即座に実行
        print(f"\n🎯 スケジュールされたタスクの実行開始...")
        await review_manager.execute_scheduled_tasks()
        
        print(f"\n✅ 全タスク実行完了")
        
        # 実行後の状態確認
        print(f"\n📊 実行後状態:")
        for task in review_manager.scheduled_tasks:
            status = task.get('status', 'Unknown')
            review_id = task.get('review_id', 'Unknown')
            
            # タスクの説明を安全に取得
            task_info = task.get('task', {})
            if isinstance(task_info, dict):
                description = task_info.get('description', 'Unknown')[:50]
            else:
                description = getattr(task_info, 'description', 'Unknown')[:50]
            
            print(f"  🎯 {review_id}: {status} - {description}...")
    
    except Exception as e:
        print(f"❌ 実行エラー: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"\n🎉 スケジュールタスク即座実行完了")

if __name__ == "__main__":
    asyncio.run(execute_scheduled_tasks_now())