#!/usr/bin/env python3
"""
新しい設計（仕様書作成フェーズと実装フェーズ分離）をテストするスクリプト
"""

import asyncio
import sys
from pathlib import Path

# プロジェクトのパスを追加
sys.path.append(str(Path(__file__).parent / "src"))

async def test_new_design():
    """新しい設計をテスト"""
    print("🧪 新しい設計（フェーズ分離）のテスト開始...")
    print("=" * 60)
    
    try:
        from nocturnal_agent.execution.spec_driven_executor import InteractiveReviewManager
        from nocturnal_agent.execution.implementation_task_manager import ImplementationTaskManager, TaskStatus
        from nocturnal_agent.log_system.structured_logger import StructuredLogger
        from nocturnal_agent.core.models import Task
        
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
        
        print("📋 Phase 1: 仕様書作成フェーズテスト")
        print("-" * 40)
        
        # InteractiveReviewManagerを初期化
        review_manager = InteractiveReviewManager(workspace_path, logger)
        
        # テスト用のタスクを作成
        test_task = Task(
            description="新設計テスト用仕様書作成",
            priority="high"
        )
        
        session_id = "test_new_design_20250921"
        
        # 仕様書作成（モックの設計書を使用）
        mock_design_doc = {
            'design_summary': {
                'project_name': '新設計テスト用仕様書作成',
                'architecture_type': 'Layered Architecture',
                'key_components': 3,
                'complexity_level': 'MEDIUM',
                'estimated_effort': '6 hours',
                'main_technologies': ['Python', 'Flask', 'SQLite']
            },
            'architecture_overview': {
                'pattern': 'MVC',
                'layers': ['View', 'Controller', 'Model'],
                'key_interfaces': ['Web API', 'Database'],
                'data_flow': 'UI -> Logic -> Database'
            },
            'implementation_plan': {
                'phases': ['設計', '実装', 'テスト', 'デプロイ'],
                'priority_components': ['ユーザー管理', 'データ処理', 'API'],
                'risk_factors': ['時間制約', '技術的複雑さ']
            },
            'quality_requirements': {
                'performance': 'Standard',
                'reliability': 'High',
                'security': 'Medium',
                'maintainability': 'High',
                'testing': 'Required'
            }
        }
        
        # レビューデータを作成
        review_data = {
            'session_id': session_id,
            'task': test_task,
            'design_document': mock_design_doc,
            'status': 'REVIEW_READY'
        }
        
        print("✅ モック仕様書作成完了")
        
        print("\n📋 Phase 2: 仕様書承認 → 実装タスク分割テスト")
        print("-" * 40)
        
        # 仕様書を承認して実装タスクに分割
        approval_result = await review_manager._approve_design(review_data)
        
        print(f"✅ 承認結果: {approval_result['status']}")
        print(f"📊 作成されたタスク数: {approval_result['implementation_tasks']['created_count']}")
        print(f"🎯 承認されたタスク数: {approval_result['implementation_tasks']['approved_count']}")
        
        print("\n📋 Phase 3: 実装タスク管理システムテスト")
        print("-" * 40)
        
        # 実装タスク管理システムを直接テスト
        task_manager = ImplementationTaskManager(workspace_path, logger)
        
        # 実行可能なタスクを取得
        ready_tasks = task_manager.get_ready_tasks()
        print(f"🚀 実行可能なタスク数: {len(ready_tasks)}")
        
        if ready_tasks:
            # 最初のタスクの詳細を表示
            first_task = ready_tasks[0]
            print(f"📝 最初のタスク: {first_task.title}")
            print(f"   - ID: {first_task.task_id}")
            print(f"   - 優先度: {first_task.priority.value}")
            print(f"   - 推定時間: {first_task.estimated_hours}h")
            print(f"   - 技術要件数: {len(first_task.technical_requirements)}")
            print(f"   - 受け入れ基準数: {len(first_task.acceptance_criteria)}")
        
        # タスクサマリーを表示
        task_summary = task_manager.get_task_summary()
        print(f"\n📊 タスクサマリー:")
        print(f"   - 総タスク数: {task_summary['total_tasks']}")
        print(f"   - 総推定時間: {task_summary['total_estimated_hours']:.1f}h")
        print(f"   - ステータス別:")
        for status, count in task_summary['status_counts'].items():
            if count > 0:
                print(f"     - {status}: {count}件")
        
        print("\n📋 Phase 4: 夜間実行システムテスト")
        print("-" * 40)
        
        # 夜間実行をテスト（少数のタスクのみ）
        if ready_tasks:
            print(f"🌙 {min(3, len(ready_tasks))}個のタスクで夜間実行をテスト...")
            
            # 最初の3つのタスクのみ実行
            for i, task in enumerate(ready_tasks[:3]):
                print(f"🔧 テストタスク {i+1}: {task.title}")
                
                # タスク実行開始
                task_manager.start_task_execution(task.task_id)
                
                # 実装タスクを実行
                execution_result = await review_manager._execute_implementation_task(task)
                
                if execution_result['status'] == 'success':
                    task_manager.complete_task(task.task_id, execution_result)
                    print(f"   ✅ 完了: {execution_result['message']}")
                else:
                    task_manager.fail_task(task.task_id, execution_result)
                    print(f"   ❌ 失敗: {execution_result['message']}")
        
        # 最終サマリー
        final_summary = task_manager.get_task_summary()
        print(f"\n📊 最終結果:")
        print(f"   - 完了率: {final_summary['completion_rate']:.1%}")
        print(f"   - 完了時間: {final_summary['completed_hours']:.1f}h / {final_summary['total_estimated_hours']:.1f}h")
        
        print("\n🎉 新設計テスト完了！")
        
    except Exception as e:
        print(f"❌ テストエラー: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_new_design())