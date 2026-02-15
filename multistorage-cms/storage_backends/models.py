from django.conf import settings
from django.db import models


class StorageBackend(models.Model):
    class Kind(models.TextChoices):
        S3 = 'S3', 'S3 Compatible'
        GDRIVE = 'GDRIVE', 'Google Drive'
        LOCAL = 'LOCAL', 'Local'
        BLOB = 'BLOB', 'Blob Storage'

    class Status(models.TextChoices):
        ACTIVE = 'ACTIVE', 'Active'
        DISABLED = 'DISABLED', 'Disabled'

    name = models.CharField(max_length=120, unique=True)
    kind = models.CharField(max_length=20, choices=Kind.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    config_encrypted = models.JSONField(default=dict, blank=True)
    project_hub = models.ForeignKey(
        'project_hubs.ProjectHub',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='storage_backends',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='created_storage_backends',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self) -> str:
        return f'{self.name} ({self.kind})'
