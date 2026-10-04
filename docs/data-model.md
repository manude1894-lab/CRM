# Triam CRM — Data Model (core entities)

Status: updated for P0 Foundations (4 Oct 2026). Answers BRD §20 "Data relationships / ER diagram — to be prepared". This shows the core client-centric entities; supporting tables (formation, compliance schedule, lifecycle, AML assessments, PEP, invoices, notifications…) hang off `CASE`.

```mermaid
erDiagram
  DEPARTMENT ||--o{ USER : "belongs to"
  DEPARTMENT ||--o{ ROLE : "optionally scopes"
  ROLE ||--o{ USER : "business role"
  USER ||--o{ USER : "supervises"

  USER ||--o{ ACCOUNT : "Anchor RM (spoc_id)"
  USER ||--o{ ACCOUNT : "created (owner_id)"
  ACCOUNT ||--o{ ACCOUNT_PARTY : "shareholders / directors / signatories"
  ACCOUNT ||--o{ DOCUMENT : "client documents"
  ACCOUNT ||--o{ CASE : "engagements"
  CASE ||--o{ DOCUMENT : "case documents"
  CASE ||--o{ INSTRUCTION : "service requests"
  CASE ||--o{ DIRECTOR : "register"
  CASE ||--o{ SHAREHOLDER : "register"
  CASE ||--o{ UBO : "register"

  USER ||--o{ AUDIT_LOG : "acted"
  ACCOUNT ||--o{ AUDIT_LOG : "history (account_id)"

  MASTER_ITEM {
    string list_type "triam_entity | service | tag | regulator | licensing_authority | document_category | rejection_reason"
    string code "value stored on records"
    string label
    int sort_order
    bool is_active
  }
  ROLE {
    string name "CO, MLRO, Dy MLRO, RO, FO, Sales Manager"
    json permissions
    bool is_active
  }
  USER {
    string role "system tier: admin | rm | ops | screening"
    int supervisor_id
    int department_id
    int business_role_id
  }
  ACCOUNT {
    string account_uid
    string account_type "Corporate | Individual"
    string anchor_entity "MASTER_ITEM triam_entity"
    json non_anchor_entities
    json services_obtained "MASTER_ITEM service"
    string tags "MASTER_ITEM tag (comma list)"
    string profile_status
    int spoc_id
    json non_anchor_rm_ids
  }
  AUDIT_LOG {
    datetime occurred_at
    string action "create | update | delete | login | login_failed"
    string subject_type
    int subject_id
    int account_id
    json changes "field: [old, new]"
  }
```

Master values are stored by **code** and referenced by convention (no foreign key), so deactivating an item never breaks old records. Validation of new values happens in the service layer.
