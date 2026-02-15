from django.urls import path

from .views import (
    DocumentDeleteView,
    DocumentDetailView,
    DocumentFileInfoView,
    DocumentListView,
    DocumentOpenView,
    DocumentStatusPartialView,
    DocumentUpdateView,
    DocumentUploadView,
)

app_name = 'documents'

urlpatterns = [
    path('hubs/<slug:slug>/documents/', DocumentListView.as_view(), name='list'),
    path('hubs/<slug:slug>/documents/upload/', DocumentUploadView.as_view(), name='upload'),
    path('hubs/<slug:slug>/documents/<uuid:pk>/', DocumentDetailView.as_view(), name='detail'),
    path('hubs/<slug:slug>/documents/<uuid:pk>/open/', DocumentOpenView.as_view(), name='open'),
    path('hubs/<slug:slug>/documents/<uuid:pk>/file-info/', DocumentFileInfoView.as_view(), name='file_info'),
    path('hubs/<slug:slug>/documents/<uuid:pk>/edit/', DocumentUpdateView.as_view(), name='edit'),
    path('hubs/<slug:slug>/documents/<uuid:pk>/delete/', DocumentDeleteView.as_view(), name='delete'),
    path('hubs/<slug:slug>/documents/<uuid:pk>/status/', DocumentStatusPartialView.as_view(), name='status'),
]
