# Architecture

GridSignal uses one scheduled worker and PostgreSQL. The design avoids a queueing system until volume requires one, but every stage has an independent persistence boundary so collectors, extractors, entity resolution, scoring, and synthesis can later be split into separate workers.

## Data flow

1. The scheduler selects due sources using `schedule_minutes` and `last_attempt_at`.
2. Collectors issue conditional requests with stored ETag and Last-Modified values.
3. New bytes are stored under a content hash in `data/raw/YYYY/MM/DD/`; PostgreSQL stores URL, headers, type, size, and retrieval time.
4. The extraction worker emits schema `1.0`. Routine HTML uses the deterministic extractor; a model adapter can replace it without changing downstream contracts.
5. Candidate resolution compares the signal with every plausible project. Conflicting county or tenant evidence prevents automatic linking.
6. Linked events are compared with current facts, scored, and written to the project timeline. Unlinked events enter the review queue with a proposed project record.
7. High-scoring events enter the alert queue. At 6:30 a.m. and 6:00 p.m. Eastern, the scheduler generates deduplicated report windows.

## Model routing

Use a low-cost local or open model for document classification, routine field extraction, and first-pass summaries. Escalate when any of these conditions applies:

- extraction confidence below 70;
- entity-match score between 45 and 87;
- a hard conflict exists;
- the document changes MW, energization, tenant, capex, cancellation, or regulatory status;
- multiple projects or facilities appear in one document;
- OCR quality is poor;
- the event is eligible for an immediate alert or top-three digest position.

The strong-model prompt should include only the source document, current project facts with provenance, and candidate features. It should return the fixed extraction or synthesis schema, never write directly to canonical project fields.

## Security and auditability

- Raw evidence is append-only and content-addressed.
- PostgreSQL credentials are supplied only through `DATABASE_URL`.
- Source content is untrusted input; it is never executed.
- Dashboard rendering escapes extracted text.
- A production deployment should use private object storage for raw documents, database row-level access, dashboard authentication, outbound-domain allowlists, and secret-managed email/model credentials.
