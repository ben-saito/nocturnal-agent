#!/usr/bin/env python3
"""
Code Validator - 生成コードの品質検証システム
実行時エラーをゼロにするための自動検証フレームワーク
"""

import ast
import asyncio
import importlib.util
import logging
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime


@dataclass
class ValidationResult:
    """検証結果"""
    file_path: str
    is_valid: bool
    syntax_errors: List[str]
    import_errors: List[str]
    runtime_errors: List[str]
    quality_score: float
    recommendations: List[str]
    execution_test_passed: bool


@dataclass
class ValidationReport:
    """検証レポート全体"""
    project_path: str
    total_files: int
    valid_files: int
    overall_quality: float
    validation_results: List[ValidationResult]
    critical_issues: List[str]
    recommendations: List[str]
    validation_time: float


class CodeValidator:
    """生成コード品質検証システム"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.validation_history: List[ValidationReport] = []
    
    async def validate_generated_project(self, project_path: str) -> ValidationReport:
        """生成されたプロジェクト全体の検証"""
        self.logger.info(f"🔍 プロジェクト品質検証開始: {project_path}")
        start_time = datetime.now()
        
        project_path = Path(project_path)
        python_files = list(project_path.rglob("*.py"))
        
        validation_results = []
        critical_issues = []
        
        for py_file in python_files:
            self.logger.info(f"📝 ファイル検証: {py_file.name}")
            result = await self._validate_single_file(py_file)
            validation_results.append(result)
            
            if not result.is_valid:
                critical_issues.extend(result.syntax_errors)
                critical_issues.extend(result.import_errors)
                critical_issues.extend(result.runtime_errors)
        
        # 全体品質スコア計算
        valid_files = len([r for r in validation_results if r.is_valid])
        overall_quality = sum(r.quality_score for r in validation_results) / len(validation_results) if validation_results else 0.0
        
        # 全体推奨事項
        recommendations = self._generate_project_recommendations(validation_results)
        
        validation_time = (datetime.now() - start_time).total_seconds()
        
        report = ValidationReport(
            project_path=str(project_path),
            total_files=len(python_files),
            valid_files=valid_files,
            overall_quality=overall_quality,
            validation_results=validation_results,
            critical_issues=critical_issues,
            recommendations=recommendations,
            validation_time=validation_time
        )
        
        self.validation_history.append(report)
        
        self.logger.info(f"✅ プロジェクト検証完了: 品質スコア {overall_quality:.2f}")
        return report
    
    async def _validate_single_file(self, file_path: Path) -> ValidationResult:
        """単一ファイルの詳細検証"""
        syntax_errors = []
        import_errors = []
        runtime_errors = []
        quality_score = 0.0
        recommendations = []
        execution_test_passed = False
        
        try:
            # Step 1: 構文チェック
            syntax_errors = self._check_syntax(file_path)
            
            # Step 2: インポートチェック
            if not syntax_errors:
                import_errors = await self._check_imports(file_path)
            
            # Step 3: 実行テスト（メイン実行可能ファイルのみ）
            if not syntax_errors and not import_errors:
                execution_test_passed, runtime_errors = await self._test_execution(file_path)
            
            # Step 4: 品質スコア計算
            quality_score = self._calculate_quality_score(
                file_path, syntax_errors, import_errors, runtime_errors, execution_test_passed
            )
            
            # Step 5: 推奨事項生成
            recommendations = self._generate_file_recommendations(
                file_path, syntax_errors, import_errors, runtime_errors
            )
            
        except Exception as e:
            self.logger.error(f"ファイル検証エラー {file_path}: {e}")
            syntax_errors.append(f"検証エラー: {e}")
        
        is_valid = len(syntax_errors) == 0 and len(import_errors) == 0 and len(runtime_errors) == 0
        
        return ValidationResult(
            file_path=str(file_path),
            is_valid=is_valid,
            syntax_errors=syntax_errors,
            import_errors=import_errors,
            runtime_errors=runtime_errors,
            quality_score=quality_score,
            recommendations=recommendations,
            execution_test_passed=execution_test_passed
        )
    
    def _check_syntax(self, file_path: Path) -> List[str]:
        """Python構文チェック"""
        errors = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source_code = f.read()
            
            # AST パース
            ast.parse(source_code, filename=str(file_path))
            
        except SyntaxError as e:
            errors.append(f"構文エラー (行 {e.lineno}): {e.msg}")
        except Exception as e:
            errors.append(f"ファイル読み込みエラー: {e}")
        
        return errors
    
    async def _check_imports(self, file_path: Path) -> List[str]:
        """インポートエラーチェック"""
        errors = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source_code = f.read()
            
            # ASTを使ってインポート文を抽出
            tree = ast.parse(source_code)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        try:
                            importlib.import_module(alias.name)
                        except ImportError as e:
                            errors.append(f"インポートエラー: {alias.name} - {e}")
                
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        try:
                            importlib.import_module(node.module)
                        except ImportError as e:
                            errors.append(f"インポートエラー: {node.module} - {e}")
        
        except Exception as e:
            errors.append(f"インポートチェックエラー: {e}")
        
        return errors
    
    async def _test_execution(self, file_path: Path) -> Tuple[bool, List[str]]:
        """実行テスト（安全な環境で）"""
        errors = []
        
        # メイン実行ブロックがある場合のみテスト
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if 'if __name__ == "__main__"' not in content:
                return True, []  # メインブロックがない場合はスキップ
            
            # 一時的な実行環境でテスト
            process = await asyncio.create_subprocess_exec(
                sys.executable, str(file_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=file_path.parent
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=10.0)
                
                if process.returncode != 0:
                    error_output = stderr.decode('utf-8')
                    errors.append(f"実行エラー (終了コード {process.returncode}): {error_output}")
                    return False, errors
                
                return True, []
                
            except asyncio.TimeoutError:
                process.kill()
                errors.append("実行タイムアウト (10秒)")
                return False, errors
        
        except Exception as e:
            errors.append(f"実行テストエラー: {e}")
            return False, errors
    
    def _calculate_quality_score(
        self, 
        file_path: Path, 
        syntax_errors: List[str], 
        import_errors: List[str], 
        runtime_errors: List[str],
        execution_test_passed: bool
    ) -> float:
        """品質スコア計算"""
        base_score = 1.0
        
        # エラーに応じて減点
        base_score -= len(syntax_errors) * 0.3  # 構文エラーは重大
        base_score -= len(import_errors) * 0.2  # インポートエラーは中程度
        base_score -= len(runtime_errors) * 0.25  # 実行エラーは重大
        
        # 実行テスト失敗時は追加減点
        if not execution_test_passed:
            base_score -= 0.1
        
        # ファイルサイズボーナス（適切な長さ）
        try:
            file_size = file_path.stat().st_size
            if 1000 <= file_size <= 10000:  # 1KB-10KB が適切
                base_score += 0.05
        except:
            pass
        
        return max(0.0, min(1.0, base_score))
    
    def _generate_file_recommendations(
        self,
        file_path: Path,
        syntax_errors: List[str],
        import_errors: List[str], 
        runtime_errors: List[str]
    ) -> List[str]:
        """ファイル別推奨事項"""
        recommendations = []
        
        if syntax_errors:
            recommendations.append("構文エラーを修正してください")
        
        if import_errors:
            recommendations.append("不足している依存関係をインストールしてください")
            recommendations.append("requirements.txtの更新を検討してください")
        
        if runtime_errors:
            recommendations.append("実行時エラーの原因を調査し修正してください")
            recommendations.append("エラーハンドリングの追加を検討してください")
        
        # ファイル名ベースの推奨事項
        if file_path.name.endswith('_test.py'):
            recommendations.append("テストケースの追加を検討してください")
        
        if file_path.name == 'main.py':
            recommendations.append("適切なログ設定を確認してください")
        
        return recommendations
    
    def _generate_project_recommendations(self, validation_results: List[ValidationResult]) -> List[str]:
        """プロジェクト全体の推奨事項"""
        recommendations = []
        
        total_files = len(validation_results)
        invalid_files = len([r for r in validation_results if not r.is_valid])
        
        if invalid_files > 0:
            recommendations.append(f"{invalid_files}/{total_files} ファイルに問題があります。優先的に修正してください。")
        
        avg_quality = sum(r.quality_score for r in validation_results) / total_files if total_files > 0 else 0
        
        if avg_quality < 0.8:
            recommendations.append("全体的な品質向上が必要です。コードレビューを実施してください。")
        
        # 共通エラーパターンの特定
        all_import_errors = []
        for result in validation_results:
            all_import_errors.extend(result.import_errors)
        
        if len(all_import_errors) > 3:
            recommendations.append("多数のインポートエラーが検出されました。requirements.txtの見直しが必要です。")
        
        return recommendations
    
    async def generate_validation_report(self, report: ValidationReport, output_path: str = None) -> str:
        """検証レポートの生成"""
        if not output_path:
            output_path = f"validation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        
        report_content = f"""# コード品質検証レポート

## 検証概要
- **プロジェクト**: {report.project_path}
- **検証日時**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- **検証時間**: {report.validation_time:.2f}秒
- **対象ファイル数**: {report.total_files}
- **有効ファイル数**: {report.valid_files}
- **全体品質スコア**: {report.overall_quality:.2f}

## 検証結果サマリー
{'✅ 全ファイル正常' if report.valid_files == report.total_files else f'⚠️ {report.total_files - report.valid_files}個のファイルに問題があります'}

## ファイル別詳細結果

"""
        
        for result in report.validation_results:
            status = "✅ 正常" if result.is_valid else "❌ 要修正"
            report_content += f"""### {Path(result.file_path).name} - {status}
- **品質スコア**: {result.quality_score:.2f}
- **実行テスト**: {'✅ 成功' if result.execution_test_passed else '❌ 失敗'}

"""
            
            if result.syntax_errors:
                report_content += f"""**構文エラー**:
{chr(10).join(f"- {error}" for error in result.syntax_errors)}

"""
            
            if result.import_errors:
                report_content += f"""**インポートエラー**:
{chr(10).join(f"- {error}" for error in result.import_errors)}

"""
            
            if result.runtime_errors:
                report_content += f"""**実行エラー**:
{chr(10).join(f"- {error}" for error in result.runtime_errors)}

"""
            
            if result.recommendations:
                report_content += f"""**推奨事項**:
{chr(10).join(f"- {rec}" for rec in result.recommendations)}

"""
        
        if report.critical_issues:
            report_content += f"""## 🚨 重要な問題

{chr(10).join(f"- {issue}" for issue in report.critical_issues)}

"""
        
        if report.recommendations:
            report_content += f"""## 📋 推奨事項

{chr(10).join(f"- {rec}" for rec in report.recommendations)}

"""
        
        report_content += f"""## 総評

{'🎉 このプロジェクトは品質基準を満たしています。' if report.overall_quality >= 0.8 else '⚠️ このプロジェクトには改善が必要な箇所があります。'}

**次のステップ**:
1. 上記の問題を修正してください
2. 修正後に再度検証を実行してください
3. 品質スコア0.8以上を目指してください

---
生成日時: {datetime.now().isoformat()}
"""
        
        # レポートファイル保存
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report_content)
        
        self.logger.info(f"📄 検証レポート生成: {output_path}")
        return output_path


# ユーティリティ関数
async def validate_project(project_path: str) -> ValidationReport:
    """プロジェクト検証のメイン関数"""
    validator = CodeValidator()
    return await validator.validate_generated_project(project_path)


# CLI実行用
async def main():
    """CLI実行"""
    import argparse
    
    parser = argparse.ArgumentParser(description="コード品質検証システム")
    parser.add_argument("project_path", help="検証するプロジェクトのパス")
    parser.add_argument("--output", "-o", help="レポート出力パス")
    
    args = parser.parse_args()
    
    # ログ設定
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    validator = CodeValidator()
    report = await validator.validate_generated_project(args.project_path)
    
    # レポート生成
    report_path = await validator.generate_validation_report(report, args.output)
    
    print(f"\n🔍 検証完了!")
    print(f"📊 品質スコア: {report.overall_quality:.2f}")
    print(f"📄 レポート: {report_path}")
    
    if report.overall_quality < 0.8:
        print("⚠️ 品質基準未達。修正が必要です。")
        sys.exit(1)
    else:
        print("✅ 品質基準クリア!")


if __name__ == "__main__":
    asyncio.run(main())