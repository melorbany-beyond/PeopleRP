import psycopg2
from psycopg2.pool import SimpleConnectionPool
from psycopg2 import pool
from contextlib import contextmanager
import os
from flask import current_app, g
from urllib.parse import urlparse
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class DatabaseError(Exception):
    """Base class for database-related errors"""
    pass

class ConnectionError(DatabaseError):
    """Error establishing database connection"""
    pass

class QueryError(DatabaseError):
    """Error executing database query"""
    pass

def get_db_config():
    """Get database configuration from environment or app config"""
    if current_app and current_app.config.get('TESTING', False):
        # Use test database configuration
        return {
            'dbname': 'prptest',
            'user': os.getenv('DB_USER', 'postgres'),
            'password': os.getenv('DB_PASSWORD', 'postgres'),
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': int(os.getenv('DB_PORT', 5432))
        }
    else:
        # Use production database configuration
        return {
            'dbname': 'prp',
            'user': os.getenv('DB_USER', 'postgres'),
            'password': os.getenv('DB_PASSWORD', 'postgres'),
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': int(os.getenv('DB_PORT', 5432))
        }

# Initialize connection pools for both databases
prod_pool = None
test_pool = None

def get_db():
    """Get a database connection from the appropriate pool."""
    global prod_pool, test_pool
    
    if 'db' not in g:
        try:
            # Determine which pool to use
            is_testing = current_app.config.get('TESTING', False) if current_app else False
            
            # Get or create the appropriate pool
            if is_testing:
                if test_pool is None:
                    db_config = get_db_config()
                    test_pool = SimpleConnectionPool(1, 20, **db_config)
                pool_to_use = test_pool
            else:
                if prod_pool is None:
                    db_config = get_db_config()
                    prod_pool = SimpleConnectionPool(1, 20, **db_config)
                pool_to_use = prod_pool
            
            # Get connection from pool
            conn = pool_to_use.getconn()
            conn.autocommit = False  # Ensure transaction control
            g.db = conn
            g.db_pool = pool_to_use  # Store which pool we're using
            
        except psycopg2.Error as e:
            current_app.logger.error(f"Database connection failed: {str(e)}")
            raise DatabaseError(f"Failed to connect to database: {str(e)}")
    
    return g.db

def close_db(e=None):
    """Close the database connection."""
    db = g.pop('db', None)
    db_pool = g.pop('db_pool', None)
    
    if db is not None and db_pool is not None:
        try:
            if db.closed == 0:  # Only return connection if it's not closed
                db_pool.putconn(db)
        except psycopg2.Error as e:
            current_app.logger.error(f"Error closing database connection: {str(e)}")

@contextmanager
def get_db_cursor():
    """Get a database cursor with transaction management"""
    db = get_db()
    try:
        cursor = db.cursor()
        yield cursor
        db.commit()  # Commit the transaction if no errors
    except Exception as e:
        db.rollback()  # Rollback on error
        raise
    finally:
        cursor.close()

def init_db():
    """Initialize the database with required tables"""
    # Always reset tables in testing mode
    reset_db = current_app.config.get('TESTING', False) or os.getenv('RESET_DB', 'false').lower() == 'true'
    
    try:
        # Create a connection for DDL operations
        db_config = get_db_config()
        ddl_conn = psycopg2.connect(**db_config)
        ddl_conn.autocommit = True  # Use autocommit for DDL
        
        try:
            with ddl_conn.cursor() as cur:
                if reset_db:
                    current_app.logger.info("Resetting database tables...")
                    # Drop existing tables in correct order
                    cur.execute("""
                        DROP TABLE IF EXISTS assignments CASCADE;
                        DROP TABLE IF EXISTS people CASCADE;
                        DROP TABLE IF EXISTS projects CASCADE;
                        DROP TABLE IF EXISTS otps CASCADE;
                        DROP TABLE IF EXISTS organization_users CASCADE;
                        DROP TABLE IF EXISTS users CASCADE;
                        DROP TABLE IF EXISTS organizations CASCADE;
                    """)
        finally:
            ddl_conn.close()
        
        # Create a new connection for table creation and data
        db = psycopg2.connect(**db_config)
        db.autocommit = False
        
        with db.cursor() as cur:
            # Create organizations table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS organizations (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    superuser_id INTEGER,  -- Will be updated after user creation
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create users table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    name VARCHAR(100) NOT NULL,
                    role VARCHAR(50) NOT NULL CHECK (role IN ('Superuser', 'Privileged', 'Normal')),
                    is_active BOOLEAN DEFAULT TRUE,
                    is_platform_admin BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Add foreign key to organizations after users table exists
            try:
                cur.execute("""
                    ALTER TABLE organizations 
                    ADD CONSTRAINT fk_superuser 
                    FOREIGN KEY (superuser_id) 
                    REFERENCES users(id)
                """)
            except psycopg2.errors.DuplicateObject:
                db.rollback()  # Rollback the failed constraint
                
            # Create organization_users table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS organization_users (
                    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                    organization_id INTEGER REFERENCES organizations(id) ON DELETE CASCADE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, organization_id)
                )
            """)
            
            # Create otps table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS otps (
                    id SERIAL PRIMARY KEY,
                    email VARCHAR(255) REFERENCES users(email) ON DELETE CASCADE,
                    otp VARCHAR(6) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP NOT NULL,
                    is_valid BOOLEAN DEFAULT TRUE
                )
            """)
            
            # Create people table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS people (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    role VARCHAR(100) NOT NULL,
                    availability VARCHAR(50) NOT NULL,
                    organization_id INTEGER REFERENCES organizations(id) ON DELETE CASCADE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create projects table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS projects (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    project_type VARCHAR(50) NOT NULL,
                    status VARCHAR(50) NOT NULL,
                    start_date DATE,
                    end_date DATE,
                    organization_id INTEGER REFERENCES organizations(id) ON DELETE CASCADE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create assignments table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS assignments (
                    id SERIAL PRIMARY KEY,
                    project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
                    person_id INTEGER REFERENCES people(id) ON DELETE CASCADE,
                    allocation INTEGER NOT NULL,
                    start_date DATE,
                    end_date DATE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(project_id, person_id)
                )
            """)
            
            db.commit()
            
    except Exception as e:
        current_app.logger.error(f"Error initializing database: {str(e)}")
        if 'db' in locals():
            db.rollback()
        raise
    finally:
        if 'db' in locals():
            db.close()

def get_db_connection():
    """Get a database connection"""
    try:
        conn = psycopg2.connect(
            dbname=os.getenv('DB_NAME', 'eagleeye'),
            user=os.getenv('DB_USER', 'postgres'),
            password=os.getenv('DB_PASSWORD', ''),
            host=os.getenv('DB_HOST', 'localhost'),
            port=os.getenv('DB_PORT', '5432')
        )
        return conn
    except psycopg2.Error as e:
        raise DatabaseError(f"Could not connect to database: {str(e)}")

@contextmanager
def get_db_cursor():
    """Context manager for database cursor"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            yield cursor
            conn.commit()
    except Exception as e:
        conn.rollback()
        raise DatabaseError(str(e))
    finally:
        conn.close() 