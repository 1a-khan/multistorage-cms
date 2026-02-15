from django.contrib import admin

from .models import ProjectDashboard, ProjectHub, ProjectMembership


@admin.register(ProjectHub)
class ProjectHubAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'slug', 'owner', 'created_at')
    search_fields = ('name', 'slug', 'owner__email')
    list_filter = ('created_at',)


@admin.register(ProjectMembership)
class ProjectMembershipAdmin(admin.ModelAdmin):
    list_display = ('id', 'project_hub', 'user', 'role', 'created_at')
    list_filter = ('role', 'created_at')
    search_fields = ('project_hub__name', 'user__email')


@admin.register(ProjectDashboard)
class ProjectDashboardAdmin(admin.ModelAdmin):
    list_display = ('id', 'project_hub', 'name', 'is_default', 'created_by', 'updated_at')
    list_filter = ('is_default', 'updated_at')
    search_fields = ('name', 'project_hub__name', 'created_by__email')
