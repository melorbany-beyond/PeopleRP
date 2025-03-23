-- Add max_users column to organizations table
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS max_users INTEGER DEFAULT 10 NOT NULL;

-- Update any existing organizations that don't have max_users set
UPDATE organizations SET max_users = 10 WHERE max_users IS NULL; 