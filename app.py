from flask import Flask, render_template, request, jsonify, redirect, url_for, send_file, session, current_app
import pandas as pd
from datetime import datetime
import uuid
import io
import csv
from flask_babel import Babel, get_locale, gettext as _
from models import *
from database import init_db, DatabaseError, close_db
import psycopg2
import traceback
import os
from routes import auth, main
from dotenv import load_dotenv

def create_app(test_config=None):
    # Load environment variables from .env file
    load_dotenv()

    app = Flask(__name__, 
                static_folder='static',
                static_url_path='/static')
    
    # Default configuration
    app.config.update({
        'SECRET_KEY': os.getenv('SECRET_KEY', 'your-secret-key'),
        'BABEL_DEFAULT_LOCALE': 'en',
        'LANGUAGES': {
            'en': 'English',
            'es': 'Español',
            'fr': 'Français',
            'de': 'Deutsch',
            'nl': 'Nederlands'
        }
    })

    # Override config with test config if provided
    if test_config:
        app.config.update(test_config)

    # Initialize Babel
    babel = Babel(app)

    def locale_selector():
        if 'lang' in session and session['lang'] in app.config['LANGUAGES']:
            return session['lang']
        return request.accept_languages.best_match(app.config['LANGUAGES'].keys())

    babel.init_app(app, locale_selector=locale_selector)

    @app.context_processor
    def inject_template_globals():
        return {
            'get_locale': get_locale,
            'languages': app.config['LANGUAGES'],
            'ROLES': sorted([_("Project Manager"), _("Senior Project Manager"), _("Senior Associate"), _("Associate"), _("Specialist Role")]),
            'PROJECT_TYPES': sorted([_("Internal"), _("External"), _("Initiative")]),
            'PROJECT_STATUSES': sorted([_("Active"), _("On Hold"), _("Completed"), _("Cancelled")]),
            'AVAILABILITY_TYPES': sorted(["Full-time", "Part-time"])
        }

    @app.template_filter('get_color')
    def get_color(allocation):
        """Returns a color based on allocation percentage"""
        if allocation > 80:
            return '#FEE2E2'  # red-100
        elif allocation > 50:
            return '#FEF3C7'  # yellow-100
        else:
            return '#DCFCE7'  # green-100

    # Register blueprints
    app.register_blueprint(auth.bp, url_prefix='/auth')
    app.register_blueprint(main.bp)

    # Initialize database
    with app.app_context():
        try:
            init_db()
            app.logger.info("Database initialized successfully")
        except DatabaseError as e:
            app.logger.error(f"Failed to initialize database: {str(e)}")
        
        # Register database close function
        app.teardown_appcontext(close_db)

    @app.errorhandler(404)
    def page_not_found(e):
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Not found'}), 404
        return render_template('error.html', 
                            error_code=404,
                            error_traceback=None), 404

    @app.errorhandler(Exception)
    def handle_exception(e):
        # Get the full traceback
        error_traceback = traceback.format_exc()
        
        # Log the error
        current_app.logger.error(f'Unhandled exception: {str(e)}\n{error_traceback}')
        
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Internal server error'}), 500
        
        return render_template('error.html',
                            error_code=500,
                            error_traceback=error_traceback), 500

    @app.before_request
    def check_auth():
        # Debug logging
        current_app.logger.info(f"check_auth - Path: {request.path}, Session: {dict(session)}")
        
        # List of paths that don't require authentication
        public_paths = ['/auth/login', '/auth/verify', '/auth/register', '/static/']
        
        # Skip auth check for public paths
        if any(request.path.startswith(path) for path in public_paths):
            current_app.logger.info(f"Skipping auth check for public path: {request.path}")
            return
        
        # Check if the path requires authentication
        if 'user_id' not in session:
            current_app.logger.info("No user_id in session, redirecting to login")
            if request.headers.get('Accept') == 'application/json':
                return jsonify({'error': 'Authentication required'}), 401
            return redirect(url_for('auth.login'))

    return app

# Only run the application if this file is executed directly
if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, port=5001)