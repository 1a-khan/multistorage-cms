import os
from pathlib import Path
from urllib.parse import urlparse

from django.conf import settings
from django.db.models import Q
from django.http import FileResponse
from django.shortcuts import get_object_or_404

from rest_framework import serializers, status
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from project_hubs.models import ProjectHub, ProjectMembership
from storage_backends.models import StorageBackend

from .models import Document, DocumentVersion


class DocumentSerializer(serializers.ModelSerializer):
    current_version_state = serializers.CharField(source='current_version.upload_state', read_only=True)
    current_storage_key = serializers.CharField(source='current_version.storage_key', read_only=True)

    class Meta:
        model = Document
        fields = [
            'id',
            'title',
            'description',
            'mime_type',
            'size_bytes',
            'checksum_sha256',
            'visibility',
            'created_at',
            'updated_at',
            'current_version_state',
            'current_storage_key',
        ]


class DocumentWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = ['title', 'description', 'visibility']


class HubAPIMixin:
    authentication_classes = [SessionAuthentication, TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get_hub(self, slug):
        return get_object_or_404(
            ProjectHub.objects.filter(Q(owner=self.request.user) | Q(memberships__user=self.request.user)).distinct(),
            slug=slug,
        )

    def get_roles(self, hub):
        if hub.owner_id == self.request.user.id:
            return {ProjectMembership.Role.OWNER}
        return set(ProjectMembership.objects.filter(project_hub=hub, user=self.request.user).values_list('role', flat=True))

    def can_manage(self, hub):
        return bool(self.get_roles(hub) & {ProjectMembership.Role.OWNER, ProjectMembership.Role.ADMIN, ProjectMembership.Role.EDITOR})

    def can_delete(self, hub):
        return bool(self.get_roles(hub) & {ProjectMembership.Role.OWNER, ProjectMembership.Role.ADMIN})

    def accessible_documents(self, hub):
        return (
            Document.objects.filter(project_hub=hub)
            .filter(
                Q(owner=self.request.user)
                | Q(access_rules__subject_user=self.request.user)
                | Q(access_rules__subject_group__in=self.request.user.groups.all())
            )
            .select_related('current_version', 'owner')
            .distinct()
        )

    def build_file_info(self, document):
        version = document.current_version
        if not version:
            return {'ready': False, 'reason': 'no_current_version'}
        if version.upload_state != DocumentVersion.UploadState.READY:
            return {'ready': False, 'reason': f'upload_state_{version.upload_state.lower()}'}

        backend = version.storage_backend
        info = {
            'ready': True,
            'backend_kind': backend.kind,
            'storage_key': version.storage_key,
            'mime_type': document.mime_type,
            'size_bytes': document.size_bytes,
            'document_id': str(document.pk),
            'version_id': version.id,
        }
        if backend.kind == StorageBackend.Kind.S3:
            info['location_type'] = 's3_uri'
        elif backend.kind == StorageBackend.Kind.GDRIVE:
            info['location_type'] = 'google_drive_file'
        else:
            info['location_type'] = 'local_path'
        return info


class DocumentListCreateAPI(HubAPIMixin, APIView):
    def get(self, request, slug):
        hub = self.get_hub(slug)
        qs = self.accessible_documents(hub).order_by('-created_at')
        query = request.query_params.get('q', '').strip()
        visibility = request.query_params.get('visibility', '').strip()
        if query:
            qs = qs.filter(Q(title__icontains=query) | Q(description__icontains=query))
        if visibility:
            qs = qs.filter(visibility=visibility)
        return Response(DocumentSerializer(qs, many=True).data)

    def post(self, request, slug):
        hub = self.get_hub(slug)
        if not self.can_manage(hub):
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        serializer = DocumentWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        document = Document.objects.create(
            owner=request.user,
            project_hub=hub,
            title=data['title'],
            description=data.get('description', ''),
            visibility=data['visibility'],
            mime_type=request.data.get('mime_type', 'application/octet-stream'),
            size_bytes=int(request.data.get('size_bytes', 0)),
            checksum_sha256=request.data.get('checksum_sha256', ''),
        )
        return Response(DocumentSerializer(document).data, status=status.HTTP_201_CREATED)


class DocumentDetailAPI(HubAPIMixin, APIView):
    def get_object(self, slug, pk):
        hub = self.get_hub(slug)
        return get_object_or_404(self.accessible_documents(hub), pk=pk), hub

    def get(self, request, slug, pk):
        document, _hub = self.get_object(slug, pk)
        return Response(DocumentSerializer(document).data)

    def patch(self, request, slug, pk):
        document, hub = self.get_object(slug, pk)
        if not (document.owner_id == request.user.id or self.can_manage(hub)):
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
        serializer = DocumentWriteSerializer(document, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(DocumentSerializer(document).data)

    def delete(self, request, slug, pk):
        document, hub = self.get_object(slug, pk)
        if not (document.owner_id == request.user.id or self.can_delete(hub)):
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
        document.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class DocumentFileInfoAPI(HubAPIMixin, APIView):
    def get(self, request, slug, pk):
        hub = self.get_hub(slug)
        document = get_object_or_404(self.accessible_documents(hub).select_related('current_version__storage_backend'), pk=pk)
        return Response(self.build_file_info(document))


class DocumentOpenAPI(HubAPIMixin, APIView):
    def get(self, request, slug, pk):
        hub = self.get_hub(slug)
        document = get_object_or_404(self.accessible_documents(hub).select_related('current_version__storage_backend'), pk=pk)
        info = self.build_file_info(document)
        if not info.get('ready'):
            return Response(info, status=status.HTTP_409_CONFLICT)

        version = document.current_version
        backend = version.storage_backend
        storage_key = version.storage_key

        if backend.kind == backend.Kind.LOCAL:
            path = Path(storage_key)
            if not path.is_absolute():
                path = Path(settings.MEDIA_ROOT) / storage_key
            if not path.exists():
                return Response({'ready': False, 'reason': 'file_missing', 'storage_key': storage_key}, status=404)
            return FileResponse(path.open('rb'), content_type=document.mime_type or 'application/octet-stream')

        if backend.kind == backend.Kind.S3:
            try:
                import boto3
            except Exception:
                return Response({'ready': False, 'reason': 'boto3_missing'}, status=500)
            cfg = backend.config_encrypted or {}
            parsed = urlparse(storage_key) if storage_key.startswith('s3://') else None
            bucket = parsed.netloc if parsed else cfg.get('bucket')
            key = parsed.path.lstrip('/') if parsed else storage_key
            access_key = cfg.get('access_key') or (cfg.get('access_key_env') and os.getenv(cfg.get('access_key_env')))
            secret_key = cfg.get('secret_key') or (cfg.get('secret_key_env') and os.getenv(cfg.get('secret_key_env')))
            client = boto3.client(
                service_name='s3',
                region_name=cfg.get('region'),
                endpoint_url=cfg.get('endpoint_url'),
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
            )
            url = client.generate_presigned_url(
                ClientMethod='get_object',
                Params={'Bucket': bucket, 'Key': key},
                ExpiresIn=300,
            )
            return Response({'ready': True, 'mode': 'redirect', 'url': url})

        if backend.kind == backend.Kind.GDRIVE and storage_key.startswith('gdrive://'):
            file_id = storage_key.replace('gdrive://', '', 1).split(':', 1)[0]
            return Response({'ready': True, 'mode': 'redirect', 'url': f'https://drive.google.com/file/d/{file_id}/view'})

        return Response({'ready': False, 'reason': 'unsupported_backend'}, status=status.HTTP_400_BAD_REQUEST)
