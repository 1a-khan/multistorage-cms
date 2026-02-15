from django.contrib import admin
from django.conf import settings
from django.urls import include, path

from .views import home

urlpatterns = [
    path('', home, name='home'),
    path('admin/', admin.site.urls),
    path('accounts/', include('allauth.urls')) if settings.ENABLE_ALLAUTH else path('accounts/', include('django.contrib.auth.urls')),
    path('project-hubs/', include('project_hubs.urls')),
    path('', include('documents.urls')),
]
