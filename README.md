## Install required system packages:
```bash
sudo apt install -y python3-pip python3-venv postgresql postgresql-contrib nginx
```

## Database Setup

1. Start PostgreSQL service:
```bash
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

2. Create database and user:
```bash
sudo -u postgres psql -c "CREATE DATABASE peoplerp;"
sudo -u postgres psql -c "CREATE USER peoplerp WITH PASSWORD 'your_secure_password';"
sudo -u postgres psql -c "ALTER ROLE peoplerp SET client_encoding TO 'utf8';"
sudo -u postgres psql -c "ALTER ROLE peoplerp SET default_transaction_isolation TO 'read committed';"
sudo -u postgres psql -c "ALTER ROLE peoplerp SET timezone TO 'UTC';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE peoplerp TO peoplerp;"
```

## Application Setup

1. Clone the repository (if using git) or copy your application files.

2. Create and activate virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate
```

3. Install Python dependencies:
```bash
pip install -r requirements.txt
```

4. Create environment file:
```bash
cat > .env << EOL
DATABASE_URL=postgresql://peoplerp:your_secure_password@localhost/peoplerp
SECRET_KEY=your_secure_secret_key
POSTMARK_API_KEY=your_postmark_api_key
EOL
```

5. Initialize the database and run migrations:
```bash
python migrate.py
```

6. Create your organization and superuser:
```bash
python manage.py create-org --name "Beyond Company" --superuser-email "fares@beyondcompany.sa" --superuser-name "Fares Alaboud"
```

7. Enable Email OTPs

Once the Postmark API key is set in the `.env` file, go to `/models/auth.py:17` and change the value to `False`.
