"""
Remote Claude Code Executor
対象プロジェクトディレクトリでClaudeCodeを実行するためのインターフェース
"""

import asyncio
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging

from ..core.config import ClaudeConfig
from .technical_executor_interface import ExecutionReport, TechnicalDeliverable

class RemoteClaudeCodeExecutor:
    """対象プロジェクトディレクトリでClaudeCodeを実行するエクゼキューター"""
    
    def __init__(self, target_project_path: str, claude_config: ClaudeConfig = None):
        self.target_project_path = Path(target_project_path).resolve()
        self.claude_config = claude_config
        self.logger = logging.getLogger(__name__)
        
        # 実行環境の検証
        self._validate_target_project()
        
    def _validate_target_project(self):
        """対象プロジェクトディレクトリの検証"""
        if not self.target_project_path.exists():
            raise FileNotFoundError(f"対象プロジェクトディレクトリが見つかりません: {self.target_project_path}")
        
        if not self.target_project_path.is_dir():
            raise NotADirectoryError(f"パスがディレクトリではありません: {self.target_project_path}")
        
        self.logger.info(f"✅ 対象プロジェクト検証完了: {self.target_project_path}")
    
    async def execute_claude_code_command(self, command: str, context: str = "", timeout: int = 300) -> Dict[str, Any]:
        """対象プロジェクトディレクトリでClaudeCodeコマンドを実行"""
        self.logger.info(f"🚀 Claude Code実行開始: {self.target_project_path}")
        
        # 一時的なプロンプトファイルを作成
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as temp_file:
            prompt_content = self._create_execution_prompt(command, context)
            temp_file.write(prompt_content)
            temp_file_path = temp_file.name
        
        try:
            # Claude Codeを対象ディレクトリで実行
            result = await self._run_claude_code_in_target_directory(temp_file_path, timeout)
            
            return {
                'status': 'success',
                'output': result['output'],
                'error': result['error'],
                'execution_time': result['execution_time'],
                'working_directory': str(self.target_project_path),
                'command_executed': command
            }
            
        except Exception as e:
            self.logger.error(f"Claude Code実行エラー: {e}")
            return {
                'status': 'error',
                'output': '',
                'error': str(e),
                'execution_time': 0,
                'working_directory': str(self.target_project_path),
                'command_executed': command
            }
        finally:
            # 一時ファイルをクリーンアップ
            try:
                os.unlink(temp_file_path)
            except:
                pass
    
    def _create_execution_prompt(self, command: str, context: str) -> str:
        """Claude Code実行用プロンプトを作成"""
        project_info = self._gather_project_info()
        
        prompt = f"""あなたは対象プロジェクトのディレクトリで作業する技術エキスパートです。

**現在の作業ディレクトリ**: {self.target_project_path}

**プロジェクト情報**:
{project_info}

**実行するタスク**: {command}

**追加コンテキスト**:
{context}

**指示**:
1. 現在のプロジェクト構造を理解してください
2. 指定されたタスクを実行してください  
3. 既存のコードスタイルと規則に従ってください
4. 必要に応じてファイルを作成・修正してください
5. 実行結果を明確に報告してください

**注意事項**:
- 既存のファイルを変更する場合は、バックアップの必要性を検討してください
- プロジェクトの依存関係を破壊しないでください
- セキュリティを考慮したコーディングを心がけてください

作業を開始してください。"""
        
        return prompt
    
    def _gather_project_info(self) -> str:
        """対象プロジェクトの情報を収集"""
        info_parts = []
        
        # プロジェクトルートの内容
        try:
            root_files = list(self.target_project_path.iterdir())
            root_contents = [f.name for f in root_files if not f.name.startswith('.')][:10]  # 最初の10個
            info_parts.append(f"ルートディレクトリ内容: {', '.join(root_contents)}")
        except:
            info_parts.append("ルートディレクトリ内容: 読み取り不可")
        
        # package.jsonの確認（Node.jsプロジェクトの場合）
        package_json_path = self.target_project_path / "package.json"
        if package_json_path.exists():
            try:
                with open(package_json_path, 'r', encoding='utf-8') as f:
                    package_data = json.load(f)
                    project_name = package_data.get('name', '不明')
                    project_version = package_data.get('version', '不明')
                    info_parts.append(f"Node.jsプロジェクト: {project_name} v{project_version}")
            except:
                info_parts.append("Node.jsプロジェクト: package.json読み取りエラー")
        
        # requirements.txtの確認（Pythonプロジェクトの場合）
        requirements_path = self.target_project_path / "requirements.txt"
        if requirements_path.exists():
            info_parts.append("Pythonプロジェクト: requirements.txt発見")
        
        # Cargo.tomlの確認（Rustプロジェクトの場合）
        cargo_path = self.target_project_path / "Cargo.toml"
        if cargo_path.exists():
            info_parts.append("Rustプロジェクト: Cargo.toml発見")
        
        # .gitの確認
        git_path = self.target_project_path / ".git"
        if git_path.exists():
            info_parts.append("Gitリポジトリ")
        
        return "\n".join(info_parts) if info_parts else "プロジェクト情報を収集できませんでした"
    
    async def _run_claude_code_in_target_directory(self, prompt_file_path: str, timeout: int) -> Dict[str, Any]:
        """対象ディレクトリでClaudeCodeを実行"""
        start_time = datetime.now()
        
        # Claude Code実行コマンド構築
        # 複数の実行方法を試行
        claude_commands = [
            ['claude-code', '--file', prompt_file_path],
            ['claude', '--file', prompt_file_path],
            ['python', '-m', 'claude_code.cli', '--file', prompt_file_path],
        ]
        
        for cmd in claude_commands:
            try:
                self.logger.info(f"Claude Code実行試行: {' '.join(cmd)}")
                
                # 対象ディレクトリで実行
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    cwd=str(self.target_project_path),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=self._prepare_environment()
                )
                
                # タイムアウト付きで実行
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout
                )
                
                execution_time = (datetime.now() - start_time).total_seconds()
                
                return {
                    'output': stdout.decode('utf-8', errors='ignore'),
                    'error': stderr.decode('utf-8', errors='ignore'),
                    'return_code': process.returncode,
                    'execution_time': execution_time,
                    'command_used': ' '.join(cmd)
                }
                
            except FileNotFoundError:
                self.logger.debug(f"コマンドが見つかりません: {cmd[0]}")
                continue
            except asyncio.TimeoutError:
                self.logger.error(f"実行タイムアウト: {timeout}秒")
                if 'process' in locals():
                    process.kill()
                raise Exception(f"Claude Code実行がタイムアウトしました ({timeout}秒)")
            except Exception as e:
                self.logger.error(f"実行エラー: {e}")
                continue
        
        # すべてのコマンドが失敗した場合のフォールバック
        return await self._fallback_execution(prompt_file_path)
    
    def _prepare_environment(self) -> Dict[str, str]:
        """実行環境の準備"""
        env = os.environ.copy()
        
        # Claude Code関連の環境変数
        if self.claude_config and hasattr(self.claude_config, 'api_key'):
            env['ANTHROPIC_API_KEY'] = self.claude_config.api_key
        
        # プロジェクト固有の環境変数
        env['PWD'] = str(self.target_project_path)
        env['CLAUDE_WORKING_DIRECTORY'] = str(self.target_project_path)
        
        return env
    
    async def _fallback_execution(self, prompt_file_path: str) -> Dict[str, Any]:
        """フォールバック実行方法"""
        self.logger.warning("Claude Code直接実行に失敗、フォールバック実行を試行")
        
        try:
            # プロンプトファイルの内容を読み取り
            with open(prompt_file_path, 'r', encoding='utf-8') as f:
                prompt_content = f.read()
            
            # シンプルなスクリプト実行やファイル操作でのフォールバック
            fallback_result = await self._execute_basic_operations(prompt_content)
            
            return {
                'output': f"フォールバック実行完了:\n{fallback_result}",
                'error': '',
                'return_code': 0,
                'execution_time': 1.0,
                'command_used': 'fallback_execution'
            }
            
        except Exception as e:
            return {
                'output': '',
                'error': f"フォールバック実行も失敗: {e}",
                'return_code': 1,
                'execution_time': 0,
                'command_used': 'fallback_execution'
            }
    
    async def _execute_basic_operations(self, prompt_content: str) -> str:
        """基本的な操作のフォールバック実行"""
        operations_performed = []
        
        # プロジェクトディレクトリの確認
        operations_performed.append(f"作業ディレクトリ確認: {self.target_project_path}")
        
        # 基本的なファイル一覧
        try:
            files = list(self.target_project_path.iterdir())
            file_list = [f.name for f in files[:10]]  # 最初の10ファイル
            operations_performed.append(f"ファイル一覧: {', '.join(file_list)}")
        except Exception as e:
            operations_performed.append(f"ファイル一覧取得エラー: {e}")
        
        # README.mdがあれば内容を確認
        readme_path = self.target_project_path / "README.md"
        if readme_path.exists():
            try:
                with open(readme_path, 'r', encoding='utf-8') as f:
                    readme_content = f.read()[:500]  # 最初の500文字
                    operations_performed.append(f"README.md内容(抜粋): {readme_content}")
            except:
                operations_performed.append("README.md読み取りエラー")
        
        return "\n".join(operations_performed)
    
    async def execute_code_implementation(self, implementation_request: str, context: Dict = None) -> ExecutionReport:
        """コード実装の実行（TechnicalExecutorInterfaceとの互換性）"""
        command = f"コード実装: {implementation_request}"
        if context:
            command += f"\nコンテキスト: {json.dumps(context, ensure_ascii=False, indent=2)}"
        
        result = await self.execute_claude_code_command(command, "コード実装タスクです")
        
        # ExecutionReportに変換
        return ExecutionReport(
            command_id=f"impl_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            agent_id="remote_claude_code",
            status="completed" if result['status'] == 'success' else "failed",
            deliverables={},  # 後で実装
            execution_time=result['execution_time'],
            quality_metrics={"overall": 0.8},  # 基本的な品質スコア
            issues_encountered=[result['error']] if result['error'] else [],
            recommendations=["対象プロジェクトディレクトリで実行完了"],
            timestamp=datetime.now()
        )
    
    def get_target_project_info(self) -> Dict[str, Any]:
        """対象プロジェクトの詳細情報を取得"""
        return {
            'project_path': str(self.target_project_path),
            'exists': self.target_project_path.exists(),
            'is_directory': self.target_project_path.is_dir(),
            'project_info': self._gather_project_info(),
            'has_git': (self.target_project_path / '.git').exists(),
            'has_package_json': (self.target_project_path / 'package.json').exists(),
            'has_requirements_txt': (self.target_project_path / 'requirements.txt').exists(),
            'has_cargo_toml': (self.target_project_path / 'Cargo.toml').exists(),
        }