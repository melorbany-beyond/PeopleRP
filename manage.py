import click
from database import get_db_cursor, DatabaseError
from models.auth import create_organization, create_platform_admin
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

@click.group()
def cli():
    """Management CLI for Beyond EagleEye"""
    pass

@cli.command()
@click.option('--email', prompt='Platform admin email', help='Email address for the platform admin')
@click.option('--name', prompt='Platform admin name', help='Full name of the platform admin')
def create_admin(email, name):
    """Create a new platform admin"""
    try:
        admin_id = create_platform_admin(email, name)
        click.echo(f"✓ Platform admin created successfully with ID: {admin_id}")
    except DatabaseError as e:
        click.echo(f"✗ Error creating platform admin: {str(e)}", err=True)

@cli.command()
@click.option('--name', prompt='Organization name', help='Name of the organization')
@click.option('--superuser-email', prompt='Superuser email', help='Email for the organization superuser')
@click.option('--superuser-name', prompt='Superuser name', help='Name of the organization superuser')
def create_org(name, superuser_email, superuser_name):
    """Create a new organization with its superuser"""
    try:
        org_id = create_organization(name, superuser_email, superuser_name)
        click.echo(f"✓ Organization created successfully with ID: {org_id}")
    except DatabaseError as e:
        click.echo(f"✗ Error creating organization: {str(e)}", err=True)

@cli.command()
def list_orgs():
    """List all organizations and their superusers"""
    try:
        with get_db_cursor() as cur:
            cur.execute("""
                SELECT o.id, o.name, u.email, u.name
                FROM organizations o
                JOIN users u ON o.superuser_id = u.id
                ORDER BY o.name
            """)
            orgs = cur.fetchall()
            
            if not orgs:
                click.echo("No organizations found.")
                return
            
            click.echo("\nOrganizations:")
            click.echo("-" * 80)
            for org in orgs:
                click.echo(f"ID: {org[0]}")
                click.echo(f"Name: {org[1]}")
                click.echo(f"Superuser: {org[3]} ({org[2]})")
                click.echo("-" * 80)
                
    except DatabaseError as e:
        click.echo(f"✗ Error listing organizations: {str(e)}", err=True)

@cli.command()
def list_admins():
    """List all platform admins"""
    try:
        with get_db_cursor() as cur:
            cur.execute("""
                SELECT id, email, name
                FROM users
                WHERE is_platform_admin = true
                ORDER BY name
            """)
            admins = cur.fetchall()
            
            if not admins:
                click.echo("No platform admins found.")
                return
            
            click.echo("\nPlatform Admins:")
            click.echo("-" * 50)
            for admin in admins:
                click.echo(f"ID: {admin[0]}")
                click.echo(f"Name: {admin[2]}")
                click.echo(f"Email: {admin[1]}")
                click.echo("-" * 50)
                
    except DatabaseError as e:
        click.echo(f"✗ Error listing platform admins: {str(e)}", err=True)

if __name__ == '__main__':
    cli() 