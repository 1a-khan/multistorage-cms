from __future__ import annotations

from pathlib import Path

try:
    from celery import shared_task
except Exception:  # pragma: no cover
    def shared_task(*_args, **_kwargs):  # type: ignore
        def decorator(fn):
            fn.delay = fn  # mimic minimal Celery task API for local fallback
            fn.run = fn
            return fn

        return decorator
from django.db import transaction
from django.utils import timezone

from .models import DocumentVersion
from storage_backends.providers import get_provider


@shared_task(bind=True, max_retries=3, autoretry_for=(Exception,), retry_backoff=True)
def upload_document_version_task(self, version_id: int, source_path: str) -> None:
    with transaction.atomic():
        version = (
            DocumentVersion.objects.select_for_update()
            .select_related('storage_backend')
            .get(id=version_id)
        )
        version.upload_state = DocumentVersion.UploadState.UPLOADING
        version.error_message = ''
        version.save(update_fields=['upload_state', 'error_message'])

    source = Path(source_path)
    if not source.exists():
        raise FileNotFoundError(f'Source upload file missing: {source_path}')

    upload_succeeded = False
    try:
        provider = get_provider(version.storage_backend)
        stored_key = provider.upload(source, version.storage_key)

        with transaction.atomic():
            fresh = DocumentVersion.objects.select_for_update().get(id=version_id)
            fresh.storage_key = stored_key
            fresh.upload_state = DocumentVersion.UploadState.READY
            fresh.uploaded_at = timezone.now()
            fresh.error_message = ''
            fresh.save(update_fields=['storage_key', 'upload_state', 'uploaded_at', 'error_message'])
            upload_succeeded = True
    except Exception as exc:
        with transaction.atomic():
            failed = DocumentVersion.objects.select_for_update().get(id=version_id)
            failed.upload_state = DocumentVersion.UploadState.FAILED
            failed.error_message = str(exc)[:1000]
            failed.save(update_fields=['upload_state', 'error_message'])
        raise
    finally:
        if upload_succeeded and source.exists():
            source.unlink(missing_ok=True)
