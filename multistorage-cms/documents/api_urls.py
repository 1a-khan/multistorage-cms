from django.urls import path

from .api import DocumentDetailAPI, DocumentFileInfoAPI, DocumentListCreateAPI, DocumentOpenAPI

app_name = 'documents_api'

urlpatterns = [
    path('hubs/<slug:slug>/documents/', DocumentListCreateAPI.as_view(), name='documents'),
    path('hubs/<slug:slug>/documents/<uuid:pk>/', DocumentDetailAPI.as_view(), name='document_detail'),
    path('hubs/<slug:slug>/documents/<uuid:pk>/file-info/', DocumentFileInfoAPI.as_view(), name='document_file_info'),
    path('hubs/<slug:slug>/documents/<uuid:pk>/open/', DocumentOpenAPI.as_view(), name='document_open'),
]
