from flask import Blueprint, request, jsonify, session, g, redirect, url_for, render_template
from models.auth import (
    create_organization, create_user, add_user_to_organization,
    get_user_organizations, get_organization_users, get_organization,
    generate_otp, store_otp, verify_otp, send_otp_email, get_user_by_email,
    invite_user
)
from functools import wraps
from database import DatabaseError
from flask import current_app

bp = Blueprint('auth', __name__)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated_function

def org_access_required(f):
    @wraps(f)
    def decorated_function(org_id, *args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        
        # Check if user has access to this organization
        user_orgs = get_user_organizations(session['user_id'])
        if not any(org['id'] == int(org_id) for org in user_orgs):
            return jsonify({'error': 'Access denied'}), 403
        return f(org_id, *args, **kwargs)
    return decorated_function

@bp.before_app_request
def load_logged_in_user():
    user_id = session.get('user_id')
    if user_id is None:
        g.user = None
    else:
        g.user = {'id': user_id}

@bp.route('/login', methods=['GET', 'POST'])
def login():
    """Handle login requests."""
    # Debug logging
    current_app.logger.info(f"Login route - Method: {request.method}, Session: {dict(session)}")
    
    if request.method == 'POST':
        data = request.get_json()
        email = data.get('email')
        
        if not email:
            return jsonify({
                'success': False,
                'error': 'Email is required'
            }), 400
        
        # Get user (don't create new users automatically)
        user = get_user_by_email(email)
        if not user:
            return jsonify({
                'success': False,
                'error': 'User not found'
            }), 401
        
        # Store email in session for OTP verification
        session['login_email'] = email
        
        # Generate and store OTP
        otp = generate_otp(email)
        if otp:
            # Send OTP email
            send_otp_email(email, otp)
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to generate OTP'
            }), 500
        
        return jsonify({
            'success': True,
            'message': 'OTP sent successfully'
        })
    
    # If user is already logged in, redirect to dashboard
    if 'user_id' in session:
        current_app.logger.info(f"User already logged in, redirecting to dashboard. Session: {dict(session)}")
        return redirect(url_for('main.dashboard'))
    
    return render_template('login.html')

@bp.route('/verify', methods=['POST'])
def verify():
    """Verify OTP and complete login."""
    data = request.get_json()
    otp = data.get('otp')
    email = session.get('login_email')
    
    if not email:
        return jsonify({
            'success': False,
            'error': 'Please request OTP first'
        }), 400
    
    if not otp:
        return jsonify({
            'success': False,
            'error': 'OTP is required'
        }), 400
    
    # Get user
    user = get_user_by_email(email)
    if not user:
        return jsonify({
            'success': False,
            'error': 'User not found'
        }), 401
    
    # Verify OTP
    if verify_otp(email, otp):  # This already handles the backdoor code
        # Store user info in session
        session.clear()  # Clear any existing session data
        session['user_id'] = user['id']
        session['user_email'] = user['email']
        session['user_name'] = user['name']
        session['user_role'] = user['role']
        
        # Get user's organization from organization_users table
        orgs = get_user_organizations(user['id'])
        if orgs:
            session['organization_id'] = orgs[0]['id']
        
        # Debug logging
        current_app.logger.info(f"Session after verify: {dict(session)}")
        
        return jsonify({
            'success': True,
            'redirect_url': url_for('main.dashboard')
        })
    
    return jsonify({
        'success': False,
        'error': 'Invalid OTP'
    }), 401

@bp.route('/logout')
def logout():
    """Handle user logout"""
    session.clear()
    return redirect(url_for('auth.login'))

@bp.route('/register', methods=['GET', 'POST'])
def register():
    """This endpoint is disabled until self-registration is implemented"""
    return jsonify({
        'error': 'Organization registration is currently by invitation only'
    }), 403

@bp.route('/invite', methods=['POST'])
@login_required
def handle_invite_user():
    """Invite a new user to the organization"""
    org_id = session.get('organization_id')
    if not org_id:
        return jsonify({'error': 'No organization selected'}), 400
        
    data = request.get_json()
    if not all(k in data for k in ['name', 'email']):
        return jsonify({'error': 'Missing required fields'}), 400
        
    # Default to Normal role if not specified or if inviter is not a superuser
    role = data.get('role', 'Normal')
    if session['user_role'] != 'Superuser':
        role = 'Normal'
    
    # Prevent creating superusers through invitation
    if role == 'Superuser':
        return jsonify({'error': 'Cannot create superuser through invitation'}), 403
    
    try:
        # Create new user and add to organization
        user_id = invite_user(
            email=data['email'],
            name=data['name'],
            role=role,
            org_id=org_id
        )
        
        return jsonify({
            'message': 'User invited successfully. They will receive a welcome email.',
            'user_id': user_id
        }), 201
            
    except DatabaseError as e:
        if "duplicate key" in str(e):
            return jsonify({'error': 'User with this email already exists'}), 400
        return jsonify({'error': str(e)}), 400
        
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@bp.route('/organizations')
@login_required
def list_organizations():
    """List organizations for the current user"""
    organizations = get_user_organizations(session['user_id'])
    return jsonify(organizations)

@bp.route('/organizations/<int:org_id>')
@org_access_required
def get_org(org_id):
    org = get_organization(org_id)
    if org:
        return jsonify(org)
    return jsonify({'error': 'Organization not found'}), 404

@bp.route('/organizations/<int:org_id>/users')
@org_access_required
def list_org_users(org_id):
    users = get_organization_users(org_id)
    return jsonify(users)

@bp.route('/organizations/<int:org_id>/users', methods=['POST'])
@org_access_required
def invite_org_user(org_id):
    data = request.get_json()
    
    try:
        # Create new user and add to organization
        user_id = invite_user(
            email=data['email'],
            name=data['name'],
            role=data.get('role', 'Normal'),
            org_id=org_id
        )
        
        return jsonify({
            'message': 'User invited successfully. They will receive a welcome email.',
            'user_id': user_id
        }), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 400 