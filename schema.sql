-- Create the API keys table linked to Supabase Auth users
CREATE TABLE IF NOT EXISTS public.api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    key_prefix VARCHAR(15) NOT NULL, -- e.g. 'gsta_live_xxxx'
    key_hash VARCHAR(64) UNIQUE NOT NULL, -- SHA-256 hash of the full key
    name VARCHAR(50) DEFAULT 'Default Key',
    is_active BOOLEAN DEFAULT TRUE,
    tier VARCHAR(20) DEFAULT 'free',
    calls_this_month INTEGER DEFAULT 0,
    monthly_limit INTEGER DEFAULT 1000,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Enable Row Level Security
ALTER TABLE public.api_keys ENABLE ROW LEVEL SECURITY;

-- Allow users to read their own keys
CREATE POLICY "Users can view their own API keys"
    ON public.api_keys FOR SELECT
    USING (auth.uid() = user_id);

-- Allow the service role (FastAPI backend) to do everything
-- Note: FastAPI uses the Service Role key, which bypasses RLS anyway, 
-- so we don't strictly need a policy for it, but it's good practice.

-- Create an index for fast lookups by hash during API requests
CREATE INDEX IF NOT EXISTS idx_api_keys_hash ON public.api_keys(key_hash);
CREATE INDEX IF NOT EXISTS idx_api_keys_user ON public.api_keys(user_id);
