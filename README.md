# Puctee API

FastAPIを使用したPucteeのバックエンドAPIサーバー

## 必要条件

- Python 3.11+
- PostgreSQL

## セットアップ

1. リポジトリをクローン
```bash
git clone https://github.com/yourusername/puctee-backend.git
cd puctee-backend
```

2. 仮想環境を作成して有効化
```bash
python -m venv venv
source venv/bin/activate  # Linuxの場合
# または
.\venv\Scripts\activate  # Windowsの場合
```

3. 依存パッケージをインストール
```bash
pip install -r requirements.txt
```

4. 環境変数の設定
`.env.example`を`.env`にコピーし、必要な環境変数を設定してください。

5. データベースのセットアップ
```bash
# データベースの作成
createdb puctee

# マイグレーションの実行
alembic upgrade head
```

## 開発サーバーの起動

```bash
uvicorn app.main:app --reload
```

## APIドキュメント

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## テストの実行

```bash
pytest
``` 