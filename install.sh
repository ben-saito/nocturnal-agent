#!/bin/bash
# Nocturnal Agent グローバルインストールスクリプト
# 外部からどこでも nocturnal-agent コマンドを使用可能にします

echo "🌙 Nocturnal Agent グローバルインストール開始..."

# スクリプトのディレクトリを取得
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="$SCRIPT_DIR/bin"
CLI_SCRIPT="$BIN_DIR/nocturnal-agent"

# CLIスクリプトが存在するか確認
if [ ! -f "$CLI_SCRIPT" ]; then
    echo "❌ エラー: $CLI_SCRIPT が見つかりません"
    exit 1
fi

# インストール方法を選択
echo "📦 インストール方法を選択してください:"
echo "1. シンボリックリンク作成 (/usr/local/bin - 推奨)"
echo "2. ホームディレクトリに追加 (~/.local/bin)"  
echo "3. 現在のシェルセッションのみ (export PATH)"

read -p "選択 [1-3]: " choice

case $choice in
    1)
        # /usr/local/bin にシンボリックリンクを作成
        echo "🔗 /usr/local/bin にシンボリックリンクを作成中..."
        
        if [ -w "/usr/local/bin" ]; then
            ln -sf "$CLI_SCRIPT" "/usr/local/bin/nocturnal-agent"
            echo "✅ インストール完了: /usr/local/bin/nocturnal-agent"
        else
            echo "🔐 管理者権限が必要です..."
            sudo ln -sf "$CLI_SCRIPT" "/usr/local/bin/nocturnal-agent"
            echo "✅ インストール完了: /usr/local/bin/nocturnal-agent"
        fi
        ;;
    2)
        # ~/.local/bin にシンボリックリンクを作成
        echo "🏠 ~/.local/bin にシンボリックリンクを作成中..."
        mkdir -p "$HOME/.local/bin"
        ln -sf "$CLI_SCRIPT" "$HOME/.local/bin/nocturnal-agent"
        echo "✅ インストール完了: $HOME/.local/bin/nocturnal-agent"
        
        # PATHに追加する必要があるかチェック
        if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
            echo "⚠️  注意: ~/.local/bin がPATHに含まれていません"
            echo "📝 以下を ~/.bashrc または ~/.zshrc に追加してください:"
            echo "   export PATH=\"\$HOME/.local/bin:\$PATH\""
        fi
        ;;
    3)
        # 現在のセッションのみ
        echo "🔄 現在のシェルセッションにPATHを追加中..."
        export PATH="$BIN_DIR:$PATH"
        echo "✅ 現在のセッションで利用可能: nocturnal-agent"
        echo "📝 永続化するには以下を ~/.bashrc または ~/.zshrc に追加:"
        echo "   export PATH=\"$BIN_DIR:\$PATH\""
        ;;
    *)
        echo "❌ 無効な選択です"
        exit 1
        ;;
esac

echo ""
echo "🎉 インストール完了！"
echo ""
echo "💡 使用方法:"
echo "   nocturnal-agent init                    # プロジェクト初期化"
echo "   nocturnal-agent add-task -t 'タスク' -p high  # タスク追加"
echo "   nocturnal-agent list                    # タスク一覧"
echo "   nocturnal-agent run                     # タスク実行"
echo "   nocturnal-agent status                  # ステータス確認"
echo ""
echo "🧪 テスト実行:"
if command -v nocturnal-agent &> /dev/null; then
    echo "✅ nocturnal-agent コマンドが利用可能です"
    nocturnal-agent --help 2>/dev/null || echo "ℹ️  プロジェクトディレクトリで実行してください"
else
    echo "⚠️  nocturnal-agent コマンドが見つかりません"
    echo "   新しいターミナルセッションを開くか、シェルを再読み込みしてください"
fi