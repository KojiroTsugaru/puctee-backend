#!/bin/bash

# 既存のdeployment.zipとdeployment_packageディレクトリを削除
rm -rf deployment.zip deployment_package

# デプロイパッケージ用のディレクトリを作成
mkdir -p deployment_package

# 必要なパッケージをインストール
pip3 install -r requirements.txt --target deployment_package

# アプリケーションのコードをコピー
cp -r app deployment_package/
cp -r alembic deployment_package/
cp alembic.ini deployment_package/

# デプロイパッケージを作成
cd deployment_package
zip -r ../deployment.zip .
cd ..

# 一時ディレクトリを削除
rm -rf deployment_package

echo "Deployment package created: deployment.zip" 