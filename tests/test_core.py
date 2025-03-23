import pytest
from flask import session, url_for
from datetime import datetime, timedelta
import json

@pytest.fixture
def auth_client(client):
    """A test client that's already logged in."""
    # First login
    response = client.post('/auth/login', json={
        'email': 'test@example.com'
    })
    assert response.status_code == 200
    
    # Then verify with backdoor OTP
    response = client.post('/auth/verify', json={
        'otp': '852852'
    })
    assert response.status_code == 200
    
    # Make sure we're logged in
    with client.session_transaction() as sess:
        assert 'user_id' in sess
    
    return client

def test_create_project(auth_client):
    """Test creating a new project."""
    project_data = {
        'name': 'Test Project',
        'project_type': 'External',
        'status': 'Active',
        'start_date': datetime.now().strftime('%Y-%m-%d'),
        'end_date': (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
    }
    
    # Create project
    response = auth_client.post('/projects', json=project_data)
    assert response.status_code == 200
    data = response.get_json()
    assert data['message'] == 'Project created successfully'
    project_id = data['id']
    
    # Verify project appears in projects list
    response = auth_client.get('/projects')
    assert response.status_code == 200
    assert b'Test Project' in response.data

def test_edit_project(auth_client):
    """Test editing a project."""
    # First create a project
    project_data = {
        'name': 'Project to Edit',
        'project_type': 'External',
        'status': 'Active',
        'start_date': datetime.now().strftime('%Y-%m-%d'),
        'end_date': (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
    }
    response = auth_client.post('/projects', json=project_data)
    project_id = response.get_json()['id']
    
    # Edit the project
    edit_data = project_data.copy()
    edit_data['name'] = 'Edited Project Name'
    response = auth_client.put(f'/projects/{project_id}', json=edit_data)
    assert response.status_code == 200
    
    # Verify changes
    response = auth_client.get('/projects')
    assert response.status_code == 200
    assert b'Edited Project Name' in response.data

def test_create_person(auth_client):
    """Test creating a new person."""
    person_data = {
        'name': 'John Doe',
        'role': 'Project Manager',
        'availability': 'Full-Time'
    }
    
    # Create person
    response = auth_client.post('/people', json=person_data)
    assert response.status_code == 200
    data = response.get_json()
    assert data['message'] == 'Person added successfully'
    person_id = data['id']
    
    # Verify person appears in people list
    response = auth_client.get('/people')
    assert response.status_code == 200
    assert b'John Doe' in response.data

def test_edit_person(auth_client):
    """Test editing a person."""
    # First create a person
    person_data = {
        'name': 'Person to Edit',
        'role': 'Project Manager',
        'availability': 'Full-Time'
    }
    response = auth_client.post('/people', json=person_data)
    person_id = response.get_json()['id']
    
    # Edit the person
    edit_data = person_data.copy()
    edit_data['name'] = 'Edited Person Name'
    response = auth_client.put(f'/people/{person_id}', json=edit_data)
    assert response.status_code == 200
    
    # Verify changes
    response = auth_client.get('/people')
    assert response.status_code == 200
    assert b'Edited Person Name' in response.data

def test_create_assignment(auth_client):
    """Test creating a project assignment."""
    # First create a project and person
    project_data = {
        'name': 'Assignment Test Project',
        'project_type': 'External',
        'status': 'Active',
        'start_date': datetime.now().strftime('%Y-%m-%d'),
        'end_date': (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
    }
    project_response = auth_client.post('/projects', json=project_data)
    project_id = project_response.get_json()['id']
    
    person_data = {
        'name': 'Assignment Test Person',
        'role': 'Project Manager',
        'availability': 'Full-Time'
    }
    person_response = auth_client.post('/people', json=person_data)
    person_id = person_response.get_json()['id']
    
    # Create assignment
    assignment_data = {
        'person_id': person_id,
        'allocation': 50,
        'start_date': datetime.now().strftime('%Y-%m-%d'),
        'end_date': (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
    }
    response = auth_client.post(f'/assignments/{project_id}', json=assignment_data)
    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    
    # Verify assignment appears in project assignments
    response = auth_client.get(f'/assignments/{project_id}')
    assert response.status_code == 200
    assert b'Assignment Test Person' in response.data

def test_edit_assignment(auth_client):
    """Test editing a project assignment."""
    # First create project, person, and assignment
    project_data = {
        'name': 'Edit Assignment Test Project',
        'project_type': 'External',
        'status': 'Active',
        'start_date': datetime.now().strftime('%Y-%m-%d'),
        'end_date': (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
    }
    project_response = auth_client.post('/projects', json=project_data)
    project_id = project_response.get_json()['id']
    
    person_data = {
        'name': 'Edit Assignment Test Person',
        'role': 'Project Manager',
        'availability': 'Full-Time'
    }
    person_response = auth_client.post('/people', json=person_data)
    person_id = person_response.get_json()['id']
    
    assignment_data = {
        'person_id': person_id,
        'allocation': 50,
        'start_date': datetime.now().strftime('%Y-%m-%d'),
        'end_date': (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
    }
    response = auth_client.post(f'/assignments/{project_id}', json=assignment_data)
    assignment_id = response.get_json()['assignment']['id']
    
    # Edit assignment
    edit_data = {
        'allocation': 75,
        'start_date': datetime.now().strftime('%Y-%m-%d'),
        'end_date': (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
    }
    response = auth_client.put(f'/assignments/{project_id}/{assignment_id}', json=edit_data)
    assert response.status_code == 200
    
    # Verify changes
    response = auth_client.get(f'/assignments/{project_id}')
    assert response.status_code == 200
    assert b'75' in response.data  # Check for updated allocation

def test_dashboard_metrics(auth_client):
    """Test that dashboard metrics are calculated correctly."""
    # Create test data
    project_data = {
        'name': 'Dashboard Test Project',
        'project_type': 'External',
        'status': 'Active',
        'start_date': datetime.now().strftime('%Y-%m-%d'),
        'end_date': (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
    }
    auth_client.post('/projects', json=project_data)
    
    person_data = {
        'name': 'Dashboard Test Person',
        'role': 'Project Manager',
        'availability': 'Full-Time'
    }
    auth_client.post('/people', json=person_data)
    
    # Check dashboard
    response = auth_client.get('/')
    assert response.status_code == 200
    assert b'Dashboard Test Project' in response.data
    assert b'Dashboard Test Person' in response.data

def test_duplicate_assignment_prevention(auth_client):
    """Test that a person cannot be assigned to the same project twice."""
    # Create project and person
    project_data = {
        'name': 'Duplicate Test Project',
        'project_type': 'External',
        'status': 'Active',
        'start_date': datetime.now().strftime('%Y-%m-%d'),
        'end_date': (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
    }
    project_response = auth_client.post('/projects', json=project_data)
    project_id = project_response.get_json()['id']
    
    person_data = {
        'name': 'Duplicate Test Person',
        'role': 'Project Manager',
        'availability': 'Full-Time'
    }
    person_response = auth_client.post('/people', json=person_data)
    person_id = person_response.get_json()['id']
    
    # First assignment should succeed
    assignment_data = {
        'person_id': person_id,
        'allocation': 50,
        'start_date': datetime.now().strftime('%Y-%m-%d'),
        'end_date': (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
    }
    response = auth_client.post(f'/assignments/{project_id}', json=assignment_data)
    assert response.status_code == 200
    
    # Second assignment should fail
    response = auth_client.post(f'/assignments/{project_id}', json=assignment_data)
    assert response.status_code == 400
    assert b'Person already assigned to this project' in response.data 