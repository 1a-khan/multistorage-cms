from django.urls import path

from .views import (
    HubRecentDocumentsPartialView,
    ProjectHubCreateView,
    ProjectHubDetailView,
    ProjectHubListView,
    choose_hub_redirect,
)

app_name = 'project_hubs'

urlpatterns = [
    path('', ProjectHubListView.as_view(), name='list'),
    path('create/', ProjectHubCreateView.as_view(), name='create'),
    path('<slug:slug>/', ProjectHubDetailView.as_view(), name='detail'),
    path('<slug:slug>/recent-documents/', HubRecentDocumentsPartialView.as_view(), name='recent_documents'),
    path('<slug:slug>/open/', choose_hub_redirect, name='open'),
]
