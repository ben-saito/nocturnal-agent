#!/usr/bin/env python3
"""
Auto Fixer - 生成コードの自動修正システム
検出されたエラーを自動的に修正する高度な品質保証システム
"""

import ast
import re
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from code_validator import ValidationResult, CodeValidator


@dataclass
class FixResult:
    """修正結果"""
    file_path: str
    original_content: str
    fixed_content: str
    fixes_applied: List[str]
    success: bool
    remaining_issues: List[str]


class AutoFixer:
    """自動コード修正システム"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.fix_patterns = self._initialize_fix_patterns()
    
    def _initialize_fix_patterns(self) -> Dict[str, Dict]:
        """修正パターンの初期化"""
        return {
            # JSONロード問題の修正
            "json_config_targets": {
                "pattern": r"return json\.load\(f\)",
                "replacement": "config = json.load(f)\n            return config.get('targets', [])",
                "description": "JSONファイルからtargetsキーを正しく取得"
            },
            
            # 変数名未定義エラーの修正
            "undefined_variable_url": {
                "pattern": r'print\(f"❌ スクレイピングエラー \({url}\): \{e\}"\)',
                "replacement": 'print(f"❌ スクレイピングエラー ({target.get(\'url\', \'unknown\')}): {e}")',
                "description": "未定義変数urlをtarget['url']で置換"
            },
            
            # インポートエラーの修正
            "relative_import_fix": {
                "pattern": r"from src\.",
                "replacement": "from .",
                "description": "相対インポートパスの修正"
            },
            
            # 文字列フォーマットエラーの修正
            "string_format_brace": {
                "pattern": r'\{e\}(?="\))',
                "replacement": r'{e}',
                "description": "文字列フォーマットの波括弧修正"
            }
        }
    
    async def auto_fix_file(self, file_path: Path, validation_result: ValidationResult) -> FixResult:
        """単一ファイルの自動修正"""
        self.logger.info(f"🔧 自動修正開始: {file_path.name}")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                original_content = f.read()
            
            fixed_content = original_content
            fixes_applied = []
            remaining_issues = []
            
            # 各エラータイプに対する修正を試行
            for error in validation_result.syntax_errors + validation_result.runtime_errors:
                fix_result = self._apply_smart_fix(fixed_content, error, str(file_path))
                if fix_result:
                    fixed_content = fix_result[0]
                    fixes_applied.append(fix_result[1])
                else:
                    remaining_issues.append(error)
            
            # パターンマッチング修正
            for pattern_name, pattern_info in self.fix_patterns.items():
                if re.search(pattern_info["pattern"], fixed_content):
                    fixed_content = re.sub(
                        pattern_info["pattern"], 
                        pattern_info["replacement"], 
                        fixed_content
                    )
                    fixes_applied.append(pattern_info["description"])
            
            # 修正結果を保存
            success = len(fixes_applied) > 0
            if success:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(fixed_content)
                self.logger.info(f"✅ 自動修正完了: {len(fixes_applied)}件の修正")
            
            return FixResult(
                file_path=str(file_path),
                original_content=original_content,
                fixed_content=fixed_content,
                fixes_applied=fixes_applied,
                success=success,
                remaining_issues=remaining_issues
            )
            
        except Exception as e:
            self.logger.error(f"自動修正エラー {file_path}: {e}")
            return FixResult(
                file_path=str(file_path),
                original_content="",
                fixed_content="",
                fixes_applied=[],
                success=False,
                remaining_issues=[f"修正エラー: {e}"]
            )
    
    def _apply_smart_fix(self, content: str, error: str, file_path: str) -> Optional[Tuple[str, str]]:
        """エラー内容に基づくスマート修正"""
        
        # AttributeError: 'str' object has no attribute 'get'
        if "'str' object has no attribute 'get'" in error:
            # JSONロードの修正
            if "json.load(f)" in content:
                fixed_content = content.replace(
                    "return json.load(f)",
                    "config = json.load(f)\n            return config.get('targets', [])"
                )
                return fixed_content, "JSONファイル読み込み時のtargetsキー取得修正"
        
        # NameError: name 'url' is not defined
        if "name 'url' is not defined" in error:
            # 未定義変数の修正
            pattern = r'print\(f"❌ スクレイピングエラー \({url}\): \{e\}"\)'
            if re.search(pattern, content):
                fixed_content = re.sub(
                    pattern,
                    'print(f"❌ スクレイピングエラー ({target.get(\'url\', \'unknown\')}): {e}")',
                    content
                )
                return fixed_content, "未定義変数urlをtarget['url']で修正"
        
        # ImportError修正
        if "No module named 'src'" in error:
            # 相対インポートパスの修正
            fixed_content = content.replace("from src.", "from .")
            if fixed_content != content:
                return fixed_content, "相対インポートパス修正"
        
        return None
    
    async def auto_fix_project(self, project_path: str) -> Dict[str, FixResult]:
        """プロジェクト全体の自動修正"""
        self.logger.info(f"🔧 プロジェクト自動修正開始: {project_path}")
        
        # 最初に品質検証を実行
        validator = CodeValidator()
        validation_report = await validator.validate_generated_project(project_path)
        
        fix_results = {}
        
        # 問題があるファイルのみ修正
        for validation_result in validation_report.validation_results:
            if not validation_result.is_valid:
                file_path = Path(validation_result.file_path)
                fix_result = await self.auto_fix_file(file_path, validation_result)
                fix_results[str(file_path)] = fix_result
        
        # 修正後に再検証
        if fix_results:
            self.logger.info("🔍 修正後の再検証実行中...")
            final_validation = await validator.validate_generated_project(project_path)
            
            self.logger.info(f"📊 修正結果:")
            self.logger.info(f"  - 修正前品質: {validation_report.overall_quality:.2f}")
            self.logger.info(f"  - 修正後品質: {final_validation.overall_quality:.2f}")
            self.logger.info(f"  - 修正ファイル数: {len(fix_results)}")
        
        return fix_results
    
    def generate_fix_report(self, fix_results: Dict[str, FixResult], output_path: str = None) -> str:
        """修正レポートの生成"""
        if not output_path:
            from datetime import datetime
            output_path = f"auto_fix_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        
        report_content = f"""# 自動修正レポート

## 修正概要
- **修正対象ファイル数**: {len(fix_results)}
- **修正成功ファイル数**: {len([r for r in fix_results.values() if r.success])}
- **総修正件数**: {sum(len(r.fixes_applied) for r in fix_results.values())}

## ファイル別修正結果

"""
        
        for file_path, fix_result in fix_results.items():
            status = "✅ 修正成功" if fix_result.success else "❌ 修正失敗"
            report_content += f"""### {Path(file_path).name} - {status}

"""
            
            if fix_result.fixes_applied:
                report_content += f"""**適用された修正**:
{chr(10).join(f"- {fix}" for fix in fix_result.fixes_applied)}

"""
            
            if fix_result.remaining_issues:
                report_content += f"""**残存問題**:
{chr(10).join(f"- {issue}" for issue in fix_result.remaining_issues)}

"""
        
        # レポートファイル保存
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report_content)
        
        self.logger.info(f"📄 修正レポート生成: {output_path}")
        return output_path


# 統合品質保証クラス
class IntegratedQualityAssurance:
    """統合品質保証システム"""
    
    def __init__(self):
        self.validator = CodeValidator()
        self.auto_fixer = AutoFixer()
        self.logger = logging.getLogger(__name__)
    
    async def ensure_code_quality(self, project_path: str, max_iterations: int = 3) -> Dict:
        """コード品質保証（検証→修正→再検証のループ）"""
        self.logger.info(f"🎯 統合品質保証開始: {project_path}")
        
        iteration = 0
        results = []
        
        while iteration < max_iterations:
            iteration += 1
            self.logger.info(f"📍 品質保証サイクル {iteration}/{max_iterations}")
            
            # 検証実行
            validation_report = await self.validator.validate_generated_project(project_path)
            
            self.logger.info(f"品質スコア: {validation_report.overall_quality:.2f}")
            
            # 品質基準達成なら完了
            if validation_report.overall_quality >= 0.8:
                self.logger.info("✅ 品質基準達成！")
                results.append({
                    "iteration": iteration,
                    "quality_score": validation_report.overall_quality,
                    "status": "passed"
                })
                break
            
            # 修正実行
            self.logger.info("🔧 自動修正実行中...")
            fix_results = await self.auto_fixer.auto_fix_project(project_path)
            
            results.append({
                "iteration": iteration,
                "quality_score": validation_report.overall_quality,
                "fixes_applied": sum(len(r.fixes_applied) for r in fix_results.values()),
                "status": "fixed"
            })
            
            if not fix_results:
                self.logger.warning("修正可能な問題が見つかりませんでした")
                break
        
        # 最終検証
        final_validation = await self.validator.validate_generated_project(project_path)
        
        summary = {
            "final_quality_score": final_validation.overall_quality,
            "iterations_used": iteration,
            "quality_target_met": final_validation.overall_quality >= 0.8,
            "iteration_results": results
        }
        
        self.logger.info(f"🏁 品質保証完了: 最終スコア {final_validation.overall_quality:.2f}")
        
        return summary


# CLI用メイン関数
async def main():
    """CLI実行"""
    import argparse
    
    parser = argparse.ArgumentParser(description="自動修正システム")
    parser.add_argument("project_path", help="修正するプロジェクトのパス")
    parser.add_argument("--integrated", "-i", action="store_true", help="統合品質保証モード")
    
    args = parser.parse_args()
    
    # ログ設定
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    if args.integrated:
        # 統合品質保証
        qa_system = IntegratedQualityAssurance()
        summary = await qa_system.ensure_code_quality(args.project_path)
        
        print(f"\n🎯 統合品質保証完了!")
        print(f"📊 最終品質スコア: {summary['final_quality_score']:.2f}")
        print(f"🔄 使用サイクル数: {summary['iterations_used']}")
        print(f"✅ 品質目標達成: {'Yes' if summary['quality_target_met'] else 'No'}")
    else:
        # 自動修正のみ
        auto_fixer = AutoFixer()
        fix_results = await auto_fixer.auto_fix_project(args.project_path)
        
        success_count = len([r for r in fix_results.values() if r.success])
        total_fixes = sum(len(r.fixes_applied) for r in fix_results.values())
        
        print(f"\n🔧 自動修正完了!")
        print(f"📊 修正ファイル数: {success_count}/{len(fix_results)}")
        print(f"🛠️ 総修正件数: {total_fixes}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())