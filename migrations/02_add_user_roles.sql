-- Add role column to users table
ALTER TABLE users ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'Normal' CHECK (role IN ('Superuser', 'Privileged', 'Normal'));

-- Add superuser_id to organizations table
ALTER TABLE organizations ADD COLUMN superuser_id INTEGER REFERENCES users(id);

-- Add created_by and updated_by to projects and people tables
ALTER TABLE projects 
    ADD COLUMN created_by INTEGER REFERENCES users(id),
    ADD COLUMN updated_by INTEGER REFERENCES users(id),
    ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

ALTER TABLE people 
    ADD COLUMN created_by INTEGER REFERENCES users(id),
    ADD COLUMN updated_by INTEGER REFERENCES users(id),
    ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

-- Create trigger function to update updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for projects and people
CREATE TRIGGER update_projects_updated_at
    BEFORE UPDATE ON projects
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_people_updated_at
    BEFORE UPDATE ON people
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column(); 