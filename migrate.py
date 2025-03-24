import pandas as pd
from models.auth import create_organization, create_user, add_user_to_organization, get_user_by_email
from models.core import add_person, add_project, add_assignment
from database import init_db, DatabaseError, get_db_cursor, get_db_connection
import os
from dotenv import load_dotenv
from app import create_app
import sys
import psycopg2

# Load environment variables
load_dotenv()

def migrate_data(app):
    """Migrate existing CSV data to the new database structure with organization support"""
    print("Starting data migration...")
    
    try:
        # Initialize database
        init_db()
        print("Database initialized")
        
        # Create test organization and admin user
        try:
            org_id = create_organization(
                name="Test Organization",
                subscription_tier="enterprise"
            )
            print(f"Created organization with ID: {org_id}")
            
            # Check if admin user exists
            admin_user = get_user_by_email("fares@ra3d.sa")
            if admin_user:
                admin_id = admin_user['id']
                print("Using existing admin user")
            else:
                admin_id = create_user(
                    email="fares@ra3d.sa",
                    name="Fares",
                    role="admin"
                )
                print(f"Created admin user with ID: {admin_id}")
            
            # Add admin to organization
            add_user_to_organization(admin_id, org_id, role="owner")
            print("Added admin user to organization")
            
        except DatabaseError as e:
            if "duplicate key" in str(e):
                print("Organization and admin user already exist, proceeding with migration...")
            else:
                raise
        
        # Load and validate CSV files
        try:
            people_df = pd.read_csv('data/people.csv')
            projects_df = pd.read_csv('data/projects.csv')
            assignments_df = pd.read_csv('data/assignments.csv')
        except FileNotFoundError as e:
            print(f"Error: Could not find required CSV files in data/ directory: {str(e)}")
            sys.exit(1)
        except pd.errors.EmptyDataError:
            print("Error: One or more CSV files are empty")
            sys.exit(1)
        
        # Migrate people
        people_map = {}  # Store UUID to new ID mapping
        print("\nMigrating people...")
        
        for _, person in people_df.iterrows():
            try:
                new_id = add_person({
                    'name': person['name'],
                    'role': person['role'],
                    'availability': person['availability']
                }, organization_id=org_id)
                people_map[person['id']] = new_id  # Store UUID mapping
                print(f"✓ Migrated person: {person['name']}")
            except Exception as e:
                print(f"✗ Error migrating person {person['name']}: {str(e)}")
        
        # Migrate projects
        projects_map = {}  # Store UUID to new ID mapping
        print("\nMigrating projects...")
        
        for _, project in projects_df.iterrows():
            try:
                new_id = add_project({
                    'name': project['name'],
                    'project_type': project['project_type'],
                    'status': project['status'],
                    'start_date': project['start_date'],
                    'end_date': project['end_date']
                }, organization_id=org_id)
                projects_map[project['id']] = new_id  # Store UUID mapping
                print(f"✓ Migrated project: {project['name']}")
            except Exception as e:
                print(f"✗ Error migrating project {project['name']}: {str(e)}")
        
        # Migrate assignments
        print("\nMigrating assignments...")
        
        for _, assignment in assignments_df.iterrows():
            try:
                project_uuid = assignment['project_id']
                person_uuid = assignment['person_id']
                
                if project_uuid not in projects_map:
                    print(f"✗ Skipping assignment: Project UUID {project_uuid} not found in mapping")
                    continue
                    
                if person_uuid not in people_map:
                    print(f"✗ Skipping assignment: Person UUID {person_uuid} not found in mapping")
                    continue
                
                new_project_id = projects_map[project_uuid]
                new_person_id = people_map[person_uuid]
                
                add_assignment({
                    'project_id': new_project_id,
                    'person_id': new_person_id,
                    'allocation': int(assignment['allocation']),
                    'start_date': assignment['start_date'],
                    'end_date': assignment['end_date']
                })
                print(f"✓ Migrated assignment: Project {new_project_id} - Person {new_person_id}")
            except Exception as e:
                print(f"✗ Error migrating assignment: {str(e)}")
        
        print("\nMigration completed successfully!")
        print("\nTest Organization Details:")
        print("Email: fares@ra3d.sa")
        print("Organization: Test Organization")
        
    except Exception as e:
        print(f"\n✗ Migration failed: {str(e)}")
        sys.exit(1)

def init_db():
    """Initialize the database with schema and initial data"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Create tables if they don't exist
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    name VARCHAR(100) NOT NULL,
                    role VARCHAR(50) NOT NULL CHECK (role IN ('Superuser', 'Privileged', 'Normal')),
                    is_active BOOLEAN DEFAULT TRUE,
                    is_platform_admin BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                -- Add is_platform_admin column if it doesn't exist
                DO $$ 
                BEGIN 
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                                WHERE table_name='users' AND column_name='is_platform_admin') THEN
                        ALTER TABLE users ADD COLUMN is_platform_admin BOOLEAN DEFAULT FALSE;
                    END IF;
                END $$;

                CREATE TABLE IF NOT EXISTS organizations (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    superuser_id INTEGER,  -- Will be updated after user creation
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS organization_users (
                    organization_id INTEGER REFERENCES organizations(id) ON DELETE CASCADE,
                    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                    role VARCHAR(50) DEFAULT 'member' NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (organization_id, user_id)
                );

                CREATE TABLE IF NOT EXISTS projects (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    project_type VARCHAR(50) NOT NULL,
                    status VARCHAR(50) NOT NULL,
                    start_date DATE NOT NULL,
                    end_date DATE NOT NULL,
                    organization_id INTEGER REFERENCES organizations(id) ON DELETE CASCADE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS people (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    role VARCHAR(50) NOT NULL,
                    availability VARCHAR(50) NOT NULL,
                    organization_id INTEGER REFERENCES organizations(id) ON DELETE CASCADE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS assignments (
                    id SERIAL PRIMARY KEY,
                    project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
                    person_id INTEGER REFERENCES people(id) ON DELETE CASCADE,
                    allocation INTEGER NOT NULL CHECK (allocation > 0 AND allocation <= 100),
                    start_date DATE NOT NULL,
                    end_date DATE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(project_id, person_id)
                );

                CREATE TABLE IF NOT EXISTS otps (
                    id SERIAL PRIMARY KEY,
                    email VARCHAR(255) NOT NULL,
                    otp VARCHAR(6) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP NOT NULL,
                    is_valid BOOLEAN DEFAULT true
                );
            """)
            
            # Apply the role-based access control migration
            cur.execute("""
                -- Add role column to users table if it doesn't exist
                DO $$ 
                BEGIN 
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                                WHERE table_name='users' AND column_name='role') THEN
                        ALTER TABLE users ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'Normal';
                        ALTER TABLE users ADD CONSTRAINT valid_role CHECK (role IN ('Superuser', 'Privileged', 'Normal'));
                    END IF;
                END $$;

                -- Add superuser_id to organizations table if it doesn't exist
                DO $$ 
                BEGIN 
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                                WHERE table_name='organizations' AND column_name='superuser_id') THEN
                        ALTER TABLE organizations ADD COLUMN superuser_id INTEGER REFERENCES users(id);
                    END IF;
                END $$;

                -- Add tracking columns to projects if they don't exist
                DO $$ 
                BEGIN 
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                                WHERE table_name='projects' AND column_name='created_by') THEN
                        ALTER TABLE projects ADD COLUMN created_by INTEGER REFERENCES users(id);
                        ALTER TABLE projects ADD COLUMN updated_by INTEGER REFERENCES users(id);
                        ALTER TABLE projects ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
                    END IF;
                END $$;

                -- Add tracking columns to people if they don't exist
                DO $$ 
                BEGIN 
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                                WHERE table_name='people' AND column_name='created_by') THEN
                        ALTER TABLE people ADD COLUMN created_by INTEGER REFERENCES users(id);
                        ALTER TABLE people ADD COLUMN updated_by INTEGER REFERENCES users(id);
                        ALTER TABLE people ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
                    END IF;
                END $$;

                -- Create trigger function if it doesn't exist
                CREATE OR REPLACE FUNCTION update_updated_at_column()
                RETURNS TRIGGER AS $$
                BEGIN
                    NEW.updated_at = CURRENT_TIMESTAMP;
                    RETURN NEW;
                END;
                $$ language 'plpgsql';

                -- Create triggers if they don't exist
                DO $$ 
                BEGIN 
                    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'update_projects_updated_at') THEN
                        CREATE TRIGGER update_projects_updated_at
                            BEFORE UPDATE ON projects
                            FOR EACH ROW
                            EXECUTE FUNCTION update_updated_at_column();
                    END IF;

                    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'update_people_updated_at') THEN
                        CREATE TRIGGER update_people_updated_at
                            BEFORE UPDATE ON people
                            FOR EACH ROW
                            EXECUTE FUNCTION update_updated_at_column();
                    END IF;
                END $$;
            """)
            
            conn.commit()
            print("Database initialized")
            
    except Exception as e:
        conn.rollback()
        print(f"✗ Migration failed: {str(e)}")
        raise
    finally:
        conn.close()

if __name__ == '__main__':
    print("Starting data migration...")
    init_db() 