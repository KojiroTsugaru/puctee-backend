import boto3
from botocore.exceptions import ClientError
from PIL import Image
import io
from fastapi import HTTPException, UploadFile
from app.core.config import settings
from anyio import to_thread
import mimetypes
import logging
import os

_IS_LAMBDA = "AWS_LAMBDA_FUNCTION_NAME" in os.environ


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

if _IS_LAMBDA:
    # Lambda 実行ロールの権限を使う（キーを渡さない）
    s3_client = boto3.client(
        "s3",
        region_name=settings.AWS_REGION,
    )
else:
    # ローカル開発時は settings 経由で明示的に渡す
    s3_client = boto3.client(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_REGION,
    )

async def compress_image(file: UploadFile, max_size=(800,800)) -> bytes:
    
    # ファイルをまるごと読む
    raw = await file.read()
    
    # Pillow の重たい処理をスレッドプールで実行
    def _sync_compress(data: bytes) -> bytes:
        img = Image.open(io.BytesIO(data))
        img.thumbnail(max_size, Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        # JPEG・PNG 自動判別させたいなら img.format を使っても OK
        img.save(buf, format="JPEG", quality=85, optimize=True)
        return buf.getvalue()

    return await to_thread.run_sync(_sync_compress, raw)

async def upload_to_s3(file: UploadFile, user_id: int) -> str:
    """画像をS3にアップロードする"""
    try:
        # 画像を圧縮
        compressed_image = await compress_image(file)
        
        # S3 キー作成
        file_extension = file.filename.split('.')[-1].lower()
        s3_key = f"profile_images/{user_id}_{file.filename}"
        
        # クライアントから来た Content-Type を優先、それ以外は拡張子から推測
        content_type = file.content_type or mimetypes.guess_type(file.filename)[0] or "application/octet-stream"
        
        # S3にアップロード
        await to_thread.run_sync(lambda: s3_client.put_object(
            Bucket=settings.AWS_S3_BUCKET,
            Key=s3_key,
            Body=compressed_image,
            ContentType=content_type,
        ))
        return f"https://{settings.AWS_S3_BUCKET}.s3.{settings.AWS_REGION}.amazonaws.com/{s3_key}"
    except ClientError as e:
        logger.exception("S3 upload failed")
        print(e.response['Error']['Message'])
        # return a detailed FastAPI error:
        raise HTTPException(status_code=502, detail=f"S3 error: {e.response['Error']['Message']}")
    except Exception:
        logger.exception("Unexpected processing error")
        print("Unexpected processing error")
        raise HTTPException(status_code=500, detail="Image processing or internal error")