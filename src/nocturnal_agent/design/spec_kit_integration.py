"""GitHub Spec Kit統合システム - 構造化タスク仕様管理"""

import yaml
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, asdict
from enum import Enum

from ..core.models import Task, TaskPriority


class SpecStatus(Enum):
    """仕様ステータス"""
    DRAFT = "draft"
    REVIEW = "review"
    APPROVED = "approved"
    IMPLEMENTED = "implemented"
    DEPRECATED = "deprecated"


class SpecType(Enum):
    """仕様タイプ"""
    FEATURE = "feature"
    ARCHITECTURE = "architecture"
    API = "api"
    DESIGN = "design"
    PROCESS = "process"


@dataclass
class SpecMetadata:
    """Spec Kit メタデータ"""
    title: str
    status: SpecStatus
    spec_type: SpecType
    authors: List[str]
    reviewers: List[str] = None
    created_at: str = None
    updated_at: str = None
    version: str = "1.0.0"
    tags: List[str] = None
    related_specs: List[str] = None
    
    def __post_init__(self):
        if self.reviewers is None:
            self.reviewers = []
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()
        if self.updated_at is None:
            self.updated_at = datetime.now().isoformat()
        if self.tags is None:
            self.tags = []
        if self.related_specs is None:
            self.related_specs = []


@dataclass
class SpecRequirement:
    """仕様要件"""
    id: str
    title: str
    description: str
    priority: str = "medium"  # high, medium, low
    acceptance_criteria: List[str] = None
    dependencies: List[str] = None
    
    def __post_init__(self):
        if self.acceptance_criteria is None:
            self.acceptance_criteria = []
        if self.dependencies is None:
            self.dependencies = []


@dataclass
class SpecDesign:
    """設計仕様"""
    overview: str
    architecture: Dict[str, Any] = None
    components: List[Dict[str, Any]] = None
    interfaces: List[Dict[str, Any]] = None
    data_models: List[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.architecture is None:
            self.architecture = {}
        if self.components is None:
            self.components = []
        if self.interfaces is None:
            self.interfaces = []
        if self.data_models is None:
            self.data_models = []


@dataclass
class SpecImplementation:
    """実装仕様"""
    approach: str
    timeline: Dict[str, str] = None
    milestones: List[Dict[str, Any]] = None
    risks: List[Dict[str, str]] = None
    testing_strategy: str = None
    
    def __post_init__(self):
        if self.timeline is None:
            self.timeline = {}
        if self.milestones is None:
            self.milestones = []
        if self.risks is None:
            self.risks = []


@dataclass
class TechnicalSpec:
    """技術仕様（Spec Kit準拠）"""
    metadata: SpecMetadata
    summary: str
    motivation: str
    requirements: List[SpecRequirement]
    design: SpecDesign
    implementation: SpecImplementation
    alternatives_considered: List[str] = None
    references: List[str] = None
    
    def __post_init__(self):
        if self.alternatives_considered is None:
            self.alternatives_considered = []
        if self.references is None:
            self.references = []


class SpecKitManager:
    """Spec Kit管理システム"""
    
    def __init__(self, specs_directory: str = "./specs"):
        self.specs_dir = Path(specs_directory)
        self.specs_dir.mkdir(parents=True, exist_ok=True)
        
        # Spec Kit標準ディレクトリ構造
        self.templates_dir = self.specs_dir / "templates"
        self.features_dir = self.specs_dir / "features"
        self.architecture_dir = self.specs_dir / "architecture"
        self.apis_dir = self.specs_dir / "apis"
        self.designs_dir = self.specs_dir / "designs"
        self.processes_dir = self.specs_dir / "processes"
        
        self._create_directory_structure()
        self._create_spec_templates()
    
    def _create_directory_structure(self):
        """Spec Kit標準ディレクトリ構造作成"""
        directories = [
            self.templates_dir,
            self.features_dir,
            self.architecture_dir,
            self.apis_dir,
            self.designs_dir,
            self.processes_dir
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
    
    def _create_spec_templates(self):
        """仕様テンプレート作成"""
        templates = {
            "feature_template.yaml": self._get_feature_template(),
            "architecture_template.yaml": self._get_architecture_template(),
            "api_template.yaml": self._get_api_template(),
            "design_template.yaml": self._get_design_template()
        }
        
        for template_name, template_content in templates.items():
            template_path = self.templates_dir / template_name
            if not template_path.exists():
                with open(template_path, 'w', encoding='utf-8') as f:
                    yaml.dump(template_content, f, allow_unicode=True, default_flow_style=False)
    
    def create_spec_from_task(self, task: Task, spec_type: SpecType = SpecType.FEATURE) -> TechnicalSpec:
        """タスクからSpec Kit仕様を生成"""
        
        # メタデータ作成
        metadata = SpecMetadata(
            title=f"{task.description}の技術仕様",
            status=SpecStatus.DRAFT,
            spec_type=spec_type,
            authors=["Nocturnal Agent"],
            tags=[task.priority.value, "automated"]
        )
        
        # 要件抽出
        requirements = []
        if task.requirements:
            for i, req_text in enumerate(task.requirements):
                requirement = SpecRequirement(
                    id=f"REQ-{i+1:03d}",
                    title=f"要件 {i+1}",
                    description=req_text,
                    priority=self._map_task_priority_to_spec(task.priority)
                )
                requirements.append(requirement)
        
        # 設計概要
        design = SpecDesign(
            overview=f"""
            {task.description}の実装に向けた設計仕様。
            
            推定品質スコア: {task.estimated_quality}
            最小品質閾値: {task.minimum_quality_threshold}
            """,
            architecture={
                "approach": "モジュラー設計",
                "quality_target": task.estimated_quality,
                "quality_threshold": task.minimum_quality_threshold
            }
        )
        
        # 実装計画
        implementation = SpecImplementation(
            approach="段階的実装アプローチ",
            timeline={
                "planning": "1日",
                "implementation": "2-3日", 
                "testing": "1日",
                "review": "1日"
            },
            testing_strategy="単体テスト + 統合テスト + 品質検証"
        )
        
        # 技術仕様作成
        spec = TechnicalSpec(
            metadata=metadata,
            summary=f"Task: {task.description}の実装仕様",
            motivation=f"タスクID {task.id} の品質要件を満たした実装を行う",
            requirements=requirements,
            design=design,
            implementation=implementation
        )
        
        return spec
    
    def save_spec(self, spec: TechnicalSpec, filename: Optional[str] = None) -> Path:
        """仕様をファイルに保存"""
        if filename is None:
            safe_title = self._sanitize_filename(spec.metadata.title)
            filename = f"{safe_title}_{datetime.now().strftime('%Y%m%d')}.yaml"
        
        # 保存ディレクトリの決定
        if spec.metadata.spec_type == SpecType.FEATURE:
            target_dir = self.features_dir
        elif spec.metadata.spec_type == SpecType.ARCHITECTURE:
            target_dir = self.architecture_dir
        elif spec.metadata.spec_type == SpecType.API:
            target_dir = self.apis_dir
        elif spec.metadata.spec_type == SpecType.DESIGN:
            target_dir = self.designs_dir
        else:
            target_dir = self.processes_dir
        
        spec_path = target_dir / filename
        
        # YAML形式で保存
        spec_dict = asdict(spec)
        # Enumを文字列に変換
        spec_dict['metadata']['status'] = spec.metadata.status.value
        spec_dict['metadata']['spec_type'] = spec.metadata.spec_type.value
        
        with open(spec_path, 'w', encoding='utf-8') as f:
            yaml.dump(spec_dict, f, allow_unicode=True, default_flow_style=False, indent=2)
        
        return spec_path
    
    def load_spec(self, spec_path: Union[str, Path]) -> TechnicalSpec:
        """仕様ファイルを読み込み"""
        spec_path = Path(spec_path)
        
        with open(spec_path, 'r', encoding='utf-8') as f:
            spec_dict = yaml.safe_load(f)
        
        # Enumの復元
        spec_dict['metadata']['status'] = SpecStatus(spec_dict['metadata']['status'])
        spec_dict['metadata']['spec_type'] = SpecType(spec_dict['metadata']['spec_type'])
        
        # ネストしたオブジェクトの復元
        metadata = SpecMetadata(**spec_dict['metadata'])
        requirements = [SpecRequirement(**req) for req in spec_dict['requirements']]
        design = SpecDesign(**spec_dict['design'])
        implementation = SpecImplementation(**spec_dict['implementation'])
        
        spec = TechnicalSpec(
            metadata=metadata,
            summary=spec_dict['summary'],
            motivation=spec_dict['motivation'],
            requirements=requirements,
            design=design,
            implementation=implementation,
            alternatives_considered=spec_dict.get('alternatives_considered', []),
            references=spec_dict.get('references', [])
        )
        
        return spec
    
    def list_specs(self, spec_type: Optional[SpecType] = None, 
                  status: Optional[SpecStatus] = None) -> List[Dict[str, Any]]:
        """仕様一覧取得"""
        specs = []
        
        # 検索対象ディレクトリ
        search_dirs = []
        if spec_type:
            if spec_type == SpecType.FEATURE:
                search_dirs = [self.features_dir]
            elif spec_type == SpecType.ARCHITECTURE:
                search_dirs = [self.architecture_dir]
            elif spec_type == SpecType.API:
                search_dirs = [self.apis_dir]
            elif spec_type == SpecType.DESIGN:
                search_dirs = [self.designs_dir]
            else:
                search_dirs = [self.processes_dir]
        else:
            search_dirs = [
                self.features_dir, self.architecture_dir, 
                self.apis_dir, self.designs_dir, self.processes_dir
            ]
        
        for search_dir in search_dirs:
            for spec_file in search_dir.glob("*.yaml"):
                try:
                    spec = self.load_spec(spec_file)
                    
                    # ステータスフィルタ
                    if status and spec.metadata.status != status:
                        continue
                    
                    specs.append({
                        'file_path': str(spec_file),
                        'title': spec.metadata.title,
                        'status': spec.metadata.status.value,
                        'spec_type': spec.metadata.spec_type.value,
                        'authors': spec.metadata.authors,
                        'created_at': spec.metadata.created_at,
                        'updated_at': spec.metadata.updated_at
                    })
                except Exception as e:
                    # 読み込みエラーの場合はスキップ
                    continue
        
        return sorted(specs, key=lambda x: x['updated_at'], reverse=True)
    
    def update_spec_status(self, spec_path: Union[str, Path], new_status: SpecStatus) -> bool:
        """仕様ステータス更新"""
        try:
            spec = self.load_spec(spec_path)
            spec.metadata.status = new_status
            spec.metadata.updated_at = datetime.now().isoformat()
            self.save_spec(spec, Path(spec_path).name)
            return True
        except Exception:
            return False
    
    def generate_spec_markdown(self, spec: TechnicalSpec) -> str:
        """仕様のMarkdown生成（GitHub形式）"""
        markdown = f"""# {spec.metadata.title}

**Status:** {spec.metadata.status.value.title()}  
**Type:** {spec.metadata.spec_type.value.title()}  
**Authors:** {', '.join(spec.metadata.authors)}  
**Version:** {spec.metadata.version}  
**Created:** {spec.metadata.created_at}  
**Updated:** {spec.metadata.updated_at}  

## Summary

{spec.summary}

## Motivation

{spec.motivation}

## Requirements

"""
        
        for req in spec.requirements:
            markdown += f"""### {req.title} (`{req.id}`)

**Priority:** {req.priority.title()}

{req.description}

"""
            if req.acceptance_criteria:
                markdown += "**Acceptance Criteria:**\n"
                for criteria in req.acceptance_criteria:
                    markdown += f"- {criteria}\n"
                markdown += "\n"
        
        markdown += f"""## Design

### Overview

{spec.design.overview}

"""
        
        if spec.design.architecture:
            markdown += "### Architecture\n\n"
            for key, value in spec.design.architecture.items():
                markdown += f"- **{key.title()}:** {value}\n"
            markdown += "\n"
        
        if spec.design.components:
            markdown += "### Components\n\n"
            for component in spec.design.components:
                markdown += f"- **{component.get('name', 'Unknown')}:** {component.get('description', '')}\n"
            markdown += "\n"
        
        markdown += f"""## Implementation

### Approach

{spec.implementation.approach}

"""
        
        if spec.implementation.timeline:
            markdown += "### Timeline\n\n"
            for phase, duration in spec.implementation.timeline.items():
                markdown += f"- **{phase.title()}:** {duration}\n"
            markdown += "\n"
        
        if spec.implementation.risks:
            markdown += "### Risks\n\n"
            for risk in spec.implementation.risks:
                markdown += f"- **{risk.get('risk', 'Unknown')}:** {risk.get('mitigation', 'TBD')}\n"
            markdown += "\n"
        
        if spec.alternatives_considered:
            markdown += "## Alternatives Considered\n\n"
            for alt in spec.alternatives_considered:
                markdown += f"- {alt}\n"
            markdown += "\n"
        
        if spec.references:
            markdown += "## References\n\n"
            for ref in spec.references:
                markdown += f"- {ref}\n"
        
        return markdown
    
    def _map_task_priority_to_spec(self, task_priority: TaskPriority) -> str:
        """タスク優先度から仕様優先度へのマッピング"""
        mapping = {
            TaskPriority.HIGH: "high",
            TaskPriority.MEDIUM: "medium", 
            TaskPriority.LOW: "low"
        }
        return mapping.get(task_priority, "medium")
    
    def _sanitize_filename(self, title: str) -> str:
        """ファイル名用文字列サニタイズ"""
        import re
        # 英数字、ハイフン、アンダースコアのみ許可
        safe_title = re.sub(r'[^\w\-_\s]', '', title)
        safe_title = re.sub(r'\s+', '_', safe_title.strip())
        return safe_title[:50]  # 最大50文字
    
    def _get_feature_template(self) -> Dict[str, Any]:
        """機能仕様テンプレート"""
        return {
            'metadata': {
                'title': 'Feature Title',
                'status': 'draft',
                'spec_type': 'feature',
                'authors': ['Author Name'],
                'reviewers': [],
                'version': '1.0.0',
                'tags': [],
                'related_specs': []
            },
            'summary': 'Brief summary of the feature',
            'motivation': 'Why is this feature needed?',
            'requirements': [
                {
                    'id': 'REQ-001',
                    'title': 'Requirement Title',
                    'description': 'Detailed requirement description',
                    'priority': 'medium',
                    'acceptance_criteria': [],
                    'dependencies': []
                }
            ],
            'design': {
                'overview': 'Design overview',
                'architecture': {},
                'components': [],
                'interfaces': [],
                'data_models': []
            },
            'implementation': {
                'approach': 'Implementation approach',
                'timeline': {},
                'milestones': [],
                'risks': [],
                'testing_strategy': 'Testing strategy'
            },
            'alternatives_considered': [],
            'references': []
        }
    
    def _get_architecture_template(self) -> Dict[str, Any]:
        """アーキテクチャ仕様テンプレート"""
        template = self._get_feature_template()
        template['metadata']['spec_type'] = 'architecture'
        template['metadata']['title'] = 'Architecture Title'
        template['design']['architecture'] = {
            'style': 'Architectural style (e.g., microservices, layered)',
            'patterns': 'Design patterns used',
            'technologies': 'Key technologies',
            'scalability': 'Scalability considerations',
            'security': 'Security considerations'
        }
        return template
    
    def _get_api_template(self) -> Dict[str, Any]:
        """API仕様テンプレート"""
        template = self._get_feature_template()
        template['metadata']['spec_type'] = 'api'
        template['metadata']['title'] = 'API Title'
        template['design']['interfaces'] = [
            {
                'name': 'API Interface Name',
                'type': 'REST/GraphQL/gRPC',
                'endpoints': [],
                'authentication': 'Auth method',
                'versioning': 'Versioning strategy'
            }
        ]
        return template
    
    def _get_design_template(self) -> Dict[str, Any]:
        """デザイン仕様テンプレート"""
        template = self._get_feature_template()
        template['metadata']['spec_type'] = 'design'
        template['metadata']['title'] = 'Design Title'
        template['design']['components'] = [
            {
                'name': 'Component Name',
                'type': 'Component type',
                'description': 'Component description',
                'interfaces': 'Component interfaces',
                'dependencies': []
            }
        ]
        return template


class TaskSpecTranslator:
    """タスクとSpec Kit仕様間の変換器"""
    
    def __init__(self, spec_manager: SpecKitManager):
        self.spec_manager = spec_manager
    
    def task_to_spec(self, task: Task, spec_type: SpecType = SpecType.FEATURE) -> TechnicalSpec:
        """タスクをSpec Kit仕様に変換"""
        return self.spec_manager.create_spec_from_task(task, spec_type)
    
    def spec_to_task(self, spec: TechnicalSpec) -> Task:
        """Spec Kit仕様をタスクに変換"""
        
        # 要件をタスク要件に変換
        requirements = [req.description for req in spec.requirements]
        
        # 制約の抽出（リスクから）
        constraints = []
        if spec.implementation.risks:
            constraints = [risk.get('risk', '') for risk in spec.implementation.risks[:3]]
        
        # 優先度マッピング
        priority_map = {
            'high': TaskPriority.HIGH,
            'medium': TaskPriority.MEDIUM,
            'low': TaskPriority.LOW
        }
        
        # 最高優先度の要件から優先度を決定
        task_priority = TaskPriority.MEDIUM
        for req in spec.requirements:
            req_priority = priority_map.get(req.priority, TaskPriority.MEDIUM)
            if req_priority.value > task_priority.value:
                task_priority = req_priority
        
        # 品質目標の抽出
        quality_target = 0.8  # デフォルト
        if 'quality_target' in spec.design.architecture:
            quality_target = float(spec.design.architecture['quality_target'])
        
        quality_threshold = 0.6  # デフォルト
        if 'quality_threshold' in spec.design.architecture:
            quality_threshold = float(spec.design.architecture['quality_threshold'])
        
        task = Task(
            id=f"spec_{spec.metadata.title.replace(' ', '_').lower()}",
            description=spec.summary,
            requirements=requirements,
            constraints=constraints,
            priority=task_priority,
            estimated_quality=quality_target,
            minimum_quality_threshold=quality_threshold
        )
        
        return task
    
    def update_spec_from_execution(self, spec_path: Path, execution_result) -> bool:
        """実行結果で仕様を更新"""
        try:
            spec = self.spec_manager.load_spec(spec_path)
            
            # 実行結果に基づいてステータス更新
            if execution_result.success and execution_result.quality_score.overall >= 0.8:
                spec.metadata.status = SpecStatus.IMPLEMENTED
            else:
                spec.metadata.status = SpecStatus.REVIEW
            
            spec.metadata.updated_at = datetime.now().isoformat()
            
            # 実装結果を追記
            if not hasattr(spec.implementation, 'execution_results'):
                spec.implementation.execution_results = []
            
            spec.implementation.execution_results.append({
                'timestamp': datetime.now().isoformat(),
                'success': execution_result.success,
                'quality_score': execution_result.quality_score.overall,
                'execution_time': execution_result.execution_time,
                'agent_used': execution_result.agent_used.value if execution_result.agent_used else None
            })
            
            self.spec_manager.save_spec(spec, spec_path.name)
            return True
            
        except Exception:
            return False