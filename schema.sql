-- 1. Add new boolean columns to identify 2-digit chapters and 4-digit headings
ALTER TABLE hsn_rates 
ADD COLUMN IF NOT EXISTS chapter_level BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS heading_level BOOLEAN DEFAULT FALSE;

-- 2. Clear existing data to prepare for the fresh v2 upload
TRUNCATE TABLE hsn_rates RESTART IDENTITY;
TRUNCATE TABLE sac_rates RESTART IDENTITY;
