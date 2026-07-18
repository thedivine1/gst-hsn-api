-- =============================================================================
-- ROLLBACK: 0001_trgm_autocomplete_indexes_rollback.sql
--
-- Reverses the changes made in 0001_trgm_autocomplete_indexes.sql.
-- Only run this if you need to undo the migration.
-- NOTE: Dropping the pg_trgm extension will also remove any other objects
-- that depend on it — leave the extension in place if other code uses it.
-- =============================================================================

DROP INDEX CONCURRENTLY IF EXISTS public.idx_hsn_description_trgm;
DROP INDEX CONCURRENTLY IF EXISTS public.idx_sac_description_trgm;
DROP INDEX CONCURRENTLY IF EXISTS public.idx_hsn_code_btree;
DROP INDEX CONCURRENTLY IF EXISTS public.idx_sac_code_btree;

-- Only drop the extension if nothing else depends on it:
-- DROP EXTENSION IF EXISTS pg_trgm;
