import os
import time
import json
import requests
import logging
from datetime import datetime
from urllib.parse import quote_plus

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# === CONFIGURATION ===
DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
TOKEN_FILE = os.path.join(DATA_DIR, 'token.json')

# Load credentials from environment variables
CLIENT_ID = os.getenv('ZENHR_CLIENT_ID')
CLIENT_SECRET = os.getenv('ZENHR_CLIENT_SECRET')
TOKEN_URL = os.getenv('ZENHR_TOKEN_URL', 'https://api.zenhr.com/oauth/token')

if not CLIENT_ID or not CLIENT_SECRET:
    logger.error("Missing ZenHR credentials. Please set ZENHR_CLIENT_ID and ZENHR_CLIENT_SECRET environment variables.")
    raise ValueError("Missing ZenHR credentials. Please set ZENHR_CLIENT_ID and ZENHR_CLIENT_SECRET environment variables.")

# === TOKEN FILE HELPERS ===

def load_token():
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'r') as f:
            token_data = json.load(f)
            # Ensure expires_at is an integer
            if 'expires_at' in token_data:
                try:
                    token_data['expires_at'] = int(token_data['expires_at'])
                except (ValueError, TypeError):
                    logger.error(f"Invalid expires_at value in token file: {token_data['expires_at']}")
                    token_data['expires_at'] = 0
            return token_data
    return {}

def save_token(token_data):
    logger.debug(f"Saving token data: {token_data}")
    expires_in = token_data.get("expires_in", 3600)
    logger.debug(f"Raw expires_in: {expires_in} (type: {type(expires_in)})")
    
    # Ensure expires_in is a number
    if isinstance(expires_in, str):
        try:
            expires_in = int(expires_in)
        except ValueError:
            logger.error(f"Invalid expires_in format: {expires_in}")
            expires_in = 3600  # Default to 1 hour
    
    current_time = time.time()
    expires_at = int(current_time + expires_in)
    token_data["expires_at"] = expires_at
    logger.debug(f"Calculated expires_at: {expires_at} (type: {type(expires_at)})")
    
    with open(TOKEN_FILE, "w") as f:
        json.dump(token_data, f, indent=2)
    logger.debug("Token saved successfully")

# === LOGIC ===

def get_initial_token():
    logger.debug("Attempting to get initial token")
    logger.debug(f"Using client_id: {CLIENT_ID}")
    
    # URL encode the credentials
    encoded_client_id = quote_plus(CLIENT_ID)
    encoded_client_secret = quote_plus(CLIENT_SECRET)
    
    payload = {
        "grant_type": "client_credentials",
        "client_id": encoded_client_id,
        "client_secret": encoded_client_secret
    }
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }

    logger.debug(f"Making token request to: {TOKEN_URL}")
    logger.debug(f"With payload: {payload}")
    
    response = requests.post(TOKEN_URL, data=payload, headers=headers)
    logger.debug(f"Token response status: {response.status_code}")
    logger.debug(f"Token response body: {response.text}")
    
    if response.status_code == 200:
        token_data = response.json()
        save_token(token_data)
        logger.debug("Successfully obtained initial token")
        return token_data["access_token"]
    else:
        error_msg = f"Failed to get initial token: {response.status_code} - {response.text}"
        logger.error(error_msg)
        raise Exception(error_msg)

def is_token_expired(token_data):
    logger.debug(f"Checking token expiration. Token data: {token_data}")
    expires_at = token_data.get("expires_at", 0)
    logger.debug(f"Raw expires_at value: {expires_at} (type: {type(expires_at)})")
    
    # Handle both string and integer timestamps
    if isinstance(expires_at, str):
        try:
            # Try to parse ISO format string
            logger.debug("Attempting to parse ISO format string")
            expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00')).timestamp()
            logger.debug(f"Parsed ISO string to timestamp: {expires_at} (type: {type(expires_at)})")
        except ValueError:
            try:
                # Try to parse as integer
                logger.debug("Attempting to parse as integer")
                expires_at = int(expires_at)
                logger.debug(f"Parsed string to integer: {expires_at} (type: {type(expires_at)})")
            except ValueError:
                logger.error(f"Invalid expires_at format: {expires_at}")
                return True
    
    current_time = time.time()
    logger.debug(f"Current time: {current_time} (type: {type(current_time)})")
    logger.debug(f"Expires at: {expires_at} (type: {type(expires_at)})")
    
    # Ensure both values are floats before subtraction
    if not isinstance(expires_at, (int, float)):
        logger.error(f"expires_at is not a number: {expires_at} (type: {type(expires_at)})")
        return True
        
    time_remaining = expires_at - current_time
    logger.debug(f"Time remaining: {time_remaining} seconds")
    
    return time_remaining < 60

def refresh_token(refresh_token_value):
    logger.debug("Attempting to refresh token")
    # URL encode the credentials
    encoded_client_id = quote_plus(CLIENT_ID)
    encoded_client_secret = quote_plus(CLIENT_SECRET)
    
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token_value,
        "client_id": encoded_client_id,
        "client_secret": encoded_client_secret
    }
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }

    logger.debug(f"Making refresh request to: {TOKEN_URL}")
    logger.debug(f"With payload: {payload}")
    
    response = requests.post(TOKEN_URL, data=payload, headers=headers)
    logger.debug(f"Refresh response status: {response.status_code}")
    logger.debug(f"Refresh response body: {response.text}")
    
    if response.status_code == 200:
        new_token = response.json()
        save_token(new_token)
        logger.debug("Successfully refreshed token")
        return new_token["access_token"]
    else:
        error_msg = f"Failed to refresh token: {response.status_code} - {response.text}"
        logger.error(error_msg)
        raise Exception(error_msg)

def get_access_token():
    logger.debug("Getting access token")
    token_data = load_token()

    if not token_data:
        logger.debug("No token found, getting initial token")
        return get_initial_token()

    if not is_token_expired(token_data):
        logger.debug("Using existing valid token")
        return token_data["access_token"]

    if "refresh_token" in token_data:
        logger.debug("Token expired, attempting to refresh")
        return refresh_token(token_data["refresh_token"])

    logger.debug("Token expired and no refresh token, getting new initial token")
    return get_initial_token()

# === TEST HOOK ===

if __name__ == "__main__":
    try:
        token = get_access_token()
        print("✅ Access token retrieved:", token)
    except Exception as e:
        print("❌", e)
