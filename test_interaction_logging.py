#!/usr/bin/env python3
"""
対話ログシステムのテスト
Claude CodeやCodexとの詳細なやり取りを記録
"""

import asyncio
import sys
sys.path.insert(0, '.')

async def test_interaction_logging():
    """対話ログシステムの動作テスト"""
    print('🔍 対話ログシステムテスト開始')
    print('=' * 60)
    
    try:
        from src.nocturnal_agent.main import NocturnalAgent
        from src.nocturnal_agent.core.models import Task, TaskPriority
        from src.nocturnal_agent.design.spec_kit_integration import SpecType
        import uuid
        from datetime import datetime
        
        # エージェント初期化
        agent = NocturnalAgent('.')
        
        # セッションIDを設定
        agent.session_id = f"test_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        print(f'🆔 セッションID: {agent.session_id}')
        print(f'📋 対話ログ有効: {hasattr(agent, "interaction_logger")}')
        
        # テストタスク作成
        task = Task(
            id=str(uuid.uuid4()),
            description='Claude Codeとの対話テスト：シンプルなHello Worldシステムの作成',
            priority=TaskPriority.MEDIUM,
            estimated_quality=0.8,
            created_at=datetime.now(),
            requirements=[
                'Hello Worldを出力する関数の作成',
                'エラーハンドリングの実装',
                'ユニットテストの追加'
            ]
        )
        
        print(f'📋 テストタスク: {task.description}')
        
        # Mock executor（対話をシミュレート）
        async def interaction_test_executor(task_to_execute):
            print(f'🤖 Claude Codeシミュレーション実行中...')
            await asyncio.sleep(1)
            
            from src.nocturnal_agent.core.models import ExecutionResult, QualityScore, AgentType
            
            # 高品質な結果を生成（承認されるテスト）
            return ExecutionResult(
                task_id=task_to_execute.id,
                success=True,
                quality_score=QualityScore(
                    overall=0.92,
                    code_quality=0.90,
                    consistency=0.95,
                    test_coverage=0.90
                ),
                generated_code='''def hello_world():
    """Hello Worldを出力する関数"""
    try:
        message = "Hello, World!"
        print(message)
        return message
    except Exception as e:
        print(f"Error: {e}")
        return None

def test_hello_world():
    """ユニットテスト"""
    result = hello_world()
    assert result == "Hello, World!"
    print("Test passed!")

if __name__ == "__main__":
    hello_world()
''',
                agent_used=AgentType.LOCAL_LLM,
                execution_time=1.2
            )
        
        # Spec Kit駆動実行（対話ログ付き）
        print('\\n🔥 対話ログ付きSpec Kit駆動実行開始...')
        result = await agent.execute_task_with_spec_design(
            task, 
            interaction_test_executor, 
            SpecType.FEATURE
        )
        
        print(f'\\n✅ 実行完了!')
        print(f'📊 品質スコア: {result.quality_score.overall:.2f}')
        print(f'⏱️ 実行時間: {result.execution_time}秒')
        
        # 対話ログ確認
        print('\\n📋 対話ログ確認中...')
        interactions = agent.interaction_logger.get_session_interactions(agent.session_id)
        
        print(f'📈 記録された対話数: {len(interactions)}')
        
        for i, interaction in enumerate(interactions, 1):
            timestamp = interaction.get('timestamp', '')[:19]  # 秒まで表示
            interaction_type = interaction.get('interaction_type', '')
            agent_type = interaction.get('agent_type', '')
            
            print(f'\\n{i}. [{timestamp}] {interaction_type.upper()} - {agent_type}')
            
            if interaction.get('instruction'):
                instruction = interaction['instruction'][:80] + "..." if len(interaction['instruction']) > 80 else interaction['instruction']
                print(f'   📤 指示: {instruction}')
            
            if interaction.get('response'):
                response = interaction['response'][:80] + "..." if len(interaction['response']) > 80 else interaction['response']
                print(f'   📥 応答: {response}')
            
            if interaction.get('approval_status') is not None:
                status = "✅ 承認" if interaction['approval_status'] else "❌ 拒否"
                print(f'   {status}')
                
                if interaction.get('rejection_reason'):
                    print(f'   🚫 拒否理由: {interaction["rejection_reason"]}')
            
            if interaction.get('quality_score'):
                print(f'   📊 品質: {interaction["quality_score"]:.2f}')
        
        # 対話レポート生成
        print('\\n📄 対話レポート生成中...')
        report_file = agent.interaction_logger.export_interactions(agent.session_id)
        print(f'📁 レポートファイル: {report_file}')
        
        # レポート内容の一部を表示
        with open(report_file, 'r', encoding='utf-8') as f:
            report_content = f.read()
            print('\\n📖 レポート内容（抜粋）:')
            print('-' * 40)
            print(report_content[:500] + "..." if len(report_content) > 500 else report_content)
            print('-' * 40)
        
        return True
        
    except Exception as e:
        print(f'❌ エラー: {e}')
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_interaction_logging())
    if success:
        print('\\n🌟 対話ログシステムテスト成功！')
        print('🎯 Claude CodeやCodexとの全対話が詳細に記録されます')
    else:
        print('\\n💥 対話ログテスト失敗')