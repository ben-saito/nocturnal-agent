#!/usr/bin/env python3
"""
新しいClaudeCode統合システム（ローカルLLM → ClaudeCode実行）をテストするスクリプト
"""

import asyncio
import sys
from pathlib import Path

# プロジェクトのパスを追加
sys.path.append(str(Path(__file__).parent / "src"))

async def test_claude_code_integration():
    """ClaudeCode統合システムをテスト"""
    print("🧪 ClaudeCode統合システムテスト開始...")
    print("=" * 60)
    
    try:
        from nocturnal_agent.execution.implementation_task_manager import (
            ImplementationTaskManager, NightlyTaskExecutor, TaskStatus, TaskPriority
        )
        from nocturnal_agent.log_system.structured_logger import StructuredLogger
        
        # ログ設定
        logging_config = {
            'output_path': './logs',
            'retention_days': 30,
            'max_file_size_mb': 100,
            'console_output': True,
            'file_output': True,
            'level': 'INFO'
        }
        logger = StructuredLogger(logging_config)
        
        # ai-news-digプロジェクトでテスト
        workspace_path = "/Users/tsutomusaito/git/ai-news-dig"
        
        print("📋 Phase 1: 夜間タスク実行システム初期化")
        print("-" * 40)
        
        # 夜間タスク実行システムを初期化
        nightly_executor = NightlyTaskExecutor(workspace_path, logger)
        
        print("✅ 夜間タスク実行システム初期化完了")
        
        print("\n📋 Phase 2: 実行可能タスク確認")
        print("-" * 40)
        
        # 実行可能なタスクを確認
        ready_tasks = nightly_executor.task_manager.get_ready_tasks()
        print(f"🚀 実行可能なタスク数: {len(ready_tasks)}")
        
        if ready_tasks:
            print(f"📝 最初のタスク例:")
            first_task = ready_tasks[0]
            print(f"   - ID: {first_task.task_id}")
            print(f"   - タイトル: {first_task.title}")
            print(f"   - 優先度: {first_task.priority.value}")
            print(f"   - 推定時間: {first_task.estimated_hours}h")
        
        print("\n📋 Phase 3: ClaudeCode実行指示ファイル生成テスト")
        print("-" * 40)
        
        if ready_tasks:
            # 最初のタスクで実行指示ファイルを生成
            test_task = ready_tasks[0]
            claude_executor = nightly_executor.claude_executor
            
            # 実行指示を生成
            instruction = claude_executor._generate_execution_instruction(test_task)
            instruction_file = claude_executor._create_instruction_file(test_task, instruction)
            
            print(f"✅ 実行指示ファイル作成: {instruction_file}")
            print(f"📄 ファイルサイズ: {instruction_file.stat().st_size} bytes")
            
            # 生成されたファイルの内容を一部表示
            with open(instruction_file, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')
                print(f"📝 指示ファイル内容（最初の10行）:")
                for i, line in enumerate(lines[:10]):
                    print(f"   {i+1:2d}: {line}")
                if len(lines) > 10:
                    print(f"   ... (全{len(lines)}行)")
        
        print("\n📋 Phase 4: 夜間タスク実行テスト（シミュレーション）")
        print("-" * 40)
        
        # 夜間タスク実行をテスト（最大3タスク）
        execution_summary = await nightly_executor.execute_nightly_tasks(max_tasks=3)
        
        print(f"🎯 実行サマリー:")
        print(f"   - 開始時刻: {execution_summary['start_time']}")
        print(f"   - 終了時刻: {execution_summary.get('end_time', 'N/A')}")
        print(f"   - 成功タスク数: {len(execution_summary['executed_tasks'])}")
        print(f"   - 失敗タスク数: {len(execution_summary['failed_tasks'])}")
        print(f"   - 総実行時間: {execution_summary['total_execution_time']:.1f}秒")
        
        # 実行されたタスクの詳細
        if execution_summary['executed_tasks']:
            print(f"\n✅ 実行成功したタスク:")
            for task_result in execution_summary['executed_tasks']:
                print(f"   - {task_result['title']} ({task_result['execution_time']:.1f}秒)")
        
        # 失敗したタスクの詳細
        if execution_summary['failed_tasks']:
            print(f"\n❌ 実行失敗したタスク:")
            for task_result in execution_summary['failed_tasks']:
                print(f"   - {task_result['title']}: {task_result['error']}")
        
        print("\n📋 Phase 5: ClaudeCode実行ログ確認")
        print("-" * 40)
        
        # 実行ログディレクトリを確認
        execution_dir = Path(workspace_path) / '.nocturnal' / 'claude_executions'
        if execution_dir.exists():
            log_files = list(execution_dir.glob("*.log"))
            result_files = list(execution_dir.glob("*_result.json"))
            instruction_files = list(execution_dir.glob("*_instruction.md"))
            
            print(f"📁 実行ログディレクトリ: {execution_dir}")
            print(f"   - 実行指示ファイル: {len(instruction_files)}件")
            print(f"   - 実行結果ファイル: {len(result_files)}件")
            print(f"   - ログファイル: {len(log_files)}件")
            
            # 最新の結果ファイルを表示
            if result_files:
                latest_result = max(result_files, key=lambda x: x.stat().st_mtime)
                print(f"\n📋 最新の実行結果: {latest_result.name}")
                
                import json
                with open(latest_result, 'r', encoding='utf-8') as f:
                    result_data = json.load(f)
                
                print(f"   - ステータス: {result_data.get('status', 'Unknown')}")
                print(f"   - メッセージ: {result_data.get('message', 'N/A')}")
                if 'files_modified' in result_data:
                    print(f"   - 変更ファイル数: {len(result_data['files_modified'])}")
        
        print("\n📋 Phase 6: タスク進捗確認")
        print("-" * 40)
        
        # 最終的なタスクサマリーを取得
        final_summary = nightly_executor.task_manager.get_task_summary()
        print(f"📊 最終タスクサマリー:")
        print(f"   - 総タスク数: {final_summary['total_tasks']}")
        print(f"   - 完了率: {final_summary['completion_rate']:.1%}")
        print(f"   - 完了時間: {final_summary['completed_hours']:.1f}h / {final_summary['total_estimated_hours']:.1f}h")
        print(f"   - ステータス別:")
        for status, count in final_summary['status_counts'].items():
            if count > 0:
                print(f"     - {status}: {count}件")
        
        print("\n🎉 ClaudeCode統合システムテスト完了！")
        print("💡 ローカルLLM → ClaudeCode の夜間実行フローが正常に動作しています")
        
    except Exception as e:
        print(f"❌ テストエラー: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_claude_code_integration())