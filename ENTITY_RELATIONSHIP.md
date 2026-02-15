## Entity Relationship

```mermaid
erDiagram
    USER {
        bigint id PK
        string email UK
        boolean is_verified
        string timezone
        datetime created_at
    }

    GROUP {
        bigint id PK
        string name UK
    }

    STORAGE_BACKEND {
        bigint id PK
        string name UK
        string kind
        string status
        json config_encrypted
        bigint project_hub_id FK
        bigint created_by_id FK
        datetime created_at
        datetime updated_at
    }

    PROJECT_HUB {
        bigint id PK
        string name
        string slug UK
        string description
        bigint owner_id FK
        datetime created_at
        datetime updated_at
    }

    PROJECT_MEMBERSHIP {
        bigint id PK
        bigint project_hub_id FK
        bigint user_id FK
        string role
        datetime created_at
    }

    PROJECT_DASHBOARD {
        bigint id PK
        bigint project_hub_id FK
        string name
        json layout_json
        boolean is_default
        bigint created_by_id FK
        datetime created_at
        datetime updated_at
    }

    DOCUMENT {
        uuid id PK
        bigint owner_id FK
        bigint project_hub_id FK
        string title
        string mime_type
        bigint size_bytes
        string checksum_sha256
        bigint current_version_id FK
        string visibility
        datetime created_at
        datetime updated_at
    }

    DOCUMENT_VERSION {
        bigint id PK
        uuid document_id FK
        int version_number
        bigint storage_backend_id FK
        string storage_key
        string upload_state
        bigint uploaded_by_id FK
        datetime created_at
    }

    DOCUMENT_TAG {
        bigint id PK
        uuid document_id FK
        string tag
    }

    DOCUMENT_ACCESS {
        bigint id PK
        uuid document_id FK
        bigint subject_user_id FK
        bigint subject_group_id FK
        string role
        datetime created_at
    }

    FEATURE_FLAG {
        bigint id PK
        string code UK
        string name
        boolean enabled_globally
    }

    USER_FEATURE_OVERRIDE {
        bigint id PK
        bigint user_id FK
        bigint feature_flag_id FK
        boolean is_enabled
    }

    AUDIT_EVENT {
        bigint id PK
        bigint actor_id FK
        uuid document_id FK
        bigint project_hub_id FK
        string event_type
        json payload_json
        datetime created_at
    }

    USER ||--o{ PROJECT_HUB : owns
    PROJECT_HUB ||--o{ PROJECT_MEMBERSHIP : has_members
    USER ||--o{ PROJECT_MEMBERSHIP : joins
    PROJECT_HUB ||--o{ PROJECT_DASHBOARD : has_dashboards
    USER ||--o{ PROJECT_DASHBOARD : creates

    PROJECT_HUB o|--o{ DOCUMENT : contains
    PROJECT_HUB o|--o{ STORAGE_BACKEND : scopes
    PROJECT_HUB o|--o{ AUDIT_EVENT : scopes

    USER ||--o{ DOCUMENT : owns
    DOCUMENT ||--o{ DOCUMENT_VERSION : has_versions
    STORAGE_BACKEND ||--o{ DOCUMENT_VERSION : stores
    USER ||--o{ DOCUMENT_VERSION : uploads
    DOCUMENT ||--o{ DOCUMENT_TAG : has_tags
    USER ||--o{ STORAGE_BACKEND : creates

    DOCUMENT ||--o{ DOCUMENT_ACCESS : access_rules
    USER o|--o{ DOCUMENT_ACCESS : subject_user
    GROUP o|--o{ DOCUMENT_ACCESS : subject_group

    USER ||--o{ USER_FEATURE_OVERRIDE : has_overrides
    FEATURE_FLAG ||--o{ USER_FEATURE_OVERRIDE : overridden_by

    USER o|--o{ AUDIT_EVENT : actor
    DOCUMENT o|--o{ AUDIT_EVENT : target_document

    DOCUMENT_VERSION o|--o{ DOCUMENT : current_version
```

Notes:
- `DOCUMENT.current_version_id` points to one selected row in `DOCUMENT_VERSION` (nullable).
- `DOCUMENT_VERSION` enforces unique `(document_id, version_number)`.
- `DOCUMENT_ACCESS` enforces exactly one subject: `subject_user_id` XOR `subject_group_id`.
- `USER_FEATURE_OVERRIDE` enforces unique `(user_id, feature_flag_id)`.
