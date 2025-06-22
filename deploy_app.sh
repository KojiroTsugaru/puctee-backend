#!/bin/bash

# エラーが発生した時点でスクリプトを停止
set -e

# エラーメッセージを表示
trap 'echo "Error occurred at line $LINENO. Command: $BASH_COMMAND"' ERR

# 一時ディレクトリを作成
mkdir -p deploy

# アプリケーションコードをコピー
cp -r app deploy/
cp lambda_function.py deploy/

# デプロイパッケージを作成
cd deploy
zip -r ../app.zip .

# 元のディレクトリに戻る
cd ..

# S3にアップロード
aws s3 cp app.zip s3://puctee-deployment/lambda/puctee-api/app.zip

# Lambda関数を更新
aws lambda update-function-code \
  --function-name puctee-app \
  --s3-bucket puctee-deployment \
  --s3-key lambda/puctee-api/app.zip

# 一時ディレクトリを削除
rm -rf deploy app.zip

echo "Deployment completed successfully!" 