from django.urls import path

from .views import DocumentDetailView, DocumentListView, DocumentStatusPartialView, DocumentUploadView

app_name = 'documents'

urlpatterns = [
    path('hubs/<slug:slug>/documents/', DocumentListView.as_view(), name='list'),
    path('hubs/<slug:slug>/documents/upload/', DocumentUploadView.as_view(), name='upload'),
    path('hubs/<slug:slug>/documents/<uuid:pk>/', DocumentDetailView.as_view(), name='detail'),
    path('hubs/<slug:slug>/documents/<uuid:pk>/status/', DocumentStatusPartialView.as_view(), name='status'),
]
