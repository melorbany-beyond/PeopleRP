import os
import sys
import pytest
from dotenv import load_dotenv

# Add the project root directory to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from app import create_app
from database import init_db

@pytest.fixture
def app():
    """Create and configure a new app instance for each test."""
    # Load environment variables
    load_dotenv()
    
    # Create app with test config
    app = create_app({
        'TESTING': True,
        'DATABASE_URL': 'postgresql://localhost/prptest',
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