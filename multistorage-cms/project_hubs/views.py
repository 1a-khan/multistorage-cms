from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.generic import CreateView, DetailView, ListView

from documents.models import Document

from .forms import ProjectHubForm
from .models import ProjectDashboard, ProjectHub, ProjectMembership


class HubAccessMixin(LoginRequiredMixin):
    def get_hub(self):
        return get_object_or_404(
            ProjectHub.objects.filter(Q(owner=self.request.user) | Q(memberships__user=self.request.user)).distinct(),
            slug=self.kwargs['slug'],
        )


class ProjectHubListView(LoginRequiredMixin, ListView):
    model = ProjectHub
    template_name = 'project_hubs/list.html'
    context_object_name = 'hubs'

    def get_queryset(self):
        return ProjectHub.objects.filter(
            Q(owner=self.request.user) | Q(memberships__user=self.request.user)
        ).distinct().order_by('name')


class ProjectHubCreateView(LoginRequiredMixin, CreateView):
    model = ProjectHub
    form_class = ProjectHubForm
    template_name = 'project_hubs/create.html'

    def form_valid(self, form):
        form.instance.owner = self.request.user
        response = super().form_valid(form)
        ProjectMembership.objects.get_or_create(
            project_hub=self.object,
            user=self.request.user,
            defaults={'role': ProjectMembership.Role.OWNER},
        )
        ProjectDashboard.objects.get_or_create(
            project_hub=self.object,
            name='Overview',
            defaults={'created_by': self.request.user, 'is_default': True},
        )
        return response

    def get_success_url(self):
        return reverse('project_hubs:detail', kwargs={'slug': self.object.slug})


class ProjectHubDetailView(HubAccessMixin, DetailView):
    model = ProjectHub
    template_name = 'project_hubs/detail.html'
    context_object_name = 'hub'
    slug_field = 'slug'
    slug_url_kwarg = 'slug'

    def get_queryset(self):
        return ProjectHub.objects.filter(Q(owner=self.request.user) | Q(memberships__user=self.request.user)).distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['memberships'] = self.object.memberships.select_related('user').order_by('role', 'user__email')
        return context


class HubRecentDocumentsPartialView(HubAccessMixin, DetailView):
    model = ProjectHub
    template_name = 'project_hubs/partials/recent_documents.html'
    context_object_name = 'hub'
    slug_field = 'slug'
    slug_url_kwarg = 'slug'

    def get_queryset(self):
        return ProjectHub.objects.filter(Q(owner=self.request.user) | Q(memberships__user=self.request.user)).distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['recent_documents'] = Document.objects.filter(project_hub=self.object).order_by('-created_at')[:8]
        return context


def choose_hub_redirect(request, slug):
    return redirect('documents:list', slug=slug)
