"""
STORAGE ABSTRACTION LAYER
==========================
Auto-detects storage backend based on env vars:
  Local dev:  ./uploads/ folder
  Production: AWS S3 (requires AWS_ACCESS_KEY_ID + S3_BUCKET_NAME)

Usage:
  storage = get_storage()
  key = storage.save(file_stream, filename)      # Returns storage_key
  stream = storage.load(key)                     # Returns BytesIO
  storage.delete(key)
  exists = storage.exists(key)
"""

import os
import io
import uuid
import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class BaseStorage(ABC):
    """Storage backend interface."""

    @abstractmethod
    def save(self, file_stream, filename): pass

    @abstractmethod
    def load(self, storage_key): pass

    @abstractmethod
    def delete(self, storage_key): pass

    @abstractmethod
    def exists(self, storage_key): pass


class LocalDiskStorage(BaseStorage):
    """Store files on local disk in ./uploads/"""

    def __init__(self, base_folder='uploads'):
        self.base_folder = base_folder
        os.makedirs(base_folder, exist_ok=True)
        logger.info(f"💾 Using LocalDiskStorage: {os.path.abspath(base_folder)}")

    def save(self, file_stream, filename):
        # Generate a unique key
        ext = filename.split('.')[-1] if '.' in filename else 'bin'
        key = f"{uuid.uuid4().hex}_{filename}"
        fpath = os.path.join(self.base_folder, key)

        # Handle both Flask FileStorage and BytesIO
        if hasattr(file_stream, 'save'):
            file_stream.save(fpath)
        else:
            with open(fpath, 'wb') as f:
                if hasattr(file_stream, 'read'):
                    data = file_stream.read()
                    if isinstance(data, str):
                        data = data.encode('utf-8')
                    f.write(data)
                else:
                    f.write(file_stream)

        return key

    def load(self, storage_key):
        fpath = os.path.join(self.base_folder, storage_key)
        if not os.path.exists(fpath):
            raise FileNotFoundError(f"File not found: {storage_key}")
        return open(fpath, 'rb')

    def delete(self, storage_key):
        fpath = os.path.join(self.base_folder, storage_key)
        if os.path.exists(fpath):
            os.remove(fpath)
            return True
        return False

    def exists(self, storage_key):
        return os.path.exists(os.path.join(self.base_folder, storage_key))

    def get_path(self, storage_key):
        """Get absolute local path (for parsers that need file paths)."""
        return os.path.abspath(os.path.join(self.base_folder, storage_key))


class S3Storage(BaseStorage):
    """AWS S3 storage backend."""

    def __init__(self):
        try:
            import boto3
        except ImportError:
            raise ImportError("boto3 required for S3 storage. Run: pip install boto3")

        self.bucket = os.environ.get('S3_BUCKET_NAME')
        if not self.bucket:
            raise ValueError("S3_BUCKET_NAME env var not set")

        region = os.environ.get('AWS_REGION', 'us-east-1')
        self.s3 = boto3.client('s3', region_name=region)
        logger.info(f"☁️ Using S3Storage: bucket={self.bucket}, region={region}")

    def save(self, file_stream, filename):
        key = f"schedules/{uuid.uuid4().hex}_{filename}"
        if hasattr(file_stream, 'read'):
            self.s3.upload_fileobj(file_stream, self.bucket, key)
        else:
            self.s3.put_object(Bucket=self.bucket, Key=key, Body=file_stream)
        return key

    def load(self, storage_key):
        buf = io.BytesIO()
        self.s3.download_fileobj(self.bucket, storage_key, buf)
        buf.seek(0)
        return buf

    def delete(self, storage_key):
        try:
            self.s3.delete_object(Bucket=self.bucket, Key=storage_key)
            return True
        except Exception:
            return False

    def exists(self, storage_key):
        try:
            self.s3.head_object(Bucket=self.bucket, Key=storage_key)
            return True
        except Exception:
            return False

    def get_path(self, storage_key):
        """S3 doesn't have local paths; download to temp file."""
        import tempfile
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.tmp')
        buf = self.load(storage_key)
        tmp.write(buf.read())
        tmp.close()
        return tmp.name


# ═══════════════════════════════════════════════════════════
# FACTORY
# ═══════════════════════════════════════════════════════════

_storage_instance = None

def get_storage():
    """Get the singleton storage instance based on env vars."""
    global _storage_instance
    if _storage_instance is not None:
        return _storage_instance

    if os.environ.get('AWS_ACCESS_KEY_ID') and os.environ.get('S3_BUCKET_NAME'):
        try:
            _storage_instance = S3Storage()
            return _storage_instance
        except Exception as e:
            logger.warning(f"S3 storage init failed, falling back to local: {e}")

    _storage_instance = LocalDiskStorage()
    return _storage_instance
