# Triam CRM — Data Model

Status: updated for the BRD alignment (20 Oct 2026). Answers BRD §21 "Data relationships / ER diagram — to be prepared". Everything hangs off the **client** (`ACCOUNT`); there is no separate case record.

```mermaid
erDiagram
  DEPARTMENT ||--o{ USER : "belongs to"
  DEPARTMENT ||--o{ ROLE : "optionally scopes"
  ROLE ||--o{ USER : "main and additional business roles"
  USER ||--o{ USER : "supervises"

  USER ||--o{ PROSPECT : "assigned RM"
  PROSPECT ||--o| ACCOUNT : "client created from it"
  USER ||--o{ ACCOUNT : "Anchor RM (spoc_id)"
  ACCOUNT ||--o{ ACCOUNT_PARTY : "UBOs, directors, signatories, joint holders"
  ACCOUNT ||--o{ APPROVAL_REQUEST : "new-client approval and amendments"
  ACCOUNT ||--o{ DOCUMENT : "client folder"
  ACCOUNT_PARTY ||--o{ DOCUMENT : "passport, EID, visa"
  ACCOUNT ||--o{ ACTIVITY : "visit and call reports"
  ACCOUNT ||--o{ INSTRUCTION : "service requests"
  ACCOUNT ||--o{ INVOICE : "invoices"
  INVOICE ||--o{ INSTRUCTION : "billed requests"
  INVOICE ||--o{ DOCUMENT : "pricing approvals, invoice file"
  ACCOUNT ||--o{ NOTIFICATION : "reminders"
  USER ||--o{ AUDIT_LOG : "acted"
  ACCOUNT ||--o{ AUDIT_LOG : "history"

  PROSPECT {
    string prospect_uid "temporary client ID until Compliance approves"
    int owner_id "assigned RM"
    text assignor_comments "up to 250 words"
    int converted_account_id
  }
  ACCOUNT {
    string client_id "issued at Compliance approval, per Triam entity"
    string account_type "Corporate | Individual"
    string anchor_entity "MASTER_ITEM triam_entity"
    string profile_status "New → WIP → Awaiting Approval → Approved → Active → Inactive → Marked for Exit → Exited"
    string risk_rating "High | Medium | Low (Compliance only)"
    date next_aml_review_date "CDD date + 1 / 2 / 3 years"
    int spoc_id "Anchor RM"
  }
  APPROVAL_REQUEST {
    string request_type "client_profile | client_amendment"
    string stage "Compliance | Approver"
    string status "Draft | Pending | Approved | Rejected | Withdrawn | Discarded"
    json changes "old and new values for amendments"
  }
  INSTRUCTION {
    string triam_entity "decides the request types and statuses"
    string instruction_type "MASTER_ITEM service_request_type"
    string other_description "free text up to 50 characters"
    string status "MASTER_ITEM service_request_status"
  }
  MASTER_ITEM {
    string list_type "triam_entity | service | tag | regulator | licensing_authority | document_category | rejection_reason | service_request_type | service_request_status"
    string code "value stored on records"
    string label
    bool is_active
  }
  USER {
    string role "admin | rm (staff user)"
    int business_role_id
    int supervisor_id
    bool is_super_admin "Ezee Tech support account, hidden from everyone else"
  }
```

Master values are stored by **code** and referenced by convention (no foreign key), so deactivating an item never breaks old records. Validation of new values happens in the service layer. Records are never deleted: they are cancelled, removed or deactivated with a reason and stay in the database.
