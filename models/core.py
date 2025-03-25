from database import get_db_cursor, DatabaseError
import pandas as pd
from datetime import datetime

def get_all_people(organization_id=None):
    """Get all people from the database"""
    with get_db_cursor() as cursor:
        if organization_id:
            cursor.execute("""
                SELECT id, name, role, availability
                FROM people
                WHERE organization_id = %s
                ORDER BY name
            """, (organization_id,))
        else:
            cursor.execute("""
                SELECT id, name, role, availability
                FROM people
                ORDER BY name
            """)
        
        columns = ['id', 'name', 'role', 'availability']
        return pd.DataFrame(cursor.fetchall(), columns=columns)

def get_all_projects(organization_id=None):
    """Get all projects from the database"""
    with get_db_cursor() as cursor:
        if organization_id:
            cursor.execute("""
                SELECT id, name, project_type, status, start_date, end_date
                FROM projects
                WHERE organization_id = %s
                ORDER BY start_date DESC
            """, (organization_id,))
        else:
            cursor.execute("""
                SELECT id, name, project_type, status, start_date, end_date
                FROM projects
                ORDER BY start_date DESC
            """)
        
        columns = ['id', 'name', 'project_type', 'status', 'start_date', 'end_date']
        return pd.DataFrame(cursor.fetchall(), columns=columns)

def add_person(data, organization_id=None):
    """Add a new person to the database"""
    with get_db_cursor() as cursor:
        if organization_id:
            cursor.execute("""
                INSERT INTO people (name, role, availability, organization_id)
                VALUES (%s, %s, %s, %s)
                RETURNING id
            """, (data['name'], data['role'], data['availability'], organization_id))
        else:
            cursor.execute("""
                INSERT INTO people (name, role, availability)
                VALUES (%s, %s, %s)
                RETURNING id
            """, (data['name'], data['role'], data['availability']))
        return cursor.fetchone()[0]

def update_person(person_id, person_data):
    """Update a person's details"""
    with get_db_cursor() as cur:
        cur.execute("""
            UPDATE people 
            SET name = %s,
                role = %s,
                availability = %s
            WHERE id = %s
            RETURNING id
        """, (
            person_data['name'],
            person_data['role'],
            person_data['availability'],
            person_id
        ))
        return cur.fetchone() is not None

def delete_person(person_id):
    """Delete a person from the database"""
    with get_db_cursor() as cursor:
        cursor.execute("DELETE FROM people WHERE id = %s", (person_id,))

def add_project(data, organization_id=None):
    """Add a new project to the database"""
    with get_db_cursor() as cursor:
        if organization_id:
            cursor.execute("""
                INSERT INTO projects (name, project_type, status, start_date, end_date, organization_id)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (data['name'], data['project_type'], data['status'], 
                data['start_date'], data['end_date'], organization_id))
        else:
            cursor.execute("""
                INSERT INTO projects (name, project_type, status, start_date, end_date)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
            """, (data['name'], data['project_type'], data['status'], 
                data['start_date'], data['end_date']))
        return cursor.fetchone()[0]

def update_project(project_id, project_data):
    """Update a project's details"""
    with get_db_cursor() as cur:
        cur.execute("""
            UPDATE projects 
            SET name = %s,
                project_type = %s,
                status = %s,
                start_date = %s,
                end_date = %s
            WHERE id = %s
            RETURNING id
        """, (
            project_data['name'],
            project_data['project_type'],
            project_data['status'],
            project_data['start_date'],
            project_data['end_date'],
            project_id
        ))
        return cur.fetchone() is not None

def delete_project(project_id):
    """Delete a project from the database"""
    with get_db_cursor() as cursor:
        cursor.execute("DELETE FROM projects WHERE id = %s", (project_id,))

def add_assignment(data):
    """Add a new assignment to the database"""
    try:
        with get_db_cursor() as cursor:
            cursor.execute("""
                INSERT INTO assignments (project_id, person_id, allocation, start_date, end_date)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
            """, (data['project_id'], data['person_id'], data['allocation'],
                data['start_date'], data['end_date']))
            return cursor.fetchone()[0]
    except DatabaseError as e:
        if "assignments_project_id_person_id_key" in str(e):
            raise ValueError("Person already assigned to this project")
        raise

def update_assignment(assignment_id, data):
    """Update an assignment in the database"""
    with get_db_cursor() as cursor:
        cursor.execute("""
            UPDATE assignments
            SET allocation = %s, start_date = %s, end_date = %s
            WHERE id = %s
            RETURNING id, project_id, person_id, allocation, start_date, end_date
        """, (int(data['allocation']), data['start_date'], data['end_date'], assignment_id))
        
        result = cursor.fetchone()
        if result:
            return {
                'id': result[0],
                'project_id': result[1],
                'person_id': result[2],
                'allocation': result[3],
                'start_date': result[4],
                'end_date': result[5]
            }
        return None

def delete_assignment(assignment_id):
    """Delete an assignment from the database"""
    with get_db_cursor() as cursor:
        cursor.execute("DELETE FROM assignments WHERE id = %s", (assignment_id,))

def get_current_assignments(date=None):
    """Get current assignments for the given date"""
    if date is None:
        date = datetime.now().strftime('%Y-%m-%d')
    
    with get_db_cursor() as cursor:
        cursor.execute("""
            SELECT a.id, a.project_id, p.name as project_name, 
                   a.person_id, pe.name as person_name,
                   a.allocation, a.start_date, a.end_date,
                   p.status as project_status
            FROM assignments a
            JOIN projects p ON a.project_id = p.id
            JOIN people pe ON a.person_id = pe.id
            WHERE %s BETWEEN a.start_date AND a.end_date
            AND p.status NOT IN ('Completed', 'Cancelled')
        """, (date,))
        
        columns = ['id', 'project_id', 'project_name', 'person_id', 'person_name',
                'allocation', 'start_date', 'end_date', 'project_status']
        return pd.DataFrame(cursor.fetchall(), columns=columns)

def calculate_total_allocation(person_id, date=None):
    """Calculate total allocation for a person on a given date"""
    if date is None:
        date = datetime.now().strftime('%Y-%m-%d')
    
    with get_db_cursor() as cursor:
        cursor.execute("""
            SELECT COALESCE(SUM(
                CASE 
                    WHEN %s BETWEEN a.start_date AND a.end_date 
                    AND p.status NOT IN ('Not Started', 'Completed', 'Cancelled')
                    THEN a.allocation 
                    ELSE 0 
                END
            ), 0) as total_allocation
            FROM assignments a
            JOIN projects p ON a.project_id = p.id
            WHERE a.person_id = %s
        """, (date, person_id))
        
        result = cursor.fetchone()
        return result[0] if result else 0

def get_project_assignments(project_id):
    """Get all assignments for a project"""
    with get_db_cursor() as cursor:
        cursor.execute("""
            SELECT a.id, a.project_id, a.person_id, p.name as person_name,
                   a.allocation, a.start_date, a.end_date,
                   COALESCE(SUM(
                       CASE 
                           WHEN CURRENT_DATE BETWEEN a2.start_date AND a2.end_date 
                           AND p2.status NOT IN ('Not Started', 'Completed', 'Cancelled')
                           THEN a2.allocation 
                           ELSE 0 
                       END
                   ), 0) as total_allocation
            FROM assignments a
            JOIN people p ON a.person_id = p.id
            LEFT JOIN assignments a2 ON p.id = a2.person_id
            LEFT JOIN projects p2 ON a2.project_id = p2.id
            WHERE a.project_id = %s
            GROUP BY a.id, a.project_id, a.person_id, p.name,
                     a.allocation, a.start_date, a.end_date
        """, (project_id,))
        
        columns = ['id', 'project_id', 'person_id', 'person_name',
                'allocation', 'start_date', 'end_date', 'total_allocation']
        return pd.DataFrame(cursor.fetchall(), columns=columns)

def get_available_people(project_id):
    """Get people not assigned to the project"""
    with get_db_cursor() as cursor:
        cursor.execute("""
            SELECT p.id, p.name, p.role, p.availability
            FROM people p
            WHERE p.id NOT IN (
                SELECT person_id
                FROM assignments
                WHERE project_id = %s
            )
            ORDER BY p.name
        """, (project_id,))
        
        columns = ['id', 'name', 'role', 'availability']
        return pd.DataFrame(cursor.fetchall(), columns=columns)

def get_all_assignments(organization_id=None):
    """Get all assignments from the database"""
    with get_db_cursor() as cursor:
        if organization_id:
            cursor.execute("""
                SELECT a.id, a.project_id, a.person_id, a.allocation, a.start_date, a.end_date,
                       p.name as project_name, pe.name as person_name
                FROM assignments a
                JOIN projects p ON a.project_id = p.id
                JOIN people pe ON a.person_id = pe.id
                WHERE p.organization_id = %s
                ORDER BY a.start_date DESC
            """, (organization_id,))
        else:
            cursor.execute("""
                SELECT a.id, a.project_id, a.person_id, a.allocation, a.start_date, a.end_date,
                       p.name as project_name, pe.name as person_name
                FROM assignments a
                JOIN projects p ON a.project_id = p.id
                JOIN people pe ON a.person_id = pe.id
                ORDER BY a.start_date DESC
            """)
        
        columns = ['id', 'project_id', 'person_id', 'allocation', 'start_date', 'end_date', 
                  'project_name', 'person_name']
        return pd.DataFrame(cursor.fetchall(), columns=columns) 