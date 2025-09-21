#!/bin/bash

# Ollama 10分タイムアウト設定スクリプト
# nocturnal-agent システム用

echo "🚀 Ollama サーバーを10分タイムアウト設定で起動中..."

# 既存プロセスを停止
pkill -f ollama 2>/dev/null || true
sleep 2

# 環境変数設定（10分タイムアウト）
export OLLAMA_LOAD_TIMEOUT=600          # モデルロードタイムアウト: 10分
export OLLAMA_KEEP_ALIVE=10m            # モデル保持時間: 10分
export OLLAMA_REQUEST_TIMEOUT=600       # リクエストタイムアウト: 10分（もしサポートされていれば）
export OLLAMA_NUM_PARALLEL=1            # 並列処理数制限
export OLLAMA_CONTEXT_LENGTH=4096       # コンテキスト長制限

# 設定確認
echo "📋 Ollama 設定:"
echo "  - LOAD_TIMEOUT: $OLLAMA_LOAD_TIMEOUT 秒"
echo "  - KEEP_ALIVE: $OLLAMA_KEEP_ALIVE"
echo "  - CONTEXT_LENGTH: $OLLAMA_CONTEXT_LENGTH"

# サーバー起動
echo "🔄 Ollamaサーバー起動中..."
ollama serve &

# 起動確認
echo "⏳ サーバー起動待機中..."
sleep 5

# 接続テスト
echo "🔍 接続テスト..."
if curl -s http://localhost:11434/api/tags > /dev/null; then
    echo "✅ Ollamaサーバーが正常に起動しました"
    echo "📋 利用可能モデル:"
    curl -s http://localhost:11434/api/tags | jq -r '.models[].name' || echo "モデル一覧取得エラー"
else
    echo "❌ Ollamaサーバーの起動に失敗しました"
    exit 1
fi

echo "🎉 Ollama 10分タイムアウト設定完了"