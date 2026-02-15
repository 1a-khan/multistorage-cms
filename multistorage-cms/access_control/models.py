from django.conf import settings
from django.contrib.auth.models import Group
from django.db import models


class DocumentAccess(models.Model):
    class Role(models.TextChoices):
        VIEWER = 'VIEWER', 'Viewer'
        EDITOR = 'EDITOR', 'Editor'
        OWNER = 'OWNER', 'Owner'

    document = models.ForeignKey('documents.Document', on_delete=models.CASCADE, related_name='access_rules')
    subject_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='document_access_rules',
    )
    subject_group = models.ForeignKey(
        Group,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='document_access_rules',
    )
    role = models.CharField(max_length=20, choices=Role.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(subject_user__isnull=False, subject_group__isnull=True)
                    | models.Q(subject_user__isnull=True, subject_group__isnull=False)
                ),
                name='exactly_one_document_access_subject',
            ),
            models.UniqueConstraint(
                fields=['document', 'subject_user', 'role'],
                condition=models.Q(subject_user__isnull=False),
                name='uniq_document_user_role_access',
            ),
            models.UniqueConstraint(
                fields=['document', 'subject_group', 'role'],
                condition=models.Q(subject_group__isnull=False),
                name='uniq_document_group_role_access',
            ),
        ]


class FeatureFlag(models.Model):
    code = models.CharField(max_length=60, unique=True)
    name = models.CharField(max_length=120)
    enabled_globally = models.BooleanField(default=False)

    def __str__(self) -> str:
        return self.code


class UserFeatureOverride(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='feature_overrides')
    feature_flag = models.ForeignKey(FeatureFlag, on_delete=models.CASCADE, related_name='user_overrides')
    is_enabled = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'feature_flag'], name='uniq_user_feature_override'),
        ]
