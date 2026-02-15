import uuid

from django.conf import settings
from django.db import models


class Document(models.Model):
    class Visibility(models.TextChoices):
        PRIVATE = 'PRIVATE', 'Private'
        TEAM = 'TEAM', 'Team'
        PUBLIC_LINK = 'PUBLIC_LINK', 'Public Link'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='documents',
    )
    project_hub = models.ForeignKey(
        'project_hubs.ProjectHub',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='documents',
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    mime_type = models.CharField(max_length=100)
    size_bytes = models.BigIntegerField()
    checksum_sha256 = models.CharField(max_length=64)
    current_version = models.ForeignKey(
        'DocumentVersion',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
    )
    visibility = models.CharField(max_length=20, choices=Visibility.choices, default=Visibility.PRIVATE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self) -> str:
        return self.title


class DocumentVersion(models.Model):
    class UploadState(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        UPLOADING = 'UPLOADING', 'Uploading'
        READY = 'READY', 'Ready'
        FAILED = 'FAILED', 'Failed'

    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='versions')
    version_number = models.PositiveIntegerField()
    storage_backend = models.ForeignKey(
        'storage_backends.StorageBackend',
        on_delete=models.PROTECT,
        related_name='document_versions',
    )
    storage_key = models.CharField(max_length=512)
    upload_state = models.CharField(max_length=20, choices=UploadState.choices, default=UploadState.PENDING)
    uploaded_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='uploaded_document_versions',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['document', 'version_number'], name='uniq_document_version_number'),
        ]
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f'{self.document_id} v{self.version_number}'


class DocumentTag(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='tags')
    tag = models.CharField(max_length=50)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['document', 'tag'], name='uniq_document_tag'),
        ]

    def __str__(self) -> str:
        return f'{self.document_id}:{self.tag}'
