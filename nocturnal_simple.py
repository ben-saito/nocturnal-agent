#!/usr/bin/env python3
"""
Nocturnal Agent Simple CLI
ユーザーが実際にタスクを追加して実行できるシンプルなCLI
"""

import sys
import argparse
import json
from datetime import datetime
from pathlib import Path

def add_task(description: str, priority: str = "medium") -> None:
    """タスクを追加する"""
    
    # タスクディレクトリを作成
    task_dir = Path("nocturnal_tasks")
    task_dir.mkdir(exist_ok=True)
    
    # タスクファイル
    tasks_file = task_dir / "tasks.json"
    
    # 既存のタスクを読み込み
    tasks = []
    if tasks_file.exists():
        try:
            with open(tasks_file, 'r', encoding='utf-8') as f:
                tasks = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            tasks = []
    
    # 新しいタスクを作成
    task_id = len(tasks) + 1
    new_task = {
        "id": task_id,
        "description": description,
        "priority": priority,
        "status": "pending",
        "created_at": datetime.now().isoformat(),
        "estimated_quality": 0.8,
        "requirements": [
            "AI coding agent でWebを検索してデータを収集",
            "データをDBに保存",
            "Web一覧表示画面を準備", 
            "詳細表示画面を準備",
            "重複記事の除去機能",
            "出典情報の保存"
        ]
    }
    
    tasks.append(new_task)
    
    # ファイルに保存
    with open(tasks_file, 'w', encoding='utf-8') as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)
    
    print(f"✅ タスクが追加されました:")
    print(f"   ID: {task_id}")
    print(f"   内容: {description}")
    print(f"   優先度: {priority}")
    print(f"   保存場所: {tasks_file}")
    
    return task_id

def list_tasks() -> None:
    """タスク一覧を表示する"""
    tasks_file = Path("nocturnal_tasks/tasks.json")
    
    if not tasks_file.exists():
        print("📋 タスクはまだ追加されていません")
        return
    
    try:
        with open(tasks_file, 'r', encoding='utf-8') as f:
            tasks = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        print("❌ タスクファイルの読み込みに失敗しました")
        return
    
    if not tasks:
        print("📋 タスクはまだ追加されていません")
        return
    
    print(f"📋 タスク一覧 ({len(tasks)}件)")
    print("=" * 60)
    
    for task in tasks:
        status_emoji = {
            "pending": "⏳",
            "running": "🔄", 
            "completed": "✅",
            "failed": "❌"
        }.get(task["status"], "❓")
        
        priority_emoji = {
            "high": "🔴",
            "medium": "🟡",
            "low": "🟢"
        }.get(task["priority"], "⚪")
        
        print(f"{status_emoji} [{task['id']}] {task['description']}")
        print(f"   優先度: {priority_emoji} {task['priority']}")
        print(f"   作成日時: {task['created_at'][:19]}")
        print()

def run_nocturnal_task(task_id: int = None) -> None:
    """Nocturnal Agentでタスクを実行する"""
    
    print("🌙 Nocturnal Agent タスク実行を開始します...")
    
    # タスクファイルの読み込み
    tasks_file = Path("nocturnal_tasks/tasks.json")
    selected_task = None
    
    if task_id and tasks_file.exists():
        try:
            with open(tasks_file, 'r', encoding='utf-8') as f:
                tasks = json.load(f)
            
            # 指定されたタスクを検索
            for task in tasks:
                if task['id'] == task_id:
                    selected_task = task
                    break
            
            if selected_task:
                print(f"📝 実行するタスク: [{task_id}] {selected_task['description'][:50]}...")
                
                # タスクステータスを実行中に更新
                for task in tasks:
                    if task['id'] == task_id:
                        task['status'] = 'running'
                        task['started_at'] = datetime.now().isoformat()
                
                with open(tasks_file, 'w', encoding='utf-8') as f:
                    json.dump(tasks, f, ensure_ascii=False, indent=2)
                
                print("📊 タスクステータスを '実行中' に更新しました")
            else:
                print(f"❌ タスクID {task_id} が見つかりません")
                return
        except Exception as e:
            print(f"❌ タスクファイルの読み込みエラー: {e}")
            return
    
    # 実際のNocturnal Agent実行
    try:
        import subprocess
        import sys
        
        print("🚀 run_nocturnal_task.py を実行中...")
        result = subprocess.run([sys.executable, 'run_nocturnal_task.py'], 
                              capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ タスク実行が完了しました")
            print("📤 出力結果:")
            print(result.stdout)
            
            # タスクステータスを完了に更新
            if selected_task and tasks_file.exists():
                try:
                    with open(tasks_file, 'r', encoding='utf-8') as f:
                        tasks = json.load(f)
                    
                    for task in tasks:
                        if task['id'] == task_id:
                            task['status'] = 'completed'
                            task['completed_at'] = datetime.now().isoformat()
                    
                    with open(tasks_file, 'w', encoding='utf-8') as f:
                        json.dump(tasks, f, ensure_ascii=False, indent=2)
                    
                    print("📊 タスクステータスを '完了' に更新しました")
                except Exception as e:
                    print(f"⚠️ ステータス更新エラー: {e}")
        else:
            print("❌ タスク実行が失敗しました")
            print("📤 エラー出力:")
            print(result.stderr)
            
            # タスクステータスを失敗に更新
            if selected_task and tasks_file.exists():
                try:
                    with open(tasks_file, 'r', encoding='utf-8') as f:
                        tasks = json.load(f)
                    
                    for task in tasks:
                        if task['id'] == task_id:
                            task['status'] = 'failed'
                            task['failed_at'] = datetime.now().isoformat()
                    
                    with open(tasks_file, 'w', encoding='utf-8') as f:
                        json.dump(tasks, f, ensure_ascii=False, indent=2)
                    
                    print("📊 タスクステータスを '失敗' に更新しました")
                except Exception as e:
                    print(f"⚠️ ステータス更新エラー: {e}")
        
    except FileNotFoundError:
        print("❌ run_nocturnal_task.py が見つかりません")
        print("💡 以下を確認してください:")
        print("   1. 正しいプロジェクトディレクトリにいるか")
        print("   2. run_nocturnal_task.py ファイルが存在するか")
    except Exception as e:
        print(f"❌ 実行エラー: {e}")

def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(
        description="Nocturnal Agent - 夜間自律開発システム",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python nocturnal_simple.py add-task -t "AI Webスクレイピングシステム作成" -p high
  python nocturnal_simple.py list
  python nocturnal_simple.py run
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='利用可能なコマンド')
    
    # add-task コマンド
    add_parser = subparsers.add_parser('add-task', help='新しいタスクを追加')
    add_parser.add_argument('-t', '--task', required=True, help='タスクの説明')
    add_parser.add_argument('-p', '--priority', choices=['high', 'medium', 'low'], 
                          default='medium', help='タスクの優先度')
    
    # list コマンド
    list_parser = subparsers.add_parser('list', help='タスク一覧を表示')
    
    # run コマンド
    run_parser = subparsers.add_parser('run', help='Nocturnal Agentでタスクを実行')
    run_parser.add_argument('--task-id', type=int, help='実行するタスクID')
    
    # 引数解析
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        if args.command == 'add-task':
            add_task(args.task, args.priority)
        elif args.command == 'list':
            list_tasks()
        elif args.command == 'run':
            run_nocturnal_task(args.task_id)
    except KeyboardInterrupt:
        print("\n⚠️ 処理が中断されました")
        sys.exit(1)
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()