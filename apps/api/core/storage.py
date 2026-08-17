import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from apps.api.core.settings import settings

_client = boto3.client(
    "s3",
    endpoint_url=settings.minio_endpoint,
    aws_access_key_id=settings.minio_root_user,
    aws_secret_access_key=settings.minio_root_password,
    config=Config(signature_version="s3v4"),
    region_name="us-east-1",
)


def ensure_bucket() -> None:
    """Idempotent create-if-missing, called once from the FastAPI lifespan
    hook. MinIO (unlike some S3-compatible stores) does not auto-create
    buckets on first write."""
    try:
        _client.head_bucket(Bucket=settings.minio_bucket)
    except ClientError:
        _client.create_bucket(Bucket=settings.minio_bucket)


def upload_bytes(key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
    _client.put_object(Bucket=settings.minio_bucket, Key=key, Body=data, ContentType=content_type)


def download_bytes(key: str) -> bytes:
    response = _client.get_object(Bucket=settings.minio_bucket, Key=key)
    return response["Body"].read()


def presigned_url(key: str, expires_seconds: int = 300) -> str:
    """Lets the frontend download directly from MinIO/S3 rather than
    proxying large files through the API."""
    return _client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.minio_bucket, "Key": key},
        ExpiresIn=expires_seconds,
    )
