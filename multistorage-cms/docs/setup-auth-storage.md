# Authentication + Storage Integration Guide

This guide covers:
- Google SSO (django-allauth)
- Amazon S3 document storage backend
- Google Drive document storage backend
- Postgres + Redis + Celery + Flower local stack

## 1) Install dependencies

```bash
cd multistorage-cms
../venv/bin/pip install -r requirements.txt
```

## 2) Start infrastructure (recommended)

```bash
docker compose up -d db redis
```

If you want the full stack (web + worker + flower):

```bash
docker compose up --build
```

## 3) Environment configuration

Copy and adapt env values:

```bash
cp .env.example .env
```

Minimum values to review:
- `POSTGRES_*`
- `REDIS_URL`
- `ENABLE_ALLAUTH`
- `GOOGLE_OAUTH_CLIENT_ID`
- `GOOGLE_OAUTH_CLIENT_SECRET`

## 4) Google SSO setup (Login with Google)

### Google Cloud Console
1. Create/select a project.
2. Configure OAuth consent screen.
3. Create OAuth 2.0 Client ID (Web application).
4. Add redirect URI:
   - `http://127.0.0.1:8000/accounts/google/login/callback/`
   - `http://localhost:8000/accounts/google/login/callback/`

### Django env
Set in `.env`:

```bash
ENABLE_ALLAUTH=1
SITE_ID=1
GOOGLE_OAUTH_CLIENT_ID=your-client-id
GOOGLE_OAUTH_CLIENT_SECRET=your-client-secret
```

### Run migrations

```bash
../venv/bin/python manage.py migrate
```

Then login page will show `Continue with Google`.

## 5) Amazon S3 backend configuration

Create a `StorageBackend` row in Django admin (`/admin`) with:
- `kind = S3`
- `status = ACTIVE`
- `config_encrypted` JSON like:

```json
{
  "bucket": "your-bucket-name",
  "region": "us-east-1",
  "access_key": "AKIA...",
  "secret_key": "...",
  "endpoint_url": "https://s3.amazonaws.com",
  "object_prefix": "multistorage"
}
```

Notes:
- For MinIO or S3-compatible services, set `endpoint_url` accordingly.
- Return path format is `s3://bucket/key`.

## 6) Google Drive backend configuration

Use a service account (recommended for server-to-server uploads).

### Google side
1. Enable Google Drive API.
2. Create service account.
3. Create and download service account JSON.
4. Share target Drive folder with service account email.
5. Copy folder id from Drive URL.

### StorageBackend JSON
Create backend with:
- `kind = GDRIVE`
- `status = ACTIVE`
- `config_encrypted` JSON example:

```json
{
  "folder_id": "1AbCdEfGhIjKlMnOp",
  "service_account_file": "/absolute/path/to/service-account.json"
}
```

Alternative:

```json
{
  "folder_id": "1AbCdEfGhIjKlMnOp",
  "service_account_json": {"type": "service_account", "project_id": "..."}
}
```

Return path format is `gdrive://file_id:file_name`.

## 7) Celery worker + Flower

Run web:

```bash
../venv/bin/python manage.py runserver
```

Run worker:

```bash
../venv/bin/celery -A core worker -l info
```

Run Flower dashboard:

```bash
../venv/bin/celery -A core flower --port=5555
```

Open:
- App: `http://127.0.0.1:8000`
- Flower: `http://127.0.0.1:5555`

## 8) Verify end-to-end upload

1. Login.
2. Create/open project hub.
3. Upload a document selecting S3 or GDrive backend.
4. Check document detail status (HTMX polling).
5. Check Flower task state.

## 9) Troubleshooting

- `Background worker unavailable` in document status:
  - Celery package missing or worker not running.
- `boto3 is required for S3 uploads`:
  - install requirements.
- `google-api-python-client and google-auth are required`:
  - install requirements.
- Google login button not visible:
  - set `ENABLE_ALLAUTH=1` and ensure allauth dependencies installed.
