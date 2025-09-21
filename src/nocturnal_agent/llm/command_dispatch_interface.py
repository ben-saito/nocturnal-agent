#!/usr/bin/env python3
"""
Command Dispatch Interface - ローカルLLM指揮官インターフェース
技術作業の指示・管理・承認に特化した指揮官型LLMインターフェース
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

from ..core.config import LLMConfig
from ..core.models import Task, TaskPriority


class CommandType(Enum):
    """指揮命令タイプ"""
    ANALYZE_REQUIREMENTS = "analyze_requirements"
    CREATE_SPECIFICATION = "create_specification"
    IMPLEMENT_CODE = "implement_code"
    CREATE_TESTS = "create_tests"
    GENERATE_DOCS = "generate_docs"
    REVIEW_QUALITY = "review_quality"


@dataclass
class CommandDirective:
    """指揮官からの指示"""
    command_id: str
    command_type: CommandType
    target_agent: str  # "claude_code", "local_executor"
    instruction: str
    context: Dict[str, Any]
    priority: str
    expected_deliverables: List[str]
    success_criteria: List[str]
    constraints: List[str]
    timestamp: datetime


@dataclass
class ExecutionReport:
    """実行者からの報告"""
    command_id: str
    agent_id: str
    status: str  # "completed", "failed", "in_progress"
    deliverables: Dict[str, Any]
    execution_time: float
    quality_metrics: Dict[str, float]
    issues_encountered: List[str]
    recommendations: List[str]
    timestamp: datetime


@dataclass
class StrategicDecision:
    """戦略的判断結果"""
    decision_type: str
    decision: str
    reasoning: str
    next_actions: List[CommandDirective]
    risk_assessment: Dict[str, str]
    resource_allocation: Dict[str, Any]


class CommandDispatchInterface:
    """指揮官型ローカルLLMインターフェース"""
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # 指揮官設定
        self.command_history: List[CommandDirective] = []
        self.execution_reports: List[ExecutionReport] = []
        self.current_campaign_id = None
        
        # 戦略パラメータ
        self.max_concurrent_commands = 3
        self.quality_threshold = 0.85
        self.risk_tolerance = "medium"
    
    async def initiate_strategic_campaign(self, task: Task) -> str:
        """戦略キャンペーンの開始"""
        campaign_id = f"campaign_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.current_campaign_id = campaign_id
        
        self.logger.info(f"🎖️ 戦略キャンペーン開始: {campaign_id}")
        self.logger.info(f"📋 作戦目標: {task.description}")
        
        return campaign_id
    
    async def analyze_mission_requirements(self, task: Task) -> StrategicDecision:
        """作戦要求分析と戦略立案"""
        self.logger.info("🎯 作戦要求分析中...")
        
        analysis_prompt = f"""
        あなたは経験豊富な技術プロジェクト指揮官です。
        以下のタスクの戦略的分析を行い、実行計画を立案してください。

        **タスク詳細:**
        - 説明: {task.description}
        - 優先度: {task.priority.value}
        - 要件: {json.dumps(task.requirements, ensure_ascii=False)}
        - 品質目標: {task.estimated_quality}

        **分析項目:**
        1. プロジェクトの戦略的重要度
        2. 技術的複雑度とリスク
        3. リソース要求予測
        4. 実行フェーズの分割
        5. 品質管理方針

        **出力形式 (JSON):**
        {{
          "strategic_priority": "high|medium|low",
          "complexity_assessment": "complex|moderate|simple",
          "execution_phases": ["phase1", "phase2", "phase3"],
          "risk_factors": ["risk1", "risk2"],
          "resource_requirements": {{"時間": "2-4時間", "技術者": "1名"}},
          "quality_strategy": "厳密品質管理|標準品質管理|基本品質管理",
          "success_metrics": ["metric1", "metric2"]
        }}
        """
        
        try:
            response = await self._strategic_consultation(analysis_prompt)
            strategic_data = json.loads(response)
            
            # 戦略的判断を基に指令を生成
            next_actions = self._generate_initial_commands(task, strategic_data)
            
            decision = StrategicDecision(
                decision_type="mission_analysis",
                decision=f"戦略: {strategic_data.get('quality_strategy', '標準品質管理')}",
                reasoning=f"複雑度: {strategic_data.get('complexity_assessment', '中程度')}、優先度: {strategic_data.get('strategic_priority', '中')}",
                next_actions=next_actions,
                risk_assessment={
                    "technical_risk": strategic_data.get('complexity_assessment', 'moderate'),
                    "timeline_risk": "低" if len(strategic_data.get('execution_phases', [])) <= 3 else "中",
                    "quality_risk": "低" if task.estimated_quality <= 0.8 else "中"
                },
                resource_allocation=strategic_data.get('resource_requirements', {})
            )
            
            self.logger.info(f"✅ 戦略分析完了: {decision.decision}")
            return decision
            
        except Exception as e:
            self.logger.error(f"戦略分析エラー: {e}")
            # フォールバック戦略
            return self._generate_fallback_strategy(task)
    
    def _generate_initial_commands(self, task: Task, strategic_data: Dict) -> List[CommandDirective]:
        """初期指令生成"""
        commands = []
        timestamp = datetime.now()
        
        # 第1フェーズ: 技術要件分析指令
        commands.append(CommandDirective(
            command_id=f"{self.current_campaign_id}_cmd_001",
            command_type=CommandType.ANALYZE_REQUIREMENTS,
            target_agent="claude_code",
            instruction=f"""
            以下のタスクの技術要件を詳細に分析してください：

            **タスク**: {task.description}
            **要件**: {json.dumps(task.requirements, ensure_ascii=False)}

            **分析項目**:
            1. 機能要件の詳細化
            2. 非機能要件の特定
            3. 技術スタックの選定
            4. アーキテクチャ要件
            5. データモデル要件
            6. インターフェース要件
            7. セキュリティ要件
            8. パフォーマンス要件

            詳細な技術要件分析レポートを作成してください。
            """,
            context={
                "task_id": task.id,
                "priority": task.priority.value,
                "quality_target": task.estimated_quality,
                "strategic_approach": strategic_data.get('quality_strategy', '標準品質管理')
            },
            priority="high",
            expected_deliverables=[
                "技術要件分析レポート",
                "機能要件リスト",
                "非機能要件リスト",
                "技術スタック提案",
                "アーキテクチャ概要"
            ],
            success_criteria=[
                "すべての要件が具体的に定義されている",
                "技術的実現可能性が検証されている",
                "品質目標を満たすアーキテクチャが提案されている"
            ],
            constraints=[
                f"品質目標: {task.estimated_quality}以上",
                "既存システムとの互換性維持",
                "実装可能な技術のみ使用"
            ],
            timestamp=timestamp
        ))
        
        return commands
    
    async def issue_command(self, directive: CommandDirective) -> str:
        """指令発令"""
        self.logger.info(f"📢 指令発令: {directive.command_type.value} -> {directive.target_agent}")
        self.logger.info(f"🎯 指令ID: {directive.command_id}")
        
        self.command_history.append(directive)
        
        return directive.command_id
    
    async def receive_execution_report(self, report: ExecutionReport) -> StrategicDecision:
        """実行報告受領と次の戦略判断"""
        self.logger.info(f"📋 実行報告受領: {report.command_id} - {report.status}")
        
        self.execution_reports.append(report)
        
        # 報告内容を評価し、次の戦略を決定
        evaluation_prompt = f"""
        指揮官として実行報告を評価し、次の戦略を決定してください。

        **実行報告内容:**
        - コマンドID: {report.command_id}
        - 実行者: {report.agent_id}
        - ステータス: {report.status}
        - 実行時間: {report.execution_time}秒
        - 品質メトリクス: {json.dumps(report.quality_metrics, ensure_ascii=False)}
        - 成果物: {len(report.deliverables)}項目
        - 課題: {report.issues_encountered}
        - 推奨事項: {report.recommendations}

        **判断項目:**
        1. 実行結果の品質評価
        2. 次フェーズ進行可否
        3. 追加指示の必要性
        4. リスク要因の評価

        **出力形式 (JSON):**
        {{
          "overall_assessment": "excellent|good|acceptable|poor",
          "proceed_to_next_phase": true|false,
          "quality_score": 0.0-1.0,
          "next_command_type": "create_specification|implement_code|review_quality|abort",
          "specific_instructions": "次の具体的指示内容",
          "risk_mitigation": "リスク軽減策"
        }}
        """
        
        try:
            response = await self._strategic_consultation(evaluation_prompt)
            evaluation = json.loads(response)
            
            # 次の指令を生成
            next_actions = self._generate_next_command(report, evaluation)
            
            decision = StrategicDecision(
                decision_type="execution_evaluation",
                decision=f"評価: {evaluation.get('overall_assessment', 'acceptable')}、次フェーズ: {'進行' if evaluation.get('proceed_to_next_phase', True) else '保留'}",
                reasoning=f"品質スコア: {evaluation.get('quality_score', 0.8)}, 課題数: {len(report.issues_encountered)}",
                next_actions=next_actions,
                risk_assessment={
                    "current_quality": str(evaluation.get('quality_score', 0.8)),
                    "execution_risk": "低" if report.status == "completed" else "高",
                    "timeline_risk": "低" if report.execution_time < 300 else "中"
                },
                resource_allocation={}
            )
            
            return decision
            
        except Exception as e:
            self.logger.error(f"戦略評価エラー: {e}")
            return self._generate_fallback_decision(report)
    
    def _generate_next_command(self, report: ExecutionReport, evaluation: Dict) -> List[CommandDirective]:
        """次の指令生成"""
        if not evaluation.get('proceed_to_next_phase', True):
            return []
        
        next_cmd_type = evaluation.get('next_command_type', 'create_specification')
        
        if next_cmd_type == "create_specification":
            return [self._create_specification_command(report, evaluation)]
        elif next_cmd_type == "implement_code":
            return [self._create_implementation_command(report, evaluation)]
        elif next_cmd_type == "review_quality":
            return [self._create_review_command(report, evaluation)]
        
        return []
    
    def _create_specification_command(self, report: ExecutionReport, evaluation: Dict) -> CommandDirective:
        """仕様書作成指令"""
        return CommandDirective(
            command_id=f"{self.current_campaign_id}_spec_{datetime.now().strftime('%H%M%S')}",
            command_type=CommandType.CREATE_SPECIFICATION,
            target_agent="claude_code",
            instruction=f"""
            前回の技術要件分析結果を基に、詳細な技術仕様書を作成してください。

            **前回の成果物:**
            {json.dumps(report.deliverables, ensure_ascii=False, indent=2)}

            **追加指示:**
            {evaluation.get('specific_instructions', '標準的な仕様書作成手順に従ってください')}

            **作成する仕様書:**
            1. プロジェクト概要
            2. システム要件（機能要件・非機能要件）
            3. アーキテクチャ設計
            4. データベース設計
            5. API仕様
            6. 実装ガイドライン
            7. テスト戦略
            8. デプロイメント手順

            GitHub Spec Kit標準に準拠した高品質な仕様書を作成してください。
            """,
            context=report.deliverables,
            priority="high",
            expected_deliverables=[
                "完全な技術仕様書",
                "実装ガイドライン",
                "テスト計画",
                "デプロイメント手順"
            ],
            success_criteria=[
                "すべてのセクションが詳細に記述されている",
                "実装可能なレベルの具体性がある",
                "品質目標を満たすアーキテクチャが含まれている"
            ],
            constraints=[
                "GitHub Spec Kit標準準拠",
                "実装可能性を重視",
                "保守性を考慮した設計"
            ],
            timestamp=datetime.now()
        )
    
    def _create_implementation_command(self, report: ExecutionReport, evaluation: Dict) -> CommandDirective:
        """実装指令"""
        return CommandDirective(
            command_id=f"{self.current_campaign_id}_impl_{datetime.now().strftime('%H%M%S')}",
            command_type=CommandType.IMPLEMENT_CODE,
            target_agent="claude_code",
            instruction=f"""
            作成された仕様書に基づいて実装を実行してください。

            **仕様書情報:**
            {json.dumps(report.deliverables, ensure_ascii=False, indent=2)}

            **実装指示:**
            {evaluation.get('specific_instructions', '仕様書に従って段階的に実装してください')}

            **実装項目:**
            1. コアモジュールの実装
            2. データモデルの実装
            3. API エンドポイントの実装
            4. ユーザーインターフェースの実装
            5. 設定ファイルの作成
            6. 必要なディレクトリ構造の作成

            高品質で保守性の高いコードを作成してください。
            """,
            context=report.deliverables,
            priority="high",
            expected_deliverables=[
                "実装コード一式",
                "設定ファイル",
                "ディレクトリ構造",
                "基本的なテストファイル"
            ],
            success_criteria=[
                "仕様書通りの機能が実装されている",
                "コード品質基準を満たしている",
                "適切なエラーハンドリングが含まれている"
            ],
            constraints=[
                "既存コードとの互換性維持",
                "セキュリティベストプラクティス準拠",
                "パフォーマンス要件達成"
            ],
            timestamp=datetime.now()
        )
    
    async def _strategic_consultation(self, prompt: str) -> str:
        """戦略的相談（ローカルLLM呼び出し）"""
        if not self.config.enabled:
            return self._generate_fallback_strategic_response(prompt)
        
        # 実際のローカルLLM呼び出し（簡略化）
        # 実装では local_llm_interface の _call_llm を使用
        await asyncio.sleep(0.1)  # 模擬処理時間
        
        # フォールバック応答（実際の実装では適切なLLM応答）
        return self._generate_fallback_strategic_response(prompt)
    
    def _generate_fallback_strategic_response(self, prompt: str) -> str:
        """フォールバック戦略応答"""
        if "作戦要求分析" in prompt:
            return json.dumps({
                "strategic_priority": "medium",
                "complexity_assessment": "moderate",
                "execution_phases": ["analysis", "specification", "implementation"],
                "risk_factors": ["技術的複雑性", "時間制約"],
                "resource_requirements": {"時間": "2-4時間", "技術者": "1名"},
                "quality_strategy": "標準品質管理",
                "success_metrics": ["機能実装完了", "品質基準達成"]
            }, ensure_ascii=False)
        elif "実行報告" in prompt:
            return json.dumps({
                "overall_assessment": "good",
                "proceed_to_next_phase": True,
                "quality_score": 0.85,
                "next_command_type": "create_specification",
                "specific_instructions": "標準的な仕様書作成手順に従ってください",
                "risk_mitigation": "定期的な品質チェックを実施"
            }, ensure_ascii=False)
        
        return '{"status": "ready", "action": "proceed"}'
    
    def _generate_fallback_strategy(self, task: Task) -> StrategicDecision:
        """フォールバック戦略"""
        return StrategicDecision(
            decision_type="fallback_analysis",
            decision="標準品質管理戦略を適用",
            reasoning="戦略分析システムが利用できないため、標準アプローチを採用",
            next_actions=self._generate_initial_commands(task, {"quality_strategy": "標準品質管理"}),
            risk_assessment={"technical_risk": "medium", "timeline_risk": "low"},
            resource_allocation={"時間": "2-4時間", "技術者": "1名"}
        )
    
    def _generate_fallback_decision(self, report: ExecutionReport) -> StrategicDecision:
        """フォールバック判断"""
        return StrategicDecision(
            decision_type="fallback_evaluation",
            decision="次フェーズに進行",
            reasoning="評価システムが利用できないため、標準進行を採用",
            next_actions=self._generate_next_command(report, {"proceed_to_next_phase": True, "next_command_type": "create_specification"}),
            risk_assessment={"execution_risk": "medium"},
            resource_allocation={}
        )
    
    async def finalize_campaign(self) -> Dict[str, Any]:
        """キャンペーン終了"""
        self.logger.info(f"🏁 戦略キャンペーン完了: {self.current_campaign_id}")
        
        campaign_summary = {
            "campaign_id": self.current_campaign_id,
            "total_commands": len(self.command_history),
            "successful_executions": len([r for r in self.execution_reports if r.status == "completed"]),
            "average_execution_time": sum(r.execution_time for r in self.execution_reports) / len(self.execution_reports) if self.execution_reports else 0,
            "overall_quality": sum(r.quality_metrics.get('overall', 0.8) for r in self.execution_reports) / len(self.execution_reports) if self.execution_reports else 0.8
        }
        
        return campaign_summary


# ユーティリティ関数
async def create_command_dispatcher(config: LLMConfig) -> CommandDispatchInterface:
    """指揮官インターフェースのファクトリ関数"""
    return CommandDispatchInterface(config)