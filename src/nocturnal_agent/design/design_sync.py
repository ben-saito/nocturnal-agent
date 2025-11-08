"""
設計書とコードの同期システム
コード解析結果と設計書を比較し、差分を設計書に反映する
"""

import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from datetime import datetime
import logging

from .code_analyzer import CodeAnalyzer, CodeAnalysisResult, CodeComponent
from .design_file_manager import DesignFileManager


@dataclass
class DesignDiff:
    """設計書とコードの差分"""
    type: str  # 'added', 'removed', 'modified', 'mismatch'
    component_name: str
    component_type: str
    design_value: Optional[Any] = None
    code_value: Optional[Any] = None
    file_path: Optional[str] = None
    description: str = ""


class DesignSyncManager:
    """設計書とコードの同期管理"""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.design_manager = DesignFileManager(logger)
    
    def sync_design_from_code(
        self,
        design_file_path: Path,
        workspace_path: Path,
        dry_run: bool = False,
        auto_apply: bool = False,
        quiet: bool = False
    ) -> List[DesignDiff]:
        """コードを解析して設計書に反映"""
        
        # 設計書を読み込み
        design = self._load_design_file(design_file_path)
        if not design:
            return []
        
        # コードを解析
        if not quiet:
            self.logger.info(f"コードベースを解析中: {workspace_path}")
        analyzer = CodeAnalyzer(str(workspace_path))
        code_analysis = analyzer.analyze_codebase()
        
        # 差分を検出
        diffs = self._detect_differences(design, code_analysis)
        
        if not diffs:
            if not quiet:
                self.logger.info("✅ 設計書とコードに差分はありません")
            return []
        
        # 差分を表示（quietモードでない場合）
        if not quiet:
            self._print_diffs(diffs)
        
        if dry_run:
            if not quiet:
                self.logger.info("🔍 Dry-runモード: 設計書は更新されませんでした")
            return diffs
        
        # 設計書を更新
        if auto_apply or (not quiet and self._confirm_update()):
            updated_design = self._apply_diffs(design, code_analysis, diffs)
            self._save_design_file(design_file_path, updated_design, backup=True)
            if not quiet:
                self.logger.info(f"✅ 設計書を更新しました: {design_file_path}")
        else:
            if not quiet:
                self.logger.info("❌ 設計書の更新がキャンセルされました")
        
        return diffs
    
    def _load_design_file(self, design_file_path: Path) -> Optional[Dict]:
        """設計書を読み込み"""
        try:
            with open(design_file_path, 'r', encoding='utf-8') as f:
                design = yaml.safe_load(f)
            return design
        except Exception as e:
            self.logger.error(f"設計書読み込みエラー: {e}")
            return None
    
    def _detect_differences(
        self,
        design: Dict,
        code_analysis: CodeAnalysisResult
    ) -> List[DesignDiff]:
        """設計書とコードの差分を検出"""
        diffs = []
        
        # 技術スタックの差分
        design_tech = set(design.get('technology_stack', {}).get('frontend', {}).get('framework', []))
        design_tech.update(design.get('technology_stack', {}).get('backend', {}).get('framework', []))
        
        code_tech = code_analysis.technologies
        
        for tech in code_tech:
            if tech not in design_tech:
                diffs.append(DesignDiff(
                    type='added',
                    component_name=tech,
                    component_type='technology',
                    code_value=tech,
                    description=f"コードで検出された技術スタック: {tech}"
                ))
        
        # コンポーネントの差分
        design_components = self._extract_design_components(design)
        code_components = {c.name: c for c in code_analysis.components}
        
        # コードに存在するが設計書にないコンポーネント
        for name, component in code_components.items():
            if name not in design_components:
                diffs.append(DesignDiff(
                    type='added',
                    component_name=name,
                    component_type=component.type,
                    code_value=component,
                    file_path=component.file_path,
                    description=f"コードで実装されているが設計書に記載されていない: {name}"
                ))
        
        # 設計書に存在するがコードにないコンポーネント
        for name in design_components:
            if name not in code_components:
                diffs.append(DesignDiff(
                    type='removed',
                    component_name=name,
                    component_type='component',
                    design_value=design_components[name],
                    description=f"設計書に記載されているがコードに実装されていない: {name}"
                ))
        
        # 実装計画の更新
        implementation_plan = design.get('implementation_plan', {})
        priority_components = implementation_plan.get('priority_components', [])
        
        # 実装済みコンポーネントを検出
        implemented_components = set(code_components.keys())
        for comp in priority_components:
            comp_name = comp.get('name', '')
            if comp_name in implemented_components:
                if comp.get('status') != 'completed':
                    diffs.append(DesignDiff(
                        type='modified',
                        component_name=comp_name,
                        component_type='implementation_status',
                        design_value=comp.get('status', 'pending'),
                        code_value='completed',
                        description=f"実装が完了しているが設計書では未完了: {comp_name}"
                    ))
        
        return diffs
    
    def _extract_design_components(self, design: Dict) -> Dict[str, Any]:
        """設計書からコンポーネント情報を抽出"""
        components = {}
        
        # architecture.componentsから抽出
        architecture = design.get('architecture', {})
        arch_components = architecture.get('components', [])
        for comp in arch_components:
            name = comp.get('name', '')
            if name:
                components[name] = comp
        
        # implementation_planから抽出
        implementation_plan = design.get('implementation_plan', {})
        priority_components = implementation_plan.get('priority_components', [])
        for comp in priority_components:
            name = comp.get('name', '')
            if name and name not in components:
                components[name] = comp
        
        return components
    
    def _print_diffs(self, diffs: List[DesignDiff]):
        """差分を表示"""
        if not diffs:
            return
        
        print("\n" + "="*80)
        print("📊 設計書とコードの差分検出結果")
        print("="*80)
        
        added = [d for d in diffs if d.type == 'added']
        removed = [d for d in diffs if d.type == 'removed']
        modified = [d for d in diffs if d.type == 'modified']
        
        if added:
            print(f"\n➕ 追加されたコンポーネント ({len(added)}件):")
            for diff in added:
                print(f"  - {diff.component_name} ({diff.component_type})")
                if diff.file_path:
                    print(f"    ファイル: {diff.file_path}")
                print(f"    {diff.description}")
        
        if removed:
            print(f"\n➖ 削除されたコンポーネント ({len(removed)}件):")
            for diff in removed:
                print(f"  - {diff.component_name}")
                print(f"    {diff.description}")
        
        if modified:
            print(f"\n🔄 変更されたコンポーネント ({len(modified)}件):")
            for diff in modified:
                print(f"  - {diff.component_name}")
                print(f"    設計書: {diff.design_value}")
                print(f"    コード: {diff.code_value}")
                print(f"    {diff.description}")
        
        print("\n" + "="*80)
    
    def _confirm_update(self) -> bool:
        """更新の確認"""
        try:
            response = input("\n設計書を更新しますか？ (y/N): ").strip().lower()
            return response in ('y', 'yes')
        except:
            return False
    
    def _apply_diffs(
        self,
        design: Dict,
        code_analysis: CodeAnalysisResult,
        diffs: List[DesignDiff]
    ) -> Dict:
        """差分を設計書に適用"""
        updated_design = design.copy()
        
        # 技術スタックを更新
        tech_diffs = [d for d in diffs if d.component_type == 'technology' and d.type == 'added']
        if tech_diffs:
            tech_stack = updated_design.setdefault('technology_stack', {})
            for diff in tech_diffs:
                tech_name = diff.component_name.lower()
                if 'react' in tech_name or 'vue' in tech_name or 'angular' in tech_name:
                    frontend = tech_stack.setdefault('frontend', {})
                    if 'framework' not in frontend:
                        frontend['framework'] = []
                    if diff.component_name not in frontend['framework']:
                        frontend['framework'].append(diff.component_name)
                elif 'flask' in tech_name or 'django' in tech_name or 'fastapi' in tech_name:
                    backend = tech_stack.setdefault('backend', {})
                    if 'framework' not in backend:
                        backend['framework'] = []
                    if diff.component_name not in backend['framework']:
                        backend['framework'].append(diff.component_name)
        
        # コンポーネントを追加
        added_comps = [d for d in diffs if d.type == 'added' and d.component_type in ('function', 'class')]
        if added_comps:
            architecture = updated_design.setdefault('architecture', {})
            components = architecture.setdefault('components', [])
            
            for diff in added_comps:
                comp_info = diff.code_value
                if isinstance(comp_info, CodeComponent):
                    new_comp = {
                        'name': comp_info.name,
                        'type': 'Code' if comp_info.type == 'class' else 'Function',
                        'description': comp_info.description or f"実装済み{comp_info.type}",
                        'file_path': comp_info.file_path,
                        'status': 'implemented'
                    }
                    # 既存のコンポーネントと重複チェック
                    if not any(c.get('name') == new_comp['name'] for c in components):
                        components.append(new_comp)
        
        # 実装計画を更新
        modified_status = [d for d in diffs if d.type == 'modified' and d.component_type == 'implementation_status']
        if modified_status:
            implementation_plan = updated_design.setdefault('implementation_plan', {})
            priority_components = implementation_plan.setdefault('priority_components', [])
            
            for diff in modified_status:
                for comp in priority_components:
                    if comp.get('name') == diff.component_name:
                        comp['status'] = 'completed'
                        comp['completed_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        break
        
        # メタデータを更新
        metadata = updated_design.setdefault('metadata', {})
        metadata['last_synced_at'] = datetime.now().isoformat()
        metadata['sync_source'] = 'code_analysis'
        
        return updated_design
    
    def _save_design_file(
        self,
        design_file_path: Path,
        design: Dict,
        backup: bool = True
    ):
        """設計書を保存（バックアップ付き）"""
        if backup:
            backup_path = design_file_path.with_suffix(
                f".backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.yaml"
            )
            try:
                with open(design_file_path, 'r', encoding='utf-8') as f:
                    backup_content = f.read()
                with open(backup_path, 'w', encoding='utf-8') as f:
                    f.write(backup_content)
                self.logger.info(f"📦 バックアップ作成: {backup_path}")
            except Exception as e:
                self.logger.warning(f"バックアップ作成エラー: {e}")
        
        # 設計書を保存
        self.design_manager.save_design_file(design, design_file_path)
