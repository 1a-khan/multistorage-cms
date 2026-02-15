from django.conf import settings
from django.db import models
from django.utils.text import slugify


class ProjectHub(models.Model):
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True)
    description = models.TextField(blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='owned_project_hubs',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(fields=['owner', 'name'], name='uniq_project_hub_owner_name'),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name


class ProjectMembership(models.Model):
    class Role(models.TextChoices):
        OWNER = 'OWNER', 'Owner'
        ADMIN = 'ADMIN', 'Admin'
        EDITOR = 'EDITOR', 'Editor'
        VIEWER = 'VIEWER', 'Viewer'

    project_hub = models.ForeignKey(ProjectHub, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='project_memberships')
    role = models.CharField(max_length=20, choices=Role.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['project_hub', 'user'], name='uniq_project_membership'),
        ]

    def __str__(self) -> str:
        return f'{self.user_id}@{self.project_hub_id}:{self.role}'


class ProjectDashboard(models.Model):
    project_hub = models.ForeignKey(ProjectHub, on_delete=models.CASCADE, related_name='dashboards')
    name = models.CharField(max_length=120)
    layout_json = models.JSONField(default=dict, blank=True)
    is_default = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='created_project_dashboards',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['project_hub', 'name'],
                name='uniq_project_dashboard_name_per_hub',
            ),
        ]
        ordering = ['name']

    def __str__(self) -> str:
        return f'{self.project_hub_id}:{self.name}'
