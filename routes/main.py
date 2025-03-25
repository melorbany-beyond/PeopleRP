from flask import Blueprint, request, jsonify, render_template, send_file, current_app, session, redirect, url_for
from models.core import (
    get_all_people, get_all_projects, get_current_assignments, get_project_assignments, get_available_people,
    add_person, add_project, add_assignment,
    update_person, update_project, update_assignment,
    delete_person, delete_project, delete_assignment,
    get_all_assignments
)
from routes.auth import org_access_required, login_required
from database import DatabaseError, get_db_cursor
from functools import wraps
from models.auth import (
    get_user_organizations, get_organization_users, update_user_status,
    can_access_users_page, can_manage_users, get_user_role
)
import pandas as pd
from datetime import datetime
import io
import csv
import psycopg2

# Constants
PROJECT_TYPES = [
    'External',
    'Internal',
    'Initiative'
]

PROJECT_STATUSES = [
    'Not Started',
    'Active',
    'On Hold',
    'Completed',
    'Cancelled',
    'Overdue'
]

ROLES = [
    'Project Associate',
    'Senior Project Associate',
    'Project Manager',
    'Senior Project Manager',
    'Specialist Role'
]

AVAILABILITY_TYPES = [
    'Full-Time',
    'Part-Time'
]

bp = Blueprint('main', __name__)

def sort_dataframe(df, sort_by, sort_order='asc'):
    """Helper function to sort dataframes"""
    if sort_by in df.columns:
        return df.sort_values(by=sort_by, ascending=(sort_order == 'asc'))
    return df

def get_project_status(project):
    """Determine project status based on dates and current status"""
    try:
        today = datetime.now().date()
        
        # Handle both string dates (from CSV) and datetime.date objects (from PostgreSQL)
        if isinstance(project['start_date'], str):
            start_date = datetime.strptime(project['start_date'], '%Y-%m-%d').date()
        else:
            start_date = project['start_date']
            
        if isinstance(project['end_date'], str):
            end_date = datetime.strptime(project['end_date'], '%Y-%m-%d').date()
        else:
            end_date = project['end_date']
        
        # First check manual statuses that override automatic ones
        if project['status'] == 'Cancelled':
            return 'Cancelled'
        elif project['status'] == 'Completed':
            return 'Completed'
        
        # Then check date-based statuses
        if start_date > today:
            return 'Not Started'
        elif end_date < today:
            return 'Overdue'
        elif project['status'] == 'On Hold':
            return 'On Hold'
        else:
            # If project was On Hold and is being changed to Active,
            # recalculate based on dates
            if project['status'] == 'Active':
                if start_date <= today and end_date >= today:
                    return 'Active'
                elif start_date > today:
                    return 'Not Started'
                elif end_date < today:
                    return 'Overdue'
            return 'Active'
    except (ValueError, KeyError):
        return 'Active'  # Default fallback

def get_current_organization():
    """Get current organization ID and name from session"""
    org_id = session.get('organization_id')
    org_name = session.get('organization_name')
    return org_id, org_name

@bp.before_request
def load_organization():
    """Load organization context before each request"""
    if 'user_id' in session and request.endpoint != 'static':
        get_current_organization()

@bp.route('/')
@login_required
def dashboard():
    """Dashboard view with organization context"""
    # Debug logging
    current_app.logger.info(f"Dashboard route - Session: {dict(session)}")
    
    org_id, org_name = get_current_organization()
    if not org_id:
        current_app.logger.warning("No organization_id in session")
        return redirect(url_for('auth.login'))
    
    try:
        with get_db_cursor() as cur:
            # Get projects for current organization
            cur.execute("""
                SELECT p.id, p.name, p.project_type, p.status,
                       p.start_date, p.end_date,
                       COUNT(DISTINCT a.person_id) as team_count
                FROM projects p
                LEFT JOIN assignments a ON p.id = a.project_id
                WHERE p.organization_id = %s
                GROUP BY p.id, p.name, p.project_type, p.status, p.start_date, p.end_date
                ORDER BY p.start_date ASC
            """, (org_id,))
            projects = [
                {
                    'id': row[0],
                    'name': row[1],
                    'project_type': row[2],
                    'status': row[3],
                    'start_date': row[4],
                    'end_date': row[5],
                    'team_count': row[6],
                    'automated_status': get_project_status({
                        'status': row[3],
                        'start_date': row[4],
                        'end_date': row[5]
                    })
                }
                for row in cur.fetchall()
            ]
            
            # Get people with their current allocations and project assignments
            cur.execute("""
                WITH person_allocations AS (
                    SELECT p.id, p.name, p.role, p.availability,
                           COALESCE(SUM(
                               CASE 
                                   WHEN CURRENT_DATE BETWEEN a.start_date AND a.end_date 
                                   AND pr.status NOT IN ('Not Started', 'Completed', 'Cancelled')
                                   THEN a.allocation 
                                   ELSE 0 
                               END
                           ), 0) as current_allocation
                    FROM people p
                    LEFT JOIN assignments a ON p.id = a.person_id
                    LEFT JOIN projects pr ON a.project_id = pr.id
                    WHERE p.organization_id = %s
                    GROUP BY p.id, p.name, p.role, p.availability
                )
                SELECT pa.id, pa.name, pa.role, pa.availability, pa.current_allocation,
                       a.project_id, a.allocation, pr.name as project_name, pr.status as project_status,
                       a.start_date, a.end_date as assignment_end_date
                FROM person_allocations pa
                LEFT JOIN assignments a ON pa.id = a.person_id
                LEFT JOIN projects pr ON a.project_id = pr.id
                ORDER BY pa.name ASC
            """, (org_id,))
            
            # Structure the data with projects for each person
            people_dict = {}
            for row in cur.fetchall():
                person_id = row[0]
                if person_id not in people_dict:
                    people_dict[person_id] = {
                        'id': person_id,
                        'name': row[1],
                        'role': row[2],
                        'availability': row[3],
                        'current_allocation': row[4],
                        'projects': []
                    }
                if row[5]:  # if there's a project assignment
                    allocation = row[6] if row[8] not in ['Not Started', 'Completed'] else 0
                    people_dict[person_id]['projects'].append({
                        'project_id': row[5],
                        'name': row[7],
                        'allocation': allocation,
                        'status': row[8],
                        'start_date': row[9],
                        'assignment_end_date': row[10]
                    })
            
            people = list(people_dict.values())
            
            # Calculate dashboard metrics
            active_project_count = sum(1 for p in projects if p['status'] == 'Active')
            total_people = len(people)
            available_count = sum(1 for p in people if p['current_allocation'] < 50)
    
    except Exception as e:
        current_app.logger.error(f"Error in dashboard: {str(e)}")
        return redirect(url_for('auth.login'))
        
    return render_template('dashboard.html',
                         projects=projects,
                         people=people,
                         organization_name=org_name,
                         now=datetime.now(),
                         active_projects=active_project_count,
                         total_people=total_people,
                         available_count=available_count)

@bp.route('/projects', methods=['GET', 'POST'])
@login_required
def projects():
    """Projects view with organization context"""
    org_id, org_name = get_current_organization()
    if not org_id:
        return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        data = request.get_json()
        with get_db_cursor() as cur:
            cur.execute("""
                INSERT INTO projects 
                (name, project_type, status, start_date, end_date, organization_id)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                data['name'],
                data['project_type'],
                data['status'],
                data['start_date'],
                data['end_date'],
                org_id
            ))
            project_id = cur.fetchone()[0]
            return jsonify({'id': project_id, 'message': 'Project created successfully'})
    
    # Fetch projects and their assignments for the current organization
    with get_db_cursor() as cur:
        # First get all projects
        cur.execute("""
            SELECT p.id, p.name, p.project_type, p.status,
                   p.start_date, p.end_date,
                   COUNT(DISTINCT a.person_id) as team_count
            FROM projects p
            LEFT JOIN assignments a ON p.id = a.project_id
            WHERE p.organization_id = %s
            GROUP BY p.id, p.name, p.project_type, p.status, p.start_date, p.end_date
            ORDER BY p.start_date ASC
        """, (org_id,))
        projects = [
            {
                'id': row[0],
                'name': row[1],
                'project_type': row[2],
                'status': row[3],
                'start_date': row[4],
                'end_date': row[5],
                'team_count': row[6],
                'automated_status': get_project_status({
                    'status': row[3],
                    'start_date': row[4],
                    'end_date': row[5]
                }),
                'assignments': []  # Will be filled with assignment data
            }
            for row in cur.fetchall()
        ]
        
        # Create a mapping of project IDs to their indices in the projects list
        project_map = {project['id']: i for i, project in enumerate(projects)}
        
        # Then get all assignments with person details
        cur.execute("""
            SELECT a.project_id, p.name, p.role, a.allocation
            FROM assignments a
            JOIN people p ON a.person_id = p.id
            WHERE a.project_id IN (SELECT id FROM projects WHERE organization_id = %s)
            ORDER BY p.name ASC
        """, (org_id,))
        
        # Add assignments to their respective projects
        for row in cur.fetchall():
            project_id, person_name, person_role, allocation = row
            if project_id in project_map:
                projects[project_map[project_id]]['assignments'].append({
                    'name': person_name,
                    'role': person_role,
                    'allocation': allocation
                })
    
    return render_template('projects.html', 
                         organization_name=org_name,
                         project_types=PROJECT_TYPES,
                         project_statuses=PROJECT_STATUSES,
                         projects=projects)

@bp.route('/projects/<project_id>', methods=['PUT', 'DELETE'])
def manage_project(project_id):
    if request.method == 'DELETE':
        delete_project(project_id)
        return jsonify({'success': True})
    
    elif request.method == 'PUT':
        data = request.json
        project_data = {
            'name': data['name'],
            'project_type': data['project_type'],
            'status': data['status'],
            'start_date': data['start_date'],
            'end_date': data['end_date']
        }
        
        # Check if dates have changed and update status accordingly
        today = datetime.now().date()
        start_date = datetime.strptime(data['start_date'], '%Y-%m-%d').date()
        end_date = datetime.strptime(data['end_date'], '%Y-%m-%d').date()
        
        # If start date is today and project is not manually set to On Hold,
        # set status to Active
        if start_date == today and project_data['status'] != 'On Hold':
            project_data['status'] = 'Active'
        # If end date is yesterday and project is not manually set to On Hold,
        # set status to Overdue
        elif end_date < today and project_data['status'] != 'On Hold':
            project_data['status'] = 'Overdue'
        
        # Update the project
        update_project(project_id, project_data)
        
        # Get the updated project with recalculated automated status
        with get_db_cursor() as cur:
            cur.execute("""
                SELECT id, name, project_type, status, start_date, end_date
                FROM projects
                WHERE id = %s
            """, (project_id,))
            row = cur.fetchone()
            if row:
                project = {
                    'id': row[0],
                    'name': row[1],
                    'project_type': row[2],
                    'status': row[3],
                    'start_date': row[4],
                    'end_date': row[5]
                }
                project['automated_status'] = get_project_status(project)
                return jsonify({'success': True, 'project': project})
        
        return jsonify({'success': True, 'project': data})

@bp.route('/people', methods=['GET', 'POST'])
@login_required
def people():
    """People view with organization context"""
    org_id, org_name = get_current_organization()
    if not org_id:
        return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        data = request.get_json()
        with get_db_cursor() as cur:
            cur.execute("""
                INSERT INTO people 
                (name, role, availability, organization_id)
                VALUES (%s, %s, %s, %s)
                RETURNING id
            """, (
                data['name'],
                data['role'],
                data['availability'],
                org_id
            ))
            person_id = cur.fetchone()[0]
            return jsonify({'id': person_id, 'message': 'Person added successfully'})
    
    # Fetch people and their current allocations
    with get_db_cursor() as cur:
        cur.execute("""
            SELECT p.id, p.name, p.role, p.availability,
                   COALESCE(SUM(a.allocation), 0) as current_allocation
            FROM people p
            LEFT JOIN assignments a ON p.id = a.person_id
            WHERE p.organization_id = %s
            GROUP BY p.id, p.name, p.role, p.availability
            ORDER BY p.name ASC
        """, (org_id,))
        people = [
            {
                'id': row[0],
                'name': row[1],
                'role': row[2],
                'availability': row[3],
                'current_allocation': row[4]
            }
            for row in cur.fetchall()
        ]
    
    return render_template('people.html', 
                         organization_name=org_name,
                         roles=ROLES,
                         availability_types=AVAILABILITY_TYPES,
                         people=people)

@bp.route('/people/<person_id>', methods=['PUT', 'DELETE'])
def manage_person(person_id):
    if request.method == 'DELETE':
        delete_person(person_id)
        return jsonify({'success': True})
    
    elif request.method == 'PUT':
        data = request.json
        person_data = {
            'name': data['name'],
            'role': data['role'],
            'availability': data['availability']
        }
        update_person(person_id, person_data)
        return jsonify({'success': True, 'person': data})

@bp.route('/assignments/<project_id>', methods=['GET', 'POST'])
def project_assignments(project_id):
    try:
        project_id = int(project_id)
    except ValueError:
        return jsonify({'error': 'Invalid project ID format'}), 400

    if request.method == 'POST':
        data = request.json
        assignment_data = {
            'project_id': project_id,
            'person_id': int(data['person_id']),
            'allocation': int(data['allocation']),
            'start_date': data['start_date'],
            'end_date': data['end_date']
        }
        
        try:
            assignment_id = add_assignment(assignment_data)
            assignment_data['id'] = assignment_id
            return jsonify({'success': True, 'assignment': assignment_data})
        except ValueError as e:
            return jsonify({'error': str(e)}), 400
        except psycopg2.IntegrityError:
            return jsonify({'error': 'Database integrity error'}), 400
    
    # GET request - return project details with assignments
    projects_df = get_all_projects()
    project = projects_df[projects_df['id'] == project_id].to_dict('records')[0]
    project['automated_status'] = get_project_status(project)
    
    # Get assignments for this project with total allocations
    project_assignments_df = get_project_assignments(project_id)
    project_assignments = project_assignments_df.to_dict('records')
    
    # Convert IDs to integers
    for assignment in project_assignments:
        assignment['id'] = int(assignment['id'])
        assignment['person_id'] = int(assignment['person_id'])
        assignment['project_id'] = int(assignment['project_id'])
        assignment['total_allocation'] = int(assignment['total_allocation'])
    
    # Set team count on project
    project['team_count'] = len(project_assignments)
    
    # Get all people and available people
    all_people = get_all_people().to_dict('records')
    available_people = get_available_people(project_id).to_dict('records')
    
    # Convert IDs to integers
    for person in all_people:
        person['id'] = int(person['id'])
    for person in available_people:
        person['id'] = int(person['id'])
    
    available_people_ids = [p['id'] for p in available_people]
    
    return render_template('assignments.html', 
                         project=project, 
                         assignments=project_assignments,
                         all_people=all_people,
                         available_people=available_people,
                         available_people_ids=available_people_ids)

@bp.route('/assignments/<project_id>/<assignment_id>', methods=['PUT', 'DELETE'])
def manage_assignment(project_id, assignment_id):
    try:
        project_id_int = int(project_id)
        assignment_id_int = int(assignment_id)
    except ValueError:
        return jsonify({
            'error': 'The application has been updated to use new ID formats. Please refresh the page to get the new IDs.'
        }), 400
    
    if request.method == 'DELETE':
        try:
            delete_assignment(assignment_id_int)
            return jsonify({'success': True})
        except DatabaseError as e:
            return jsonify({'error': str(e)}), 500
    
    elif request.method == 'PUT':
        try:
            data = request.json
            assignment_data = {
                'allocation': int(data['allocation']),
                'start_date': data['start_date'],
                'end_date': data['end_date']
            }
            
            result = update_assignment(assignment_id_int, assignment_data)
            if result:
                return jsonify({'success': True, 'assignment': result})
            return jsonify({'error': 'Assignment not found'}), 404
            
        except DatabaseError as e:
            return jsonify({'error': str(e)}), 500

@bp.route('/faqs')
def faqs():
    return render_template('faqs.html')

@bp.route('/set-language/<lang>', methods=['POST'])
def set_language(lang):
    """Set the user's preferred language"""
    if lang not in current_app.config['LANGUAGES']:
        return jsonify({'error': 'Invalid language'}), 400
    session['lang'] = lang
    return jsonify({'message': 'Language updated successfully'})

@bp.route('/export/<report_type>')
def export_data(report_type):
    if report_type == 'allocations':
        # Get current allocations data
        current_assignments = get_current_assignments()
        people_df = get_all_people()
        
        # Create report data
        report_data = []
        for _, person in people_df.iterrows():
            person_assignments = current_assignments[current_assignments['person_id'] == person['id']]
            total_allocation = person_assignments['allocation'].sum()
            
            projects = []
            for _, assignment in person_assignments.iterrows():
                projects.append(f"{assignment['project_name']} ({assignment['allocation']}%)")
            
            report_data.append({
                'Name': person['name'],
                'Role': person['role'],
                'Total Allocation': f"{total_allocation}%",
                'Projects': ', '.join(projects)
            })
        
        # Create CSV in memory
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=['Name', 'Role', 'Total Allocation', 'Projects'])
        writer.writeheader()
        writer.writerows(report_data)
        
        # Create the response
        mem_file = io.BytesIO()
        mem_file.write(output.getvalue().encode('utf-8'))
        mem_file.seek(0)
        output.close()
        
        return send_file(
            mem_file,
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'resource_allocation_{datetime.now().strftime("%Y-%m-%d")}.csv'
        )

@bp.route('/users')
@login_required
def users():
    """Users view with role-based access control"""
    org_id, org_name = get_current_organization()
    if not org_id:
        return redirect(url_for('auth.login'))
    
    if not can_access_users_page(session['user_id'], org_id):
        return redirect(url_for('main.dashboard'))
    
    users_list = get_organization_users(org_id, session['user_id'])
    if users_list is None:
        return redirect(url_for('main.dashboard'))
    
    return render_template('users.html',
                         users=users_list,
                         organization_name=org_name,
                         current_user_id=session['user_id'])

@bp.route('/api/users/<int:user_id>/status', methods=['POST'])
@login_required
def update_user(user_id):
    """Update user status with role-based permission check"""
    org_id, _ = get_current_organization()
    if not org_id:
        return jsonify({'error': 'Organization not found'}), 404
    
    if not can_manage_users(session['user_id'], org_id):
        return jsonify({'error': 'Permission denied'}), 403
    
    data = request.get_json()
    is_active = data.get('is_active')
    if is_active is None:
        return jsonify({'error': 'Missing is_active parameter'}), 400
    
    success = update_user_status(user_id, org_id, is_active, session['user_id'])
    if not success:
        return jsonify({'error': 'Permission denied'}), 403
    
    return jsonify({'message': 'User status updated successfully'})

@bp.route('/switch-organization/<int:org_id>')
@login_required
def switch_organization(org_id):
    """Switch current organization context"""
    orgs = get_user_organizations(session['user_id'])
    if not any(org['id'] == org_id for org in orgs):
        return redirect(url_for('main.dashboard'))
    
    session['organization_id'] = org_id
    for org in orgs:
        if org['id'] == org_id:
            session['organization_name'] = org['name']
            break
    
    return redirect(request.referrer or url_for('main.dashboard')) 