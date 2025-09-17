# Nocturnal Agent Configuration Guide / 設定ガイド

This directory contains configuration files for Nocturnal Agent, the autonomous night development system.  
このディレクトリには、夜間自律開発システムNocturnal Agentの設定ファイルが含まれています。

## Configuration Files / 設定ファイル

### 📄 `nocturnal-agent.yaml`
Main configuration file with detailed settings for all system components.  
すべてのシステムコンポーネントの詳細設定を含むメイン設定ファイル。

### 📄 `nocturnal_config.yaml` 
Runtime configuration used by the current system implementation.  
現在のシステム実装で使用されるランタイム設定。

### 📄 `nocturnal_config.yaml.example`
Example configuration template for reference.  
参考用の設定テンプレート例。

---

## Main Configuration Settings / メイン設定項目

### 🎯 Core Project Settings / プロジェクト基本設定

```yaml
project_name: "nocturnal-agent"        # プロジェクト名
working_directory: "."                 # 作業ディレクトリ
debug_mode: false                      # デバッグモード
dry_run: false                         # ドライランモード（実際の変更なし）
```

**説明:**
- `project_name`: システムが管理するプロジェクトの名前
- `working_directory`: タスク実行時の基準ディレクトリ
- `debug_mode`: 詳細ログとデバッグ情報の出力
- `dry_run`: 実際のファイル変更を行わないテストモード

### 🤖 Local LLM Configuration / ローカルLLM設定

```yaml
llm:
  model_path: "models/codellama-13b"   # モデルパス
  api_url: "http://localhost:1234/v1"  # LM Studio APIエンドポイント
  timeout: 300                         # タイムアウト（秒）
  max_tokens: 4096                     # 最大トークン数
  temperature: 0.7                     # 創造性レベル（0.0-1.0）
  enabled: true                        # LLM有効化
```

**説明:**
- `model_path`: LM Studioで使用するモデルのパス
- `api_url`: LM StudioのAPIエンドポイント（通常localhost:1234）
- `timeout`: API呼び出しのタイムアウト時間
- `max_tokens`: 生成される最大トークン数
- `temperature`: 0.0（確定的）〜1.0（創造的）の出力制御
- `enabled`: ローカルLLMの使用可否

### 🔧 External Agents Configuration / 外部エージェント設定

```yaml
agents:
  claude:
    cli_command: "claude"              # Claude Code CLI コマンド
    max_retries: 3                     # 最大リトライ回数
    timeout: 300                       # タイムアウト（秒）
    enabled: true                      # エージェント有効化
    check_auth_on_startup: true        # 起動時認証チェック
```

**説明:**
- `cli_command`: Claude Code CLIのコマンド名
- `max_retries`: 失敗時の最大再試行回数
- `timeout`: エージェント応答のタイムアウト
- `enabled`: このエージェントの使用可否
- `check_auth_on_startup`: システム起動時の認証確認

### 📊 Quality Assessment / 品質評価設定

```yaml
quality:
  overall_threshold: 0.85              # 全体品質閾値
  consistency_threshold: 0.85          # 一貫性閾値
  max_improvement_cycles: 3            # 最大改善サイクル数
  enable_static_analysis: true         # 静的解析有効化
  static_analysis_tools:               # 使用する静的解析ツール
    - "pylint"
    - "flake8" 
    - "mypy"
```

**説明:**
- `overall_threshold`: 自動承認に必要な全体品質スコア（0.0-1.0）
- `consistency_threshold`: コード一貫性の最低要求レベル
- `max_improvement_cycles`: 品質改善の最大繰り返し回数
- `enable_static_analysis`: Pylint等による自動コード解析
- `static_analysis_tools`: 使用する静的解析ツールのリスト

### 🌙 Night Scheduler / 夜間スケジューラー設定

```yaml
scheduler:
  start_time: "22:00"                  # 開始時刻（22:00 = 午後10時）
  end_time: "06:00"                    # 終了時刻（06:00 = 午前6時）
  max_changes_per_night: 10            # 一晩の最大変更数
  max_task_duration_minutes: 30        # タスクの最大実行時間（分）
  check_interval_seconds: 30           # チェック間隔（秒）
  timezone: "local"                    # タイムゾーン
```

**説明:**
- `start_time`: 自動実行開始時刻（24時間形式）
- `end_time`: 自動実行終了時刻
- `max_changes_per_night`: 安全性のための一晩の変更制限
- `max_task_duration_minutes`: 単一タスクの実行時間制限
- `check_interval_seconds`: システム状態チェックの頻度
- `timezone`: "local"、"UTC"、または具体的なタイムゾーン

### 🔒 Safety and Security / 安全・セキュリティ設定

```yaml
safety:
  enable_backups: true                 # バックアップ有効化
  backup_before_execution: true        # 実行前バックアップ
  max_file_changes_per_task: 20        # タスクあたり最大ファイル変更数
  cpu_limit_percent: 80.0              # CPU使用率制限（%）
  memory_limit_gb: 8.0                 # メモリ使用量制限（GB）
  dangerous_commands:                  # 危険コマンドブロックリスト
    - "rm"
    - "rmdir"
    - "del"
    - "format"
    # ... more commands
  protected_paths:                     # 保護パスリスト
    - "/etc"
    - "/sys"
    - "C:\\Windows"
    # ... more paths
```

**説明:**
- `enable_backups`: 自動バックアップ機能の有効化
- `backup_before_execution`: 各タスク実行前の強制バックアップ
- `max_file_changes_per_task`: 単一タスクでの最大ファイル変更数制限
- `cpu_limit_percent`: システムリソース保護のためのCPU使用率上限
- `memory_limit_gb`: メモリ使用量の上限
- `dangerous_commands`: 実行がブロックされる危険なコマンドのリスト
- `protected_paths`: 変更が禁止されているシステムパスのリスト

### 💰 Cost Management / コスト管理設定

```yaml
cost:
  monthly_budget_usd: 10.0             # 月間予算（USD）
  local_llm_priority: true             # ローカルLLM優先使用
  free_tool_preference_percent: 90.0   # 無料ツール優先率（%）
  track_api_usage: true                # API使用量追跡
  warn_at_budget_percent: 80.0         # 予算警告閾値（%）
```

**説明:**
- `monthly_budget_usd`: 月間のAPI使用料予算（米ドル）
- `local_llm_priority`: 有料APIよりローカルLLMを優先使用
- `free_tool_preference_percent`: 無料ツールの使用優先度
- `track_api_usage`: API呼び出しとコストの詳細追跡
- `warn_at_budget_percent`: 予算の何%で警告を発するか

### 📝 Obsidian Knowledge Base / Obsidian知識ベース設定

```yaml
obsidian:
  vault_path: "knowledge-vault"        # Vaultディレクトリパス
  auto_create_vault: true              # Vault自動作成
  markdown_template_path: null         # テンプレートファイルパス
  enable_frontmatter: true             # フロントマター有効化
  enable_backlinks: true               # バックリンク有効化
```

**説明:**
- `vault_path`: Obsidian Vaultのディレクトリパス
- `auto_create_vault`: 存在しない場合のVault自動作成
- `markdown_template_path`: 新規ノート作成時のテンプレート
- `enable_frontmatter`: YAML フロントマターの使用
- `enable_backlinks`: ノート間の自動リンク生成

### 🔀 Parallel Execution / 並列実行設定

```yaml
parallel:
  max_parallel_branches: 5             # 最大並列ブランチ数
  high_quality_threshold: 0.85         # 高品質閾値
  medium_quality_threshold: 0.70       # 中品質閾値
  enable_experimental_branches: true   # 実験ブランチ有効化
  merge_strategy: "auto"               # マージ戦略
```

**説明:**
- `max_parallel_branches`: 同時に作業できる最大Gitブランチ数
- `high_quality_threshold`: 高品質と判定される品質スコア
- `medium_quality_threshold`: 中品質と判定される品質スコア
- `enable_experimental_branches`: 実験的な実装ブランチの作成許可
- `merge_strategy`: "auto"（自動）、"manual"（手動）、"quality_based"（品質ベース）

### 📊 Logging / ログ設定

```yaml
logging:
  level: "INFO"                        # ログレベル
  format: "json"                       # ログ形式
  file_path: "logs/nocturnal-agent.log" # ログファイルパス
  max_file_size_mb: 100                # ログファイル最大サイズ（MB）
  backup_count: 5                      # ローテーション保持数
  enable_structlog: true               # 構造化ログ有効化
```

**説明:**
- `level`: ログレベル（DEBUG, INFO, WARNING, ERROR, CRITICAL）
- `format`: "json"（機械読み取り用）または"text"（人間読み取り用）
- `file_path`: ログファイルの保存パス
- `max_file_size_mb`: 単一ログファイルの最大サイズ
- `backup_count`: ローテーション時の保持ファイル数
- `enable_structlog`: 構造化ログライブラリの使用

---

## Runtime Configuration / ランタイム設定

### 📄 `nocturnal_config.yaml` の主要設定

```yaml
minimum_quality_threshold: 0.6         # 最低品質閾値
target_quality_threshold: 0.8          # 目標品質閾値
monthly_budget: 10.0                   # 月間予算
night_start_hour: 22                   # 夜間開始時刻
night_end_hour: 6                      # 夜間終了時刻
```

**重要な設定項目:**
- **品質閾値**: システムが自動承認する最低品質レベル
- **予算管理**: API使用料の上限設定
- **夜間動作時間**: 自律開発が実行される時間帯
- **安全機能**: バックアップと危険操作の防止
- **並列実行**: 複数ブランチでの同時開発制御

---

## Getting Started / 開始方法

### 1. 基本設定の確認
```bash
# 設定ファイルの存在確認
ls config/

# 設定の妥当性チェック
nocturnal config-check
```

### 2. カスタマイズ
1. `nocturnal_config.yaml` を編集して基本設定を調整
2. API キーやローカルLLMの設定を環境に合わせて変更
3. 品質閾値を要求レベルに調整

### 3. システム起動
```bash
# 設定確認後に実行
python run_nocturnal_task.py
```

---

## Troubleshooting / トラブルシューティング

### よくある問題

**Q: LM Studioに接続できない**  
A: `llm.api_url` の設定を確認し、LM Studioが起動していることを確認

**Q: 品質スコアが低い**  
A: `quality.overall_threshold` を一時的に下げるか、改善サイクル数を増加

**Q: 夜間に実行されない**  
A: `scheduler.start_time` と `scheduler.end_time` がタイムゾーンに合っているか確認

**Q: 予算警告が出る**  
A: `cost.monthly_budget_usd` を増額するか、`local_llm_priority` を true に設定

---

## Security Notes / セキュリティ注意事項

⚠️ **重要**: 
- API キーは環境変数で管理することを推奨
- `dangerous_commands` リストは環境に応じてカスタマイズ
- `protected_paths` に重要なシステムディレクトリを必ず含める
- 定期的にバックアップの動作を確認

📝 **推奨**: 本番環境では `debug_mode: false` と `dry_run: false` に設定

---

Generated by Nocturnal Agent Configuration System  
Nocturnal Agent設定システムにより生成