"""
コード解析システム
実装されたコードを解析して設計書との差分を検出する
"""

import ast
import os
from pathlib import Path
from typing import Dict, List, Set, Optional, Any
from dataclasses import dataclass, field
from collections import defaultdict
import logging


@dataclass
class CodeComponent:
    """コードコンポーネント情報"""
    name: str
    type: str  # 'function', 'class', 'module', 'variable'
    file_path: str
    line_number: int
    description: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    methods: List[str] = field(default_factory=list)  # クラスの場合
    attributes: List[str] = field(default_factory=list)  # クラスの場合


@dataclass
class CodeAnalysisResult:
    """コード解析結果"""
    components: List[CodeComponent] = field(default_factory=list)
    modules: Dict[str, List[str]] = field(default_factory=dict)  # モジュール名 -> エクスポート名
    dependencies: Dict[str, List[str]] = field(default_factory=dict)  # モジュール -> 依存モジュール
    technologies: Set[str] = field(default_factory=set)  # 検出された技術スタック
    file_structure: Dict[str, List[str]] = field(default_factory=dict)  # ディレクトリ構造


class CodeAnalyzer:
    """コード解析器"""
    
    def __init__(self, workspace_path: str):
        self.workspace_path = Path(workspace_path)
        self.logger = logging.getLogger(__name__)
        self.ignored_dirs = {'.git', '__pycache__', 'node_modules', '.venv', 'venv', '.env', 'dist', 'build'}
        self.ignored_extensions = {'.pyc', '.pyo', '.pyd'}
        
    def analyze_codebase(self) -> CodeAnalysisResult:
        """コードベース全体を解析"""
        result = CodeAnalysisResult()
        
        # Pythonファイルを解析
        python_files = self._find_python_files()
        for file_path in python_files:
            try:
                components = self._analyze_python_file(file_path)
                result.components.extend(components)
                
                # モジュール情報を追加
                module_name = self._get_module_name(file_path)
                if module_name:
                    result.modules[module_name] = [c.name for c in components if c.type in ('function', 'class')]
            except Exception as e:
                self.logger.warning(f"ファイル解析エラー {file_path}: {e}")
        
        # 技術スタックを検出
        result.technologies = self._detect_technologies()
        
        # ファイル構造を取得
        result.file_structure = self._get_file_structure()
        
        return result
    
    def _find_python_files(self) -> List[Path]:
        """Pythonファイルを検索"""
        python_files = []
        
        for root, dirs, files in os.walk(self.workspace_path):
            # 無視するディレクトリを除外
            dirs[:] = [d for d in dirs if d not in self.ignored_dirs]
            
            for file in files:
                if file.endswith('.py') and not any(file.endswith(ext) for ext in self.ignored_extensions):
                    file_path = Path(root) / file
                    python_files.append(file_path)
        
        return python_files
    
    def _analyze_python_file(self, file_path: Path) -> List[CodeComponent]:
        """Pythonファイルを解析"""
        components = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content, filename=str(file_path))
            
            relative_path = str(file_path.relative_to(self.workspace_path))
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    component = CodeComponent(
                        name=node.name,
                        type='function',
                        file_path=relative_path,
                        line_number=node.lineno,
                        description=ast.get_docstring(node),
                        dependencies=self._extract_dependencies(node),
                        imports=self._extract_imports_from_node(node)
                    )
                    components.append(component)
                
                elif isinstance(node, ast.ClassDef):
                    methods = [n.name for n in node.body if isinstance(n, ast.FunctionDef)]
                    attributes = [n.targets[0].id for n in node.body 
                                if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)]
                    
                    component = CodeComponent(
                        name=node.name,
                        type='class',
                        file_path=relative_path,
                        line_number=node.lineno,
                        description=ast.get_docstring(node),
                        dependencies=self._extract_dependencies(node),
                        imports=self._extract_imports_from_node(node),
                        methods=methods,
                        attributes=attributes
                    )
                    components.append(component)
        
        except SyntaxError as e:
            self.logger.warning(f"構文エラー {file_path}: {e}")
        except Exception as e:
            self.logger.warning(f"解析エラー {file_path}: {e}")
        
        return components
    
    def _extract_dependencies(self, node: ast.AST) -> List[str]:
        """ノードから依存関係を抽出"""
        dependencies = []
        
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Name):
                    dependencies.append(child.func.id)
                elif isinstance(child.func, ast.Attribute):
                    dependencies.append(child.func.attr)
        
        return dependencies
    
    def _extract_imports_from_node(self, node: ast.AST) -> List[str]:
        """ノードからインポートを抽出"""
        imports = []
        
        for child in ast.walk(node):
            if isinstance(child, ast.Import):
                for alias in child.names:
                    imports.append(alias.name)
            elif isinstance(child, ast.ImportFrom):
                if child.module:
                    imports.append(child.module)
        
        return imports
    
    def _get_module_name(self, file_path: Path) -> Optional[str]:
        """モジュール名を取得"""
        try:
            relative = file_path.relative_to(self.workspace_path)
            parts = relative.parts[:-1] + (relative.stem,)
            return '.'.join(parts).replace('/', '.').replace('\\', '.')
        except:
            return None
    
    def _detect_technologies(self) -> Set[str]:
        """技術スタックを検出"""
        technologies = set()
        
        # requirements.txtやpackage.jsonなどを確認
        requirements_file = self.workspace_path / 'requirements.txt'
        if requirements_file.exists():
            technologies.add('Python')
            with open(requirements_file, 'r') as f:
                content = f.read()
                if 'flask' in content.lower():
                    technologies.add('Flask')
                if 'django' in content.lower():
                    technologies.add('Django')
                if 'fastapi' in content.lower():
                    technologies.add('FastAPI')
        
        package_json = self.workspace_path / 'package.json'
        if package_json.exists():
            technologies.add('Node.js')
            try:
                import json
                with open(package_json, 'r') as f:
                    data = json.load(f)
                    deps = data.get('dependencies', {})
                    if 'react' in deps:
                        technologies.add('React')
                    if 'vue' in deps:
                        technologies.add('Vue')
                    if 'express' in deps:
                        technologies.add('Express')
            except:
                pass
        
        # ファイル構造から検出
        if (self.workspace_path / 'src').exists():
            technologies.add('Standard Project Structure')
        
        return technologies
    
    def _get_file_structure(self) -> Dict[str, List[str]]:
        """ファイル構造を取得"""
        structure = defaultdict(list)
        
        for root, dirs, files in os.walk(self.workspace_path):
            dirs[:] = [d for d in dirs if d not in self.ignored_dirs]
            
            relative_root = str(Path(root).relative_to(self.workspace_path))
            if relative_root == '.':
                relative_root = '/'
            
            python_files = [f for f in files if f.endswith('.py')]
            if python_files:
                structure[relative_root] = python_files
        
        return dict(structure)
