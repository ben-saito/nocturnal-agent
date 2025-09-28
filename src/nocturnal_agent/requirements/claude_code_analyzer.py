"""
ClaudeCode連携による自然言語要件解析システム
ClaudeCodeを呼び出して高精度な自然言語解析を実行する
"""
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Any, Optional
import logging
from .requirements_parser import RequirementAnalysis

class ClaudeCodeAnalyzer:
    """ClaudeCodeを使用した自然言語要件解析器"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
    def analyze_requirements(self, requirements_text: str) -> RequirementAnalysis:
        """ClaudeCodeを使用して自然言語要件を解析"""
        try:
            # ClaudeCodeに送る解析指示を作成
            analysis_prompt = self._create_analysis_prompt(requirements_text)
            
            # ClaudeCodeを呼び出して解析実行
            analysis_result = self._call_claude_code(analysis_prompt)
            
            # 結果をRequirementAnalysisオブジェクトに変換
            return self._parse_analysis_result(analysis_result)
            
        except Exception as e:
            self.logger.error(f"ClaudeCode解析エラー: {e}")
            # フォールバック: 基本的な解析結果を返す
            return self._create_fallback_analysis(requirements_text)
    
    def _create_analysis_prompt(self, requirements_text: str) -> str:
        """ClaudeCode用の解析指示を作成"""
        prompt = f"""以下の自然言語要件を詳細に解析して、JSON形式で構造化された要件定義を作成してください。

**要件文:**
{requirements_text}

**解析指示:**
以下の項目について詳細に分析し、JSON形式で出力してください：

1. **project_type**: プロジェクトタイプを以下から選択
   - frontend: フロントエンド中心
   - backend: バックエンド・API中心  
   - fullstack: フロント・バック両方
   - database: データ処理・分析中心
   - mobile: モバイルアプリ

2. **primary_features**: 主要機能を具体的な機能名で5-8個リストアップ
   例: ["ユーザー登録機能", "商品検索機能", "決済機能"]

3. **technical_requirements**: 技術要件・使用技術を抽出
   例: ["React", "Node.js", "PostgreSQL", "Docker"]

4. **database_needs**: データベースに保存が必要な要素
   例: ["ユーザー情報", "商品データ", "注文履歴"]

5. **ui_requirements**: UI・画面要件
   例: ["レスポンシブデザイン", "ダークモード", "多言語対応"]

6. **quality_requirements**: 品質・非機能要件
   例: ["セキュリティ対策", "パフォーマンス最適化", "自動テスト"]

7. **estimated_complexity**: 複雑度を以下から選択
   - simple: 基本的な機能のみ
   - medium: 一般的な複雑さ
   - complex: 高度な機能・大規模

8. **suggested_architecture**: 推奨アーキテクチャ
   例: "SPA (Single Page Application)", "RESTful API", "Microservices"

9. **agent_assignments**: 各専門エージェントへのタスク割り当て
   以下の4つのエージェントそれぞれに、具体的で実行可能なタスクを最低3個ずつ割り当て：
   - frontend_specialist: フロントエンド開発タスク
   - backend_specialist: バックエンド・API開発タスク
   - database_specialist: データベース設計・管理タスク
   - qa_specialist: テスト・品質保証タスク

**出力形式:**
```json
{{
  "project_type": "...",
  "primary_features": [...],
  "technical_requirements": [...],
  "database_needs": [...],
  "ui_requirements": [...],
  "quality_requirements": [...],
  "estimated_complexity": "...",
  "suggested_architecture": "...",
  "agent_assignments": {{
    "frontend_specialist": [...],
    "backend_specialist": [...],
    "database_specialist": [...],
    "qa_specialist": [...]
  }}
}}
```

**重要:**
- 各エージェントには必ず3個以上の具体的なタスクを割り当ててください
- タスクは実装可能で明確な内容にしてください
- JSON形式で正確に出力してください
- コードブロック内にJSONを含めてください
"""
        return prompt
    
    def _call_claude_code(self, prompt: str) -> str:
        """ClaudeCodeを呼び出して解析を実行"""
        try:
            # 一時ファイルにプロンプトを保存
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
                f.write(prompt)
                temp_file = f.name
            
            # ClaudeCodeコマンドを実行（正しい形式）
            cmd = ['claude', '--print', prompt]
            
            self.logger.info(f"ClaudeCode実行: claude --print [prompt]")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                timeout=180  # 3分タイムアウト
            )
            
            # 一時ファイルを削除
            Path(temp_file).unlink()
            
            if result.returncode != 0:
                self.logger.error(f"ClaudeCode stderr: {result.stderr}")
                self.logger.error(f"ClaudeCode stdout: {result.stdout}")
                raise Exception(f"ClaudeCode実行エラー (exit code {result.returncode}): {result.stderr}")
            
            if not result.stdout.strip():
                raise Exception("ClaudeCodeからの出力が空です")
            
            return result.stdout
            
        except subprocess.TimeoutExpired:
            raise Exception("ClaudeCode実行がタイムアウトしました")
        except FileNotFoundError:
            raise Exception("ClaudeCodeが見つかりません。claude cliがインストールされているか確認してください")
        except Exception as e:
            raise Exception(f"ClaudeCode呼び出しエラー: {e}")
    
    def _parse_analysis_result(self, claude_output: str) -> RequirementAnalysis:
        """ClaudeCodeの出力をRequirementAnalysisオブジェクトに変換"""
        try:
            # JSON部分を抽出
            json_data = self._extract_json_from_output(claude_output)
            
            # RequirementAnalysisオブジェクトを作成
            return RequirementAnalysis(
                project_type=json_data.get('project_type', 'fullstack'),
                primary_features=json_data.get('primary_features', []),
                technical_requirements=json_data.get('technical_requirements', []),
                database_needs=json_data.get('database_needs', []),
                ui_requirements=json_data.get('ui_requirements', []),
                quality_requirements=json_data.get('quality_requirements', []),
                estimated_complexity=json_data.get('estimated_complexity', 'medium'),
                suggested_architecture=json_data.get('suggested_architecture', 'RESTful API'),
                agent_assignments=json_data.get('agent_assignments', {})
            )
            
        except Exception as e:
            self.logger.error(f"解析結果のパースエラー: {e}")
            raise Exception(f"ClaudeCode出力の解析に失敗: {e}")
    
    def _extract_json_from_output(self, output: str) -> Dict[str, Any]:
        """ClaudeCodeの出力からJSON部分を抽出"""
        try:
            # コードブロック内のJSONを探す
            lines = output.split('\n')
            json_lines = []
            in_json_block = False
            
            for line in lines:
                if '```json' in line.lower():
                    in_json_block = True
                    continue
                elif '```' in line and in_json_block:
                    break
                elif in_json_block:
                    json_lines.append(line)
            
            if json_lines:
                json_text = '\n'.join(json_lines)
            else:
                # コードブロックがない場合、{から}までを抽出
                start_idx = output.find('{')
                end_idx = output.rfind('}') + 1
                if start_idx != -1 and end_idx != 0:
                    json_text = output[start_idx:end_idx]
                else:
                    raise Exception("JSON形式のデータが見つかりません")
            
            return json.loads(json_text)
            
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON解析エラー: {e}\n出力: {output}")
            raise Exception(f"ClaudeCodeの出力がJSON形式ではありません: {e}")
    
    def _create_fallback_analysis(self, requirements_text: str) -> RequirementAnalysis:
        """ClaudeCode解析失敗時のフォールバック解析"""
        self.logger.warning("ClaudeCode解析失敗、フォールバック解析を使用")
        
        # 基本的な解析結果を作成
        return RequirementAnalysis(
            project_type='fullstack',
            primary_features=[
                'データ収集機能',
                'データ保存機能', 
                'Web UI表示機能',
                'データ分析機能',
                '管理機能'
            ],
            technical_requirements=['React', 'Node.js', 'PostgreSQL'],
            database_needs=['収集データ', 'ユーザー情報', 'システムログ'],
            ui_requirements=['Web インターフェース', 'レスポンシブデザイン'],
            quality_requirements=['自動テスト', 'セキュリティ対策'],
            estimated_complexity='medium',
            suggested_architecture='RESTful API with SPA Frontend',
            agent_assignments={
                'frontend_specialist': [
                    'Webユーザーインターフェースの実装',
                    'レスポンシブデザインの適用',
                    'データ表示画面の作成'
                ],
                'backend_specialist': [
                    'RESTful API設計・実装',
                    'データ処理ロジックの実装', 
                    '外部システム連携機能の実装'
                ],
                'database_specialist': [
                    'データベーススキーマ設計',
                    'データモデルの最適化',
                    'バックアップ・復旧戦略の策定'
                ],
                'qa_specialist': [
                    '単体テストの作成',
                    '統合テストの実装',
                    'E2Eテストの自動化',
                    'パフォーマンステストの実施'
                ]
            }
        )