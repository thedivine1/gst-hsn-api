-- =============================================================================
-- Migration: 0001_trgm_autocomplete_indexes.sql
--
-- PURPOSE:
--   Enable fast partial-text matching for the GET /api/v1/autocomplete endpoint.
--   Currently the endpoint performs ILIKE '%term%' scans across 48,000+ rows in
--   hsn_rates and sac_rates, resulting in ~200ms latency.
--
--   This migration:
--     1. Enables the pg_trgm extension (provides GIN/GiST trigram indexes)
--     2. Creates GIN trigram indexes on hsn_description and sac_description
--     3. Creates B-tree indexes on hsn_code and sac_code for prefix lookups
--
-- EFFECT:
--   ILIKE '%term%' and ILIKE 'term%' queries are accelerated by trigram index
--   scans instead of sequential table scans, typically reducing autocomplete
--   latency from ~200ms to <10ms.
--
-- HOW TO RUN:
--   Option A — Supabase SQL Editor (recommended):
--     Paste this file into the Supabase Dashboard -> SQL Editor -> Run
--
--   Option B — psql (direct connection):
--     psql "$DATABASE_URL" -f migrations/0001_trgm_autocomplete_indexes.sql
--
--   Option C — Python migration runner:
--     python migrations/run_migration.py
--
-- ROLLBACK:
--   Run migrations/0001_trgm_autocomplete_indexes_rollback.sql
--
-- INVALIDATION NOTE:
--   After any GST Council dataset update or bulk-import script, indexes are
--   maintained automatically by PostgreSQL. No manual rebuild required.
--   If you DROP + re-CREATE either table, re-run this migration.
-- =============================================================================

-- Step 1: Enable pg_trgm extension
-- This is idempotent — safe to run multiple times.
CREATE EXTENSION IF NOT EXISTS pg_trgm;


-- Step 2: GIN trigram index on hsn_rates.hsn_description
-- GIN is preferred over GiST for static/rarely-updated datasets because:
--   - Faster reads  (better for autocomplete)
--   - Slightly slower writes (acceptable for monthly GST updates)
-- CONCURRENTLY avoids a full table lock — safe to run on live production.
CREATE INDEX CONCURRENTLY IF NOT EXISTS
    idx_hsn_description_trgm
ON public.hsn_rates
USING GIN (hsn_description gin_trgm_ops);


-- Step 3: GIN trigram index on sac_rates.sac_description
CREATE INDEX CONCURRENTLY IF NOT EXISTS
    idx_sac_description_trgm
ON public.sac_rates
USING GIN (sac_description gin_trgm_ops);


-- Step 4: B-tree indexes on code columns for prefix lookups
-- Standard B-tree handles left-anchored ILIKE 'term%' efficiently.
CREATE INDEX CONCURRENTLY IF NOT EXISTS
    idx_hsn_code_btree
ON public.hsn_rates (hsn_code);

CREATE INDEX CONCURRENTLY IF NOT EXISTS
    idx_sac_code_btree
ON public.sac_rates (sac_code);


-- =============================================================================
-- VERIFY: Run this after migration to confirm indexes exist
-- =============================================================================
-- SELECT indexname, indexdef
-- FROM pg_indexes
-- WHERE tablename IN ('hsn_rates', 'sac_rates')
-- ORDER BY tablename, indexname;
