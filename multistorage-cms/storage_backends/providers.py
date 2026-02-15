from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from django.conf import settings

from storage_backends.models import StorageBackend


class StorageProvider:
    def __init__(self, storage_backend: StorageBackend):
        self.storage_backend = storage_backend
        self.config = storage_backend.config_encrypted or {}

    def upload(self, local_path: Path, storage_key: str) -> str:
        raise NotImplementedError

    def _resolve_config_value(self, direct_key: str, env_key_name_key: str) -> Any:
        direct = self.config.get(direct_key)
        if direct not in (None, ''):
            return direct
        env_name = self.config.get(env_key_name_key)
        if env_name:
            return os.getenv(env_name, '')
        return None


class LocalStorageProvider(StorageProvider):
    def upload(self, local_path: Path, storage_key: str) -> str:
        root_override = self.config.get('root_dir')
        root = Path(root_override) if root_override else Path(settings.MEDIA_ROOT) / 'storage' / 'local'
        target = root / storage_key
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(local_path.read_bytes())
        try:
            return str(target.relative_to(settings.MEDIA_ROOT))
        except Exception:
            return str(target)


class S3StorageProvider(StorageProvider):
    def upload(self, local_path: Path, storage_key: str) -> str:
        try:
            import boto3
        except Exception as exc:
            raise RuntimeError('boto3 is required for S3 uploads.') from exc

        bucket = self.config.get('bucket')
        region = self.config.get('region')
        endpoint_url = self.config.get('endpoint_url')
        access_key = self._resolve_config_value('access_key', 'access_key_env')
        secret_key = self._resolve_config_value('secret_key', 'secret_key_env')
        object_prefix = self.config.get('object_prefix', '').strip('/')

        if not bucket:
            raise ValueError('S3 storage backend requires `bucket` in config_encrypted.')

        object_key = f'{object_prefix}/{storage_key}' if object_prefix else storage_key
        client_kwargs: dict[str, Any] = {
            'service_name': 's3',
            'region_name': region,
            'endpoint_url': endpoint_url,
            'aws_access_key_id': access_key,
            'aws_secret_access_key': secret_key,
        }
        client = boto3.client(**{k: v for k, v in client_kwargs.items() if v})
        extra_args = {}
        content_type = self.config.get('content_type')
        if content_type:
            extra_args['ContentType'] = content_type
        client.upload_file(str(local_path), bucket, object_key, ExtraArgs=extra_args or None)
        return f's3://{bucket}/{object_key}'


class GoogleDriveStorageProvider(StorageProvider):
    def upload(self, local_path: Path, storage_key: str) -> str:
        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaFileUpload
        except Exception as exc:
            raise RuntimeError(
                'google-api-python-client and google-auth are required for Google Drive uploads.'
            ) from exc

        folder_id = self._resolve_config_value('folder_id', 'folder_id_env')
        service_account_json = self._resolve_config_value('service_account_json', 'service_account_json_env')
        service_account_file = self._resolve_config_value('service_account_file', 'service_account_file_env')
        if not folder_id:
            raise ValueError('Google Drive backend requires `folder_id` in config_encrypted.')
        if not service_account_json and not service_account_file:
            raise ValueError(
                'Google Drive backend requires either `service_account_json` or `service_account_file`.'
            )

        scopes = ['https://www.googleapis.com/auth/drive.file']
        if service_account_json:
            if isinstance(service_account_json, str):
                service_account_info = json.loads(service_account_json)
            else:
                service_account_info = service_account_json
            credentials = service_account.Credentials.from_service_account_info(service_account_info, scopes=scopes)
        else:
            credentials = service_account.Credentials.from_service_account_file(service_account_file, scopes=scopes)

        drive = build('drive', 'v3', credentials=credentials, cache_discovery=False)
        file_name = Path(storage_key).name
        metadata = {'name': file_name, 'parents': [folder_id]}
        media = MediaFileUpload(str(local_path), resumable=True)
        created = drive.files().create(
            body=metadata,
            media_body=media,
            fields='id,name',
            supportsAllDrives=True,
        ).execute()
        return f'gdrive://{created["id"]}:{created["name"]}'


def get_provider(storage_backend: StorageBackend) -> StorageProvider:
    if storage_backend.kind == StorageBackend.Kind.LOCAL:
        return LocalStorageProvider(storage_backend)
    if storage_backend.kind == StorageBackend.Kind.S3:
        return S3StorageProvider(storage_backend)
    if storage_backend.kind == StorageBackend.Kind.GDRIVE:
        return GoogleDriveStorageProvider(storage_backend)
    raise ValueError(f'Unsupported storage backend kind: {storage_backend.kind}')
