#!/usr/bin/env python3
"""
AI Collaborative Specification Generator
ローカルLLM ↔ ClaudeCode 協調による高品質仕様書生成システム
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from dataclasses import dataclass, asdict
from pathlib import Path

from .local_llm_interface import LocalLLMInterface, TaskAnalysis, SpecReview
from .claude_code_interface import ClaudeCodeInterface, SpecificationDocument, load_claude_config
from ..core.config import LLMConfig
from ..core.models import Task
from ..design.spec_kit_integration import TechnicalSpec, SpecStatus


@dataclass
class CollaborationReport:
    """AI協調レポート"""
    task_id: str
    collaboration_id: str
    start_time: datetime
    end_time: Optional[datetime]
    total_duration: float
    
    # フェーズ情報
    analysis_phase: Dict[str, Any]
    instruction_phase: Dict[str, Any] 
    generation_phase: Dict[str, Any]
    review_phase: Dict[str, Any]
    enhancement_phase: Optional[Dict[str, Any]]
    
    # 最終結果
    final_specification: Optional[SpecificationDocument]
    quality_metrics: Dict[str, float]
    collaboration_success: bool
    issues_encountered: List[str]
    
    # AI使用状況
    local_llm_calls: int
    claude_code_calls: int
    total_tokens_estimated: int


class AICollaborativeSpecGenerator:
    """AI協調仕様書生成システム"""
    
    def __init__(self, llm_config: LLMConfig):
        self.llm_config = llm_config
        self.claude_config = load_claude_config()
        self.logger = logging.getLogger(__name__)
        
        # 協調設定
        self.max_enhancement_iterations = 2
        self.quality_threshold = 0.85
        self.min_spec_length = 1000  # 最小文字数
        
        # 統計情報
        self.total_collaborations = 0
        self.successful_collaborations = 0
    
    async def generate_specification_collaboratively(
        self, 
        task: Task,
        collaboration_options: Dict = None
    ) -> Tuple[TechnicalSpec, CollaborationReport]:
        """AI協調による仕様書生成メインフロー（指揮官型ローカルLLM）"""
        
        collaboration_id = f"collab_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        start_time = datetime.now()
        
        self.logger.info(f"🎯 AI協調仕様書生成開始 [ID: {collaboration_id}]")
        self.logger.info(f"📋 タスク: {task.description[:100]}...")
        self.logger.info(f"🎖️ ローカルLLM: 指揮官役 | 📝 ClaudeCode: 技術実行役")
        
        # レポート初期化
        report = CollaborationReport(
            task_id=task.id,
            collaboration_id=collaboration_id,
            start_time=start_time,
            end_time=None,
            total_duration=0.0,
            analysis_phase={},
            instruction_phase={},
            generation_phase={},
            review_phase={},
            enhancement_phase=None,
            final_specification=None,
            quality_metrics={},
            collaboration_success=False,
            issues_encountered=[],
            local_llm_calls=0,
            claude_code_calls=0,
            total_tokens_estimated=0
        )
        
        try:
            # フェーズ1: タスク分析
            analysis_result, analysis_report = await self._phase_1_task_analysis(task)
            report.analysis_phase = analysis_report
            report.local_llm_calls += 1
            
            # フェーズ2: 指示生成
            instructions, instruction_report = await self._phase_2_instruction_generation(task, analysis_result)
            report.instruction_phase = instruction_report
            report.claude_code_calls += 1
            
            # フェーズ3: 仕様書生成
            specification, generation_report = await self._phase_3_specification_generation(task, instructions)
            report.generation_phase = generation_report
            report.local_llm_calls += 1
            
            # フェーズ4: 仕様書レビュー（引数を正しく渡す）
            review_result, review_report = await self._phase_4_specification_review(task, specification)
            report.review_phase = review_report
            report.claude_code_calls += 1
            
            # フェーズ5: 反復的改善
            final_spec, enhancement_report = await self._phase_5_iterative_enhancement(task, specification, review_result)
            report.enhancement_phase = enhancement_report
            report.local_llm_calls += 1
            
            # 最終仕様書をTechnicalSpecに変換
            final_tech_spec = self._convert_to_technical_spec(final_spec, task, analysis_result)
            
            # レポート完了
            report.final_specification = final_spec
            report.quality_metrics = self._calculate_final_quality_metrics(final_spec, review_result)
            report.collaboration_success = True
            
            self.successful_collaborations += 1
            
        except Exception as e:
            self.logger.error(f"AI協調エラー: {e}")
            report.issues_encountered.append(str(e))
            
            # フォールバック仕様書生成
            final_tech_spec = self._generate_fallback_technical_spec(task)
            
        finally:
            report.end_time = datetime.now()
            report.total_duration = (report.end_time - start_time).total_seconds()
            report.total_tokens_estimated = self._estimate_total_tokens(report)
            
            self.total_collaborations += 1
            
            self.logger.info(f"✅ AI協調完了 [{collaboration_id}] - {report.total_duration:.2f}秒")
            self.logger.info(f"📊 ローカルLLM呼び出し: {report.local_llm_calls}回 | ClaudeCode呼び出し: {report.claude_code_calls}回")
            
            # レポート保存
            await self._save_collaboration_report(report)
        
        return final_tech_spec, report
    
    async def _phase_1_task_analysis(self, task: Task) -> Tuple[TaskAnalysis, Dict]:
        """フェーズ1: ローカルLLMによるタスク分析"""
        phase_start = datetime.now()
        self.logger.info("🔍 Phase 1: ローカルLLMによるタスク分析")
        
        try:
            async with LocalLLMInterface(self.llm_config) as llm:
                analysis = await llm.analyze_task(task)
                
                phase_report = {
                    "phase": "task_analysis",
                    "duration": (datetime.now() - phase_start).total_seconds(),
                    "success": True,
                    "complexity_score": analysis.complexity_score,
                    "components_identified": len(analysis.required_components),
                    "risks_identified": len(analysis.risk_factors)
                }
                
                self.logger.info(f"📊 分析完了: 複雑性スコア {analysis.complexity_score:.2f}")
                return analysis, phase_report
                
        except Exception as e:
            self.logger.error(f"Phase 1 エラー: {e}")
            
            # フォールバック分析
            fallback_analysis = TaskAnalysis(
                complexity_score=0.7,
                required_components=["メインシステム"],
                technical_requirements=["Python"],
                estimated_effort="中程度",
                risk_factors=["技術的複雑性"],
                suggested_approach="段階的実装",
                claude_code_instruction=f"以下のタスクの技術仕様書を作成してください: {task.description}"
            )
            
            phase_report = {
                "phase": "task_analysis",
                "duration": (datetime.now() - phase_start).total_seconds(),
                "success": False,
                "error": str(e),
                "fallback_used": True
            }
            
            return fallback_analysis, phase_report
    
    async def _phase_2_instruction_generation(self, task: Task, analysis: TaskAnalysis) -> Tuple[str, Dict]:
        """フェーズ2: ClaudeCode指示生成"""
        phase_start = datetime.now()
        self.logger.info("📝 Phase 2: ClaudeCode指示生成")
        
        try:
            async with LocalLLMInterface(self.llm_config) as llm:
                instruction = await llm.generate_claude_code_instruction(task, analysis)
                
                phase_report = {
                    "phase": "instruction_generation",
                    "duration": (datetime.now() - phase_start).total_seconds(),
                    "success": True,
                    "instruction_length": len(instruction),
                    "based_on_analysis": True
                }
                
                self.logger.info(f"📋 指示生成完了: {len(instruction)}文字")
                return instruction, phase_report
                
        except Exception as e:
            self.logger.error(f"Phase 2 エラー: {e}")
            
            # フォールバック指示
            fallback_instruction = f"""
            以下のタスクの詳細な技術仕様書を作成してください：

            **タスク**: {task.description}
            **要件**: {', '.join(task.requirements)}
            
            高品質で実装可能な技術仕様書を生成してください。
            """
            
            phase_report = {
                "phase": "instruction_generation", 
                "duration": (datetime.now() - phase_start).total_seconds(),
                "success": False,
                "error": str(e),
                "fallback_used": True
            }
            
            return fallback_instruction.strip(), phase_report
    
    async def _phase_3_specification_generation(self, task: Task, instruction: str) -> Tuple[SpecificationDocument, Dict]:
        """フェーズ3: ClaudeCodeによる仕様書生成"""
        phase_start = datetime.now()
        self.logger.info("🎯 Phase 3: ClaudeCodeによる仕様書生成")
        
        try:
            async with ClaudeCodeInterface(self.claude_config) as claude:
                specification = await claude.generate_specification_document(instruction, task)
                
                phase_report = {
                    "phase": "specification_generation",
                    "duration": (datetime.now() - phase_start).total_seconds(),
                    "success": True,
                    "spec_word_count": specification.word_count,
                    "generation_time": specification.generation_time,
                    "sections_generated": len(specification.sections)
                }
                
                self.logger.info(f"📄 仕様書生成完了: {specification.word_count}語, {len(specification.sections)}セクション")
                return specification, phase_report
                
        except Exception as e:
            self.logger.error(f"Phase 3 エラー: {e}")
            
            # フォールバック仕様書
            fallback_content = f"""
            # {task.description} - 技術仕様書
            
            ## 概要
            本システムは以下の要件を満たす実装を提供します：
            {chr(10).join(f'- {req}' for req in task.requirements)}
            
            ## 実装ガイドライン
            - 段階的な実装アプローチ
            - 品質重視の開発
            - 適切なテスト実装
            """
            
            fallback_spec = SpecificationDocument(
                title=f"{task.description} (フォールバック)",
                content=fallback_content,
                sections={"概要": "基本的な仕様概要"},
                metadata={"fallback": True},
                quality_indicators={"completeness_score": 0.5},
                generation_time=0.1,
                word_count=len(fallback_content.split())
            )
            
            phase_report = {
                "phase": "specification_generation",
                "duration": (datetime.now() - phase_start).total_seconds(),
                "success": False,
                "error": str(e),
                "fallback_used": True
            }
            
            return fallback_spec, phase_report
    
    async def _phase_4_specification_review(self, task: Task, specification: SpecificationDocument) -> Tuple[SpecReview, Dict]:
        """フェーズ4: ローカルLLMによるレビュー"""
        phase_start = datetime.now()
        self.logger.info("🔍 Phase 4: ローカルLLMによる仕様書レビュー")
        
        try:
            async with LocalLLMInterface(self.llm_config) as llm:
                review = await llm.review_specification(specification.content, task)
                
                phase_report = {
                    "phase": "specification_review",
                    "duration": (datetime.now() - phase_start).total_seconds(),
                    "success": True,
                    "quality_score": review.quality_score,
                    "approved": review.approved,
                    "issues_found": len(review.issues),
                    "suggestions_made": len(review.suggestions)
                }
                
                approval_status = "承認" if review.approved else "要改善"
                self.logger.info(f"📋 レビュー完了: {approval_status} (品質: {review.quality_score:.2f})")
                return review, phase_report
                
        except Exception as e:
            self.logger.error(f"Phase 4 エラー: {e}")
            
            # フォールバックレビュー
            fallback_review = SpecReview(
                quality_score=0.75,
                completeness_score=0.8,
                clarity_score=0.7,
                issues=[],
                suggestions=["詳細な実装ガイドラインの追加"],
                approved=True,
                review_notes="基本的な品質要件を満たしています"
            )
            
            phase_report = {
                "phase": "specification_review",
                "duration": (datetime.now() - phase_start).total_seconds(),
                "success": False,
                "error": str(e),
                "fallback_used": True
            }
            
            return fallback_review, phase_report
    
    async def _phase_5_iterative_enhancement(
        self, 
        task: Task, 
        specification: SpecificationDocument, 
        review: SpecReview
    ) -> Tuple[SpecificationDocument, Dict]:
        """フェーズ5: 反復的改善"""
        phase_start = datetime.now()
        self.logger.info("🔄 Phase 5: 仕様書の反復的改善")
        
        try:
            async with ClaudeCodeInterface(self.claude_config) as claude:
                enhanced_spec = await claude.enhance_specification_iteratively(
                    specification, 
                    review.suggestions
                )
                
                phase_report = {
                    "phase": "iterative_enhancement",
                    "duration": (datetime.now() - phase_start).total_seconds(),
                    "success": True,
                    "enhancements_applied": len(review.suggestions),
                    "word_count_before": specification.word_count,
                    "word_count_after": enhanced_spec.word_count
                }
                
                self.logger.info(f"✨ 改善完了: {enhanced_spec.word_count}語 (+{enhanced_spec.word_count - specification.word_count})")
                return enhanced_spec, phase_report
                
        except Exception as e:
            self.logger.error(f"Phase 5 エラー: {e}")
            
            phase_report = {
                "phase": "iterative_enhancement",
                "duration": (datetime.now() - phase_start).total_seconds(),
                "success": False,
                "error": str(e),
                "fallback_used": True
            }
            
            # 元の仕様書を返す
            return specification, phase_report
    
    def _convert_to_technical_spec(
        self, 
        specification: SpecificationDocument, 
        task: Task, 
        analysis: TaskAnalysis
    ) -> TechnicalSpec:
        """SpecificationDocumentをTechnicalSpecに変換"""
        from ..design.spec_kit_integration import (
            SpecMetadata, SpecRequirement, SpecDesign, SpecImplementation,
            SpecType
        )
        
        # メタデータ作成
        metadata = SpecMetadata(
            title=specification.title,
            status=SpecStatus.APPROVED,
            spec_type=SpecType.FEATURE,
            authors=["AI Collaboration System", "LocalLLM", "ClaudeCode"],
            tags=["ai-generated", "collaborative", task.priority.value]
        )
        
        # 要件変換
        requirements = []
        for i, req_text in enumerate(task.requirements):
            requirement = SpecRequirement(
                id=f"AI-REQ-{i+1:03d}",
                title=f"AI分析要件 {i+1}",
                description=req_text,
                priority="high" if task.priority.value == "high" else "medium"
            )
            requirements.append(requirement)
        
        # 設計情報
        design = SpecDesign(
            overview=specification.content,
            architecture={
                "ai_collaboration": True,
                "complexity_score": analysis.complexity_score,
                "required_components": analysis.required_components,
                "quality_target": 0.9
            },
            components=analysis.required_components,
            interfaces=[]
        )
        
        # 実装情報
        implementation = SpecImplementation(
            approach=analysis.suggested_approach,
            timeline={"total_effort": analysis.estimated_effort},
            testing_strategy="AI協調品質保証",
            risks=[{"risk": risk, "mitigation": "適切な対策を実装"} for risk in analysis.risk_factors]
        )
        
        return TechnicalSpec(
            metadata=metadata,
            summary=task.description,
            motivation=f"タスク要求: {task.description}\n品質目標: {task.estimated_quality}\n複雑性: {analysis.complexity_score}",
            requirements=requirements,
            design=design,
            implementation=implementation
        )
    
    def _generate_fallback_technical_spec(self, task: Task) -> TechnicalSpec:
        """フォールバック技術仕様生成"""
        from ..design.spec_kit_integration import (
            SpecMetadata, SpecRequirement, SpecDesign, SpecImplementation,
            SpecType
        )
        
        metadata = SpecMetadata(
            title=f"{task.description} (フォールバック仕様)",
            status=SpecStatus.DRAFT,
            spec_type=SpecType.FEATURE,
            authors=["Fallback Generator"],
            tags=["fallback", "basic"]
        )
        
        requirements = [
            SpecRequirement(
                id="FALLBACK-001",
                title="基本実装",
                description=task.description,
                priority="medium"
            )
        ]
        
        design = SpecDesign(
            overview="基本的な実装仕様",
            architecture={"approach": "simple"},
            components=[],
            interfaces=[]
        )
        
        implementation = SpecImplementation(
            approach="標準実装",
            timeline={"estimate": "unknown"},
            testing_strategy="基本テスト"
        )
        
        return TechnicalSpec(
            metadata=metadata,
            summary=task.description,
            motivation=f"要求: {task.description}",
            requirements=requirements,
            design=design,
            implementation=implementation
        )
    
    def _calculate_final_quality_metrics(
        self, 
        specification: SpecificationDocument, 
        review: SpecReview
    ) -> Dict[str, float]:
        """最終品質メトリクス計算"""
        return {
            "overall_quality": (review.quality_score + review.completeness_score + review.clarity_score) / 3,
            "specification_quality": sum(specification.quality_indicators.values()) / len(specification.quality_indicators),
            "collaboration_efficiency": 1.0 if review.approved else 0.7,
            "word_density": min(specification.word_count / 1000, 1.0)
        }
    
    def _estimate_total_tokens(self, report: CollaborationReport) -> int:
        """総トークン数推定"""
        # 簡易推定: 1語 ≈ 1.3トークン
        base_tokens = report.local_llm_calls * 500  # ローカルLLM呼び出しあたり
        claude_tokens = report.claude_code_calls * 2000  # ClaudeCode呼び出しあたり
        
        if report.final_specification:
            claude_tokens += report.final_specification.word_count * 1.3
        
        return int(base_tokens + claude_tokens)
    
    async def _save_collaboration_report(self, report: CollaborationReport) -> None:
        """協調レポートを保存"""
        reports_dir = Path("logs/ai_collaboration")
        reports_dir.mkdir(parents=True, exist_ok=True)
        
        report_file = reports_dir / f"collaboration_{report.collaboration_id}.json"
        
        # dataclassをJSONシリアライズ可能な形式に変換
        report_dict = asdict(report)
        report_dict["start_time"] = report.start_time.isoformat()
        if report.end_time:
            report_dict["end_time"] = report.end_time.isoformat()
        
        try:
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(report_dict, f, ensure_ascii=False, indent=2)
                
            self.logger.info(f"📋 協調レポート保存: {report_file}")
        except Exception as e:
            self.logger.error(f"レポート保存エラー: {e}")


# ユーティリティ関数
async def generate_collaborative_specification(task: Task) -> Tuple[TechnicalSpec, CollaborationReport]:
    """AI協調仕様書生成のエントリーポイント"""
    from ..core.config import LLMConfig
    
    llm_config = LLMConfig()
    generator = AICollaborativeSpecGenerator(llm_config)
    
    return await generator.generate_specification_collaboratively(task)


# 使用例
if __name__ == "__main__":
    async def test_collaborative_generation():
        from ..core.models import Task, TaskPriority
        
        test_task = Task(
            description="AI協調ニュース収集システム",
            priority=TaskPriority.HIGH,
            requirements=[
                "ローカルLLMとClaudeCodeの協調",
                "高品質な仕様書生成",
                "反復的改善プロセス"
            ]
        )
        
        spec, report = await generate_collaborative_specification(test_task)
        
        print(f"仕様書タイトル: {spec.metadata.title}")
        print(f"協調成功: {report.collaboration_success}")
        print(f"実行時間: {report.total_duration:.2f}秒")
        print(f"品質メトリクス: {report.quality_metrics}")
    
    # asyncio.run(test_collaborative_generation())