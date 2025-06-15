#!/bin/bash

# 仮想環境が有効化されていない場合は有効化
if [ -z "$VIRTUAL_ENV" ]; then
    if [ -d ".venv" ]; then
        source .venv/bin/activate
    else
        echo "仮想環境が見つかりません。.venv ディレクトリが存在することを確認してください。"
        exit 1
    fi
fi

# Pythonのパスに app ディレクトリを追加
export PYTHONPATH=$PYTHONPATH:$(pwd)

# テストを実行
pytest tests/ -v --cov=app --cov-report=term-missing

# エラーハンドリング
if [ $? -ne 0 ]; then
    echo "テストの実行中にエラーが発生しました。"
    exit 1
fi