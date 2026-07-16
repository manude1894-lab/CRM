# EZEETECH GROUP — API Reference

Base URL: `http://localhost:8000/api/v1`

Interactive docs: `http://localhost:8000/docs` (Swagger) · `http://localhost:8000/redoc` (ReDoc)

## Authentication

All endpoints except `/auth/login` and `/auth/refresh` require a Bearer token in the `Authorization` header:

```
Authorization: Bearer <access_token>
```

Tokens expire in 60 minutes (access) / 7 days (refresh). The frontend auto-refreshes on 401.

---

### `POST /auth/login`

Login with email + password. Returns access + refresh tokens and the user profile.

**Request**
```json
{ "email": "admin@ezeetechgroup.com", "password": "admin123" }
```

**Response 200**
```json
{
  "access_token": "eyJhbGciOi...",
  "refresh_token": "eyJhbGciOi...",
  "token_type": "bearer",
  "user": { "id": 1, "name": "Admin User", "email": "admin@ezeetechgroup.com", "role": "admin", "is_active": true, "created_at": "...", "updated_at": "..." }
}
```

**Errors:** 401 invalid credentials.

### `POST /auth/refresh`

**Request:** `{ "refresh_token": "..." }` → same response shape as `/login`.

### `GET /auth/me`

Returns the authenticated user.

---

## Users (Admin-only CRUD, any authenticated user can read the list)

| Method | Path | Role required |
|---|---|---|
| `GET` | `/users` | any authenticated |
| `GET` | `/users/{id}` | any authenticated |
| `POST` | `/users` | admin |
| `PATCH` | `/users/{id}` | admin |
| `DELETE` | `/users/{id}` | admin |

**User create payload:**
```json
{
  "name": "Jane Doe",
  "email": "jane@ezeetechgroup.com",
  "password": "strong-password",
  "role": "sales_rep",
  "is_active": true
}
```

Roles: `admin`, `sales_manager`, `sales_rep`.

The last admin cannot be deleted.

---

## Leads

| Method | Path | Notes |
|---|---|---|
| `GET` | `/leads` | paginated, filterable |
| `GET` | `/leads/{id}` | |
| `POST` | `/leads` | any authenticated (reps auto-own) |
| `PATCH` | `/leads/{id}` | rep can only edit own |
| `DELETE` | `/leads/{id}` | manager/admin only |
| `POST` | `/leads/{id}/convert` | convert to Opportunity + Account |

**Query params for `GET /leads`:**
`skip`, `limit`, `search`, `status_filter`, `source_filter`, `industry`, `country`, `owner_id`.

**Response 200 (list):**
```json
{
  "items": [{ "id": 1, "lead_uid": "LEAD-0001", "company_name": "Pfizer Inc.", "contact_name": "Dr. Sarah Mitchell", "email": "...", "source": "Conference", "industry": "Pharma", "interest_area": "ADMET", "lead_score": 82, "status": "Qualified", "owner_id": 3, "notes": "...", "date_captured": "2025-01-05", "created_at": "...", "updated_at": "..." }],
  "total": 20
}
```

**`POST /leads/{id}/convert` payload:**
```json
{
  "deal_name": "Pfizer ADMET Pilot",
  "product_service": "ADMET",
  "deal_type": "Pilot",
  "deal_value": 950000,
  "expected_close_date": "2025-06-30",
  "create_account": true
}
```

Returns the newly-created opportunity. Also sets the lead's `status` to `Converted` and creates an Account if one didn't exist for that company.

---

## Opportunities

| Method | Path | Notes |
|---|---|---|
| `GET` | `/opportunities` | paginated, filterable |
| `GET` | `/opportunities/{id}` | |
| `POST` | `/opportunities` | |
| `PATCH` | `/opportunities/{id}` | validates stage transition if stage changes |
| `POST` | `/opportunities/{id}/stage` | dedicated stage-change endpoint |
| `DELETE` | `/opportunities/{id}` | manager/admin only |

**Query params:** `skip`, `limit`, `search`, `stage`, `owner_id`, `product`, `risk`, `min_value`, `max_value`.

**Stages:** `Lead Qualified`, `Discovery Call`, `Technical Discussion`, `Proposal Shared`, `Negotiation`, `Pilot/POC`, `Closed Won`, `Closed Lost`.

**Probability auto-mapped** from stage on every create/update/stage-change. `weighted_revenue = deal_value × probability` recomputed server-side.

**Valid stage transitions (forward only, or jump to Closed Lost):**

```
Lead Qualified     → Discovery Call | Closed Lost
Discovery Call     → Technical Discussion | Closed Lost
Technical          → Proposal Shared | Closed Lost
Proposal Shared    → Negotiation | Closed Lost
Negotiation        → Pilot/POC | Closed Won | Closed Lost
Pilot/POC          → Closed Won | Closed Lost
Closed Won         → (terminal)
Closed Lost        → (terminal)
```

Invalid transitions return HTTP 400 with:
```json
{ "detail": "Invalid stage transition: 'Discovery Call' → 'Negotiation'. Allowed: ['Technical Discussion', 'Closed Lost']" }
```

**`POST /opportunities/{id}/stage` body:**
```json
{ "stage": "Proposal Shared" }
```

---

## Accounts

| Method | Path | Notes |
|---|---|---|
| `GET` | `/accounts` | |
| `GET` | `/accounts/{id}` | |
| `POST` | `/accounts` | manager/admin only |
| `PATCH` | `/accounts/{id}` | |
| `DELETE` | `/accounts/{id}` | manager/admin only |

**Query params:** `skip`, `limit`, `search`, `industry`, `country`, `priority`.

`total_opportunities` and `total_revenue_generated` are cached on the account and refreshed on every opportunity mutation. Accounts are usually created via the lead conversion endpoint — manual creation is available for edge cases.

---

## Activities

| Method | Path | Notes |
|---|---|---|
| `GET` | `/activities` | |
| `GET` | `/activities/{id}` | |
| `POST` | `/activities` | updates parent opportunity's `last_interaction_date` |
| `PATCH` | `/activities/{id}` | |
| `DELETE` | `/activities/{id}` | |

**Query params:** `skip`, `limit`, `opportunity_id`, `activity_type`, `owner_id`, `search`.

**Types:** `Call`, `Email`, `Meeting`, `Demo`, `Follow-up`, `Note`.

**Statuses:** `Planned`, `Completed`, `Cancelled`, `Overdue`.

**Payload:**
```json
{
  "opportunity_id": 1,
  "company_name": "Pfizer Inc.",
  "activity_date": "2025-04-15",
  "activity_type": "Demo",
  "status": "Completed",
  "summary": "Product demo with R&D team",
  "outcome": "Positive feedback on accuracy",
  "next_action": "Send technical report"
}
```

---

## Dashboard

### `GET /dashboard`

Returns the full analytics payload: KPIs, pipeline-by-stage, monthly forecast vs target, rep performance, lead source breakdown, product breakdown.

**Response 200:**
```json
{
  "kpis": {
    "total_pipeline": "26450000.00",
    "weighted_pipeline": "13235000.00",
    "closed_won_ytd": "500000.00",
    "closed_lost_ytd": "2100000.00",
    "open_opportunities": 13,
    "total_leads": 20,
    "qualified_leads": 11,
    "win_rate": 0.333
  },
  "stage_breakdown": [
    { "stage": "Lead Qualified", "count": 2, "total_value": "5370000.00", "weighted_value": "537000.00", "probability": 0.1 },
    ...
  ],
  "monthly_forecast": [
    { "month": "2025-01", "target": "120000", "forecast": "0", "closed": "0" },
    ...
  ],
  "rep_performance": [
    { "user_id": 3, "name": "Arjun Sharma", "pipeline_value": "...", "closed_won": "...", "total_deals": 7, "total_activities": 12 }
  ],
  "source_breakdown": [
    { "source": "Conference", "total_leads": 5, "qualified_leads": 2 }
  ],
  "product_breakdown": [
    { "product": "ADMET", "total_value": "...", "deal_count": 6 }
  ]
}
```

The response is automatically filtered by the caller's role — a Sales Rep sees only their own data.

---

## Reports (PDF)

All 4 endpoints return a PDF binary (`application/pdf`) with a `Content-Disposition: attachment` header.

| Method | Path | Description |
|---|---|---|
| `GET` | `/reports/pipeline-summary` | KPIs + stage breakdown + lead sources |
| `GET` | `/reports/opportunity-details` | All opportunities with totals |
| `GET` | `/reports/revenue-forecast` | Monthly forecast vs target with achievement % |
| `GET` | `/reports/sales-performance` | Per-rep pipeline, won, deals, activities |

Reports are scoped to the caller's role — a Sales Rep report contains only their own deals.

---

## Error responses

Standard HTTP status codes:

- **400** — validation error, invalid stage transition, account already exists
- **401** — missing/invalid/expired token
- **403** — authenticated but lacks role permission for the action
- **404** — entity not found
- **422** — Pydantic validation failure (malformed request body)

All errors return:
```json
{ "detail": "Human-readable message" }
```

---

## Pagination

List endpoints take `skip` (default 0) and `limit` (default 100). Response includes a `total` count in the body and an `X-Total-Count` header. Increase `limit` up to the server cap or paginate client-side.
