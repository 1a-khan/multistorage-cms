from pathlib import Path
from unittest import mock

from django.test import TestCase, override_settings

from accounts.models import User
from documents.models import Document, DocumentVersion
from documents.tasks import upload_document_version_task
from project_hubs.models import ProjectHub, ProjectMembership
from storage_backends.models import StorageBackend


@override_settings(MEDIA_ROOT=Path('/tmp/multistorage-cms-test-media'))
class UploadDocumentVersionTaskTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='u@example.com', password='x')
        self.hub = ProjectHub.objects.create(name='Hub', slug='hub', owner=self.user)
        ProjectMembership.objects.create(
            project_hub=self.hub,
            user=self.user,
            role=ProjectMembership.Role.OWNER,
        )
        self.backend = StorageBackend.objects.create(
            name='Local',
            kind=StorageBackend.Kind.LOCAL,
            created_by=self.user,
            project_hub=self.hub,
        )
        self.document = Document.objects.create(
            owner=self.user,
            project_hub=self.hub,
            title='Doc',
            description='',
            mime_type='text/plain',
            size_bytes=3,
            checksum_sha256='abc',
            visibility=Document.Visibility.PRIVATE,
        )

    def _create_version(self):
        version = DocumentVersion.objects.create(
            document=self.document,
            version_number=1,
            storage_backend=self.backend,
            storage_key='hub/doc/file.txt',
            upload_state=DocumentVersion.UploadState.PENDING,
            uploaded_by=self.user,
        )
        self.document.current_version = version
        self.document.save(update_fields=['current_version'])
        return version

    def test_upload_task_sets_ready_on_success(self):
        version = self._create_version()
        source = Path('/tmp/multistorage-cms-task-source-success.txt')
        source.write_text('content', encoding='utf-8')

        fake_provider = mock.Mock()
        fake_provider.upload.return_value = 'storage/local/hub/doc/file.txt'

        with mock.patch('documents.tasks.get_provider', return_value=fake_provider):
            upload_document_version_task.run(version.id, str(source))

        version.refresh_from_db()
        self.assertEqual(version.upload_state, DocumentVersion.UploadState.READY)
        self.assertEqual(version.storage_key, 'storage/local/hub/doc/file.txt')
        self.assertIsNotNone(version.uploaded_at)
        self.assertEqual(version.error_message, '')
        self.assertFalse(source.exists())

    def test_upload_task_sets_failed_on_error(self):
        version = self._create_version()
        source = Path('/tmp/multistorage-cms-task-source-fail.txt')
        source.write_text('content', encoding='utf-8')

        fake_provider = mock.Mock()
        fake_provider.upload.side_effect = RuntimeError('upload exploded')

        with mock.patch('documents.tasks.get_provider', return_value=fake_provider):
            with self.assertRaises(RuntimeError):
                upload_document_version_task.run(version.id, str(source))

        version.refresh_from_db()
        self.assertEqual(version.upload_state, DocumentVersion.UploadState.FAILED)
        self.assertIn('upload exploded', version.error_message)
        self.assertTrue(source.exists())
        source.unlink(missing_ok=True)
