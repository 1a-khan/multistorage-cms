from django.conf import settings
from django.db import models


class AuditEvent(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='audit_events',
    )
    event_type = models.CharField(max_length=80)
    document = models.ForeignKey(
        'documents.Document',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='audit_events',
    )
    project_hub = models.ForeignKey(
        'project_hubs.ProjectHub',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='audit_events',
    )
    payload_json = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f'{self.event_type} @ {self.created_at.isoformat()}'
