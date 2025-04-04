from flask import current_app, session
from database import get_db_cursor, DatabaseError
from datetime import datetime, timedelta
import random
import os
from postmarker.core import PostmarkClient
from dotenv import load_dotenv
import string

# Load environment variables
load_dotenv()

# Initialize Postmark client with API key from environment
postmark = PostmarkClient(server_token=os.getenv('POSTMARK_API_KEY'))

# Development settings
DISABLE_EMAILS = os.getenv('POSTMARK_DISABLE_EMAILS', 'True').lower() == 'true'  # Default to True if not set

def create_organization(name, superuser_email, superuser_name):
    """Create a new organization with its superuser. Only platform admin can do this."""
    with get_db_cursor() as cur:
        try:
            # Check if the superuser email already exists
            cur.execute("SELECT id FROM users WHERE email = %s", (superuser_email,))
            existing_user = cur.fetchone()
            
            if existing_user:
                raise DatabaseError("User with this email already exists")
            
            # Create superuser
            cur.execute("""
                INSERT INTO users (email, name, role, is_active)
                VALUES (%s, %s, 'Superuser', true)
                RETURNING id
            """, (superuser_email, superuser_name))
            superuser_id = cur.fetchone()[0]
            
            # Create organization
            cur.execute("""
                INSERT INTO organizations (name, superuser_id)
                VALUES (%s, %s)
                RETURNING id
            """, (name, superuser_id))
            org_id = cur.fetchone()[0]
            
            # Link superuser to organization
            cur.execute("""
                INSERT INTO organization_users (user_id, organization_id)
                VALUES (%s, %s)
            """, (superuser_id, org_id))
            
            return org_id
        except Exception as e:
            current_app.logger.error(f"Error creating organization: {str(e)}")
            raise DatabaseError(f"Failed to create organization: {str(e)}")

def is_platform_admin(user_id):
    """Check if a user is a platform admin"""
    with get_db_cursor() as cur:
        cur.execute("SELECT is_platform_admin FROM users WHERE id = %s", (user_id,))
        result = cur.fetchone()
        return result[0] if result else False

def create_platform_admin(email, name):
    """Create a platform admin user. This should be done manually or through a secure process."""
    with get_db_cursor() as cur:
        try:
            cur.execute("""
                INSERT INTO users (email, name, role, is_platform_admin, is_active)
                VALUES (%s, %s, 'Superuser', true, true)
                RETURNING id
            """, (email, name))
            return cur.fetchone()[0]
        except Exception as e:
            raise DatabaseError(f"Failed to create platform admin: {str(e)}")

def get_organization(org_id):
    """Get organization details"""
    with get_db_cursor() as cursor:
        cursor.execute("""
            SELECT id, name, created_at, subscription_tier
            FROM organizations
            WHERE id = %s
        """, (org_id,))
        result = cursor.fetchone()
        if result:
            return {
                'id': result[0],
                'name': result[1],
                'created_at': result[2],
                'subscription_tier': result[3]
            }
        return None

def create_user(email, name, role='Normal', organization_id=None):
    """Create a new user and optionally link to organization"""
    with get_db_cursor() as cur:
        try:
            # Create user
            cur.execute("""
                INSERT INTO users (email, name, role)
                VALUES (%s, %s, %s)
                RETURNING id
            """, (email, name, role))
            user_id = cur.fetchone()[0]
            
            # Link to organization if provided
            if organization_id:
                cur.execute("""
                    INSERT INTO organization_users (organization_id, user_id, role)
                    VALUES (%s, %s, %s)
                """, (organization_id, user_id, role))
            
            return user_id
        except Exception as e:
            current_app.logger.error(f"Error creating user: {str(e)}")
            raise DatabaseError(f"Failed to create user: {str(e)}")

def add_user_to_organization(user_id, organization_id):
    """Add a user to an organization"""
    with get_db_cursor() as cur:
        # Add user to organization
        cur.execute("""
            INSERT INTO organization_users (organization_id, user_id)
            VALUES (%s, %s)
        """, (organization_id, user_id))
        return True

def get_user_organizations(user_id):
    """Get all organizations a user belongs to"""
    with get_db_cursor() as cur:
        cur.execute("""
            SELECT o.id, o.name, o.superuser_id = %s as is_superuser
            FROM organizations o
            JOIN organization_users ou ON o.id = ou.organization_id
            WHERE ou.user_id = %s
        """, (user_id, user_id))
        return [
            {
                'id': row[0],
                'name': row[1],
                'is_superuser': row[2]
            }
            for row in cur.fetchall()
        ]

def generate_otp(email):
    """Generate OTP for user authentication"""
    with get_db_cursor() as cur:
        # Verify user exists and is active
        cur.execute("SELECT id, is_active FROM users WHERE email = %s", (email,))
        user = cur.fetchone()
        if not user or not user[1]:
            return None
        
        # Generate OTP
        otp = ''.join(random.choices(string.digits, k=6))
        expires_at = datetime.now() + timedelta(minutes=10)
        
        # Invalidate any existing valid OTPs
        cur.execute("""
            UPDATE otps
            SET is_valid = FALSE
            WHERE email = %s AND is_valid = TRUE
        """, (email,))
        
        # Create new OTP
        cur.execute("""
            INSERT INTO otps (email, otp, expires_at)
            VALUES (%s, %s, %s)
        """, (email, otp, expires_at))
        
        return otp

def store_otp(email, otp):
    """Store OTP in the database"""
    with get_db_cursor() as cursor:
        # First, invalidate any existing OTPs for this email
        cursor.execute("""
            UPDATE otps
            SET is_valid = false
            WHERE email = %s
        """, (email,))
        
        # Then insert the new OTP
        cursor.execute("""
            INSERT INTO otps (email, otp, created_at, expires_at, is_valid)
            VALUES (%s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP + interval '5 minutes', true)
        """, (email, otp))

def verify_otp(email, otp):
    """Verify OTP and return user details if valid"""
    # In development mode, accept the backdoor code
    if DISABLE_EMAILS and otp == '852852':
        return get_user_by_email(email)
    
    with get_db_cursor() as cur:
        cur.execute("""
            SELECT o.id
            FROM otps o
            WHERE o.email = %s
            AND o.otp = %s
            AND o.is_valid = TRUE
            AND o.expires_at > CURRENT_TIMESTAMP
        """, (email, otp))
        
        otp_record = cur.fetchone()
        if not otp_record:
            return None
        
        # Invalidate the OTP
        cur.execute("""
            UPDATE otps
            SET is_valid = FALSE
            WHERE id = %s
        """, (otp_record[0],))
        
        # Get user details
        return get_user_by_email(email)

def send_otp_email(email, otp):
    """Send OTP via Postmark"""
    if DISABLE_EMAILS:
        print(f"\n=== DEVELOPMENT MODE ===")
        print(f"Email to: {email}")
        print(f"OTP code: {otp}")
        print(f"Test OTP: 852852")
        print(f"=======================\n")
        return

    try:
        postmark.emails.send(
            From=os.getenv('POSTMARK_SENDER_EMAIL'),
            To=email,
            Subject='Your Beyond PeopleRP Login Code',
            TextBody=f'Your login code is: {otp}\n\nThis code will expire in 10 minutes.',
            HtmlBody=f'''
                <h2>Your Beyond PeopleRP Login Code</h2>
                <p>Your login code is: <strong>{otp}</strong></p>
                <p>This code will expire in 10 minutes.</p>
                <p>If you didn't request this code, please ignore this email.</p>
            '''
        )
        current_app.logger.info(f"OTP email sent to {email}")
    except Exception as e:
        current_app.logger.error(f"Failed to send OTP email: {str(e)}")
        if DISABLE_EMAILS:
            print(f"Would have sent email to {email} with OTP {otp}")
        else:
            raise

def get_user_role(user_id, organization_id):
    """Get user's role in an organization"""
    with get_db_cursor() as cur:
        cur.execute("""
            SELECT u.role, o.superuser_id, u.is_platform_admin
            FROM users u
            JOIN organization_users ou ON u.id = ou.user_id
            JOIN organizations o ON ou.organization_id = o.id
            WHERE u.id = %s AND o.id = %s
        """, (user_id, organization_id))
        result = cur.fetchone()
        if not result:
            return None
        role, superuser_id, is_platform_admin = result
        
        # Platform admin has full access everywhere
        if is_platform_admin:
            return 'Superuser'
        
        # If user is the organization's superuser, always return Superuser role
        if user_id == superuser_id:
            return 'Superuser'
            
        return role

def can_manage_users(user_id, organization_id):
    """Check if user can manage users in an organization"""
    role = get_user_role(user_id, organization_id)
    return role in ['Superuser', 'Privileged']

def can_access_users_page(user_id, organization_id):
    """Check if user can access the users page"""
    role = get_user_role(user_id, organization_id)
    return role in ['Superuser', 'Privileged']

def can_manage_user(manager_id, user_id, organization_id):
    """Check if a user can manage another user"""
    manager_role = get_user_role(manager_id, organization_id)
    target_role = get_user_role(user_id, organization_id)
    
    if not manager_role or not target_role:
        return False
    
    # Platform admin can manage everyone
    with get_db_cursor() as cur:
        cur.execute("SELECT is_platform_admin FROM users WHERE id = %s", (manager_id,))
        if cur.fetchone()[0]:
            return True
    
    # Superusers can manage everyone except other superusers
    if manager_role == 'Superuser':
        return target_role != 'Superuser'
    
    # Privileged users can only manage normal users
    if manager_role == 'Privileged':
        return target_role == 'Normal'
    
    return False

def get_organization_users(organization_id, current_user_id):
    """Get all users in an organization with proper role filtering"""
    role = get_user_role(current_user_id, organization_id)
    if not can_access_users_page(current_user_id, organization_id):
        return None
        
    with get_db_cursor() as cur:
        cur.execute("""
            SELECT u.id, u.name, u.email, u.role, u.is_active,
                   o.superuser_id = u.id as is_superuser
            FROM users u
            JOIN organization_users ou ON u.id = ou.user_id
            JOIN organizations o ON ou.organization_id = o.id
            WHERE o.id = %s
            ORDER BY u.name
        """, (organization_id,))
        return [
            {
                'id': row[0],
                'name': row[1],
                'email': row[2],
                'role': 'Superuser' if row[5] else row[3],
                'is_active': row[4],
                'is_superuser': row[5]
            }
            for row in cur.fetchall()
        ]

def send_welcome_email(email, name):
    """Send welcome email to new user"""
    if DISABLE_EMAILS:
        print(f"\n=== DEVELOPMENT MODE ===")
        print(f"Welcome email to: {email}")
        print(f"Name: {name}")
        print(f"=======================\n")
        return

    try:
        postmark.emails.send(
            From=os.getenv('POSTMARK_SENDER_EMAIL'),
            To=email,
            Subject='Welcome to Beyond PeopleRP',
            TextBody=f'''Welcome to Beyond PeopleRP!

You have been invited to join Beyond PeopleRP. Please visit rp.beyondcompany.sa to log in.

Best regards,
The Beyond Team''',
            HtmlBody=f'''
                <h2>Welcome to Beyond PeopleRP!</h2>
                <p>You have been invited to join Beyond PeopleRP. Please visit <a href="https://rp.beyondcompany.sa">rp.beyondcompany.sa</a> to log in.</p>
                <p>Best regards,<br>The Beyond Team</p>
            '''
        )
        current_app.logger.info(f"Welcome email sent to {email}")
    except Exception as e:
        current_app.logger.error(f"Failed to send welcome email: {str(e)}")
        if DISABLE_EMAILS:
            print(f"Would have sent welcome email to {email}")
        else:
            raise

def invite_user(email, name, role='Normal', org_id=None):
    """Invite a new user to the organization"""
    with get_db_cursor() as cur:
        try:
            # Check if user already exists
            cur.execute("SELECT id FROM users WHERE email = %s", (email,))
            existing_user = cur.fetchone()
            
            if existing_user:
                user_id = existing_user[0]
                # Update user's role if they're new to this organization
                if org_id:
                    cur.execute("""
                        INSERT INTO organization_users (user_id, organization_id, role)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (user_id, organization_id) 
                        DO UPDATE SET role = EXCLUDED.role
                    """, (user_id, org_id, role))
            else:
                # Create new user
                cur.execute("""
                    INSERT INTO users (email, name, role, is_active)
                    VALUES (%s, %s, %s, true)
                    RETURNING id
                """, (email, name, role))
                user_id = cur.fetchone()[0]
                
                # Add to organization if specified
                if org_id:
                    cur.execute("""
                        INSERT INTO organization_users (user_id, organization_id, role)
                        VALUES (%s, %s, %s)
                    """, (user_id, org_id, role))
            
            # Send welcome email
            send_welcome_email(email, name)
            
            return user_id
            
        except Exception as e:
            current_app.logger.error(f"Error inviting user: {str(e)}")
            raise DatabaseError(f"Failed to invite user: {str(e)}")

def update_user_status(user_id, organization_id, is_active, updater_id):
    """Update user's active status"""
    if not can_manage_user(updater_id, user_id, organization_id):
        return False
        
    with get_db_cursor() as cur:
        cur.execute("""
            UPDATE users 
            SET is_active = %s 
            WHERE id = %s AND id IN (
                SELECT user_id 
                FROM organization_users 
                WHERE organization_id = %s
            )
        """, (is_active, user_id, organization_id))
        return True

# Add role to session during login
def login_user(user_id, organization_id):
    """Log in a user and set up their session"""
    session['user_id'] = user_id
    session['organization_id'] = organization_id
    session['user_role'] = get_user_role(user_id, organization_id)
    return True

def get_user_by_email(email):
    """Get a user by their email address."""
    with get_db_cursor() as cur:
        cur.execute("""
            SELECT id, email, name, role, is_active
            FROM users
            WHERE email = %s
        """, (email,))
        row = cur.fetchone()
        if row is None:
            return None
        return {
            'id': row[0],
            'email': row[1],
            'name': row[2],
            'role': row[3],
            'is_active': row[4]
        } 