# API v1 (Frontend-ready)

Base path: `/api/v1/`

Auth:
- Session auth (browser cookie), or
- Token auth (`Authorization: Token <key>`)

Get token:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/auth/token/ \
  -d "username=your-email@example.com" \
  -d "password=your-password"
```

## Endpoints

- `GET /api/v1/hubs/<hub-slug>/documents/`
- `POST /api/v1/hubs/<hub-slug>/documents/`
- `GET /api/v1/hubs/<hub-slug>/documents/<document-id>/`
- `PATCH /api/v1/hubs/<hub-slug>/documents/<document-id>/`
- `DELETE /api/v1/hubs/<hub-slug>/documents/<document-id>/`
- `GET /api/v1/hubs/<hub-slug>/documents/<document-id>/file-info/`
- `GET /api/v1/hubs/<hub-slug>/documents/<document-id>/open/`

## Notes

- API permission model matches UI: owner/member scoped access.
- `/open/` returns:
  - file stream for local backend
  - JSON redirect URL for S3/GDrive
- `storage_key` is provider metadata, not guaranteed public URL.
