import hashlib
import uuid
from pathlib import Path

from django.contrib import messages
from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.generic import DetailView, FormView, ListView

from project_hubs.models import ProjectHub, ProjectMembership

from .forms import DocumentUploadForm
from .models import Document, DocumentVersion


class HubMembershipMixin(LoginRequiredMixin):
    def get_hub(self):
        return get_object_or_404(
            ProjectHub.objects.filter(Q(owner=self.request.user) | Q(memberships__user=self.request.user)).distinct(),
            slug=self.kwargs['slug'],
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['hub'] = self.get_hub()
        return context


class DocumentListView(HubMembershipMixin, ListView):
    model = Document
    template_name = 'documents/list.html'
    context_object_name = 'documents'

    def get_queryset(self):
        hub = self.get_hub()
        queryset = (
            Document.objects.filter(project_hub=hub)
            .filter(
                Q(owner=self.request.user)
                | Q(access_rules__subject_user=self.request.user)
                | Q(access_rules__subject_group__in=self.request.user.groups.all())
            )
            .select_related('owner', 'current_version', 'project_hub')
            .distinct()
            .order_by('-created_at')
        )
        query = self.request.GET.get('q', '').strip()
        visibility = self.request.GET.get('visibility', '').strip()
        if query:
            queryset = queryset.filter(Q(title__icontains=query) | Q(description__icontains=query))
        if visibility:
            queryset = queryset.filter(visibility=visibility)
        return queryset

    def get_template_names(self):
        if self.request.headers.get('HX-Request') == 'true':
            return ['documents/partials/document_table.html']
        return [self.template_name]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['q'] = self.request.GET.get('q', '').strip()
        context['visibility'] = self.request.GET.get('visibility', '').strip()
        context['visibility_choices'] = Document.Visibility.choices
        return context


class DocumentDetailView(HubMembershipMixin, DetailView):
    model = Document
    template_name = 'documents/detail.html'
    context_object_name = 'document'

    def get_queryset(self):
        hub = self.get_hub()
        return (
            Document.objects.filter(project_hub=hub)
            .filter(
                Q(owner=self.request.user)
                | Q(access_rules__subject_user=self.request.user)
                | Q(access_rules__subject_group__in=self.request.user.groups.all())
            )
            .select_related('owner', 'current_version', 'project_hub')
            .distinct()
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        current_version = self.object.current_version
        context['should_poll_status'] = bool(
            current_version and current_version.upload_state in {
                DocumentVersion.UploadState.PENDING,
                DocumentVersion.UploadState.UPLOADING,
            }
        )
        return context


class DocumentStatusPartialView(HubMembershipMixin, DetailView):
    model = Document
    template_name = 'documents/partials/upload_status.html'
    context_object_name = 'document'

    def get_queryset(self):
        hub = self.get_hub()
        return (
            Document.objects.filter(project_hub=hub)
            .filter(
                Q(owner=self.request.user)
                | Q(access_rules__subject_user=self.request.user)
                | Q(access_rules__subject_group__in=self.request.user.groups.all())
            )
            .select_related('owner', 'current_version', 'project_hub')
            .distinct()
        )


class DocumentUploadView(HubMembershipMixin, FormView):
    form_class = DocumentUploadForm
    template_name = 'documents/upload.html'

    def dispatch(self, request, *args, **kwargs):
        self.hub = self.get_hub()
        can_upload = ProjectMembership.objects.filter(
            project_hub=self.hub,
            user=request.user,
            role__in=[
                ProjectMembership.Role.OWNER,
                ProjectMembership.Role.ADMIN,
                ProjectMembership.Role.EDITOR,
            ],
        ).exists() or self.hub.owner_id == request.user.id
        if not can_upload:
            raise Http404('You do not have upload permissions for this hub.')
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['project_hub'] = self.hub
        return kwargs

    def form_valid(self, form):
        uploaded_file = form.cleaned_data['file']
        storage_backend = form.cleaned_data['storage_backend']

        sha256 = hashlib.sha256()
        for chunk in uploaded_file.chunks():
            sha256.update(chunk)

        document = Document.objects.create(
            owner=self.request.user,
            project_hub=self.hub,
            title=form.cleaned_data['title'],
            description=form.cleaned_data['description'],
            mime_type=uploaded_file.content_type or 'application/octet-stream',
            size_bytes=uploaded_file.size,
            checksum_sha256=sha256.hexdigest(),
            visibility=form.cleaned_data['visibility'],
        )

        version = DocumentVersion.objects.create(
            document=document,
            version_number=1,
            storage_backend=storage_backend,
            storage_key=f'{self.hub.slug}/{document.id}/{uploaded_file.name}',
            upload_state=DocumentVersion.UploadState.PENDING,
            uploaded_by=self.request.user,
        )

        document.current_version = version
        document.save(update_fields=['current_version'])

        tmp_root = Path(settings.MEDIA_ROOT) / 'tmp_uploads'
        tmp_root.mkdir(parents=True, exist_ok=True)
        temp_file = tmp_root / f'{uuid.uuid4()}_{uploaded_file.name}'
        with temp_file.open('wb') as out:
            for chunk in uploaded_file.chunks():
                out.write(chunk)

        try:
            from .tasks import upload_document_version_task

            upload_document_version_task.delay(version.id, str(temp_file))
        except Exception:
            version.upload_state = DocumentVersion.UploadState.FAILED
            version.error_message = 'Background worker unavailable. Install/start Celery worker.'
            version.save(update_fields=['upload_state', 'error_message'])

        messages.success(self.request, 'Document upload was initiated successfully.')
        return redirect('documents:detail', slug=self.hub.slug, pk=document.pk)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['hub'] = self.hub
        return context
