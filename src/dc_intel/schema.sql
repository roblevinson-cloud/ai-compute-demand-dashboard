CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS companies (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    canonical_name text NOT NULL UNIQUE,
    company_type text NOT NULL DEFAULT 'other',
    website_url text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS projects (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    canonical_name text NOT NULL,
    slug text NOT NULL UNIQUE,
    status text NOT NULL DEFAULT 'signal',
    location_precision text NOT NULL DEFAULT 'unknown',
    address text,
    parcel_ids text[] NOT NULL DEFAULT '{}',
    city text,
    county text,
    state char(2),
    latitude numeric(10,7),
    longitude numeric(10,7),
    acreage numeric,
    square_feet bigint,
    building_count integer,
    phase_count integer,
    utility_load_mw numeric,
    it_load_mw numeric,
    generation_capacity_mw numeric,
    capex_usd numeric,
    construction_start date,
    expected_energization date,
    operation_start date,
    water_gpd numeric,
    status_detail text,
    first_seen_at timestamptz NOT NULL DEFAULT now(),
    last_updated_at timestamptz NOT NULL DEFAULT now(),
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    CHECK (state IS NULL OR state ~ '^[A-Z]{2}$')
);

CREATE INDEX IF NOT EXISTS projects_location_idx ON projects (state, county);
CREATE INDEX IF NOT EXISTS projects_status_idx ON projects (status, last_updated_at DESC);
CREATE INDEX IF NOT EXISTS projects_scale_idx ON projects (utility_load_mw DESC NULLS LAST);

CREATE TABLE IF NOT EXISTS project_aliases (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    alias text NOT NULL,
    alias_type text NOT NULL DEFAULT 'codename',
    source_document_id uuid,
    confidence smallint NOT NULL DEFAULT 50 CHECK (confidence BETWEEN 0 AND 100),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (project_id, alias)
);

CREATE TABLE IF NOT EXISTS project_companies (
    project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    company_id uuid NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    relationship_type text NOT NULL,
    start_date date,
    end_date date,
    confidence smallint NOT NULL DEFAULT 50 CHECK (confidence BETWEEN 0 AND 100),
    source_document_id uuid,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    PRIMARY KEY (project_id, company_id, relationship_type)
);

CREATE TABLE IF NOT EXISTS sources (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_key text NOT NULL UNIQUE,
    name text NOT NULL,
    source_type text NOT NULL,
    jurisdiction text,
    base_url text NOT NULL,
    collection_method text NOT NULL,
    schedule_minutes integer NOT NULL DEFAULT 60 CHECK (schedule_minutes >= 5),
    priority smallint NOT NULL DEFAULT 50 CHECK (priority BETWEEN 0 AND 100),
    enabled boolean NOT NULL DEFAULT true,
    parser_config jsonb NOT NULL DEFAULT '{}'::jsonb,
    last_success_at timestamptz,
    last_attempt_at timestamptz,
    consecutive_failures integer NOT NULL DEFAULT 0,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS collection_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id uuid REFERENCES sources(id) ON DELETE SET NULL,
    started_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    status text NOT NULL DEFAULT 'running',
    http_status integer,
    documents_found integer NOT NULL DEFAULT 0,
    documents_new integer NOT NULL DEFAULT 0,
    duration_ms integer,
    detail jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS collection_errors (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    collection_run_id uuid REFERENCES collection_runs(id) ON DELETE CASCADE,
    source_id uuid REFERENCES sources(id) ON DELETE SET NULL,
    occurred_at timestamptz NOT NULL DEFAULT now(),
    error_class text NOT NULL,
    message text NOT NULL,
    retryable boolean NOT NULL DEFAULT true,
    detail jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS source_checkpoints (
    source_id uuid PRIMARY KEY REFERENCES sources(id) ON DELETE CASCADE,
    etag text,
    last_modified text,
    content_hash text,
    cursor text,
    checked_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS raw_documents (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id uuid NOT NULL REFERENCES sources(id) ON DELETE RESTRICT,
    collection_run_id uuid REFERENCES collection_runs(id) ON DELETE SET NULL,
    canonical_url text NOT NULL,
    title text,
    published_at timestamptz,
    retrieved_at timestamptz NOT NULL DEFAULT now(),
    content_type text,
    content_hash char(64) NOT NULL,
    storage_uri text NOT NULL,
    byte_size bigint NOT NULL,
    http_headers jsonb NOT NULL DEFAULT '{}'::jsonb,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (source_id, canonical_url, content_hash)
);

CREATE INDEX IF NOT EXISTS raw_documents_retrieved_idx ON raw_documents (retrieved_at DESC);
CREATE INDEX IF NOT EXISTS raw_documents_hash_idx ON raw_documents (content_hash);

ALTER TABLE project_aliases
    DROP CONSTRAINT IF EXISTS project_aliases_source_document_id_fkey;
ALTER TABLE project_aliases
    ADD CONSTRAINT project_aliases_source_document_id_fkey
    FOREIGN KEY (source_document_id) REFERENCES raw_documents(id) ON DELETE SET NULL;

ALTER TABLE project_companies
    DROP CONSTRAINT IF EXISTS project_companies_source_document_id_fkey;
ALTER TABLE project_companies
    ADD CONSTRAINT project_companies_source_document_id_fkey
    FOREIGN KEY (source_document_id) REFERENCES raw_documents(id) ON DELETE SET NULL;

CREATE TABLE IF NOT EXISTS extracted_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    raw_document_id uuid NOT NULL REFERENCES raw_documents(id) ON DELETE CASCADE,
    schema_version text NOT NULL,
    event_type text NOT NULL,
    headline text NOT NULL,
    summary text NOT NULL,
    occurred_at timestamptz,
    extraction_model text NOT NULL,
    extraction_confidence smallint NOT NULL CHECK (extraction_confidence BETWEEN 0 AND 100),
    extraction_json jsonb NOT NULL,
    extraction_hash char(64) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (raw_document_id, extraction_hash)
);

CREATE TABLE IF NOT EXISTS project_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    extracted_event_id uuid NOT NULL REFERENCES extracted_events(id) ON DELETE CASCADE,
    event_type text NOT NULL,
    occurred_at timestamptz,
    is_new_information boolean NOT NULL DEFAULT true,
    materiality_score smallint NOT NULL CHECK (materiality_score BETWEEN 0 AND 100),
    novelty_score smallint NOT NULL CHECK (novelty_score BETWEEN 0 AND 100),
    confidence_score smallint NOT NULL CHECK (confidence_score BETWEEN 0 AND 100),
    score_breakdown jsonb NOT NULL,
    analyst_status text NOT NULL DEFAULT 'unreviewed',
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (project_id, extracted_event_id)
);

CREATE INDEX IF NOT EXISTS project_events_feed_idx ON project_events (occurred_at DESC, materiality_score DESC);

CREATE TABLE IF NOT EXISTS fact_claims (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    project_event_id uuid REFERENCES project_events(id) ON DELETE SET NULL,
    raw_document_id uuid NOT NULL REFERENCES raw_documents(id) ON DELETE RESTRICT,
    field_name text NOT NULL,
    value_json jsonb NOT NULL,
    normalized_numeric numeric,
    unit text,
    valid_from timestamptz,
    valid_to timestamptz,
    confidence smallint NOT NULL CHECK (confidence BETWEEN 0 AND 100),
    evidence_quote text,
    evidence_page integer,
    supersedes_claim_id uuid REFERENCES fact_claims(id) ON DELETE SET NULL,
    is_current boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS fact_claims_current_idx ON fact_claims (project_id, field_name) WHERE is_current;

CREATE TABLE IF NOT EXISTS entity_match_candidates (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    extracted_event_id uuid NOT NULL REFERENCES extracted_events(id) ON DELETE CASCADE,
    candidate_project_id uuid REFERENCES projects(id) ON DELETE CASCADE,
    proposed_project_json jsonb,
    score smallint NOT NULL CHECK (score BETWEEN 0 AND 100),
    recommendation text NOT NULL,
    supporting_evidence jsonb NOT NULL DEFAULT '[]'::jsonb,
    conflicting_evidence jsonb NOT NULL DEFAULT '[]'::jsonb,
    feature_scores jsonb NOT NULL DEFAULT '{}'::jsonb,
    review_status text NOT NULL DEFAULT 'pending',
    reviewed_by text,
    reviewed_at timestamptz,
    resolution_note text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS entity_match_review_idx ON entity_match_candidates (review_status, score DESC);

CREATE TABLE IF NOT EXISTS alerts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_event_id uuid NOT NULL REFERENCES project_events(id) ON DELETE CASCADE,
    alert_type text NOT NULL DEFAULT 'immediate',
    severity text NOT NULL,
    subject text NOT NULL,
    body_html text NOT NULL,
    delivery_status text NOT NULL DEFAULT 'queued',
    destination text,
    created_at timestamptz NOT NULL DEFAULT now(),
    sent_at timestamptz
);

CREATE TABLE IF NOT EXISTS digests (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    digest_type text NOT NULL,
    window_start timestamptz NOT NULL,
    window_end timestamptz NOT NULL,
    subject text NOT NULL,
    body_text text NOT NULL,
    body_html text NOT NULL,
    event_ids uuid[] NOT NULL DEFAULT '{}',
    status text NOT NULL DEFAULT 'generated',
    generated_at timestamptz NOT NULL DEFAULT now(),
    sent_at timestamptz,
    UNIQUE (digest_type, window_start, window_end)
);

CREATE OR REPLACE VIEW current_project_facts AS
SELECT DISTINCT ON (project_id, field_name)
    project_id, field_name, value_json, normalized_numeric, unit, confidence,
    raw_document_id, evidence_quote, valid_from, created_at
FROM fact_claims
WHERE is_current
ORDER BY project_id, field_name, confidence DESC, created_at DESC;
