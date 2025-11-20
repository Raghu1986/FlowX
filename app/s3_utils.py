# app/s3_utils.py
from io import BytesIO
import aioboto3
from app.core.config import settings


async def read_file_from_s3(bucket: str, key: str) -> tuple[BytesIO, str]:
    """
    Download object and return (BytesIO, content_type).
    """
    session = aioboto3.Session(
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_REGION,
    )
    async with session.client("s3") as s3:
        resp = await s3.get_object(Bucket=bucket, Key=key)
        data = await resp["Body"].read()
        ctype = (resp.get("ContentType") or "").lower()
    return BytesIO(data), ctype


async def upload_stream_to_s3(file_obj, bucket: str, key: str, content_type: str | None = None) -> None:
    """
    Stream an UploadFile (or any file-like) to S3 without loading to memory.
    """
    session = aioboto3.Session(
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_REGION,
    )
    extra = {}
    if content_type:
        extra["ContentType"] = content_type

    async with session.client("s3") as s3:
        # aioboto3 exposes upload_fileobj as an async coroutine
        await s3.upload_fileobj(file_obj, bucket, key, ExtraArgs=extra)  # type: ignore[attr-defined]


async def upload_bytes_to_s3(bucket: str, key: str, data: bytes, content_type: str | None = None) -> None:
    """
    Upload a bytes buffer to S3.
    """
    session = aioboto3.Session(
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_REGION,
    )
    extra = {}
    if content_type:
        extra["ContentType"] = content_type
    async with session.client("s3") as s3:
        await s3.put_object(Bucket=bucket, Key=key, Body=data, **extra)


async def generate_presigned_get_url(bucket: str, key: str, expires_in: int = 1800) -> str:
    """
    aioboto3: generate_presigned_url is a coroutine — must be awaited.
    """
    session = aioboto3.Session(
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_REGION,
    )
    async with session.client("s3") as s3:
        url = await s3.generate_presigned_url(
            ClientMethod="get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expires_in,
        )
        return url
