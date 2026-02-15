from django.conf import settings
from django.contrib import admin
from django.urls import include, path

from .views import home

urlpatterns = [
    path('', home, name='home'),
    path('admin/', admin.site.urls),
    path('accounts/', include('allauth.urls')) if settings.ENABLE_ALLAUTH else path('accounts/', include('django.contrib.auth.urls')),
    path('project-hubs/', include('project_hubs.urls')),
    path('', include('documents.urls')),
]

if settings.ENABLE_API:
    from rest_framework.authtoken.views import obtain_auth_token

    urlpatterns += [
        path('api/v1/', include('documents.api_urls')),
        path('api/v1/auth/token/', obtain_auth_token),
    ]
