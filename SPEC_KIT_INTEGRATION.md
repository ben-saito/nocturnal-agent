# GitHub Spec Kit統合 - Nocturnal Agent

Nocturnal Agentは[GitHub Spec Kit](https://github.com/github/spec-kit)に準拠した技術仕様管理システムを統合しています。

## 🎯 概要

Spec Kit統合により、タスクの実行前に構造化された技術仕様を自動生成し、設計駆動開発を実現します。すべての仕様は GitHub Spec Kit標準に従って管理されます。

## 📋 主要機能

### 1. 仕様駆動タスク実行
```bash
# 通常のタスク実行が自動的にSpec Kit仕様を生成・実行
./nocturnal start --immediate
```

### 2. 仕様管理コマンド
```bash
# 仕様一覧表示
./nocturnal spec list
./nocturnal spec list --type feature --status draft

# 新規仕様作成
./nocturnal spec create "新機能の仕様" --type feature --template

# 仕様内容表示
./nocturnal spec show specs/features/新機能の仕様_20241216.yaml
./nocturnal spec show specs/features/新機能の仕様_20241216.yaml --format markdown

# 仕様ステータス更新
./nocturnal spec update specs/features/新機能の仕様_20241216.yaml --status approved

# 仕様レポート生成
./nocturnal spec report
./nocturnal spec report --output spec_report.json

# 古い仕様のクリーンアップ
./nocturnal spec cleanup --days 30
```

## 🏗️ 仕様構造

### GitHub Spec Kit準拠の構造
```yaml
metadata:
  title: "機能名の技術仕様"
  status: "draft"  # draft, review, approved, implemented, deprecated
  spec_type: "feature"  # feature, architecture, api, design, process
  authors: ["Nocturnal Agent"]
  version: "1.0.0"
  created_at: "2024-12-16T10:30:00"
  updated_at: "2024-12-16T10:30:00"

summary: "仕様の概要説明"

motivation: "この仕様が必要な理由・背景"

requirements:
  - id: "REQ-001"
    title: "要件1"
    description: "詳細な要件説明"
    priority: "high"  # high, medium, low
    acceptance_criteria: []
    dependencies: []

design:
  overview: "設計概要"
  architecture: {}
  components: []
  interfaces: []
  data_models: []

implementation:
  approach: "実装アプローチ"
  timeline: {}
  milestones: []
  risks: []
  testing_strategy: "テスト戦略"

alternatives_considered: []
references: []
```

## 📁 ディレクトリ構造

```
specs/
├── templates/           # 仕様テンプレート
│   ├── feature_template.yaml
│   ├── architecture_template.yaml
│   ├── api_template.yaml
│   └── design_template.yaml
├── features/           # 機能仕様
├── architecture/       # アーキテクチャ仕様
├── apis/              # API仕様
├── designs/           # デザイン仕様
└── processes/         # プロセス仕様
```

## 🔄 仕様駆動開発フロー

1. **タスク受信**: 新しいタスクが渡される
2. **仕様生成**: タスクから技術仕様を自動生成
3. **仕様検証**: 自動検証チェックを実行
4. **設計拡張**: コンポーネント・インターフェース設計を補完
5. **実装実行**: 仕様に基づいて実装を実行
6. **結果反映**: 実行結果を仕様にフィードバック
7. **ステータス更新**: 仕様ステータスを自動更新

## 🎨 仕様タイプ

### Feature (機能仕様)
- 新機能の実装仕様
- ユーザーストーリーベースの要件定義
- アイコン: ⭐

### Architecture (アーキテクチャ仕様)  
- システム全体の設計仕様
- 技術選択とアーキテクチャパターン
- アイコン: 🏗️

### API (API仕様)
- インターフェース設計
- エンドポイント・データ形式の定義
- アイコン: 🔌

### Design (設計仕様)
- コンポーネント詳細設計
- データモデル設計
- アイコン: 🎨

### Process (プロセス仕様)
- 開発プロセス・ワークフローの定義
- 運用手順の仕様化
- アイコン: ⚙️

## 📊 ステータス管理

| ステータス | アイコン | 説明 |
|-----------|---------|------|
| draft | 📝 | 仕様作成中・初期段階 |
| review | 👀 | レビュー・検証中 |
| approved | ✅ | 承認済み・実装可能 |
| implemented | 🚀 | 実装完了 |
| deprecated | ❌ | 非推奨・無効 |

## 🎯 品質管理

### 自動品質評価
- 実装結果に基づく品質スコア算出
- 品質閾値による自動判定
- 品質メトリクスの継続追跡

### 仕様品質チェック
- 要件の完全性チェック
- 受入条件の定義確認
- 設計整合性の検証

## 📈 レポート機能

### 仕様管理レポート
```json
{
  "generated_at": "2024-12-16T10:30:00",
  "total_specs": 15,
  "status_breakdown": {
    "draft": 3,
    "review": 2, 
    "approved": 4,
    "implemented": 6
  },
  "type_breakdown": {
    "feature": 8,
    "architecture": 3,
    "api": 2,
    "design": 2
  },
  "quality_metrics": {
    "average_quality": 0.847,
    "max_quality": 0.952,
    "success_rate": 0.867
  }
}
```

## 🔧 API Usage

### Python API
```python
from nocturnal_agent.main import NocturnalAgent
from nocturnal_agent.design.spec_kit_integration import SpecType
from nocturnal_agent.core.models import Task

# Nocturnal Agentインスタンス作成
agent = NocturnalAgent()

# サンプルタスク
task = Task(
    id="sample_task",
    description="新機能の実装",
    estimated_quality=0.8
)

# Spec Kit仕様駆動実行
async def my_executor(task):
    # 実装ロジック
    pass

result = await agent.execute_task_with_spec_design(
    task, 
    my_executor, 
    SpecType.FEATURE
)

# 仕様レポート生成
report = await agent.generate_spec_report()
```

### 直接Spec Kit API
```python
from nocturnal_agent.design.spec_kit_integration import SpecKitManager
from nocturnal_agent.execution.spec_driven_executor import SpecDrivenExecutor

# Spec Kit管理
spec_manager = SpecKitManager("./specs")

# 仕様一覧取得
specs = spec_manager.list_specs(spec_type=SpecType.FEATURE)

# 仕様読み込み
spec = spec_manager.load_spec("specs/features/sample.yaml")

# Markdown生成
markdown = spec_manager.generate_spec_markdown(spec)
```

## 🚀 使用例

### 1. 機能開発での使用
```bash
# 1. 新機能仕様を作成
./nocturnal spec create "ユーザー認証機能" --type feature --template

# 2. 仕様を編集（エディタで詳細を記述）

# 3. 仕様を承認
./nocturnal spec update specs/features/ユーザー認証機能_20241216.yaml --status approved

# 4. 仕様駆動で実装実行
./nocturnal start --immediate

# 5. 実行後のレポート確認
./nocturnal spec report
```

### 2. アーキテクチャ変更での使用
```bash
# アーキテクチャ仕様作成
./nocturnal spec create "マイクロサービス移行" --type architecture

# 仕様一覧でアーキテクチャ関連を確認
./nocturnal spec list --type architecture

# 進捗レポート
./nocturnal spec report --output architecture_progress.json
```

## 🎖️ ベストプラクティス

1. **仕様ファーストアプローチ**: 実装前に必ず仕様を作成・承認
2. **継続的更新**: 実装完了後は必ずステータスを更新
3. **テンプレート活用**: 一貫性のためにテンプレートから開始
4. **定期的クリーンアップ**: 古い仕様の整理を定期実行
5. **品質メトリクス確認**: レポート機能で品質動向を監視

## 🔗 関連リソース

- [GitHub Spec Kit](https://github.com/github/spec-kit) - 公式仕様
- [Nocturnal Agent Documentation](./README.md) - メインドキュメント
- [設定ガイド](./config/nocturnal_config.yaml.example) - 設定例

---

**📝 Note**: この機能はGitHub Spec Kitの思想を基に、Nocturnal Agent専用にカスタマイズした実装です。標準的なSpec Kit仕様に準拠しており、外部ツールとの互換性も考慮されています。