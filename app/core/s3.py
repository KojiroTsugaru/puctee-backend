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
    # Use Lambda execution role permissions (don't pass keys)
    s3_client = boto3.client(
        "s3",
        region_name=settings.AWS_REGION,
    )
else:
    # For local development, pass explicitly via settings
    s3_client = boto3.client(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_REGION,
    )

async def compress_image(file: UploadFile, max_size=(800,800)) -> bytes:
    
    # Read entire file
    raw = await file.read()
    
    # Execute heavy Pillow processing in thread pool
    def _sync_compress(data: bytes) -> bytes:
        img = Image.open(io.BytesIO(data))
        img.thumbnail(max_size, Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        # Use img.format for automatic JPEG/PNG detection if desired
        img.save(buf, format="JPEG", quality=85, optimize=True)
        return buf.getvalue()

    return await to_thread.run_sync(_sync_compress, raw)

async def upload_to_s3(file: UploadFile, user_id: int) -> str:
    """Upload image to S3"""
    try:
        # Compress image
        compressed_image = await compress_image(file)
        
        # Create S3 key
        file_extension = file.filename.split('.')[-1].lower()
        s3_key = f"profile_images/{user_id}_{file.filename}"
        
        # Prioritize Content-Type from client, otherwise infer from extension
        content_type = file.content_type or mimetypes.guess_type(file.filename)[0] or "application/octet-stream"
        
        # Upload to S3
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