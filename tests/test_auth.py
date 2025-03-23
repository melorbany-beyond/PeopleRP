import pytest
from flask import session, url_for
from app import create_app
from database import init_db
import os

@pytest.fixture
def app():
    """Create and configure a new app instance for each test."""
    # Create the app with test config
    app = create_app()
    app.config.update({
        'TESTING': True,
        'SERVER_NAME': 'test.local',
        'WTF_CSRF_ENABLED': False,
    })
    
    # Create tables and test data
    with app.app_context():
        init_db()
    
    yield app

@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()

@pytest.fixture
def runner(app):
    """A test runner for the app's Click commands."""
    return app.test_cli_runner()

def test_login_page(client):
    """Test that the login page loads."""
    response = client.get('/auth/login')
    assert response.status_code == 200
    assert b'Login' in response.data

def test_login_request(client):
    """Test the login request with email."""
    response = client.post('/auth/login', json={
        'email': 'test@example.com'
    })
    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    assert 'message' in data

def test_verify_otp_backdoor(client):
    """Test OTP verification with backdoor code."""
    # First login to get session
    client.post('/auth/login', json={
        'email': 'test@example.com'
    })
    
    # Then verify with backdoor OTP
    response = client.post('/auth/verify', json={
        'otp': '852852'
    })
    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    assert 'redirect_url' in data
    
    # Check that we're logged in
    with client.session_transaction() as sess:
        assert 'user_id' in sess

def test_verify_otp_incorrect(client):
    """Test OTP verification with incorrect code."""
    # First login to get session
    client.post('/auth/login', json={
        'email': 'test@example.com'
    })
    
    # Then verify with incorrect OTP
    response = client.post('/auth/verify', json={
        'otp': '000000'
    })
    assert response.status_code == 401
    data = response.get_json()
    assert data['success'] is False
    assert 'error' in data

def test_logout(client):
    """Test logging out."""
    # First login and verify
    client.post('/auth/login', json={'email': 'test@example.com'})
    client.post('/auth/verify', json={'otp': '852852'})
    
    # Then logout
    response = client.get('/auth/logout')
    assert response.status_code == 302  # Redirect
    
    # Check that we're logged out
    with client.session_transaction() as sess:
        assert 'user_id' not in sess
    
    # Check that we can't access protected routes
    response = client.get('/projects')
    assert response.status_code == 302  # Redirect to login 