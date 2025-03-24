import os
from dotenv import load_dotenv
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# Load environment variables
load_dotenv()

def reset_database():
    """Reset the database by dropping and recreating all tables"""
    # Get database connection details from environment
    db_user = os.getenv('DB_USER')
    db_password = os.getenv('DB_PASSWORD')
    db_host = os.getenv('DB_HOST')
    db_name = os.getenv('DB_NAME')

    if not all([db_user, db_password, db_host, db_name]):
        print("Error: Missing database configuration in environment variables")
        print("Required variables: DB_USER, DB_PASSWORD, DB_HOST, DB_NAME")
        return False

    try:
        # Connect to the database
        conn = psycopg2.connect(
            dbname=db_name,
            user=db_user,
            password=db_password,
            host=db_host
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()

        # Read and execute the reset SQL file
        with open('migrations/00_reset_db.sql', 'r') as f:
            sql = f.read()
            cur.execute(sql)

        # Create default organization and superuser
        cur.execute("""
            INSERT INTO users (email, name, role, is_active)
            VALUES (%s, %s, 'Superuser', true)
            RETURNING id
        """, ('fares@beyondcompany.sa', 'Fares'))
        superuser_id = cur.fetchone()[0]

        cur.execute("""
            INSERT INTO organizations (name, superuser_id)
            VALUES (%s, %s)
            RETURNING id
        """, ('Beyond Company', superuser_id))
        org_id = cur.fetchone()[0]

        cur.execute("""
            INSERT INTO organization_users (organization_id, user_id, role)
            VALUES (%s, %s, 'Superuser')
        """, (org_id, superuser_id))

        print("Database reset successful!")
        print("\nDefault organization and superuser created:")
        print("Organization: Beyond Company")
        print("Superuser: Fares (fares@beyondcompany.sa)")
        return True

    except Exception as e:
        print(f"Error resetting database: {str(e)}")
        return False
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    if reset_database():
        print("\nDatabase has been reset and initialized successfully.")
    else:
        print("Failed to reset and initialize database.") 