from pathlib import Path
from types import ModuleType
from unittest import mock

from django.test import TestCase, override_settings

from accounts.models import User
from storage_backends.models import StorageBackend
from storage_backends.providers import GoogleDriveStorageProvider, LocalStorageProvider, S3StorageProvider


@override_settings(MEDIA_ROOT=Path('/tmp/multistorage-cms-test-media'))
class LocalStorageProviderTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='owner@example.com', password='x')

    def test_local_provider_uploads_file_and_returns_relative_path(self):
        backend = StorageBackend.objects.create(
            name='Local Test',
            kind=StorageBackend.Kind.LOCAL,
            created_by=self.user,
        )
        provider = LocalStorageProvider(backend)

        source = Path('/tmp/multistorage-cms-test-source.txt')
        source.write_text('hello world', encoding='utf-8')

        try:
            stored_key = provider.upload(source, 'hub/doc/file.txt')
            self.assertIn('storage/local/hub/doc/file.txt', stored_key)
            target = Path('/tmp/multistorage-cms-test-media') / stored_key
            self.assertTrue(target.exists())
            self.assertEqual(target.read_text(encoding='utf-8'), 'hello world')
        finally:
            source.unlink(missing_ok=True)


class CloudProviderTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='cloud-owner@example.com', password='x')

    def test_s3_provider_supports_env_credentials(self):
        with mock.patch.dict('os.environ', {'AWS_ACCESS_KEY_ID': 'abc-env', 'AWS_SECRET_ACCESS_KEY': 'def-env'}):
            backend = StorageBackend.objects.create(
                name='S3 Backend',
                kind=StorageBackend.Kind.S3,
                created_by=self.user,
                config_encrypted={
                    'bucket': 'demo-bucket',
                    'region': 'us-east-1',
                    'access_key_env': 'AWS_ACCESS_KEY_ID',
                    'secret_key_env': 'AWS_SECRET_ACCESS_KEY',
                    'endpoint_url': 'https://s3.amazonaws.com',
                    'object_prefix': 'uploads',
                },
            )
            provider = S3StorageProvider(backend)
            source = Path('/tmp/multistorage-cms-s3-source.txt')
            source.write_text('s3-content', encoding='utf-8')
            try:
                fake_client = mock.Mock()
                fake_boto3 = ModuleType('boto3')
                fake_boto3.client = mock.Mock(return_value=fake_client)
                with mock.patch.dict('sys.modules', {'boto3': fake_boto3}):
                    result = provider.upload(source, 'hub/doc.txt')

                self.assertEqual(result, 's3://demo-bucket/uploads/hub/doc.txt')
                fake_boto3.client.assert_called_once_with(
                    service_name='s3',
                    region_name='us-east-1',
                    endpoint_url='https://s3.amazonaws.com',
                    aws_access_key_id='abc-env',
                    aws_secret_access_key='def-env',
                )
                fake_client.upload_file.assert_called_once()
            finally:
                source.unlink(missing_ok=True)

    def test_google_drive_provider_supports_service_account_json_env(self):
        service_json = (
            '{"type":"service_account","project_id":"demo-project","private_key_id":"k",'
            '"private_key":"-----BEGIN PRIVATE KEY-----\\nabc\\n-----END PRIVATE KEY-----\\n",'
            '"client_email":"svc@example.iam.gserviceaccount.com","client_id":"123",'
            '"token_uri":"https://oauth2.googleapis.com/token"}'
        )

        with mock.patch.dict('os.environ', {'GDRIVE_SERVICE_ACCOUNT_JSON': service_json}):
            backend = StorageBackend.objects.create(
                name='Drive Backend Env',
                kind=StorageBackend.Kind.GDRIVE,
                created_by=self.user,
                config_encrypted={
                    'folder_id': 'folder123',
                    'service_account_json_env': 'GDRIVE_SERVICE_ACCOUNT_JSON',
                },
            )
            provider = GoogleDriveStorageProvider(backend)
            source = Path('/tmp/multistorage-cms-gdrive-source-env.txt')
            source.write_text('drive-content', encoding='utf-8')
            try:
                credentials_obj = object()

                class FakeCredentials:
                    @staticmethod
                    def from_service_account_info(_info, scopes):
                        assert scopes == ['https://www.googleapis.com/auth/drive.file']
                        return credentials_obj

                fake_service_account_module = ModuleType('google.oauth2.service_account')
                fake_service_account_module.Credentials = FakeCredentials
                fake_google_module = ModuleType('google')
                fake_google_oauth2_module = ModuleType('google.oauth2')
                fake_google_oauth2_module.service_account = fake_service_account_module

                fake_drive_files = mock.Mock()
                fake_drive_files.create.return_value.execute.return_value = {'id': 'file-id-1', 'name': 'doc.txt'}
                fake_drive_service = mock.Mock()
                fake_drive_service.files.return_value = fake_drive_files

                fake_discovery_module = ModuleType('googleapiclient.discovery')
                fake_discovery_module.build = mock.Mock(return_value=fake_drive_service)

                fake_http_module = ModuleType('googleapiclient.http')
                fake_http_module.MediaFileUpload = mock.Mock()
                fake_googleapiclient_module = ModuleType('googleapiclient')

                with mock.patch.dict(
                    'sys.modules',
                    {
                        'google': fake_google_module,
                        'google.oauth2': fake_google_oauth2_module,
                        'google.oauth2.service_account': fake_service_account_module,
                        'googleapiclient': fake_googleapiclient_module,
                        'googleapiclient.discovery': fake_discovery_module,
                        'googleapiclient.http': fake_http_module,
                    },
                ):
                    result = provider.upload(source, 'hub/doc.txt')

                self.assertEqual(result, 'gdrive://file-id-1:doc.txt')
                fake_drive_files.create.assert_called_once_with(
                    body={'name': 'doc.txt', 'parents': ['folder123']},
                    media_body=fake_http_module.MediaFileUpload.return_value,
                    fields='id,name',
                    supportsAllDrives=True,
                )
            finally:
                source.unlink(missing_ok=True)
