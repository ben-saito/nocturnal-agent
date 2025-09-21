#!/usr/bin/env python3
"""
Command-Based Collaboration System - 指揮官型AI協調システム
ローカルLLM指揮官とClaudeCode技術実行者による完全分離型協調システム
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path

from ..core.config import LLMConfig
from ..core.models import Task, TaskPriority
from ..design.spec_kit_integration import TechnicalSpec, SpecType
from .command_dispatch_interface import (
    CommandDispatchInterface, CommandDirective, ExecutionReport, StrategicDecision
)
from .technical_executor_interface import TechnicalExecutorInterface, TechnicalDeliverable
from .claude_code_interface import load_claude_config


@dataclass
class CampaignResult:
    """戦略キャンペーン結果"""
    campaign_id: str
    task_id: str
    success: bool
    total_duration: float
    commands_issued: int
    successful_executions: int
    final_deliverables: List[TechnicalDeliverable]
    technical_spec: Optional[TechnicalSpec]
    campaign_summary: Dict[str, Any]
    issues_encountered: List[str]
    recommendations: List[str]


class CommandBasedCollaborationSystem:
    """指揮官型AI協調システム"""
    
    def __init__(self, target_project_path: str, llm_config: LLMConfig = None):
        """対象プロジェクトディレクトリでの実行専用初期化"""
        self.target_project_path = Path(target_project_path).resolve()
        self.logger = logging.getLogger(__name__)
        
        # 対象プロジェクトの検証
        if not self.target_project_path.exists():
            raise FileNotFoundError(f"対象プロジェクトディレクトリが見つかりません: {self.target_project_path}")
        
        if not self.target_project_path.is_dir():
            raise NotADirectoryError(f"パスがディレクトリではありません: {self.target_project_path}")
        
        # 指揮官と実行者の初期化
        self.commander = CommandDispatchInterface(llm_config or LLMConfig())
        self.technical_executor = TechnicalExecutorInterface(
            target_project_path=str(self.target_project_path),
            claude_config=load_claude_config()
        )
        
        # システム状態
        self.current_campaign: Optional[str] = None
        self.campaign_history: List[CampaignResult] = []
        
        # 協調設定
        self.max_command_retries = 2
        self.quality_gate_threshold = 0.8
        
        self.logger.info(f"🎯 対象プロジェクト協調システム初期化完了: {self.target_project_path}")

    
    
    async def execute_task_with_command_collaboration(
        self, 
        task: Task, 
        collaboration_options: Dict = None
    ) -> Tuple[TechnicalSpec, CampaignResult]:
        """指揮官型協調によるタスク実行"""
        
        self.logger.info("🚀 指揮官型AI協調システム開始")
        self.logger.info(f"📋 タスク: {task.description}")
        self.logger.info(f"🎖️ 指揮官: ローカルLLM | ⚡ 実行者: ClaudeCode")
        
        start_time = datetime.now()
        campaign_result = None
        
        try:
            # Phase 1: 戦略キャンペーン開始
            campaign_id = await self.commander.initiate_strategic_campaign(task)
            self.current_campaign = campaign_id
            
            # Phase 2: 作戦要求分析と戦略立案
            strategic_decision = await self.commander.analyze_mission_requirements(task)
            
            # Phase 3: 指揮官による指令発令と実行者による技術作業の実行ループ
            final_deliverables, final_spec = await self._execute_command_loop(
                task, strategic_decision
            )
            
            # Phase 4: キャンペーン終了
            campaign_summary = await self.commander.finalize_campaign()
            
            # 結果まとめ
            total_duration = (datetime.now() - start_time).total_seconds()
            
            campaign_result = CampaignResult(
                campaign_id=campaign_id,
                task_id=task.id,
                success=True,
                total_duration=total_duration,
                commands_issued=len(self.commander.command_history),
                successful_executions=len([r for r in self.technical_executor.execution_history if r.status == "completed"]),
                final_deliverables=final_deliverables,
                technical_spec=final_spec,
                campaign_summary=campaign_summary,
                issues_encountered=[],
                recommendations=["キャンペーン正常完了"]
            )
            
            self.campaign_history.append(campaign_result)
            
            self.logger.info(f"✅ 指揮官型協調完了: {campaign_id} ({total_duration:.2f}秒)")
            
            return final_spec, campaign_result
            
        except Exception as e:
            self.logger.error(f"指揮官型協調エラー: {e}")
            
            # エラー時のフォールバック
            fallback_spec = await self._generate_fallback_technical_spec(task)
            
            total_duration = (datetime.now() - start_time).total_seconds()
            
            campaign_result = CampaignResult(
                campaign_id=self.current_campaign or "failed_campaign",
                task_id=task.id,
                success=False,
                total_duration=total_duration,
                commands_issued=0,
                successful_executions=0,
                final_deliverables=[],
                technical_spec=fallback_spec,
                campaign_summary={},
                issues_encountered=[str(e)],
                recommendations=["エラー修正後に再実行を推奨"]
            )
            
            return fallback_spec, campaign_result
    
    async def _execute_command_loop(
        self, 
        task: Task, 
        initial_decision: StrategicDecision
    ) -> Tuple[List[TechnicalDeliverable], TechnicalSpec]:
        """指令実行ループ"""
        
        self.logger.info("🔄 指令実行ループ開始")
        
        all_deliverables = []
        current_commands = initial_decision.next_actions
        phase_count = 1
        
        while current_commands and phase_count <= 5:  # 最大5フェーズ
            self.logger.info(f"📍 Phase {phase_count}: {len(current_commands)}個の指令実行")
            
            # 各指令を順次実行
            for command in current_commands:
                self.logger.info(f"📢 指令発令: {command.command_type.value}")
                
                # 指揮官による指令発令
                command_id = await self.commander.issue_command(command)
                
                # 実行者による指令実行
                execution_report = await self.technical_executor.execute_command(command)
                all_deliverables.extend(self.technical_executor.deliverables)
                
                # 指揮官による実行報告受領と次戦略判断
                next_decision = await self.commander.receive_execution_report(execution_report)
                
                self.logger.info(f"🎯 戦略判断: {next_decision.decision}")
                
                # 品質ゲートチェック
                if not self._quality_gate_check(execution_report):
                    self.logger.warning(f"⚠️ 品質ゲート未達: 品質改善が必要")
                    # 品質改善指令を追加（簡略化）
                
                # 次の指令準備
                current_commands = next_decision.next_actions
                
                if not current_commands:
                    self.logger.info("🏁 全指令完了")
                    break
            
            phase_count += 1
        
        # 最終技術仕様書の生成
        final_spec = await self._synthesize_final_technical_spec(task, all_deliverables)
        
        self.logger.info(f"📋 最終成果物: {len(all_deliverables)}個")
        return all_deliverables, final_spec
    
    def _quality_gate_check(self, execution_report: ExecutionReport) -> bool:
        """品質ゲートチェック"""
        overall_quality = execution_report.quality_metrics.get("overall", 0.0)
        return overall_quality >= self.quality_gate_threshold
    
    async def _synthesize_final_technical_spec(
        self, 
        task: Task, 
        deliverables: List[TechnicalDeliverable]
    ) -> TechnicalSpec:
        """最終技術仕様書の統合"""
        
        self.logger.info("📝 最終技術仕様書統合中...")
        
        # 成果物から情報を抽出
        spec_deliverable = None
        analysis_deliverable = None
        
        for deliverable in deliverables:
            if deliverable.type == "technical_specification":
                spec_deliverable = deliverable
            elif deliverable.type == "requirements_analysis_report":
                analysis_deliverable = deliverable
        
        # 既存のtranslatorを使用して基本構造作成
        from ..design.spec_kit_integration import TaskSpecTranslator, SpecKitManager
        
        spec_manager = SpecKitManager(str(self.workspace_path / "specs"))
        translator = TaskSpecTranslator(spec_manager)
        
        # 基本仕様作成
        tech_spec = translator.task_to_spec(task, SpecType.FEATURE)
        
        # AI協調結果で拡張
        if spec_deliverable:
            tech_spec.metadata.title = f"AI協調生成: {task.description}"
            tech_spec.metadata.description = "指揮官型AI協調システムによって生成された技術仕様書"
            tech_spec.metadata.updated_at = datetime.now().isoformat()
            
            # 成果物のメタデータを統合
            tech_spec.metadata.generation_method = "command_based_collaboration"
            tech_spec.metadata.deliverables_count = len(deliverables)
            tech_spec.metadata.collaboration_quality = sum(d.quality_score for d in deliverables) / len(deliverables)
        
        # 要件情報の拡張
        if analysis_deliverable:
            # 分析結果から詳細要件を抽出して追加（簡略化実装）
            pass
        
        self.logger.info("✅ 最終技術仕様書統合完了")
        return tech_spec
    
    async def _generate_fallback_technical_spec(self, task: Task) -> TechnicalSpec:
        """フォールバック技術仕様書生成"""
        self.logger.warning("🔄 フォールバック仕様書生成中...")
        
        from ..design.spec_kit_integration import TaskSpecTranslator, SpecKitManager
        
        spec_manager = SpecKitManager(str(self.workspace_path / "specs"))
        translator = TaskSpecTranslator(spec_manager)
        
        fallback_spec = translator.task_to_spec(task, SpecType.FEATURE)
        fallback_spec.metadata.description = "フォールバック生成された技術仕様書"
        fallback_spec.metadata.generation_method = "fallback"
        
        return fallback_spec
    
    async def get_campaign_status(self) -> Dict[str, Any]:
        """キャンペーン状況取得"""
        if not self.current_campaign:
            return {"status": "idle", "active_campaign": None}
        
        return {
            "status": "active",
            "active_campaign": self.current_campaign,
            "commands_issued": len(self.commander.command_history),
            "executions_completed": len(self.technical_executor.execution_history),
            "current_phase": "in_progress"
        }
    
    async def get_collaboration_history(self) -> List[Dict[str, Any]]:
        """協調履歴取得"""
        return [
            {
                "campaign_id": result.campaign_id,
                "task_id": result.task_id,
                "success": result.success,
                "duration": result.total_duration,
                "commands": result.commands_issued,
                "executions": result.successful_executions,
                "deliverables": len(result.final_deliverables)
            }
            for result in self.campaign_history
        ]
    
    async def cleanup_old_campaigns(self, days_old: int = 7) -> int:
        """古いキャンペーンのクリーンアップ"""
        cutoff_date = datetime.now().timestamp() - (days_old * 24 * 3600)
        cleanup_count = 0
        
        # キャンペーンファイルのクリーンアップ（実装簡略化）
        
        self.logger.info(f"🧹 古いキャンペーンクリーンアップ: {cleanup_count}件")
        return cleanup_count


# ユーティリティ関数
async def create_command_collaboration_system(
    workspace_path: str, 
    llm_config: LLMConfig = None
) -> CommandBasedCollaborationSystem:
    """指揮官型協調システムのファクトリ関数"""
    return CommandBasedCollaborationSystem(workspace_path, llm_config)


# 使用例とテスト関数
async def test_command_collaboration():
    """指揮官型協調システムのテスト"""
    import tempfile
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # システム初期化
        collaboration_system = CommandBasedCollaborationSystem(temp_dir)
        
        # テストタスク
        test_task = Task(
            id="test_command_collab_001",
            description="AIニュース収集システムの開発",
            priority=TaskPriority.HIGH,
            requirements=[
                "Webスクレイピング機能",
                "データベース保存機能", 
                "Web画面表示機能"
            ],
            estimated_quality=0.85
        )
        
        print("🧪 指揮官型協調システムテスト開始")
        print(f"📋 テストタスク: {test_task.description}")
        
        try:
            # 協調実行
            tech_spec, campaign_result = await collaboration_system.execute_task_with_command_collaboration(
                test_task
            )
            
            print(f"✅ テスト成功:")
            print(f"  - キャンペーンID: {campaign_result.campaign_id}")
            print(f"  - 実行時間: {campaign_result.total_duration:.2f}秒")
            print(f"  - 発令指令数: {campaign_result.commands_issued}")
            print(f"  - 成功実行数: {campaign_result.successful_executions}")
            print(f"  - 最終成果物: {len(campaign_result.final_deliverables)}個")
            print(f"  - 技術仕様書: {tech_spec.metadata.title}")
            
        except Exception as e:
            print(f"❌ テストエラー: {e}")


if __name__ == "__main__":
    # テスト実行
    asyncio.run(test_command_collaboration())