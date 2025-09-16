"""Code pattern extraction engine for consistency analysis."""

import ast
import logging
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from nocturnal_agent.core.models import CodePattern, ConsistencyRule, ProjectContext


logger = logging.getLogger(__name__)


class CodeAnalyzer(ast.NodeVisitor):
    """AST-based code analyzer for extracting patterns."""
    
    def __init__(self):
        """Initialize code analyzer."""
        self.patterns = {
            'functions': [],
            'classes': [],
            'variables': [],
            'imports': [],
            'constants': [],
            'decorators': [],
            'docstrings': [],
            'exceptions': []
        }
        
        self.statistics = {
            'function_count': 0,
            'class_count': 0,
            'variable_count': 0,
            'import_count': 0,
            'line_count': 0,
            'complexity_scores': []
        }
        
        self.current_class = None
        self.current_function = None
    
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Analyze function definitions."""
        self.statistics['function_count'] += 1
        
        # Extract function pattern
        function_info = {
            'name': node.name,
            'args': [arg.arg for arg in node.args.args],
            'decorators': [self._get_decorator_name(dec) for dec in node.decorator_list],
            'docstring': ast.get_docstring(node),
            'is_private': node.name.startswith('_'),
            'is_async': isinstance(node, ast.AsyncFunctionDef),
            'line_number': node.lineno,
            'complexity': self._calculate_complexity(node)
        }
        
        # Context information
        if self.current_class:
            function_info['class'] = self.current_class
            function_info['is_method'] = True
        else:
            function_info['is_method'] = False
        
        self.patterns['functions'].append(function_info)
        
        # Analyze function body
        old_function = self.current_function
        self.current_function = node.name
        self.generic_visit(node)
        self.current_function = old_function
    
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Analyze async function definitions."""
        self.visit_FunctionDef(node)
    
    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Analyze class definitions."""
        self.statistics['class_count'] += 1
        
        # Extract class pattern
        class_info = {
            'name': node.name,
            'bases': [self._get_base_name(base) for base in node.bases],
            'decorators': [self._get_decorator_name(dec) for dec in node.decorator_list],
            'docstring': ast.get_docstring(node),
            'is_private': node.name.startswith('_'),
            'line_number': node.lineno,
            'methods': [],
            'attributes': []
        }
        
        self.patterns['classes'].append(class_info)
        
        # Analyze class body
        old_class = self.current_class
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = old_class
    
    def visit_Import(self, node: ast.Import) -> None:
        """Analyze import statements."""
        for alias in node.names:
            self.statistics['import_count'] += 1
            import_info = {
                'module': alias.name,
                'alias': alias.asname,
                'type': 'import',
                'line_number': node.lineno
            }
            self.patterns['imports'].append(import_info)
    
    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Analyze from-import statements."""
        for alias in node.names:
            self.statistics['import_count'] += 1
            import_info = {
                'module': node.module,
                'name': alias.name,
                'alias': alias.asname,
                'type': 'from_import',
                'level': node.level,
                'line_number': node.lineno
            }
            self.patterns['imports'].append(import_info)
    
    def visit_Assign(self, node: ast.Assign) -> None:
        """Analyze variable assignments."""
        for target in node.targets:
            if isinstance(target, ast.Name):
                self.statistics['variable_count'] += 1
                
                var_info = {
                    'name': target.id,
                    'is_constant': target.id.isupper(),
                    'is_private': target.id.startswith('_'),
                    'line_number': node.lineno,
                    'context': self.current_class or self.current_function or 'module'
                }
                
                if var_info['is_constant']:
                    self.patterns['constants'].append(var_info)
                else:
                    self.patterns['variables'].append(var_info)
        
        self.generic_visit(node)
    
    def _get_decorator_name(self, decorator: ast.expr) -> str:
        """Extract decorator name."""
        if isinstance(decorator, ast.Name):
            return decorator.id
        elif isinstance(decorator, ast.Attribute):
            return f"{self._get_base_name(decorator.value)}.{decorator.attr}"
        elif isinstance(decorator, ast.Call):
            return self._get_decorator_name(decorator.func)
        return str(decorator)
    
    def _get_base_name(self, base: ast.expr) -> str:
        """Extract base class name."""
        if isinstance(base, ast.Name):
            return base.id
        elif isinstance(base, ast.Attribute):
            return f"{self._get_base_name(base.value)}.{base.attr}"
        return str(base)
    
    def _calculate_complexity(self, node: ast.FunctionDef) -> int:
        """Calculate cyclomatic complexity of a function."""
        complexity = 1  # Base complexity
        
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.While, ast.For, ast.AsyncFor)):
                complexity += 1
            elif isinstance(child, (ast.ExceptHandler, ast.With, ast.AsyncWith)):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1
        
        return complexity


class PatternExtractor:
    """Extracts code patterns from codebases."""
    
    def __init__(self):
        """Initialize pattern extractor."""
        self.supported_extensions = {'.py', '.js', '.ts', '.jsx', '.tsx'}
        self.analyzers = {
            '.py': self._analyze_python_file,
            '.js': self._analyze_javascript_file,
            '.ts': self._analyze_javascript_file,  # TypeScript uses similar patterns
        }
    
    async def extract_patterns_from_directory(
        self, 
        directory: str, 
        exclude_patterns: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Extract patterns from entire directory."""
        
        exclude_patterns = exclude_patterns or [
            '__pycache__', 'node_modules', '.git', '.env',
            'venv', 'env', 'dist', 'build', '.pytest_cache'
        ]
        
        directory_path = Path(directory)
        if not directory_path.exists():
            raise ValueError(f"Directory does not exist: {directory}")
        
        extracted_patterns = {
            'naming_patterns': defaultdict(list),
            'structure_patterns': defaultdict(list),
            'import_patterns': defaultdict(list),
            'architecture_patterns': defaultdict(list),
            'statistics': defaultdict(int),
            'files_analyzed': []
        }
        
        # Recursively analyze files
        for file_path in directory_path.rglob('*'):
            if (file_path.is_file() and 
                file_path.suffix in self.supported_extensions and
                not self._should_exclude_file(file_path, exclude_patterns)):
                
                try:
                    file_patterns = await self._analyze_file(file_path)
                    self._merge_patterns(extracted_patterns, file_patterns, str(file_path))
                    extracted_patterns['files_analyzed'].append(str(file_path))
                    
                except Exception as e:
                    logger.warning(f"Failed to analyze {file_path}: {e}")
        
        # Generate insights from patterns
        insights = self._generate_pattern_insights(extracted_patterns)
        extracted_patterns['insights'] = insights
        
        return extracted_patterns
    
    async def _analyze_file(self, file_path: Path) -> Dict[str, Any]:
        """Analyze single file for patterns."""
        extension = file_path.suffix
        analyzer = self.analyzers.get(extension, self._analyze_generic_file)
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            return await analyzer(content, file_path)
            
        except Exception as e:
            logger.error(f"Error analyzing {file_path}: {e}")
            return {}
    
    async def _analyze_python_file(self, content: str, file_path: Path) -> Dict[str, Any]:
        """Analyze Python file using AST."""
        try:
            tree = ast.parse(content)
            analyzer = CodeAnalyzer()
            analyzer.visit(tree)
            
            # Extract patterns from analyzer results
            patterns = {
                'naming_patterns': self._extract_naming_patterns(analyzer.patterns),
                'structure_patterns': self._extract_structure_patterns(analyzer.patterns),
                'import_patterns': self._extract_import_patterns(analyzer.patterns),
                'architecture_patterns': self._extract_architecture_patterns(analyzer.patterns),
                'statistics': analyzer.statistics
            }
            
            return patterns
            
        except SyntaxError as e:
            logger.warning(f"Syntax error in {file_path}: {e}")
            return {}
    
    async def _analyze_javascript_file(self, content: str, file_path: Path) -> Dict[str, Any]:
        """Analyze JavaScript/TypeScript file using regex patterns."""
        # Basic regex-based analysis for JS/TS files
        patterns = {
            'naming_patterns': self._extract_js_naming_patterns(content),
            'structure_patterns': self._extract_js_structure_patterns(content),
            'import_patterns': self._extract_js_import_patterns(content),
            'architecture_patterns': self._extract_js_architecture_patterns(content),
            'statistics': self._calculate_js_statistics(content)
        }
        
        return patterns
    
    async def _analyze_generic_file(self, content: str, file_path: Path) -> Dict[str, Any]:
        """Generic file analysis using text patterns."""
        return {
            'statistics': {
                'line_count': len(content.split('\n')),
                'character_count': len(content)
            }
        }
    
    def _extract_naming_patterns(self, ast_patterns: Dict[str, List]) -> Dict[str, List]:
        """Extract naming conventions from AST patterns."""
        naming_patterns = {
            'function_names': [],
            'class_names': [],
            'variable_names': [],
            'constant_names': []
        }
        
        # Function naming patterns
        for func in ast_patterns['functions']:
            naming_patterns['function_names'].append({
                'name': func['name'],
                'case_style': self._detect_case_style(func['name']),
                'is_private': func['is_private'],
                'length': len(func['name'])
            })
        
        # Class naming patterns
        for cls in ast_patterns['classes']:
            naming_patterns['class_names'].append({
                'name': cls['name'],
                'case_style': self._detect_case_style(cls['name']),
                'is_private': cls['is_private'],
                'length': len(cls['name'])
            })
        
        # Variable naming patterns
        for var in ast_patterns['variables']:
            naming_patterns['variable_names'].append({
                'name': var['name'],
                'case_style': self._detect_case_style(var['name']),
                'is_private': var['is_private'],
                'length': len(var['name'])
            })
        
        # Constant naming patterns
        for const in ast_patterns['constants']:
            naming_patterns['constant_names'].append({
                'name': const['name'],
                'case_style': self._detect_case_style(const['name']),
                'length': len(const['name'])
            })
        
        return naming_patterns
    
    def _extract_structure_patterns(self, ast_patterns: Dict[str, List]) -> Dict[str, Any]:
        """Extract structural patterns from AST."""
        return {
            'function_patterns': {
                'avg_complexity': sum(f.get('complexity', 1) for f in ast_patterns['functions']) / max(len(ast_patterns['functions']), 1),
                'async_usage': sum(1 for f in ast_patterns['functions'] if f.get('is_async', False)),
                'decorator_usage': [f['decorators'] for f in ast_patterns['functions'] if f['decorators']],
                'docstring_usage': sum(1 for f in ast_patterns['functions'] if f.get('docstring'))
            },
            'class_patterns': {
                'inheritance_usage': sum(1 for c in ast_patterns['classes'] if c['bases']),
                'decorator_usage': [c['decorators'] for c in ast_patterns['classes'] if c['decorators']],
                'docstring_usage': sum(1 for c in ast_patterns['classes'] if c.get('docstring'))
            }
        }
    
    def _extract_import_patterns(self, ast_patterns: Dict[str, List]) -> Dict[str, Any]:
        """Extract import patterns from AST."""
        imports = ast_patterns['imports']
        
        # Group by import type
        import_types = defaultdict(list)
        for imp in imports:
            import_types[imp['type']].append(imp)
        
        # Most common modules
        modules = [imp['module'] for imp in imports if imp.get('module')]
        module_counter = Counter(modules)
        
        return {
            'import_types': dict(import_types),
            'common_modules': module_counter.most_common(10),
            'alias_usage': sum(1 for imp in imports if imp.get('alias')),
            'relative_imports': sum(1 for imp in imports if imp.get('level', 0) > 0)
        }
    
    def _extract_architecture_patterns(self, ast_patterns: Dict[str, List]) -> Dict[str, Any]:
        """Extract architectural patterns from AST."""
        # Detect common architectural patterns
        patterns = {
            'singleton_pattern': self._detect_singleton_pattern(ast_patterns),
            'factory_pattern': self._detect_factory_pattern(ast_patterns),
            'decorator_pattern': self._detect_decorator_pattern(ast_patterns),
            'context_manager_pattern': self._detect_context_manager_pattern(ast_patterns)
        }
        
        return patterns
    
    def _detect_case_style(self, name: str) -> str:
        """Detect naming case style."""
        if name.isupper():
            return 'UPPER_CASE'
        elif name.islower():
            if '_' in name:
                return 'snake_case'
            else:
                return 'lowercase'
        elif name[0].isupper():
            if '_' in name or name.isupper():
                return 'UPPER_CASE'
            else:
                return 'PascalCase'
        elif '_' in name:
            return 'snake_case'
        else:
            return 'camelCase'
    
    def _detect_singleton_pattern(self, ast_patterns: Dict[str, List]) -> bool:
        """Detect singleton pattern usage."""
        for cls in ast_patterns['classes']:
            # Look for __new__ method or instance class variable
            if any('__new__' in str(method) for method in cls.get('methods', [])):
                return True
        return False
    
    def _detect_factory_pattern(self, ast_patterns: Dict[str, List]) -> bool:
        """Detect factory pattern usage."""
        factory_indicators = ['create', 'build', 'make', 'factory']
        
        for func in ast_patterns['functions']:
            if any(indicator in func['name'].lower() for indicator in factory_indicators):
                return True
        
        return False
    
    def _detect_decorator_pattern(self, ast_patterns: Dict[str, List]) -> int:
        """Count decorator pattern usage."""
        decorator_count = 0
        
        for func in ast_patterns['functions']:
            decorator_count += len(func.get('decorators', []))
        
        for cls in ast_patterns['classes']:
            decorator_count += len(cls.get('decorators', []))
        
        return decorator_count
    
    def _detect_context_manager_pattern(self, ast_patterns: Dict[str, List]) -> bool:
        """Detect context manager pattern usage."""
        for cls in ast_patterns['classes']:
            methods = cls.get('methods', [])
            if ('__enter__' in str(methods) and '__exit__' in str(methods)):
                return True
        return False
    
    def _extract_js_naming_patterns(self, content: str) -> Dict[str, List]:
        """Extract JavaScript naming patterns using regex."""
        patterns = {
            'function_names': [],
            'class_names': [],
            'variable_names': [],
            'constant_names': []
        }
        
        # Function patterns
        func_pattern = r'(?:function\s+|const\s+|let\s+|var\s+)(\w+)\s*(?:=\s*(?:function|async|\()|(?:\(.*?\)\s*=>))'
        for match in re.finditer(func_pattern, content):
            name = match.group(1)
            patterns['function_names'].append({
                'name': name,
                'case_style': self._detect_case_style(name),
                'length': len(name)
            })
        
        # Class patterns
        class_pattern = r'class\s+(\w+)'
        for match in re.finditer(class_pattern, content):
            name = match.group(1)
            patterns['class_names'].append({
                'name': name,
                'case_style': self._detect_case_style(name),
                'length': len(name)
            })
        
        return patterns
    
    def _extract_js_structure_patterns(self, content: str) -> Dict[str, Any]:
        """Extract JavaScript structural patterns."""
        return {
            'arrow_function_usage': len(re.findall(r'=>', content)),
            'async_usage': len(re.findall(r'\basync\b', content)),
            'class_usage': len(re.findall(r'\bclass\b', content)),
            'const_usage': len(re.findall(r'\bconst\b', content)),
            'let_usage': len(re.findall(r'\blet\b', content))
        }
    
    def _extract_js_import_patterns(self, content: str) -> Dict[str, Any]:
        """Extract JavaScript import patterns."""
        import_patterns = {
            'es6_imports': len(re.findall(r'\bimport\b.*\bfrom\b', content)),
            'require_usage': len(re.findall(r'\brequire\s*\(', content)),
            'default_imports': len(re.findall(r'import\s+\w+\s+from', content)),
            'named_imports': len(re.findall(r'import\s*{[^}]+}\s*from', content))
        }
        
        return import_patterns
    
    def _extract_js_architecture_patterns(self, content: str) -> Dict[str, Any]:
        """Extract JavaScript architectural patterns."""
        return {
            'module_exports': len(re.findall(r'module\.exports', content)),
            'export_usage': len(re.findall(r'\bexport\b', content)),
            'promise_usage': len(re.findall(r'\bPromise\b|\.then\(|\.catch\(', content)),
            'callback_usage': len(re.findall(r'function\s*\([^)]*callback', content))
        }
    
    def _calculate_js_statistics(self, content: str) -> Dict[str, int]:
        """Calculate JavaScript file statistics."""
        lines = content.split('\n')
        return {
            'line_count': len(lines),
            'non_empty_lines': len([line for line in lines if line.strip()]),
            'comment_lines': len([line for line in lines if line.strip().startswith('//')]),
            'character_count': len(content)
        }
    
    def _should_exclude_file(self, file_path: Path, exclude_patterns: List[str]) -> bool:
        """Check if file should be excluded from analysis."""
        file_str = str(file_path)
        return any(pattern in file_str for pattern in exclude_patterns)
    
    def _merge_patterns(self, target: Dict, source: Dict, file_path: str) -> None:
        """Merge patterns from single file into overall patterns."""
        for category, patterns in source.items():
            if category == 'statistics':
                for key, value in patterns.items():
                    target['statistics'][key] += value if isinstance(value, int) else 0
            else:
                target[category][file_path] = patterns
    
    def _generate_pattern_insights(self, patterns: Dict) -> Dict[str, Any]:
        """Generate insights from extracted patterns."""
        insights = {
            'dominant_naming_convention': self._find_dominant_naming_convention(patterns),
            'code_organization': self._analyze_code_organization(patterns),
            'architecture_decisions': self._identify_architecture_decisions(patterns),
            'consistency_score': self._calculate_consistency_score(patterns)
        }
        
        return insights
    
    def _find_dominant_naming_convention(self, patterns: Dict) -> Dict[str, str]:
        """Find dominant naming conventions."""
        naming_stats = defaultdict(Counter)
        
        for file_patterns in patterns['naming_patterns'].values():
            for category, names in file_patterns.items():
                for name_info in names:
                    naming_stats[category][name_info['case_style']] += 1
        
        dominant_conventions = {}
        for category, counter in naming_stats.items():
            if counter:
                dominant_conventions[category] = counter.most_common(1)[0][0]
        
        return dominant_conventions
    
    def _analyze_code_organization(self, patterns: Dict) -> Dict[str, Any]:
        """Analyze code organization patterns."""
        return {
            'files_analyzed': len(patterns['files_analyzed']),
            'total_functions': patterns['statistics']['function_count'],
            'total_classes': patterns['statistics']['class_count'],
            'avg_functions_per_file': patterns['statistics']['function_count'] / max(len(patterns['files_analyzed']), 1),
            'avg_classes_per_file': patterns['statistics']['class_count'] / max(len(patterns['files_analyzed']), 1)
        }
    
    def _identify_architecture_decisions(self, patterns: Dict) -> List[str]:
        """Identify architectural patterns and decisions."""
        decisions = []
        
        # Analyze import patterns across files
        total_files = len(patterns['files_analyzed'])
        if total_files > 0:
            # Check for common architectural patterns
            if patterns['statistics'].get('import_count', 0) / total_files > 5:
                decisions.append("Heavy use of modular architecture")
            
            if any('async' in str(p) for p in patterns.get('structure_patterns', {}).values()):
                decisions.append("Asynchronous programming patterns used")
            
            if any('decorator' in str(p) for p in patterns.get('architecture_patterns', {}).values()):
                decisions.append("Decorator pattern widely adopted")
        
        return decisions
    
    def _calculate_consistency_score(self, patterns: Dict) -> float:
        """Calculate overall consistency score."""
        if not patterns['files_analyzed']:
            return 0.0
        
        # Factors contributing to consistency
        naming_consistency = self._calculate_naming_consistency(patterns)
        structure_consistency = self._calculate_structure_consistency(patterns)
        import_consistency = self._calculate_import_consistency(patterns)
        
        # Weighted average
        weights = {'naming': 0.4, 'structure': 0.3, 'imports': 0.3}
        
        consistency_score = (
            naming_consistency * weights['naming'] +
            structure_consistency * weights['structure'] +
            import_consistency * weights['imports']
        )
        
        return min(consistency_score, 1.0)
    
    def _calculate_naming_consistency(self, patterns: Dict) -> float:
        """Calculate naming consistency score."""
        # Implementation would analyze naming convention consistency
        # For now, return a placeholder
        return 0.8
    
    def _calculate_structure_consistency(self, patterns: Dict) -> float:
        """Calculate structural consistency score."""
        # Implementation would analyze structural patterns consistency
        # For now, return a placeholder
        return 0.75
    
    def _calculate_import_consistency(self, patterns: Dict) -> float:
        """Calculate import consistency score."""
        # Implementation would analyze import patterns consistency
        # For now, return a placeholder
        return 0.85
    
    def generate_consistency_rules(
        self, 
        patterns: Dict[str, Any], 
        project_name: str
    ) -> List[ConsistencyRule]:
        """Generate consistency rules based on extracted patterns."""
        rules = []
        insights = patterns.get('insights', {})
        
        # Naming convention rules
        naming_conventions = insights.get('dominant_naming_convention', {})
        for category, convention in naming_conventions.items():
            if category == 'function_names' and convention == 'snake_case':
                rules.append(ConsistencyRule(
                    rule_id=f"{project_name}_func_naming",
                    name="Function naming convention",
                    description=f"Functions should use {convention}",
                    pattern=r"^[a-z_][a-z0-9_]*$",
                    severity="warning",
                    auto_fixable=False,
                    fix_suggestion="Use snake_case for function names"
                ))
            
            elif category == 'class_names' and convention == 'PascalCase':
                rules.append(ConsistencyRule(
                    rule_id=f"{project_name}_class_naming",
                    name="Class naming convention", 
                    description=f"Classes should use {convention}",
                    pattern=r"^[A-Z][a-zA-Z0-9]*$",
                    severity="warning",
                    auto_fixable=False,
                    fix_suggestion="Use PascalCase for class names"
                ))
        
        return rules
    
    def generate_code_patterns(
        self, 
        patterns: Dict[str, Any], 
        project_name: str
    ) -> List[CodePattern]:
        """Generate code patterns based on analysis."""
        code_patterns = []
        insights = patterns.get('insights', {})
        
        # Naming patterns
        naming_conventions = insights.get('dominant_naming_convention', {})
        for category, convention in naming_conventions.items():
            code_patterns.append(CodePattern(
                name=f"{category}_naming",
                pattern_type="naming",
                description=f"Use {convention} for {category.replace('_', ' ')}",
                examples=[],  # Would be populated from actual examples
                confidence=0.8,
                usage_count=patterns['statistics'].get('function_count', 0),
                project_specific=True
            ))
        
        # Architecture patterns
        arch_decisions = insights.get('architecture_decisions', [])
        for decision in arch_decisions:
            code_patterns.append(CodePattern(
                name=f"architecture_{decision.lower().replace(' ', '_')}",
                pattern_type="architecture", 
                description=decision,
                examples=[],
                confidence=0.7,
                usage_count=1,
                project_specific=True
            ))
        
        return code_patterns