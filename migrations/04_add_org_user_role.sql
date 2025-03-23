-- Add role column to organization_users table
ALTER TABLE organization_users ADD COLUMN IF NOT EXISTS role VARCHAR(50) DEFAULT 'member' NOT NULL;

-- Update any existing organization_users that don't have role set
UPDATE organization_users SET role = 'member' WHERE role IS NULL; 