"""
Interaction Logger for Claude Code and Codex Communications
Claude CodeやCodexとの対話を詳細にログ記録するシステム
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum

class InteractionType(Enum):
    """対話タイプ列挙型"""
    INSTRUCTION = "instruction"  # 指示送信
    RESPONSE = "response"       # レスポンス受信
    APPROVAL = "approval"       # 承認
    REJECTION = "rejection"     # 拒否・やり直し指示
    CLARIFICATION = "clarification"  # 確認・質問
    COMPLETION = "completion"   # 完了報告

class AgentType(Enum):
    """エージェントタイプ"""
    CLAUDE_CODE = "claude_code"
    CODEX = "codex"
    LOCAL_LLM = "local_llm"
    GITHUB_COPILOT = "github_copilot"

@dataclass
class InteractionRecord:
    """対話記録データクラス"""
    timestamp: datetime
    session_id: str
    task_id: str
    interaction_type: InteractionType
    agent_type: AgentType
    instruction: Optional[str] = None
    response: Optional[str] = None
    approval_status: Optional[bool] = None
    rejection_reason: Optional[str] = None
    retry_count: int = 0
    quality_score: Optional[float] = None
    execution_time: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None

class InteractionLogger:
    """
    Claude CodeやCodexとの対話を詳細に記録するロガー
    指示・応答・承認・拒否のすべてを追跡
    """
    
    def __init__(self, log_dir: str = "logs/interactions"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # JSONログファイル
        self.json_log_file = self.log_dir / f"interactions_{datetime.now().strftime('%Y%m%d')}.json"
        
        # 人間が読みやすいログファイル
        self.human_log_file = self.log_dir / f"interactions_human_{datetime.now().strftime('%Y%m%d')}.log"
        
        # Python標準ログ設定
        self.logger = logging.getLogger("interaction_logger")
        self.logger.setLevel(logging.INFO)
        
        # ファイルハンドラー設定
        if not self.logger.handlers:
            handler = logging.FileHandler(self.human_log_file, encoding='utf-8')
            formatter = logging.Formatter(
                '%(asctime)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
    
    def log_instruction(self, session_id: str, task_id: str, agent_type: AgentType, 
                       instruction: str, metadata: Optional[Dict] = None) -> str:
        """指示送信をログ記録"""
        interaction_id = f"{session_id}_{task_id}_{datetime.now().strftime('%H%M%S%f')}"
        
        record = InteractionRecord(
            timestamp=datetime.now(),
            session_id=session_id,
            task_id=task_id,
            interaction_type=InteractionType.INSTRUCTION,
            agent_type=agent_type,
            instruction=instruction,
            metadata=metadata or {}
        )
        
        self._save_record(record, interaction_id)
        
        self.logger.info(f"📤 INSTRUCTION to {agent_type.value}: {instruction[:100]}...")
        
        return interaction_id
    
    def log_response(self, session_id: str, task_id: str, agent_type: AgentType,
                    response: str, quality_score: Optional[float] = None,
                    execution_time: Optional[float] = None,
                    metadata: Optional[Dict] = None) -> str:
        """レスポンス受信をログ記録"""
        interaction_id = f"{session_id}_{task_id}_{datetime.now().strftime('%H%M%S%f')}"
        
        record = InteractionRecord(
            timestamp=datetime.now(),
            session_id=session_id,
            task_id=task_id,
            interaction_type=InteractionType.RESPONSE,
            agent_type=agent_type,
            response=response,
            quality_score=quality_score,
            execution_time=execution_time,
            metadata=metadata or {}
        )
        
        self._save_record(record, interaction_id)
        
        quality_info = f" (Quality: {quality_score:.2f})" if quality_score else ""
        time_info = f" (Time: {execution_time:.1f}s)" if execution_time else ""
        
        self.logger.info(f"📥 RESPONSE from {agent_type.value}: {response[:100]}...{quality_info}{time_info}")
        
        return interaction_id
    
    def log_approval(self, session_id: str, task_id: str, agent_type: AgentType,
                    response: str, reason: Optional[str] = None,
                    metadata: Optional[Dict] = None) -> str:
        """承認をログ記録"""
        interaction_id = f"{session_id}_{task_id}_{datetime.now().strftime('%H%M%S%f')}"
        
        record = InteractionRecord(
            timestamp=datetime.now(),
            session_id=session_id,
            task_id=task_id,
            interaction_type=InteractionType.APPROVAL,
            agent_type=agent_type,
            response=response,
            approval_status=True,
            metadata=metadata or {}
        )
        
        if reason:
            record.metadata['approval_reason'] = reason
        
        self._save_record(record, interaction_id)
        
        reason_info = f" - {reason}" if reason else ""
        self.logger.info(f"✅ APPROVED {agent_type.value} response{reason_info}")
        
        return interaction_id
    
    def log_rejection(self, session_id: str, task_id: str, agent_type: AgentType,
                     response: str, rejection_reason: str, retry_count: int = 0,
                     metadata: Optional[Dict] = None) -> str:
        """拒否・やり直し指示をログ記録"""
        interaction_id = f"{session_id}_{task_id}_{datetime.now().strftime('%H%M%S%f')}"
        
        record = InteractionRecord(
            timestamp=datetime.now(),
            session_id=session_id,
            task_id=task_id,
            interaction_type=InteractionType.REJECTION,
            agent_type=agent_type,
            response=response,
            approval_status=False,
            rejection_reason=rejection_reason,
            retry_count=retry_count,
            metadata=metadata or {}
        )
        
        self._save_record(record, interaction_id)
        
        retry_info = f" (Retry #{retry_count})" if retry_count > 0 else ""
        self.logger.info(f"❌ REJECTED {agent_type.value} response{retry_info}: {rejection_reason}")
        
        return interaction_id
    
    def log_clarification(self, session_id: str, task_id: str, agent_type: AgentType,
                         question: str, response: Optional[str] = None,
                         metadata: Optional[Dict] = None) -> str:
        """確認・質問をログ記録"""
        interaction_id = f"{session_id}_{task_id}_{datetime.now().strftime('%H%M%S%f')}"
        
        record = InteractionRecord(
            timestamp=datetime.now(),
            session_id=session_id,
            task_id=task_id,
            interaction_type=InteractionType.CLARIFICATION,
            agent_type=agent_type,
            instruction=question,
            response=response,
            metadata=metadata or {}
        )
        
        self._save_record(record, interaction_id)
        
        self.logger.info(f"❓ CLARIFICATION with {agent_type.value}: {question[:100]}...")
        
        return interaction_id
    
    def log_completion(self, session_id: str, task_id: str, agent_type: AgentType,
                      final_result: str, quality_score: Optional[float] = None,
                      total_retries: int = 0, metadata: Optional[Dict] = None) -> str:
        """完了報告をログ記録"""
        interaction_id = f"{session_id}_{task_id}_{datetime.now().strftime('%H%M%S%f')}"
        
        record = InteractionRecord(
            timestamp=datetime.now(),
            session_id=session_id,
            task_id=task_id,
            interaction_type=InteractionType.COMPLETION,
            agent_type=agent_type,
            response=final_result,
            quality_score=quality_score,
            retry_count=total_retries,
            metadata=metadata or {}
        )
        
        self._save_record(record, interaction_id)
        
        quality_info = f" (Final Quality: {quality_score:.2f})" if quality_score else ""
        retry_info = f" after {total_retries} retries" if total_retries > 0 else ""
        
        self.logger.info(f"🎉 COMPLETED {agent_type.value} task{retry_info}{quality_info}")
        
        return interaction_id
    
    def _save_record(self, record: InteractionRecord, interaction_id: str):
        """記録をJSONファイルに保存"""
        record_dict = asdict(record)
        record_dict['interaction_id'] = interaction_id
        record_dict['timestamp'] = record.timestamp.isoformat()
        record_dict['interaction_type'] = record.interaction_type.value
        record_dict['agent_type'] = record.agent_type.value
        
        # JSONファイルに追記
        with open(self.json_log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(record_dict, ensure_ascii=False) + '\n')
    
    def get_session_interactions(self, session_id: str) -> List[Dict]:
        """セッションの全対話履歴を取得"""
        interactions = []
        
        if not self.json_log_file.exists():
            return interactions
        
        with open(self.json_log_file, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    record = json.loads(line.strip())
                    if record.get('session_id') == session_id:
                        interactions.append(record)
                except json.JSONDecodeError:
                    continue
        
        return sorted(interactions, key=lambda x: x['timestamp'])
    
    def get_task_interactions(self, task_id: str) -> List[Dict]:
        """タスクの全対話履歴を取得"""
        interactions = []
        
        if not self.json_log_file.exists():
            return interactions
        
        with open(self.json_log_file, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    record = json.loads(line.strip())
                    if record.get('task_id') == task_id:
                        interactions.append(record)
                except json.JSONDecodeError:
                    continue
        
        return sorted(interactions, key=lambda x: x['timestamp'])
    
    def generate_interaction_report(self, session_id: str) -> str:
        """セッションの対話レポートを生成"""
        interactions = self.get_session_interactions(session_id)
        
        if not interactions:
            return f"No interactions found for session {session_id}"
        
        report = f"# Interaction Report for Session {session_id}\n\n"
        report += f"Total Interactions: {len(interactions)}\n"
        report += f"Period: {interactions[0]['timestamp']} - {interactions[-1]['timestamp']}\n\n"
        
        # 統計情報
        stats = {
            'instructions': 0,
            'responses': 0,
            'approvals': 0,
            'rejections': 0,
            'clarifications': 0,
            'completions': 0
        }
        
        agents_used = set()
        
        for interaction in interactions:
            interaction_type = interaction.get('interaction_type', '')
            agent_type = interaction.get('agent_type', '')
            
            agents_used.add(agent_type)
            
            if interaction_type in stats:
                stats[interaction_type] += 1
        
        report += "## Statistics\n"
        for stat_type, count in stats.items():
            report += f"- {stat_type.title()}: {count}\n"
        
        report += f"\n## Agents Used\n"
        for agent in sorted(agents_used):
            report += f"- {agent}\n"
        
        report += "\n## Detailed Timeline\n"
        for i, interaction in enumerate(interactions, 1):
            timestamp = interaction.get('timestamp', '')
            interaction_type = interaction.get('interaction_type', '')
            agent_type = interaction.get('agent_type', '')
            
            report += f"\n### {i}. {timestamp} - {interaction_type.upper()} ({agent_type})\n"
            
            if interaction.get('instruction'):
                report += f"**Instruction:** {interaction['instruction'][:200]}...\n"
            
            if interaction.get('response'):
                report += f"**Response:** {interaction['response'][:200]}...\n"
            
            if interaction.get('approval_status') is not None:
                status = "✅ APPROVED" if interaction['approval_status'] else "❌ REJECTED"
                report += f"**Status:** {status}\n"
            
            if interaction.get('rejection_reason'):
                report += f"**Rejection Reason:** {interaction['rejection_reason']}\n"
            
            if interaction.get('quality_score'):
                report += f"**Quality Score:** {interaction['quality_score']:.2f}\n"
            
            if interaction.get('retry_count', 0) > 0:
                report += f"**Retry Count:** {interaction['retry_count']}\n"
        
        return report
    
    def export_interactions(self, session_id: str, output_file: Optional[str] = None) -> str:
        """対話履歴をファイルにエクスポート"""
        if not output_file:
            output_file = self.log_dir / f"interaction_report_{session_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        
        report = self.generate_interaction_report(session_id)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(report)
        
        return str(output_file)

# 使用例とテスト関数
def demo_interaction_logging():
    """対話ログのデモ"""
    logger = InteractionLogger()
    
    session_id = "test_session_001"
    task_id = "codex_news_task_001"
    
    # 指示送信
    logger.log_instruction(
        session_id, task_id, AgentType.CLAUDE_CODE,
        "1時間に1回Codexのニュースを取得してデータをDBに保持するシステムを作成してください",
        {"priority": "high", "deadline": "2025-09-17"}
    )
    
    # レスポンス受信
    logger.log_response(
        session_id, task_id, AgentType.CLAUDE_CODE,
        "Codexニュース収集システムを作成します。SQLiteデータベースとAPSchedulerを使用した実装を提案します。",
        quality_score=0.85, execution_time=2.3
    )
    
    # 拒否とやり直し
    logger.log_rejection(
        session_id, task_id, AgentType.CLAUDE_CODE,
        "提案された実装",
        "エラーハンドリングが不十分です。より堅牢な実装を求めます。",
        retry_count=1
    )
    
    # 改善されたレスポンス
    logger.log_response(
        session_id, task_id, AgentType.CLAUDE_CODE,
        "改善されたCodexニュース収集システム。包括的なエラーハンドリングとログ機能を追加しました。",
        quality_score=0.95, execution_time=3.1
    )
    
    # 承認
    logger.log_approval(
        session_id, task_id, AgentType.CLAUDE_CODE,
        "改善された実装",
        "エラーハンドリングとログ機能が適切に実装されています"
    )
    
    # 完了
    logger.log_completion(
        session_id, task_id, AgentType.CLAUDE_CODE,
        "Codexニュース収集システムが正常に完成しました",
        quality_score=0.95, total_retries=1
    )
    
    # レポート生成
    report_file = logger.export_interactions(session_id)
    print(f"Interaction report saved to: {report_file}")

if __name__ == "__main__":
    demo_interaction_logging()