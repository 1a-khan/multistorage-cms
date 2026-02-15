import hashlib
import os
import uuid
from pathlib import Path
from urllib.parse import urlparse

from django.contrib import messages
from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View
from django.views.generic import DeleteView, DetailView, FormView, ListView, UpdateView

from project_hubs.models import ProjectHub, ProjectMembership

from .forms import DocumentEditForm, DocumentUploadForm
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

    def hub_roles_for_user(self):
        hub = self.get_hub()
        if hub.owner_id == self.request.user.id:
            return {ProjectMembership.Role.OWNER}
        return set(
            ProjectMembership.objects.filter(project_hub=hub, user=self.request.user).values_list('role', flat=True)
        )

    def can_manage_documents(self):
        return bool(
            self.hub_roles_for_user()
            & {
                ProjectMembership.Role.OWNER,
                ProjectMembership.Role.ADMIN,
                ProjectMembership.Role.EDITOR,
            }
        )

    def can_delete_documents(self):
        return bool(
            self.hub_roles_for_user()
            & {
                ProjectMembership.Role.OWNER,
                ProjectMembership.Role.ADMIN,
            }
        )


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
        context['can_open_file'] = bool(current_version and current_version.upload_state == DocumentVersion.UploadState.READY)
        context['can_manage_document'] = self.can_manage_documents() or self.object.owner_id == self.request.user.id
        context['can_delete_document'] = self.can_delete_documents() or self.object.owner_id == self.request.user.id
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


class DocumentFileAccessMixin(HubMembershipMixin):
    def get_document(self):
        hub = self.get_hub()
        return get_object_or_404(
            Document.objects.filter(project_hub=hub)
            .filter(
                Q(owner=self.request.user)
                | Q(access_rules__subject_user=self.request.user)
                | Q(access_rules__subject_group__in=self.request.user.groups.all())
            )
            .select_related('current_version__storage_backend')
            .distinct(),
            pk=self.kwargs['pk'],
        )

    def build_file_info(self, document):
        version = document.current_version
        if not version:
            return {'ready': False, 'reason': 'no_current_version'}
        if version.upload_state != DocumentVersion.UploadState.READY:
            return {'ready': False, 'reason': f'upload_state_{version.upload_state.lower()}'}

        backend = version.storage_backend
        storage_key = version.storage_key
        info = {
            'ready': True,
            'backend_kind': backend.kind,
            'storage_key': storage_key,
            'mime_type': document.mime_type,
            'size_bytes': document.size_bytes,
            'document_id': str(document.pk),
            'version_id': version.id,
        }
        if backend.kind == 'S3':
            info['location_type'] = 's3_uri'
        elif backend.kind == 'GDRIVE':
            info['location_type'] = 'google_drive_file'
        else:
            info['location_type'] = 'local_path'
        return info


class DocumentFileInfoView(DocumentFileAccessMixin, View):
    def get(self, request, *args, **kwargs):
        document = self.get_document()
        return JsonResponse(self.build_file_info(document))


class DocumentOpenView(DocumentFileAccessMixin, View):
    def get(self, request, *args, **kwargs):
        document = self.get_document()
        info = self.build_file_info(document)
        if not info.get('ready'):
            return JsonResponse(info, status=409)

        version = document.current_version
        backend = version.storage_backend
        storage_key = version.storage_key

        if backend.kind == backend.Kind.LOCAL:
            path = Path(storage_key)
            if not path.is_absolute():
                path = Path(settings.MEDIA_ROOT) / storage_key
            if not path.exists():
                return JsonResponse({'ready': False, 'reason': 'file_missing', 'storage_key': storage_key}, status=404)
            return FileResponse(path.open('rb'), content_type=document.mime_type or 'application/octet-stream')

        if backend.kind == backend.Kind.S3:
            try:
                import boto3
            except Exception:
                return JsonResponse({'ready': False, 'reason': 'boto3_missing'}, status=500)

            cfg = backend.config_encrypted or {}
            parsed = urlparse(storage_key) if storage_key.startswith('s3://') else None
            bucket = parsed.netloc if parsed else cfg.get('bucket')
            key = parsed.path.lstrip('/') if parsed else storage_key
            if not bucket:
                return JsonResponse({'ready': False, 'reason': 'bucket_missing'}, status=500)
            region = cfg.get('region')
            endpoint_url = cfg.get('endpoint_url')
            access_key = cfg.get('access_key') or (cfg.get('access_key_env') and os.getenv(cfg.get('access_key_env')))
            secret_key = cfg.get('secret_key') or (cfg.get('secret_key_env') and os.getenv(cfg.get('secret_key_env')))
            client_kwargs = {
                'service_name': 's3',
                'region_name': region,
                'endpoint_url': endpoint_url,
                'aws_access_key_id': access_key,
                'aws_secret_access_key': secret_key,
            }
            client = boto3.client(**{k: v for k, v in client_kwargs.items() if v})
            url = client.generate_presigned_url(
                ClientMethod='get_object',
                Params={'Bucket': bucket, 'Key': key},
                ExpiresIn=300,
            )
            return redirect(url)

        if backend.kind == backend.Kind.GDRIVE and storage_key.startswith('gdrive://'):
            file_id = storage_key.replace('gdrive://', '', 1).split(':', 1)[0]
            return redirect(f'https://drive.google.com/file/d/{file_id}/view')

        return JsonResponse({'ready': False, 'reason': 'unsupported_backend'}, status=400)


class DocumentUploadView(HubMembershipMixin, FormView):
    form_class = DocumentUploadForm
    template_name = 'documents/upload.html'

    def dispatch(self, request, *args, **kwargs):
        self.hub = self.get_hub()
        can_upload = self.can_manage_documents()
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


class DocumentUpdateView(HubMembershipMixin, UpdateView):
    model = Document
    form_class = DocumentEditForm
    template_name = 'documents/edit.html'
    context_object_name = 'document'

    def get_queryset(self):
        hub = self.get_hub()
        return Document.objects.filter(project_hub=hub).select_related('owner', 'current_version')

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        can_edit = self.object.owner_id == request.user.id or self.can_manage_documents()
        if not can_edit:
            raise Http404('You do not have permission to edit this document.')
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        messages.success(self.request, 'Document metadata updated.')
        return reverse('documents:detail', kwargs={'slug': self.kwargs['slug'], 'pk': self.object.pk})


class DocumentDeleteView(HubMembershipMixin, DeleteView):
    model = Document
    template_name = 'documents/delete.html'
    context_object_name = 'document'

    def get_queryset(self):
        hub = self.get_hub()
        return Document.objects.filter(project_hub=hub).select_related('owner')

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        can_delete = self.object.owner_id == request.user.id or self.can_delete_documents()
        if not can_delete:
            raise Http404('You do not have permission to delete this document.')
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        messages.success(self.request, 'Document deleted.')
        return reverse('documents:list', kwargs={'slug': self.kwargs['slug']})
