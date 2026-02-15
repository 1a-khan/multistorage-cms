from django.contrib import admin

from .models import StorageBackend


@admin.register(StorageBackend)
class StorageBackendAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'kind', 'status', 'project_hub', 'created_by', 'updated_at')
    list_filter = ('kind', 'status', 'project_hub')
    search_fields = ('name', 'created_by__email')
