from database import get_db_cursor, DatabaseError
import pandas as pd
from datetime import datetime
import psycopg2
from flask import current_app

def handle_db_error(func):
    """Decorator to handle database errors"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except psycopg2.Error as e:
            current_app.logger.error(f"Database error in {func.__name__}: {str(e)}")
            raise DatabaseError(f"Database operation failed: {str(e)}")
        except Exception as e:
            current_app.logger.error(f"Unexpected error in {func.__name__}: {str(e)}")
            raise
    return wrapper

@handle_db_error
def get_all_people(organization_id):
    """Get all people for an organization"""
    with get_db_cursor() as cursor:
        cursor.execute("""
            SELECT id, name, role, availability
            FROM people
            WHERE organization_id = %s
            ORDER BY name
        """, (organization_id,))
        return [
            {
                'id': row[0],
                'name': row[1],
                'role': row[2],
                'availability': row[3]
            }
            for row in cursor.fetchall()
        ]

@handle_db_error
def get_all_projects(organization_id):
    """Get all projects for an organization"""
    with get_db_cursor() as cursor:
        cursor.execute("""
            SELECT id, name, project_type, status, start_date, end_date
            FROM projects
            WHERE organization_id = %s
            ORDER BY name
        """, (organization_id,))
        return [
            {
                'id': row[0],
                'name': row[1],
                'project_type': row[2],
                'status': row[3],
                'start_date': row[4],
                'end_date': row[5]
            }
            for row in cursor.fetchall()
        ]

@handle_db_error
def get_all_assignments():
    with get_db_cursor() as cur:
        cur.execute("SELECT * FROM assignments")
        columns = ['id', 'project_id', 'person_id', 'allocation', 'start_date', 'end_date']
        return pd.DataFrame(cur.fetchall(), columns=columns)

@handle_db_error
def add_person(person_data, organization_id):
    """Add a new person to an organization"""
    with get_db_cursor() as cursor:
        cursor.execute("""
            INSERT INTO people (name, role, availability, organization_id)
            VALUES (%s, %s, %s, %s)
            RETURNING id
        """, (person_data['name'], person_data['role'], person_data['availability'], organization_id))
        return cursor.fetchone()[0]

@handle_db_error
def update_person(person_id, person_data, organization_id):
    """Update a person's details"""
    with get_db_cursor() as cursor:
        cursor.execute("""
            UPDATE people
            SET name = %s, role = %s, availability = %s
            WHERE id = %s AND organization_id = %s
        """, (
            person_data['name'],
            person_data['role'],
            person_data['availability'],
            person_id,
            organization_id
        ))

@handle_db_error
def delete_person(person_id, organization_id):
    """Delete a person"""
    with get_db_cursor() as cursor:
        cursor.execute("""
            DELETE FROM people
            WHERE id = %s AND organization_id = %s
        """, (person_id, organization_id))

@handle_db_error
def add_project(project_data, organization_id):
    """Add a new project to an organization"""
    with get_db_cursor() as cursor:
        cursor.execute("""
            INSERT INTO projects (name, project_type, status, start_date, end_date, organization_id)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            project_data['name'],
            project_data['project_type'],
            project_data['status'],
            project_data.get('start_date'),
            project_data.get('end_date'),
            organization_id
        ))
        return cursor.fetchone()[0]

@handle_db_error
def update_project(project_id, project_data, organization_id):
    """Update a project's details"""
    with get_db_cursor() as cursor:
        cursor.execute("""
            UPDATE projects
            SET name = %s, project_type = %s, status = %s, start_date = %s, end_date = %s
            WHERE id = %s AND organization_id = %s
        """, (
            project_data['name'],
            project_data['project_type'],
            project_data['status'],
            project_data.get('start_date'),
            project_data.get('end_date'),
            project_id,
            organization_id
        ))

@handle_db_error
def delete_project(project_id, organization_id):
    """Delete a project"""
    with get_db_cursor() as cursor:
        cursor.execute("""
            DELETE FROM projects
            WHERE id = %s AND organization_id = %s
        """, (project_id, organization_id))

@handle_db_error
def add_assignment(assignment_data, organization_id):
    """Add a new assignment"""
    with get_db_cursor() as cursor:
        # Verify that both person and project belong to the organization
        cursor.execute("""
            SELECT COUNT(*) 
            FROM people p, projects pr 
            WHERE p.id = %s AND pr.id = %s 
            AND p.organization_id = %s AND pr.organization_id = %s
        """, (
            assignment_data['person_id'],
            assignment_data['project_id'],
            organization_id,
            organization_id
        ))
        if cursor.fetchone()[0] != 1:
            raise DatabaseError("Invalid person or project for this organization")
            
        cursor.execute("""
            INSERT INTO assignments (project_id, person_id, allocation, start_date, end_date)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """, (
            assignment_data['project_id'],
            assignment_data['person_id'],
            assignment_data['allocation'],
            assignment_data.get('start_date'),
            assignment_data.get('end_date')
        ))
        return cursor.fetchone()[0]

@handle_db_error
def update_assignment(assignment_id, assignment_data, organization_id):
    """Update an assignment"""
    with get_db_cursor() as cursor:
        # Verify that both person and project belong to the organization
        cursor.execute("""
            SELECT COUNT(*) 
            FROM assignments a
            JOIN people p ON a.person_id = p.id
            JOIN projects pr ON a.project_id = pr.id
            WHERE a.id = %s AND p.organization_id = %s AND pr.organization_id = %s
        """, (assignment_id, organization_id, organization_id))
        if cursor.fetchone()[0] != 1:
            raise DatabaseError("Assignment not found or not authorized")
            
        cursor.execute("""
            UPDATE assignments
            SET allocation = %s, start_date = %s, end_date = %s
            WHERE id = %s
        """, (
            assignment_data['allocation'],
            assignment_data.get('start_date'),
            assignment_data.get('end_date'),
            assignment_id
        ))

@handle_db_error
def delete_assignment(assignment_id, organization_id):
    """Delete an assignment"""
    with get_db_cursor() as cursor:
        # Verify that the assignment belongs to the organization
        cursor.execute("""
            DELETE FROM assignments a
            USING people p, projects pr
            WHERE a.id = %s 
            AND a.person_id = p.id 
            AND a.project_id = pr.id
            AND p.organization_id = %s 
            AND pr.organization_id = %s
        """, (assignment_id, organization_id, organization_id))

@handle_db_error
def get_current_assignments(date=None):
    if date is None:
        date = datetime.now().strftime('%Y-%m-%d')
    
    with get_db_cursor() as cur:
        cur.execute("""
            SELECT a.*, p.name as person_name, p.role as person_role,
                   pr.name as project_name, pr.status as project_status
            FROM assignments a
            JOIN people p ON a.person_id = p.id
            JOIN projects pr ON a.project_id = pr.id
            WHERE a.start_date <= %s AND a.end_date >= %s
        """, (date, date))
        columns = ['id', 'project_id', 'person_id', 'allocation', 'start_date', 'end_date',
                  'person_name', 'person_role', 'project_name', 'project_status']
        return pd.DataFrame(cur.fetchall(), columns=columns)

@handle_db_error
def get_project_assignments(project_id):
    with get_db_cursor() as cur:
        cur.execute("""
            SELECT a.*, p.name as person_name, p.role as person_role
            FROM assignments a
            JOIN people p ON a.person_id = p.id
            WHERE a.project_id = %s
        """, (project_id,))
        columns = ['id', 'project_id', 'person_id', 'allocation', 'start_date', 'end_date',
                  'person_name', 'person_role']
        return pd.DataFrame(cur.fetchall(), columns=columns)

@handle_db_error
def get_available_people(project_id):
    with get_db_cursor() as cur:
        cur.execute("""
            SELECT p.*
            FROM people p
            WHERE p.id NOT IN (
                SELECT person_id
                FROM assignments
                WHERE project_id = %s
            )
        """, (project_id,))
        columns = ['id', 'name', 'role', 'availability']
        return pd.DataFrame(cur.fetchall(), columns=columns)

@handle_db_error
def get_assignments(organization_id):
    """Get all assignments for an organization"""
    with get_db_cursor() as cursor:
        cursor.execute("""
            SELECT a.id, a.project_id, a.person_id, a.allocation,
                   a.start_date, a.end_date, p.name as person_name,
                   pr.name as project_name
            FROM assignments a
            JOIN people p ON a.person_id = p.id
            JOIN projects pr ON a.project_id = pr.id
            WHERE p.organization_id = %s
        """, (organization_id,))
        return [
            {
                'id': row[0],
                'project_id': row[1],
                'person_id': row[2],
                'allocation': row[3],
                'start_date': row[4],
                'end_date': row[5],
                'person_name': row[6],
                'project_name': row[7]
            }
            for row in cursor.fetchall()
        ] 