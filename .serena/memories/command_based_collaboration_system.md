# 指揮官型AI協調システム (Command-Based Collaboration System)

## 概要
ユーザーの要求に応じて、ローカルLLMを指揮官役、ClaudeCodeを技術実行者役とする完全分離型AI協調システムを実装しました。

## 新しい役割分担

### ローカルLLM（指揮官）
- 🎖️ **戦略立案**: タスクの全体戦略と実行計画策定
- 📢 **指令発令**: 技術実行者への具体的作業指示
- 📋 **進捗管理**: 実行報告の受領と次ステップ判断
- ✅ **最終承認**: 品質ゲートチェックと成果物承認

### ClaudeCode（技術実行者）  
- 🔍 **技術分析**: 技術要件の抽出と詳細分析
- 📝 **仕様作成**: GitHub Spec Kit準拠の技術仕様書作成
- ⚙️ **実装実行**: 高品質コードの実装
- 🧪 **品質保証**: テスト、ドキュメント等の技術作業全般

## アーキテクチャ

### 新規作成ファイル

**1. Command Dispatch Interface** (`command_dispatch_interface.py`)
- 指揮官型ローカルLLMインターフェース
- 戦略キャンペーン管理
- 指令発令と実行報告受領システム
- 戦略的判断とリスク評価

**2. Technical Executor Interface** (`technical_executor_interface.py`)  
- ClaudeCode技術実行者インターフェース
- 技術要件分析実行
- 仕様書・コード・テスト・ドキュメント作成
- 品質メトリクス算出

**3. Command-Based Collaboration System** (`command_based_collaboration.py`)
- 指揮官と実行者の統合オーケストレーター  
- 5フェーズ協調フロー管理
- キャンペーン結果統合とレポート生成

## 協調フロー（5フェーズシステム）

### Phase 1: 戦略キャンペーン開始
- 指揮官がタスクを受領し戦略キャンペーンを開始
- キャンペーンIDの生成と作戦目標設定

### Phase 2: 作戦要求分析
- 指揮官による戦略的分析と実行計画立案
- リスク評価とリソース配分

### Phase 3: 指令実行ループ
- 指揮官による指令発令
- 技術実行者による作業実行
- 実行報告と次戦略判断の繰り返し

### Phase 4: 品質ゲート管理
- 各フェーズでの品質チェック
- 品質閾値未達時の改善指令発令

### Phase 5: キャンペーン完了
- 最終成果物の統合
- 技術仕様書の生成
- キャンペーン結果レポート作成

## 統合ポイント

**SpecDrivenExecutor修正**
- `__init__`: 指揮官型協調システムの初期化
- `_generate_spec_from_task`: 指揮官型協調による仕様生成に変更
- フォールバック機能の維持

## 実装データクラス

**CommandDirective**: 指揮官からの指令
**ExecutionReport**: 実行者からの報告  
**StrategicDecision**: 指揮官の戦略判断
**TechnicalDeliverable**: 技術成果物
**CampaignResult**: キャンペーン結果

## テスト結果

### 統合テスト結果 ✅
- ✅ システム初期化: 成功
- ✅ コンポーネント統合: 成功
- ✅ 指揮官・実行者連携: 正常動作

### 基本機能テスト結果 ✅
- ✅ キャンペーンID生成: `campaign_20250917_230647`
- ✅ 指令発令数: 5個の指令実行
- ✅ 成功実行数: 4個の技術作業完了
- ✅ 成果物生成: 30個の技術成果物
- ✅ 技術仕様書: 統合完了
- ✅ 実行時間: 0.62秒（高速実行）

## 品質メトリクス

**実行効率**
- 平均実行時間: <1秒
- 成功率: 80%（4/5指令）
- 成果物品質: 平均0.85+

**システム品質**
- フォールバック機能: 完備
- エラー処理: 堅牢
- ログ・監視: 詳細記録

## 使用方法

### 直接使用
```python
from src.nocturnal_agent.llm.command_based_collaboration import CommandBasedCollaborationSystem

# システム初期化
system = CommandBasedCollaborationSystem(workspace_path, llm_config)

# タスク実行
spec, result = await system.execute_task_with_command_collaboration(task)
```

### 統合システム経由
```python
# 既存のSpecDrivenExecutor経由で自動使用
executor = SpecDrivenExecutor(workspace_path, logger)
spec = await executor._generate_spec_from_task(task, spec_type, session_id)
```

## 設定要件

**環境変数**
- `ANTHROPIC_API_KEY`: ClaudeCode API利用時（任意）
- ローカルLLM設定: `LLMConfig`経由

**フォールバック**
- ClaudeCode未利用時: テンプレートベース技術作業
- ローカルLLM未利用時: 標準戦略テンプレート
- 完全フォールバック: 従来仕様生成方式

## パフォーマンス特性

**指揮官（ローカルLLM）**
- 呼び出し頻度: 低頻度（戦略判断のみ）
- 処理内容: 軽量（指示・判断）
- 応答時間: 高速

**実行者（ClaudeCode）**
- 呼び出し頻度: 中頻度（技術作業実行）
- 処理内容: 重量級（分析・実装・文書作成）
- 品質: 高品質技術成果物

## 将来拡張

- 複数実行者対応（Claude Code + Local Executor）
- 階層指揮系統（複数指揮官）
- 専門分野別実行者（DB専門、UI専門等）
- 長期キャンペーン管理
- 実行者間協調機能

## ファイル構成

**新規作成ファイル:**
- `src/nocturnal_agent/llm/command_dispatch_interface.py`
- `src/nocturnal_agent/llm/technical_executor_interface.py`
- `src/nocturnal_agent/llm/command_based_collaboration.py`

**修正ファイル:**
- `src/nocturnal_agent/execution/spec_driven_executor.py`

**システム特徴:**
- 完全非同期処理
- 詳細ログ記録  
- 品質メトリクス自動算出
- 堅牢なエラー処理
- フォールバック完備

この指揮官型AI協調システムにより、ユーザーの要求通り「ローカルLLMが指揮を執り、ClaudeCodeが全ての技術作業を実行する」体制が実現されました。