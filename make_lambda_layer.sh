#!/bin/bash

# エラーが発生した時点でスクリプトを停止
set -e

# エラーメッセージを表示
trap 'echo "Error occurred at line $LINENO. Command: $BASH_COMMAND"' ERR

mkdir python

pip install \
--platform manylinux2014_aarch64 \
--target=python/python/lib/python3.11/site-packages/ \
--implementation cp \
--python-version 3.11 \
--only-binary=:all: \
--upgrade \
-r requirements.txt

# 現在のディレクトリを保存
CURRENT_DIR=$(pwd)

# pythonディレクトリに移動してZIPを作成
cd python
zip -r "${CURRENT_DIR}/lambda-layer.zip" .

# 元のディレクトリに戻る
cd "${CURRENT_DIR}"

# S3にアップロード
aws s3 cp lambda-layer.zip s3://puctee-deployment/lambda/puctee-api/lambda-layer.zip

# レイヤーを作成
LAYER_ARN=$(aws lambda publish-layer-version \
  --layer-name puctee-dependencies \
  --description "Dependencies for Puctee API" \
  --content S3Bucket=puctee-deployment,S3Key=lambda/puctee-api/lambda-layer.zip \
  --compatible-runtimes python3.11 \
  --query 'LayerVersionArn' \
  --output text)

echo "Created layer with ARN: $LAYER_ARN"

# Lambda関数を更新
aws lambda update-function-configuration \
  --function-name puctee-app \
  --layers "$LAYER_ARN"

# 一時ディレクトリを削除
rm -rf python lambda-layer.zip
