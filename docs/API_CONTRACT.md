# M4 API contract - FROZEN 2026-09-05

The backend routers and the Next.js dashboard are built against this. All routes
are prefixed `/api`. All fields are required unless marked `?`. Dates are ISO
strings. This exists so the two halves of M4 can be built in parallel; changing
it means telling both sides.

## GET /api/tasks?status=&severity=&sector=

```json
{
  "tasks": [
    {
      "id": 1,
      "reference": "CC-2026-0001",
      "status": "new",
      "severity": "high",
      "document_count": 1,
      "proposal_count": 2,
      "created_at": "2026-09-05T07:02:11",
      "assignee": {
        "id": 2,
        "name": "John Goh",
        "initials": "JG",
        "role": "Partner"
      },
      "is_demo": true,
      "item": {
        "id": 168,
        "title": "...",
        "sitting_date": "2026-08-05",
        "item_type": "bill",
        "legislation_type": "Amendment",
        "speaker": "...",
        "url": "https://...",
        "summary": "..."
      }
    }
  ]
}
```

`is_demo` is true when the item's `sprs_id` starts with `demo-` - the UI must
label it a planted fixture. `assignee` is null unless the task is assigned.

**2026-09-05 addition**: task objects also carry `"sectors": ["real-estate", ...]`

- the sorted, de-duplicated list of `Document.sector` across every document the
  task touches. Additive, non-breaking. Added because the sidebar was summing
  `open_task_count` per document to get a per-sector task count, which double-
  counted any task spanning two documents in the same sector; the sidebar now
  counts distinct tasks via this field instead.

## GET /api/tasks/{task_id}

The task object above plus:

```json
{
  "documents": [
    {
      "id": 5,
      "document_id": 8,
      "slug": "01-tenancy-agreement-pte",
      "title": "Tenancy Agreement (Pte)",
      "sector": "real-estate",
      "severity": "high",
      "review_state": "pending",
      "proposal_count": 2,
      "version": 3,
      "preview": {
        "clause_ref": "01-tenancy-agreement-pte#4-k",
        "heading": "Option to Renew",
        "before": "...",
        "after": "..."
      }
    }
  ]
}
```

## GET /api/tasks/{task_id}/documents/{doc_slug}

```json
{"task": {...task object...},
 "document": {...document object...},
 "proposals": [{
   "id": 3, "clause_ref": "01-tenancy-agreement-pte#4-k", "status": "pending",
   "severity": "high", "rationale": "...", "suggested_text": "...",
   "clause": {"anchor": "4-k", "number": "4(k)", "heading": "Option to Renew",
              "text": "...current clause text..."},
   "diff": [["equal", "The Landlord shall "], ["delete", "one "],
            ["insert", "three "], ["equal", "months notice."]]
 }]}
```

`diff` comes from `analysis/proposal.py::render_diff(before, after)` - word-level
`[op, text]` pairs, `op` in `equal|insert|delete`. Never diff in the browser.

## POST /api/proposals/{id}/approve · POST /api/proposals/{id}/reject

Body: `{"user_id": 1}`. Approve rewrites the vault markdown, bumps the document
version, records an `Edit`, and fans out `Notification` rows. Both return the
updated proposal object. Reject only sets status.

## GET /api/documents?sector=

```json
{
  "sectors": [
    {
      "sector": "real-estate",
      "count": 3,
      "documents": [
        {
          "id": 8,
          "slug": "...",
          "title": "...",
          "file_type": "pdf",
          "version": 3,
          "clause_count": 74,
          "updated_at": "...",
          "parse_error": null,
          "open_task_count": 1
        }
      ]
    }
  ]
}
```

## GET /api/documents/{slug}

Document object plus `"clauses": [{"anchor","number","heading","text","concepts":["..."]}]`
and `"history": [{"clause_ref","before_text","after_text","user","created_at","version_after"}]`.

## GET /api/notifications?user_id=1

```json
{
  "unread": 3,
  "notifications": [
    {
      "id": 7,
      "message": "...",
      "read": false,
      "created_at": "...",
      "actor": { "name": "...", "initials": "..." },
      "task_id": 2,
      "task_reference": "CC-2026-0002",
      "document_slug": "01-tenancy-agreement-pte"
    }
  ]
}
```

`POST /api/notifications/{id}/read` marks one read.

## GET /api/parliament?date=

```json
{"items": [{...item object..., "vault_path": "...", "task_id": 2, "task_reference": "CC-2026-0002"}],
 "sitting": {"parliament_no": 15, "session_no": 1, "volume_no": 96, "sitting_no": 34}}
```

`sitting` comes from the fixture `metadata`, never hard-coded.

## GET /api/users

`{"users": [{"id","name","email","role","initials"}]}` - powers the user switcher.
