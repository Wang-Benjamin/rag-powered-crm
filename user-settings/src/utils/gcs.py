"""Shared GCS upload/delete helpers for all routers that handle file uploads."""

import os
import logging
from datetime import datetime, timezone
from pathlib import Path

from google.cloud import storage

logger = logging.getLogger(__name__)

GCS_BUCKET = os.getenv('GCS_DEAL_ROOM_BUCKET', 'prelude-deal-rooms')
GCS_SIGNATURE_BUCKET = os.getenv('GCS_SIGNATURE_BUCKET', 'prelude-signature-logos')

_client = storage.Client()


def _sanitize_email(email: str) -> str:
    return email.replace('@', '_').replace('.', '_')


def upload_file(file, folder: str, email: str, file_id: str = None, bucket_name: str = None) -> str:
    """Upload a file to GCS and return the public URL.

    Args:
        file: FastAPI UploadFile object
        folder: GCS path prefix (e.g., 'factory-photos', 'certs', 'logos', 'signatures')
        email: Owner email (used in path for uniqueness)
        file_id: Optional identifier (e.g., cert_id). Defaults to timestamp.
        bucket_name: Override bucket. Defaults to GCS_DEAL_ROOM_BUCKET.
    """
    bucket_name = bucket_name or GCS_BUCKET
    ext = Path(file.filename).suffix if file.filename else ''
    sanitized = _sanitize_email(email)
    identifier = file_id or str(int(datetime.now(timezone.utc).timestamp()))
    filename = f"{folder}/{sanitized}_{identifier}{ext}"

    bucket = _client.bucket(bucket_name)
    blob = bucket.blob(filename)
    file.file.seek(0)
    blob.upload_from_file(file.file, content_type=file.content_type)

    url = f"https://storage.googleapis.com/{bucket_name}/{filename}"
    logger.info(f"Uploaded to GCS: {url}")
    return url


def upload_bytes(
    data: bytes,
    folder: str,
    email: str,
    file_id: str,
    ext: str,
    content_type: str,
    bucket_name: str = None,
) -> str:
    """Upload raw bytes to GCS and return the public URL.

    Sibling of :func:`upload_file` for callers that already hold bytes in memory
    (e.g. the product-PDF extractor renders pages with pdf2image + Pillow and
    uploads each cropped PNG). Unlike ``upload_file``, ``file_id`` and ``ext``
    are required — there's no UploadFile to infer them from.
    """
    bucket_name = bucket_name or GCS_BUCKET
    sanitized = _sanitize_email(email)
    if ext and not ext.startswith('.'):
        ext = '.' + ext
    filename = f"{folder}/{sanitized}_{file_id}{ext}"

    bucket = _client.bucket(bucket_name)
    blob = bucket.blob(filename)
    blob.upload_from_string(data, content_type=content_type)

    url = f"https://storage.googleapis.com/{bucket_name}/{filename}"
    logger.info(f"Uploaded to GCS: {url}")
    return url


def delete_file(url: str, bucket_name: str = None):
    """Delete a file from GCS by its public URL."""
    bucket_name = bucket_name or GCS_BUCKET
    prefix = f"https://storage.googleapis.com/{bucket_name}/"
    if not url or not url.startswith(prefix):
        return
    try:
        blob_name = url[len(prefix):]
        blob = _client.bucket(bucket_name).blob(blob_name)
        blob.delete()
        logger.info(f"Deleted GCS file: {blob_name}")
    except Exception as e:
        logger.warning(f"Failed to delete GCS file {url}: {e}")


def download_bytes(url: str, bucket_name: str = None) -> bytes:
    """Download a GCS object to bytes via its public URL.

    Used by the document-ingestion runner to fetch a just-uploaded file for
    async extraction. Raises on missing/unreachable blobs.
    """
    bucket_name = bucket_name or GCS_BUCKET
    prefix = f"https://storage.googleapis.com/{bucket_name}/"
    if not url or not url.startswith(prefix):
        raise ValueError(f"URL is not a {bucket_name} GCS URL: {url!r}")
    blob_name = url[len(prefix):]
    blob = _client.bucket(bucket_name).blob(blob_name)
    return blob.download_as_bytes()
